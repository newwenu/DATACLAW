from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from background_loop import BackgroundLoop
from core.config import get_config
from core.llm_factory import create_llm
from core.prompt_builder import build_system_prompt
from memory_manager import MemoryManager
from tools import get_all_tools
from tui import run_tui


class TokenStats:
    """会话级 token 用量累计。"""

    def __init__(self) -> None:
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.cached_tokens: int = 0

    def record(self, input_t: int, output_t: int, cached_t: int) -> None:
        self.input_tokens += input_t
        self.output_tokens += output_t
        self.cached_tokens += cached_t

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "cached": self.cached_tokens,
            "total": self.total,
        }


class CoreClawAgent:
    """CoreClaw Agent with tool support and memory management."""

    def __init__(self, base_dir: Path | None = None, model: str | None = None):
        self.base_dir = base_dir or Path.cwd()
        self.tools = get_all_tools(self.base_dir)
        self.work_dir: Path | None = None

        config = get_config()

        self.llm = create_llm(config)

        self.memory = MemoryManager(
            self.base_dir,
            llm_client=self.llm,
        )

        self.bg_loop = BackgroundLoop(self.base_dir)
        self._bg_started = False

        full_system_prompt = build_system_prompt(
            memory_dir=self.memory.memory_dir,
            skills_dir=self.base_dir / "skills",
            inject_long_term_memory=config.memory_inject_long_term,
        )

        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=full_system_prompt,
        )

        self.messages: list[Any] = []
        self.token_stats = TokenStats()

    def close(self) -> None:
        if hasattr(self, "memory") and self.memory:
            self.memory.close()
        if hasattr(self, "bg_loop") and self.bg_loop and self._bg_started:
            self.bg_loop.stop()
            self._bg_started = False

    def _ensure_bg_started(self) -> None:
        if not self._bg_started:
            self.bg_loop.start()
            self._bg_started = True

    def _prepare_chat(self, user_input: str) -> None:
        self._ensure_bg_started()
        user_msg = HumanMessage(content=user_input)
        self.messages.append(user_msg)
        self.memory.log_message(user_msg)

    def _finalize_chat(self, ai_message: BaseMessage | None) -> None:
        if ai_message is not None:
            self.memory.log_message(ai_message)

    async def chat(self, user_input: str) -> str:
        self._prepare_chat(user_input)

        response = await self.agent.ainvoke(
            {"messages": self.messages},
            config={"recursion_limit": 200},
        )

        self.messages = response["messages"]
        ai_message = self.messages[-1] if self.messages else None
        self._finalize_chat(ai_message)

        return ai_message.content if ai_message and hasattr(ai_message, "content") else ""

    async def stream_chat_with_events(self, user_input: str):
        self._prepare_chat(user_input)

        current_reasoning = ""
        current_content = ""
        async for chunk in self.agent.astream(
            {"messages": self.messages},
            config={"recursion_limit": 200},
            stream_mode=["updates", "messages"],
        ):
            mode, data = chunk
            if mode == "messages":
                msg, _metadata = data

                if getattr(msg, "type", None) != "ai":
                    continue

                reasoning_raw = ""
                if hasattr(msg, "additional_kwargs"):
                    reasoning_raw = msg.additional_kwargs.get("reasoning_content") or ""
                if reasoning_raw:
                    if reasoning_raw.startswith(current_reasoning):
                        delta = reasoning_raw[len(current_reasoning):]
                    else:
                        delta = reasoning_raw
                        current_reasoning = ""
                    if delta:
                        current_reasoning += delta
                        yield {
                            "type": "reasoning",
                            "content": current_reasoning,
                            "delta": delta,
                        }

                content_raw = getattr(msg, "content", "") or ""
                if content_raw:
                    if content_raw.startswith(current_content):
                        delta = content_raw[len(current_content):]
                    else:
                        delta = content_raw
                        current_content = ""
                    if delta:
                        current_content += delta
                        yield {
                            "type": "thinking",
                            "content": current_content,
                            "delta": delta,
                        }

            elif mode == "updates":
                for node_name, update in data.items():
                    if node_name == "agent":
                        msgs = update.get("messages", [])
                        for msg in msgs:
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield {
                                        "type": "tool_call",
                                        "name": tc.get("name", "unknown"),
                                        "args": tc.get("args", {}),
                                        "id": tc.get("id", ""),
                                        "content": msg.content or "",
                                    }
                            elif hasattr(msg, "response_metadata") and msg.response_metadata:
                                token_usage = msg.response_metadata.get("token_usage") or {}
                                if token_usage:
                                    self.token_stats.record(
                                        token_usage.get("input_tokens", 0),
                                        token_usage.get("output_tokens", 0),
                                        (token_usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                                    )
                    elif node_name == "tools":
                        msgs = update.get("messages", [])
                        for msg in msgs:
                            if hasattr(msg, "content") and msg.content:
                                name = getattr(msg, "name", "tool") or "tool"
                                tool_call_id = getattr(msg, "tool_call_id", "") or ""
                                yield {
                                    "type": "tool_result",
                                    "name": name,
                                    "content": str(msg.content),
                                    "tool_call_id": tool_call_id,
                                }

        full_response = await self.agent.ainvoke(
            {"messages": self.messages},
            config={"recursion_limit": 200},
        )
        ai_message = full_response["messages"][-1]
        self.messages = full_response["messages"]
        self._finalize_chat(ai_message)

        yield {
            "type": "final",
            "content": ai_message.content or "",
            "token_usage": self.token_stats.as_dict(),
        }

    def export_log(self, save_dir: str | None = None) -> str:
        log_entries = []
        for msg in self.messages:
            entry: dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "type": getattr(msg, "type", msg.__class__.__name__),
            }
            if hasattr(msg, "content"):
                entry["content"] = msg.content
            if hasattr(msg, "additional_kwargs") and msg.additional_kwargs:
                entry["additional_kwargs"] = msg.additional_kwargs
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                entry["tool_calls"] = msg.tool_calls
            if hasattr(msg, "name") and msg.name:
                entry["name"] = msg.name
            log_entries.append(entry)

        target_dir = Path(save_dir) if save_dir else self.base_dir
        save_path = target_dir / f"claw_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_text(
            json.dumps(log_entries, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return str(save_path)

    def clear_history(self):
        self.messages = []
        print("✅ 对话历史已清除")

    def set_work_dir(self, path: str) -> str:
        target = Path(path).expanduser()

        if target.is_absolute() and target.exists() and target.is_dir():
            pass
        else:
            target = target.resolve()
            if target.is_absolute() and target.exists() and target.is_dir():
                pass
            else:
                name = target.name
                if not name:
                    return f"❌ 无效的目录路径: {path}"
                base_parent = Path(self.base_dir).parent.resolve()
                home = Path.home()
                locations = [
                    base_parent / name,
                    Path(self.base_dir) / name,
                    home / name,
                    home / "Desktop" / name,
                    home / "Documents" / name,
                    home / "Downloads" / name,
                    Path.cwd() / name,
                ]
                found = None
                for loc in locations:
                    resolved = loc.resolve()
                    if resolved.exists() and resolved.is_dir():
                        found = resolved
                        break
                if found is None:
                    return f"❌ 找不到目录: {path}"
                target = found

        self.work_dir = target.resolve()

        for tool in self.tools:
            if tool.name == "read_skill_file":
                continue
            if tool.name == "write_memory":
                continue
            current_val = getattr(tool, "root_dir", None)
            if current_val is not None:
                try:
                    setattr(tool, "root_dir", str(target.resolve()))
                except (AttributeError, TypeError):
                    pass

        sys_msg = SystemMessage(content=(
            f"## 工作目录变更通知\n\n"
            f"用户已指定工作目录：`{target}`\n\n"
            f"**重要约束（必须遵守）：**\n"
            f"1. 所有文件读取操作**只能**访问 `{target}` 及其子目录下的文件\n"
            f"2. 所有文件写入/下载操作**必须**保存到 `{target}` 目录下\n"
            f"3. 严禁访问 `{target}` 之外的任何文件和目录\n"
            f"4. 如果用户未指定具体路径，默认使用 `{target}` 作为输出目录\n"
            f"5. 你的工作范围限定在此目录内，超出此目录的操作将被拒绝"
        ))
        self.messages.append(sys_msg)

        print(f"[WorkDir] 已设置为: {target}")
        return f"✅ 工作目录已设置为: {target}\n工具沙盒已更新，所有文件操作限制在此目录内。"

    def get_work_dir(self) -> str:
        return str(self.work_dir) if self.work_dir else ""


async def single_query(agent: CoreClawAgent, query: str) -> str:
    return await agent.chat(query)


def main():
    config = get_config()
    errors = config.validate_api_keys()
    if errors:
        for err in errors:
            print(f"❌ 错误: {err}")
        print("请在 .env 文件中配置正确的 API Key")
        sys.exit(1)

    base_dir = Path(__file__).parent.resolve()
    agent = CoreClawAgent(base_dir=base_dir)

    if len(sys.argv) > 1:
        query = sys.argv[1]
        result = asyncio.run(single_query(agent, query))
        print(result)
    else:
        run_tui(agent)


if __name__ == "__main__":
    main()