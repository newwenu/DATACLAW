<p align="center">
  <img src="https://img.shields.io/badge/🐾%20Claw-v2.0-1a73e8" alt="Claw">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue">
  <img src="https://img.shields.io/badge/LLM-DeepSeek%20%7C%20Qwen-brightgreen">
</p>

<h1 align="center">🐾 数据分析 Claw — 易扩展的终端智能体</h1>

<p align="center">
  基于 LangChain / LangGraph ReAct Agent 构建，支持工具调用、技能扩展、记忆持久化与定时任务。
</p>

***

## 🚀 快速使用

### 1️⃣ 安装依赖

```bash
pip install -r requirements.txt
```

### 2️⃣ 配置 API Key

```env
# 选择模型：deepseek（默认）或 qwen
MAIN_MODEL=deepseek

# DeepSeek 配置
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat

# Qwen（通义千问）配置
DASHSCOPE_API_KEY=sk-你的key
QWEN_MODEL=qwen-plus
```

### 3️⃣ 运行

```bash
# 交互式对话模式
python Claw.py

# 单次查询模式
python Claw.py "帮我分析一下 Summer.csv"
```

***

## 🧠 模型切换

在 `.env` 中修改 `MAIN_MODEL` 即可切换：

| 模型            | `MAIN_MODEL` 值 | API Key             |
| ------------- | -------------- | ------------------- |
| **DeepSeek**  | `deepseek`（默认） | `DEEPSEEK_API_KEY`  |
| **Qwen 通义千问** | `qwen`         | `DASHSCOPE_API_KEY` |

除真实 API 模式外，还支持：

- `LLM_MODE=mock`：本地 Mock LLM，零 token，适合调试
- `LLM_MODE=proxy`：通过 OpenAI 兼容接口转发到本地模型服务

***

## 🔑 API Key 获取

### DeepSeek

| 项目       | 说明                                        |
| -------- | ----------------------------------------- |
| **申请地址** | <https://platform.deepseek.com/api_keys>  |
| **步骤**   | 注册/登录 → 控制台 → API Keys → 创建 → 复制 `sk-...` |
| **费用**   | 新用户有免费额度，后续按量计费                           |

```env
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_MODEL=deepseek-chat        # 可选: deepseek-chat, deepseek-reasoner
```

### Qwen（通义千问）

| 项目       | 说明                                            |
| -------- | --------------------------------------------- |
| **申请地址** | <https://bailian.console.aliyun.com/>         |
| **步骤**   | 登录阿里云 → 百炼控制台 → API-KEY 管理 → 创建 → 复制 `sk-...` |
| **费用**   | 新用户有免费额度，按量计费                                 |

```env
DASHSCOPE_API_KEY=sk-你的key
QWEN_MODEL=qwen-plus                 # 可选: qwen-plus, qwen-turbo, qwen-max
```

***

## 🏗️ 项目架构

```
DataClaw/
├── Claw.py                 # 主入口：CoreClawAgent + 单次/TUI 启动
├── core/                   # 核心基础设施
│   ├── config.py           # 配置中心（pydantic-settings + .env）
│   ├── llm_factory.py      # LLM 工厂（live / mock / proxy）
│   ├── path_utils.py       # 统一沙盒路径解析
│   └── prompt_builder.py   # System Prompt 组装
├── tools/                  # Agent 可调用的原子工具
│   ├── terminal_tool.py    # 沙盒 Shell 执行
│   ├── python_repl_tool.py # Python REPL
│   ├── read_file_tool.py   # 项目内文件读取（沙盒）
│   ├── write_memory_tool.py# 记忆写入
│   ├── arxiv_search_tool.py# arXiv 论文检索与报告导出
│   └── summer_analysis_tool.py  # 夏季温室数据挖掘
├── skills/                 # 技能定义（LLM 可读取并按步骤执行）
│   ├── Data_Anlysis/
│   ├── arxiv_paper_search/
│   ├── summer_data_mining/
│   └── translate-pdf/
├── tasks/                  # 后台定时任务
│   ├── check_temperature_warning.py
│   └── say_hello_task.py
├── memory/                 # 记忆文件
│   ├── IDENTITY.md         # Agent 身份
│   ├── SOUL.md             # 性格/风格
│   ├── USER.md             # 用户档案
│   └── logs/               # 对话日志（按日期）
├── ui/                     # Textual 终端 UI
│   ├── app.py              # TUI 主应用
│   ├── chat.py             # 对话消息组件
│   ├── commands.py         # 斜杠命令
│   ├── completer.py        # 命令补全
│   └── styles.tcss         # 样式
├── background_loop.py      # 后台任务调度器
├── memory_manager.py       # 记忆管理器
├── skills_scanner.py       # 技能扫描与提示词生成
├── tui.py                  # TUI 兼容入口
├── requirements.txt
└── .env.example
```

