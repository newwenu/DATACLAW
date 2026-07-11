name: translate-pdf
description: 翻译 PDF 学术论文，生成双语对照输出，保留公式、图表、目录和注释。基于 pdf2zh-next (BabelDOC)。当用户需要翻译 PDF 文档（尤其是英译中）、生成双语对照 PDF、翻译指定页面或批量处理多个 PDF 时触发。支持 Google、DeepL、OpenAI、DeepSeek、SiliconFlow 等翻译后端。

# PDF 论文翻译 (pdf2zh-next)

将 PDF 文档（尤其是学术论文）翻译为中文，保留公式、图表、目录和注释。默认输出双语对照 + 纯译文两个文件。

## 快速开始

```bash
pdf2zh_next input.pdf --lang-out zh-CN
```

首次运行会下载模型资源（约 500MB，含 CMap 字体映射和 DocLayout-YOLO 模型），之后即用即翻。

## 安装

### 方式一：uv 安装（推荐，跨平台）

```bash
pip install uv
uv tool install --python 3.12 pdf2zh-next
```

安装后二进制路径（按 `pdf2zh_next` 找不到时用完整路径调用）：

| 平台 | 路径 |
|------|------|
| **Windows** | `%USERPROFILE%\.local\bin\pdf2zh_next.exe` |
| **macOS** | `~/Library/Application Support/uv/tools/pdf2zh-next/bin/pdf2zh_next` |
| **Linux** | `~/.local/bin/pdf2zh_next` |

### 方式二：pip 直接安装（备选）

```bash
pip install pdf2zh-next
```

此方式 `pdf2zh_next` 会直接加入 PATH，无需手动找路径。

---

运行 `pdf2zh_next --version` 确认安装成功。

## 常用翻译场景

### 英文论文 → 中文（最常用）

```bash
pdf2zh_next paper.pdf --lang-in en --lang-out zh-CN
```

### 中→英

```bash
pdf2zh_next paper.pdf --lang-in zh-CN --lang-out en
```

### 指定翻译页面

```bash
pdf2zh_next paper.pdf --pages 1-5,7,10-12 --lang-out zh-CN
```

### 只输出纯译文（不要双语对照）

```bash
pdf2zh_next paper.pdf --no-dual --lang-out zh-CN
```

### 指定输出目录

```bash
pdf2zh_next paper.pdf --output /path/to/dir --lang-out zh-CN
```

### 批量翻译

```bash
pdf2zh_next file1.pdf file2.pdf file3.pdf --lang-out zh-CN
```

## 翻译服务选择

默认使用 SiliconFlow 免费引擎（无需 API key）。若免费引擎质量不足或需要更快速度，可切换：

```bash
# Google 翻译（免费，需网络）
pdf2zh_next paper.pdf --google --lang-out zh-CN

# DeepL（需配置 API key）
pdf2zh_next paper.pdf --deepl --lang-out zh-CN

# OpenAI / DeepSeek（需配置 API key，质量最好）
pdf2zh_next paper.pdf --openai --lang-out zh-CN
pdf2zh_next paper.pdf --deepseek --lang-out zh-CN
```

## 核心参数速查

| 参数 | 说明 |
|------|------|
| `--lang-in <code>` | 源语言，省略则自动检测 |
| `--lang-out <code>` | 目标语言，中译用 `zh-CN` |
| `--pages <range>` | 页码范围，如 `1-5,7,10-12` |
| `--output <dir>` | 指定输出目录 |
| `--no-dual` | 不生成双语对照文件 |
| `--no-mono` | 不生成纯译文文件 |
| `--dual-translate-first` | 双语模式下译文页在前 |
| `--qps <n>` | 翻译速率限制（默认不限） |
| `--debug` | 输出详细调试信息 |
| `--gui` | 启动 Web UI 而非命令行 |

## 常用语言代码

| 语言 | 代码 |
|------|------|
| 简体中文 | `zh-CN` |
| 繁体中文 | `zh-TW` |
| 英语 | `en` |
| 日语 | `ja` |
| 韩语 | `ko` |
| 法语 | `fr` |
| 德语 | `de` |
| 西班牙语 | `es` |
| 俄语 | `ru` |
| 阿拉伯语 | `ar` |

## 输出文件

翻译完成后在当前（或指定）目录生成：

- `xxx.zh-CN.mono.pdf` — 纯中文译文
- `xxx.zh-CN.dual.pdf` — 中英双语对照（推荐阅读用）
- `xxx.zh-CN.glossary.csv` — 自动提取的术语表

**推荐使用 dual.pdf**，可以同时对照原文和译文看。

## 故障排查

**WARNING 类信息一般不影响翻译结果**：`Expecting ',' delimiter` 和 `Expecting property name` 等警告来自免费翻译引擎的 JSON 解析问题，工具会自动 fallback 重试，只要最终显示 "Translation completed" 即为成功。

**翻译质量不佳**：切换翻译服务，推荐 `--openai` 或 `--deepseek` 获得更好的翻译质量。

**内存不足**：大文件翻译峰值内存可能超过 1.3GB，用 `--pages` 分批翻译。

**命令找不到**：用 uv 安装后二进制可能不在 PATH 中，使用完整路径调用。

## 辅助脚本

`scripts/translate_pdf.sh` — Unix/macOS 一键翻译脚本（Windows 请直接使用 `pdf2zh_next` 命令）：

```bash
# 默认英→中
bash scripts/translate_pdf.sh input.pdf

# 指定语言和页面
bash scripts/translate_pdf.sh input.pdf en 1-10 /output/dir
```

> **注意**：该脚本仅限 Linux/macOS/WSL。在 Windows 原生 cmd/PowerShell 中直接调用 `pdf2zh_next` 命令即可，功能完全相同，无需脚本。
