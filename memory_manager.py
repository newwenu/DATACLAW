"""Memory Manager — 管理聊天记录和长期记忆。

功能:
1. 按日期保存聊天记录到 memory/logs/
2. 记忆由 Agent 通过 write_memory 工具主动写入（不再自动监听提取）
   写入后下次启动时 load_user_memory() 自动加载到 System Prompt
"""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.messages import BaseMessage


class MemoryEncoder(json.JSONEncoder):
    """处理 LangChain 消息的 JSON 编码器。"""

    def default(self, obj: Any) -> Any:
        # 处理 LangChain 消息对象
        if hasattr(obj, "model_dump"):
            try:
                return obj.model_dump()
            except Exception:
                pass
        # 处理有 content 属性的消息对象
        if hasattr(obj, "content"):
            return {
                "_type": obj.__class__.__name__,
                "content": obj.content,
                "type": getattr(obj, "type", "unknown"),
            }
        # 处理普通对象
        if hasattr(obj, "__dict__"):
            return {
                "_type": obj.__class__.__name__,
                "__dict__": obj.__dict__,
            }
        return super().default(obj)


class ChatLogger:
    """按日期记录聊天记录。"""

    def __init__(self, logs_dir: Path):
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._current_date: str | None = None
        self._current_file: Path | None = None
        self._buffer: list[dict] = []
        self._lock = threading.Lock()

    def _get_today_file(self) -> Path:
        """获取今天的日志文件路径。"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._current_date:
            self._current_date = today
            self._current_file = self.logs_dir / f"{today}.jsonl"
            if self._buffer:
                self._flush()
        return self._current_file

    def _flush(self) -> None:
        """将缓冲数据写入文件。"""
        if not self._buffer or not self._current_file:
            return
        with open(self._current_file, "a", encoding="utf-8") as f:
            for record in self._buffer:
                f.write(json.dumps(record, cls=MemoryEncoder, ensure_ascii=False) + "\n")
        self._buffer = []

    def log_message(self, message: BaseMessage | dict) -> None:
        """记录一条消息。"""
        with self._lock:
            self._get_today_file()
            record = {
                "timestamp": datetime.now().isoformat(),
                "message": message,
            }
            self._buffer.append(record)
            self._flush()

    def close(self) -> None:
        """关闭日志，写入剩余数据。"""
        with self._lock:
            self._flush()

    def get_today_messages(self) -> list[dict]:
        """获取今天的所有消息。"""
        file_path = self._get_today_file()
        if not file_path.exists():
            return []
        messages = []
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages


class MemoryManager:
    """记忆管理器 — 精简版。

    保留能力:
    - ChatLogger: 按日期持久化对话日志
    - 记忆文件读写: write_memory 工具写入 → 下次启动加载

    已移除:
    - MemoryWatcher (watchdog 监听 + LLM 自动提取)
      → 记忆由 Agent 通过 write_memory 工具主动写入
    """

    def __init__(self, base_dir: Path, llm_client: Any | None = None):
        self.base_dir = base_dir
        self.memory_dir = base_dir / "memory"
        self.logs_dir = self.memory_dir / "logs"

        # 创建目录
        self.memory_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        # 聊天日志
        self.chat_logger = ChatLogger(self.logs_dir)

    def log_message(self, message: BaseMessage | dict) -> None:
        """记录消息。"""
        self.chat_logger.log_message(message)

    def close(self) -> None:
        """关闭管理器。"""
        self.chat_logger.close()

    def get_memory_files(self) -> dict[str, Path]:
        """获取所有记忆文件路径。"""
        return {
            "memory": self.memory_dir / "MEMORY.md",
            "user": self.memory_dir / "USER.md",
            "identity": self.memory_dir / "IDENTITY.md",
            "soul": self.memory_dir / "SOUL.md",
        }
