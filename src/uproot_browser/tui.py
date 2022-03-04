from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import plotext as plt
import rich.panel
import textual.widgets
import uproot
from textual.app import App
import textual.views
from textual.widget import Widget
from textual.widgets import Footer, Header
import textual.geometry

import uproot_browser
import uproot_browser.dirs
import uproot_browser.plot
import uproot_browser.tree

from .plot_view import PlotWidget
from .tree import UprootItem
from .tree_view import TreeView, UprootClick


class Browser(App):
    """A basic implementation of the uproot-browser TUI"""

    def __init__(self, *args, path: Path, **kwargs) -> None:
        self.path = path
        super().__init__(*args, **kwargs)

    async def on_load(self) -> None:
        """Sent before going in to application mode."""

        # Bind our basic keys
        await self.bind("b", "view.toggle('tree')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""

        self.tree = TreeView(self.path)
        self.plot = PlotWidget(self.tree.upfile)

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
        except Exception:
            self.plot.set_plot(None)

        await self.plot.update()
