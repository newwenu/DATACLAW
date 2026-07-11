"""DataClaw TUI 组件包。"""

from __future__ import annotations

from collections.abc import Callable

import rich.cells

_orig_cell_len: Callable[[str], int] = rich.cells.cell_len


def _fixed_cell_len(
    text: str, _cell_len: Callable[[str], int] = _orig_cell_len
) -> int:
    if "\ufe0f" not in text:
        return _cell_len(text)

    width = _cell_len(text)
    extra = 0
    prev_width = 0
    for ch in text:
        if ch == "\ufe0f":
            extra += 1
            prev_width = 2
        else:
            prev_width = _cell_len(ch)
    return width + extra


rich.cells.cell_len = _fixed_cell_len

from ui.app import DataClawApp, run_tui
from ui.capture import BackgroundCapture
from ui.commands import COMMANDS, CommandHandler
from ui.completer import CommandCompleter

__all__ = [
    "DataClawApp",
    "run_tui",
    "BackgroundCapture",
    "COMMANDS",
    "CommandHandler",
    "CommandCompleter",
]