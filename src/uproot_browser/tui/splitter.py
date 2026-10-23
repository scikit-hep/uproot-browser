"""A draggable vertical bar that resizes a neighbouring panel."""

from __future__ import annotations

__lazy_modules__ = {"textual", "textual.events"}

import textual.events
from textual.widget import Widget

__all__ = ["Splitter"]

MIN_WIDTH = 10


class Splitter(Widget):
    """Drag to resize the panel selected by `target`.

    `grow_left` is True when the target lies to the left of the bar.
    """

    DEFAULT_CSS = """
    Splitter {
        width: 1;
        height: 100%;
        background: $panel;
    }
    Splitter:hover, Splitter.-dragging {
        background: $accent;
    }
    """

    def __init__(self, target: str, *, grow_left: bool, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._target = target
        self._sign = 1 if grow_left else -1
        self._start: tuple[int, int] | None = None

    def render(self) -> str:
        return ""

    def on_mouse_down(self, event: textual.events.MouseDown) -> None:
        panel = self.screen.query_one(self._target)
        self._start = (event.screen_x, panel.size.width)
        self.add_class("-dragging")
        self.capture_mouse()

    def on_mouse_move(self, event: textual.events.MouseMove) -> None:
        if self._start is None:
            return
        x0, w0 = self._start
        panel = self.screen.query_one(self._target)
        panel.styles.width = max(MIN_WIDTH, w0 + self._sign * (event.screen_x - x0))

    def on_mouse_up(self, _event: textual.events.MouseUp) -> None:
        self._start = None
        self.remove_class("-dragging")
        self.release_mouse()
