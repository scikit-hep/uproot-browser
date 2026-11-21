from __future__ import annotations

from typing import TYPE_CHECKING

import rich.repr
import textual.message

if TYPE_CHECKING:
    from uproot_browser.nodes import Node
    from uproot_browser.tui.plot import PlotItem


@rich.repr.auto
class UprootSelected(textual.message.Message, bubble=True):
    def __init__(self, root: Node, path: str, y_path: str = "") -> None:
        self.root = root
        self.path = path
        self.y_path = y_path
        super().__init__()


@rich.repr.auto
class RenderFailed(textual.message.Message, bubble=True):
    """The render ``render_id`` of ``source`` raised ``error``."""

    def __init__(self, source: PlotItem, error: Exception, render_id: int) -> None:
        self.source = source
        self.error = error
        self.render_id = render_id
        super().__init__()


@rich.repr.auto
class RequestRender(textual.message.Message, bubble=True):
    """Ask the app to render the current plot item (e.g. after a resize)."""
