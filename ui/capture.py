"""BackgroundCapture — 后台捕获 stdout，供 TUI 日志面板消费。"""

from __future__ import annotations

import io
import sys
import threading
from collections import deque
from typing import TextIO


class BackgroundCapture(TextIO):
    """线程安全的 stdout 替代品，同时保留终端输出能力。"""

    def __init__(self, *, echo: bool = True) -> None:
        self._real_stdout = sys.__stdout__
        self._echo = echo
        self._lines: deque[str] = deque()
        self._lock = threading.Lock()
        self._buffer = io.StringIO()

    def write(self, s: str) -> int:
        if not s:
            return 0
        with self._lock:
            for line in s.splitlines():
                stripped = line.rstrip()
                if stripped:
                    self._lines.append(stripped)
        if self._echo:
            try:
                self._real_stdout.write(s)
                self._real_stdout.flush()
            except Exception:
                pass
        return len(s)

    def flush(self) -> None:
        if self._echo:
            try:
                self._real_stdout.flush()
            except Exception:
                pass

    def drain(self) -> list[str]:
        with self._lock:
            result = list(self._lines)
            self._lines.clear()
        return result

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return False