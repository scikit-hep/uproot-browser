from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import textual.app
import textual.containers
from textual.reactive import var
from textual.widgets import Footer, Header

from uproot_browser.exceptions import EmptyTreeError

from .right_panel import EmptyWidget, ErrorWidget, LogoWidget, PlotWidget, Plotext, make_plot, Error
from .left_panel import UprootSelected, UprootTree


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

        # self.uptree = UprootTree(self.path)

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Header()
        with textual.containers.Container():
            # left
            yield UprootTree(self.path, id="tree-view")
            # with textual.containers.VerticalScroll():
            #     yield Static(id="code", expand=True)
            # yield textual.widgets.ScrollView(self.tree)
            # right
            yield textual.widgets.ContentSwitcher(
                LogoWidget(id="logo"),
                PlotWidget(id="plot"),
                ErrorWidget(id="error"),
                EmptyWidget(id="empty"),
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

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        content_switcher = self.query_one("#main-view")

        try:
            make_plot(message.upfile[message.path], 10, 10)
            plot_widget = content_switcher.query_one("#plot")
            plot_widget.item = Plotext(message.upfile[message.path])
            content_switcher.current = "plot"
            plot_widget.refresh()

        except EmptyTreeError:
            content_switcher.current = "empty"

        except Exception:
            error_widget = content_switcher.query_one("#error")
            error_widget.exc = sys.exc_info()
            content_switcher.current = "error"
            # error_widget.refresh()


        



