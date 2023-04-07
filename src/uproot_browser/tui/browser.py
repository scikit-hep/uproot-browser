from __future__ import annotations

from pathlib import Path
from typing import Any

import textual.app
import textual.containers
from textual.reactive import var
from textual.widgets import Footer, Header

from .plot import ErrorWidget, LogoWidget, PlotWidget
from .tree import TreeWidget


class Browser(textual.app.App):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS = [
        ("b", "toggle_files", "Toggle sidebar"),
        ("q", "quit", "Quit"),
        ("d", "dump", "Quit with dump"),
    ]

    show_tree = var(True)

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-tree")

    def __init__(self, path: Path, **kwargs: Any) -> None:
        self.path = path
        super().__init__(**kwargs)

        # self.tree = TreeView(self.path)
        # self.plot = PlotWidget(self.tree.upfile)
        self.results: list[Any] = []

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Header()
        with textual.containers.Container():
            # left
            yield TreeWidget("./", id="tree-view")
            # right
            yield textual.widgets.ContentSwitcher(
                LogoWidget(id="logo"),
                PlotWidget(id="plot"),
                ErrorWidget(id="error"),
                id="main-view",
                initial="logo",
            )
        yield Footer()

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def action_dump(self):
        """Called in response to key binding."""
        self.exit(message="Quit with Dump")
