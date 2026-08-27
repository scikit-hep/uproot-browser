"""
Shared TUI palette, used by both the plotext themes and the mpl image path.
"""

from __future__ import annotations

LIGHT_BACKGROUND = 0xF5, 0xF5, 0xF5
DARK_BACKGROUND = 0x1E, 0x1E, 0x1E
DARK_TEXT = 0xFF, 0xA6, 0x2B


def as_hex(color: tuple[int, int, int]) -> str:
    r, g, b = color
    return f"#{r:02X}{g:02X}{b:02X}"
