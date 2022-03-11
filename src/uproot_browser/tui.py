from __future__ import annotations

from pathlib import Path
from typing import Any

import textual.geometry
import textual.views
import textual.widgets
from textual.app import App
from textual.widgets import Footer

from .header import Header
from .plot_view import PlotWidget
from .tree_view import TreeView, UprootClick


class Browser(App):
    """A basic implementation of the uproot-browser TUI"""

    def __init__(self, path: Path, **kwargs: Any) -> None:
        self.path = path
        super().__init__(**kwargs)

        self.tree = TreeView(self.path)
        self.plot = PlotWidget(self.tree.upfile)

    async def on_load(self) -> None:
        """Sent before going in to application mode."""

        # Bind our basic keys
        await self.bind("b", "view.toggle('tree')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""

        # Set our file name as subtitle
        self.app.sub_title = self.path.name

        # Dock our widget
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        await self.view.dock(
            textual.widgets.ScrollView(self.tree), edge="left", size=48, name="tree"
        )
        await self.view.dock(self.plot, edge="right", name="plot")

    async def handle_uproot_click(self, message: UprootClick) -> None:
        """A message sent by the tree when a file is clicked."""

        try:
            self.plot.set_plot(message.path)
        except Exception:  # pylint: disable=broad-except
            self.plot.set_plot(None)

        await self.plot.update()
