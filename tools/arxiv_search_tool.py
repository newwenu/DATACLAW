"""ArxivSearchTool — arxiv.org 论文检索、验证、导出工具。

使用 arxiv API（免费，无需 API Key），零额外依赖。
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

# arXiv API namespace
ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
ARXIV_API = "http://export.arxiv.org/api/query"
OUTPUT_DIR = Path("./output")
REQUEST_DELAY = 3.0  # arXiv API 速率限制：每 3 秒一次


class ArxivSearchInput(BaseModel):
    """Input schema for arxiv_search tool."""

    action: str = Field(
        description=(
            "操作类型: 'search' (搜索论文), 'fetch' (获取单篇详情), "
            "'validate' (验证链接), 'batch_search' (多关键词并行搜索), "
            "'export' (导出报告)"
        )
    )
    query: str = Field(
        default="",
        description=(
            "搜索关键词，支持 arXiv API 查询语法。"
            "如 'cat:cs.AI AND all:agent' 表示在 cs.AI 分类下搜索 agent"
        ),
    )
    keywords: str = Field(
        default="",
        description="batch_search 时使用的多关键词，用逗号分隔，如 'LLM agent,RAG,diffusion model'",
    )
    arxiv_id: str = Field(
        default="", description="论文 arXiv ID，如 '2301.12345'，配合 fetch/validate 使用"
    )
    url: str = Field(
        default="", description="论文完整 URL，配合 validate 使用"
    )
    max_results: int = Field(
        default=10, ge=1, le=50, description="最大返回结果数 (1-50)"
    )
    start: int = Field(
        default=0, ge=0, description="结果起始偏移量"
    )
    sort_by: str = Field(
        default="relevance",
        description="排序方式: 'relevance' (相关度), 'lastUpdatedDate' (最近更新), 'submittedDate' (提交日期)",
    )
    papers: str = Field(
        default="",
        description="export 时使用的论文 JSON 字符串 (LLM 传入已分析的论文列表)",
    )
    export_format: str = Field(
        default="markdown",
        description="导出格式: 'markdown' 或 'html'",
    )
    output_path: str = Field(
        default="",
        description="导出文件路径，默认 output/arxiv_report_YYYYMMDD_HHMMSS.md",
    )


class ArxivSearchTool(BaseTool):
    """arxiv.org 论文检索工具（零依赖，使用标准库）。"""

    name: str = "arxiv_search"
    description: str = (
        "【arXiv 论文检索工具】在 arxiv.org 上搜索学术论文，验证链接，导出综述报告。\n"
        "action 选项：\n"
        "  - 'search': 按关键词搜索论文 (需 query, max_results, sort_by)\n"
        "  - 'batch_search': 多关键词并行搜索并去重 (需 keywords)\n"
        "  - 'fetch': 获取单篇论文详情 (需 arxiv_id)\n"
        "  - 'validate': 验证链接是否有效 (需 url 或 arxiv_id)\n"
        "  - 'export': 将分析结果导出为 Markdown/HTML 报告 (需 papers, export_format)\n"
        "注意：arXiv API 为免费公开接口，无需认证，但请控制请求频率（每 3 秒一次）。"
    )
    args_schema: Type[BaseModel] = ArxivSearchInput
    output_dir: str = "./output"

    # ========================================================================
    # 核心方法
    # ========================================================================

    def _run(
        self,
        action: str,
        query: str = "",
        keywords: str = "",
        arxiv_id: str = "",
        url: str = "",
        max_results: int = 10,
        start: int = 0,
        sort_by: str = "relevance",
        papers: str = "",
        export_format: str = "markdown",
        output_path: str = "",
    ) -> str:
        try:
            if action == "search":
                return self._search(query, max_results, start, sort_by)
            elif action == "batch_search":
                return self._batch_search(keywords, max_results, start, sort_by)
            elif action == "fetch":
                return self._fetch(arxiv_id)
            elif action == "validate":
                return self._validate(url, arxiv_id)
            elif action == "export":
                return self._export(papers, export_format, output_path)
            else:
                return f"❌ 未知 action: {action}，可用: search, batch_search, fetch, validate, export"
        except Exception as e:
            return f"❌ arXiv 工具出错 [{action}]: {str(e)}"

    # ========================================================================
    # Action: search — 单次搜索
    # ========================================================================

    def _search(
        self, query: str, max_results: int = 10, start: int = 0, sort_by: str = "relevance"
    ) -> str:
        if not query:
            return "❌ 请提供搜索关键词 (query)"

        params = {
            "search_query": query,
            "start": str(start),
            "max_results": str(max_results),
            "sortBy": sort_by,
        }
        url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
        papers = self._call_arxiv_api(url)

        if not papers:
            return f"📭 未找到与 '{query}' 相关的论文。"

        return self._format_results(papers, f"搜索结果: '{query}'")

    # ========================================================================
    # Action: batch_search — 多关键词搜索 + 去重
    # ========================================================================

    def _batch_search(self, keywords: str, max_results: int = 10, start: int = 0, sort_by: str = "relevance") -> str:
        if not keywords:
            return "❌ 请提供关键词列表 (keywords)，用逗号分隔"

        kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
        if not kw_list:
            return "❌ 关键词列表为空"

        all_papers: list[dict] = []
        seen_ids: set[str] = set()

        results_per_keyword = max_results

        output_lines = [f"🔍 多关键词并行搜索 ({len(kw_list)} 个关键词，每个最多 {results_per_keyword} 篇):\n"]
        output_lines.append(f"关键词: {', '.join(kw_list)}\n")
        output_lines.append("=" * 60)

        for kw in kw_list:
            params = {
                "search_query": f"all:{kw}",
                "start": str(start),
                "max_results": str(results_per_keyword),
                "sortBy": sort_by,
            }
            url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
            papers = self._call_arxiv_api(url)

            new_count = 0
            for p in papers:
                pid = p.get("id", "")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_papers.append(p)
                    new_count += 1

            output_lines.append(f"\n  📌 '{kw}': 找到 {len(papers)} 篇，新增 {new_count} 篇（去重后）")
            time.sleep(REQUEST_DELAY)  # 控制频率

        output_lines.append(f"\n{'=' * 60}")
        output_lines.append(f"✅ 总计: {len(all_papers)} 篇唯一论文")

        if not all_papers:
            output_lines.append("\n📭 未找到任何论文。")
            return "\n".join(output_lines)

        # 按日期降序排列
        all_papers.sort(
            key=lambda p: p.get("published", ""),
            reverse=True,
        )

        # 输出简要列表 + 完整 JSON
        output_lines.append("\n" + self._format_results(all_papers, "去重后的合并结果"))
        return "\n".join(output_lines)

    # ========================================================================
    # Action: fetch — 获取单篇论文详情
    # ========================================================================

    def _fetch(self, arxiv_id: str) -> str:
        if not arxiv_id:
            return "❌ 请提供论文 arXiv ID"

        params = {"id_list": arxiv_id, "max_results": "1"}
        url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"
        papers = self._call_arxiv_api(url)

        if not papers:
            return f"📭 未找到论文: {arxiv_id}"

        p = papers[0]
        return f"""📄 论文详情: {arxiv_id}

