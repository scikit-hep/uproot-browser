from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import plotext as plt
import uproot
from textual.app import App
from textual.widgets import Footer, Header

import uproot_browser
import uproot_browser.dirs
import uproot_browser.plot
import uproot_browser.tree

from .plot_view import PlotView
from .tree_view import TreeView


class Browser(App):
    """A basic implementation of the uproot-browser TUI"""

    def __init__(self, *args, path: Path, **kwargs) -> None:
        self.path = path
        super().__init__(*args, **kwargs)

    async def on_load(self) -> None:
        """Sent before going in to application mode."""

        # Bind our basic keys
        await self.bind("b", "view.toggle('sidebar')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""

        # Create our widgets
        fname = uproot_browser.dirs.filename(self.path)
        selections = uproot_browser.dirs.selections(f"{self.path}:hstat")
        my_tree = uproot.open(fname)
        *_, item = uproot_browser.dirs.apply_selection(my_tree, selections)

        uproot_browser.plot.plot(item)
        self.plot = plt.build()
        self.tree = TreeView(self.path)

        # Dock our widget
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        await self.view.dock(self.tree, edge="left", size=48, name="tree")
        await self.view.dock(self.plot, edge="top")


# Run the uproot-browser TUI
Browser.run(
    title="uproot-browser",
    log="textual.log",
    path=Path("../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"),
)
