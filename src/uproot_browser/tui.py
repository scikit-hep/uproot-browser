from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import plotext as plt
import rich.panel
import uproot
from textual.app import App
from textual.widgets import Footer, Header
from textual.widget import Widget
import textual.widgets

import uproot_browser
import uproot_browser.dirs
import uproot_browser.plot
import uproot_browser.tree

from .plot_view import PlotWidget
from .tree import UprootItem
from .tree_view import TreeView


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

        self.plot = PlotWidget()

        self.tree = TreeView(self.path)

        # Dock our widget
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        await self.view.dock(textual.widgets.ScrollView(self.tree), edge="left", size=48, name="tree")
        await self.view.dock(self.plot, edge="top")