### 核心执行流程

1. **启动**：`Claw.py` 读取 `.env` 配置，创建 `CoreClawAgent`
2. **Prompt 组装**：`prompt_builder.py` 把 `IDENTITY.md`、`SOUL.md`、技能菜单、用户档案拼接为 System Prompt
3. **Agent 运行**：`LangGraph create_react_agent` 驱动 LLM 循环推理与工具调用
4. **工具层**：7 个原子工具覆盖终端、代码执行、文件读取、记忆、论文检索、数据分析
5. **技能层**：每个 skill 是一个 `skills/<name>/SKILL.md`，Agent 先读取再执行
6. **记忆层**：`write_memory` 工具写入 `USER.md` / `MEMORY.md`，下次启动自动加载
7. **定时任务**：`background_loop.py` 自动扫描 `tasks/*.py` 并调度执行

***

## 🛠️ 可用工具

| 工具                       | 能力          | 说明                                        |
| ------------------------ | ----------- | ----------------------------------------- |
| 💻 **terminal**          | 沙盒 Shell 执行 | 文件操作、安装依赖、运行脚本，30s 超时保护，危险命令拦截            |
| 🐍 **python\_repl**      | Python REPL | 计算、数据处理、代码执行，安全沙箱                         |
| 📁 **read\_file**        | 文件读取（沙盒）    | 读取项目内文件，自动截断大文件（>10KB），只读操作               |
| 📖 **read\_skill\_file** | 技能文件读取      | 读取 `skills/` 目录下的技能定义与辅助文件                |
| 🧠 **write\_memory**     | 记忆写入        | 记录用户偏好、兴趣、项目信息到记忆文件，跨会话持久化                |
| 📚 **arxiv\_search**     | arXiv 论文检索  | 搜索/批量搜索/获取详情/验证链接/导出 Markdown 或 HTML 综述报告 |
| 🌡️ **summer\_analysis** | 温室数据挖掘      | 针对 `Summer.csv` 的加载、统计、异常检测、相关性、可视化与报告生成  |

***

## 💬 命令行使用方法

### 交互模式

```bash
python Claw.py
```

内置 `/` 命令：

| 命令              | 功能           |
| --------------- | ------------ |
| `/quit`         | 退出           |
| `/clear`        | 清除对话历史       |
| `/help`         | 查看命令列表       |
| `/tools`        | 查看可用工具列表     |
| `/skills`       | 查看已加载的技能     |
| `/memory`       | 查看记忆文件状态     |
| `/task`         | 查看运行中的定时任务   |
| `/workdir <路径>` | 设置工作目录       |
| `/export`       | 导出对话日志为 JSON |
| `/log`          | 切换日志面板显隐     |

### 代码集成

```python
from Claw import CoreClawAgent
import asyncio

async def main():
    agent = CoreClawAgent()
    response = await agent.chat("帮我分析一下 Summer.csv")
    print(response)

asyncio.run(main())
```

***

## 🎯 内置技能

| 技能                           | 功能                                 |
| ---------------------------- | ---------------------------------- |
| 📊 **Data\_Anlysis**         | 数据科学：机器学习 / 统计 / 深度学习代码执行与可视化      |
| 📚 **arxiv\_paper\_search**  | arXiv 多关键词并行检索、LLM 深度分析、生成综述报告     |
| 🌡️ **summer\_data\_mining** | `Summer.csv` 温室环境监测数据的多维度数据挖掘      |
| 🌐 **translate-pdf**         | 基于 `pdf2zh-next` 翻译 PDF 论文，保留公式与图表 |

***

<p align="center">
  <b>🐾 Claw — 终端 AI 智能体</b>
</p>