| 字段 | 内容 |
|------|------|
| **标题** | {p.get('title', 'N/A')} |
| **作者** | {p.get('authors', 'N/A')} |
| **发布日期** | {p.get('published', 'N/A')} |
| **发表** | {p.get('journal_ref', 'N/A') or p.get('comment', 'N/A') or '(未标注)'} |
| **分类** | {p.get('categories', 'N/A')} |
| **arXiv URL** | {p.get('url', 'N/A')} |
| **PDF** | {p.get('pdf_url', 'N/A')} |

**摘要**:
{p.get('summary', 'N/A')}
"""

    # ========================================================================
    # Action: validate — 验证链接有效性
    # ========================================================================

    def _validate(self, url: str = "", arxiv_id: str = "") -> str:
        target_url = url
        if not target_url and arxiv_id:
            target_url = f"https://arxiv.org/abs/{arxiv_id}"
        if not target_url:
            return "❌ 请提供 url 或 arxiv_id"

        try:
            req = urllib.request.Request(target_url, method="HEAD")
            req.add_header("User-Agent", "ClawArxivBot/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
            if status == 200:
                return f"✅ 链接有效 (HTTP {status}): {target_url}"
            else:
                return f"⚠️ 链接返回 HTTP {status}: {target_url}"
        except urllib.error.HTTPError as e:
            return f"❌ 链接无效 (HTTP {e.code}): {target_url}"
        except Exception as e:
            return f"❌ 无法访问链接: {target_url} — {str(e)}"

    # ========================================================================
    # Action: export — 导出报告
    # ========================================================================

    def _export(self, papers: str, export_format: str = "markdown", output_path: str = "") -> str:
        if not papers:
            return "❌ 请提供 papers 参数（JSON 字符串，LLM 传入已分析的论文数据）"

        try:
            paper_list = json.loads(papers)
        except json.JSONDecodeError:
            # 尝试修复：LLM 可能传了不完整的 JSON
            import re
            match = re.search(r"\[[\s\S]*\]", papers)
            if match:
                try:
                    paper_list = json.loads(match.group())
                except json.JSONDecodeError:
                    return "❌ papers 参数不是有效的 JSON 数组"
            else:
                return "❌ papers 参数不是有效的 JSON 数组"

        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"output/arxiv_report_{ts}"

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        full_path = Path(self.output_dir) / Path(output_path).name

        if export_format == "html":
            content = self._build_html_report(paper_list)
            full_path = full_path.with_suffix(".html")
        else:
            content = self._build_markdown_report(paper_list)
            full_path = full_path.with_suffix(".md")

        full_path.write_text(content, encoding="utf-8")
        return f"✅ 报告已导出: {full_path} ({len(paper_list)} 篇论文，格式: {export_format})"

    # ========================================================================
    # arXiv API 调用
    # ========================================================================

    def _call_arxiv_api(self, url: str) -> list[dict]:
        """调用 arXiv API 并解析 Atom XML 响应。"""
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "ClawArxivBot/1.0 (mailto:student@example.com)")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                xml_data = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise RuntimeError(f"arXiv API 请求失败: {e}")

        return self._parse_atom(xml_data)

    def _parse_atom(self, xml_data: str) -> list[dict]:
        """解析 arXiv API 返回的 Atom XML。"""
        root = ET.fromstring(xml_data)
        papers = []

        for entry in root.findall("atom:entry", ARXIV_NS):
            try:
                # 基本字段
                title = self._el_text(entry, "atom:title")
                summary = self._el_text(entry, "atom:summary")
                published = self._el_text(entry, "atom:published")

                # 作者列表
                authors = []
                for author_el in entry.findall("atom:author", ARXIV_NS):
                    name = self._el_text(author_el, "atom:name")
                    if name:
                        authors.append(name)

                # 链接
                arxiv_url = ""
                pdf_url = ""
                for link_el in entry.findall("atom:link", ARXIV_NS):
                    href = link_el.attrib.get("href", "")
                    rel = link_el.attrib.get("title", "")
                    if not rel:
                        arxiv_url = href
                    elif "pdf" in rel.lower():
                        pdf_url = href

                # 提取 ID（如 http://arxiv.org/abs/2301.12345v1）
                raw_id = self._el_text(entry, "atom:id") or ""
                paper_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

                # 分类
                categories = [
                    cat.attrib.get("term", "")
                    for cat in entry.findall("atom:category", ARXIV_NS)
                ]

                # 主要分类
                primary_cat = ""
                for cat_el in entry.findall("arxiv:primary_category", ARXIV_NS):
                    primary_cat = cat_el.attrib.get("term", "")

                # 发表信息（会议/期刊 + 备注）
                journal_ref = self._el_text(entry, "arxiv:journal_ref")
                comment = self._el_text(entry, "arxiv:comment")

                papers.append(
                    {
                        "id": paper_id,
                        "title": title.replace("\n", " ").strip(),
                        "authors": ", ".join(authors),
                        "author_list": authors,
                        "summary": summary.replace("\n", " ").strip(),
                        "published": published[:10] if published else "",
                        "categories": ", ".join(categories),
                        "primary_category": primary_cat,
                        "journal_ref": journal_ref,
                        "comment": comment,
                        "url": arxiv_url,
                        "pdf_url": pdf_url,
                    }
                )
            except Exception:
                continue

        return papers

    @staticmethod
    def _el_text(parent: ET.Element, tag: str) -> str:
        el = parent.find(tag, ARXIV_NS)
        return el.text.strip() if el is not None and el.text else ""

    # ========================================================================
    # 格式化输出
    # ========================================================================

    def _format_results(self, papers: list[dict], title: str) -> str:
        """格式化论文列表为可读文本 + 结构化 JSON。"""
        lines = [f"\n📚 {title} ({len(papers)} 篇)\n"]

        for i, p in enumerate(papers, 1):
            authors = p.get("authors", "N/A")
            if len(authors) > 80:
                authors = authors[:77] + "..."

            # 发表信息
            venue = p.get("journal_ref", "") or p.get("comment", "")
            venue_line = f"      发表: {venue}\n" if venue else ""

            lines.append(
                f"  [{i}] **{p.get('title', 'N/A')}**\n"
                f"      作者: {authors}\n"
                f"      日期: {p.get('published', 'N/A')} | 分类: {p.get('primary_category', 'N/A')}\n"
                f"{venue_line}"
                f"      ID: {p.get('id', 'N/A')} | URL: {p.get('url', 'N/A')}\n"
            )

        # 附加结构化 JSON（供后续处理，LLM 不会直接展示这部分给用户）
        lines.append(f"\n<arxiv_json_data>\n{json.dumps(papers, ensure_ascii=False, indent=2)}\n</arxiv_json_data>")

        return "\n".join(lines)

    # ========================================================================
    # 报告生成
    # ========================================================================

    def _build_markdown_report(self, papers: list[dict]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        total = len(papers)

        lines = [
            f"# arXiv 论文综述报告",
            f"",
            f"> 生成时间: {now} | 论文数: {total}",
            f"",
            f"---",
            f"",
            f"## 目录",
            f"",
        ]

        for i, p in enumerate(papers, 1):
            lines.append(f"{i}. [{p.get('title', 'Untitled')}](#paper-{i})")

        lines.extend(["", "---", ""])

        for i, p in enumerate(papers, 1):
            lines.extend(
                [
                    f"## {i}. {p.get('title', 'Untitled')} {{#paper-{i}}}",
                    f"",
                    f"| 字段 | 内容 |",
                    f"|------|------|",
                    f"| **作者** | {p.get('authors', 'N/A')} |",
                    f"| **发布日期** | {p.get('published', 'N/A')} |",
                    f"| **发表** | {p.get('journal_ref', '') or p.get('comment', '') or '(未标注)'} |",
                    f"| **arXiv** | [{p.get('id', '')}]({p.get('url', '')}) |",
                    f"| **PDF** | [下载]({p.get('pdf_url', '')}) |",
                    f"| **分类** | {p.get('categories', 'N/A')} |",
                    f"",
                    f"### 摘要",
                    f"",
                    p.get("summary", "N/A"),
                    f"",
                    f"### LLM 分析",
                    f"",
                    f"| 维度 | 分析 |",
                    f"|------|------|",
                    f"| **解决的问题** | *(待 LLM 填充)* |",
                    f"| **创新点** | *(待 LLM 填充)* |",
                    f"| **解决方案** | *(待 LLM 填充)* |",
                    f"| **结论** | *(待 LLM 填充)* |",
                    f"| **局限性** | *(待 LLM 填充)* |",
                    f"",
                    f"---",
                    f"",
                ]
            )

        lines.extend(
            [
                f"## 总结与展望",
                f"",
                f"*（由 LLM 综合分析 {total} 篇论文后生成）*",
                f"",
            ]
        )

        return "\n".join(lines)

    def _build_html_report(self, papers: list[dict]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            "<!DOCTYPE html>",
            '<html lang="zh-CN">',
            "<head>",
            '<meta charset="UTF-8">',
            "<title>arXiv 论文综述报告</title>",
            "<style>",
            "body { font-family: -apple-system, sans-serif; max-width: 900px; margin: 0 auto; padding: 2em; }",
            "h1 { border-bottom: 2px solid #333; }",
            "h2 { border-bottom: 1px solid #ccc; margin-top: 2em; }",
            "table { border-collapse: collapse; width: 100%; }",
            "td, th { border: 1px solid #ddd; padding: 8px; }",
            "th { background: #f5f5f5; }",
            ".summary { background: #f9f9f9; padding: 1em; border-left: 4px solid #0366d6; }",
            "</style>",
            "</head>",
            "<body>",
            f"<h1>arXiv 论文综述报告</h1>",
            f"<p>生成时间: {now} | 论文数: {len(papers)}</p>",
        ]

        for i, p in enumerate(papers, 1):
            lines.extend(
                [
                    f"<h2>{i}. {p.get('title', 'Untitled')}</h2>",
                    "<table>",
                    f"<tr><td><strong>作者</strong></td><td>{p.get('authors', 'N/A')}</td></tr>",
                    f"<tr><td><strong>日期</strong></td><td>{p.get('published', 'N/A')}</td></tr>",
                    f"<tr><td><strong>发表</strong></td><td>{p.get('journal_ref', '') or p.get('comment', '') or '(未标注)'}</td></tr>",
                    f"<tr><td><strong>arXiv</strong></td><td><a href='{p.get('url', '#')}'>{p.get('id', '')}</a></td></tr>",
                    f"<tr><td><strong>分类</strong></td><td>{p.get('categories', 'N/A')}</td></tr>",
                    "</table>",
                    f"<h3>摘要</h3>",
                    f"<div class='summary'>{p.get('summary', 'N/A')}</div>",
                ]
            )

        lines.extend(["</body>", "</html>"])
        return "\n".join(lines)


# ========================================================================
# 工厂函数
# ========================================================================

def create_arxiv_search_tool() -> ArxivSearchTool:
    """创建 arxiv_search tool 实例。"""
    return ArxivSearchTool(output_dir="./output")
