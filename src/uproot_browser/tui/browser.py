from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"

import contextlib
import sys
from pathlib import Path
from typing import Any

import plotext as plt
import textual.app
import textual.containers
from textual.reactive import var
from textual.widgets import Footer, Header

with contextlib.suppress(AttributeError):
    light_background = 0xDF, 0xDF, 0xDF  # $surface-darken-1
    plt._dict.themes["default"][0] = light_background
    plt._dict.themes["default"][1] = light_background


from uproot_browser.exceptions import EmptyTreeError

from .left_panel import UprootSelected, UprootTree
from .right_panel import (
    EmptyWidget,
    ErrorWidget,
    LogoWidget,
    Plotext,
    PlotWidget,
    make_plot,
)


class Browser(textual.app.App):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS = [
        ("b", "toggle_files", "Toggle sidebar"),
        ("q", "quit", "Quit"),
        ("d", "dump", "Quit with dump"),
        ("t", "toggle_theme", "Toggle light/dark theme"),
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
            # left_panel
            yield UprootTree(self.path, id="tree-view")
            # right_panel
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

    def action_toggle_theme(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark
        content_switcher = self.query_one("#main-view")
        plot_widget = content_switcher.query_one("#plot")
        if plot_widget.item:
            plot_widget.item.theme = "dark" if self.dark else "default"
            plot_widget.refresh()

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        content_switcher = self.query_one("#main-view")

        try:
            make_plot(message.upfile[message.path], 10, 10)
            plot_widget = content_switcher.query_one("#plot")
            theme = "dark" if self.dark else "default"
            plot_widget.item = Plotext(message.upfile[message.path], theme)
            content_switcher.current = "plot"

        except EmptyTreeError:
            content_switcher.current = "empty"

        except Exception:
            error_widget = content_switcher.query_one("#error")
            error_widget.exc = sys.exc_info()
            content_switcher.current = "error"


if __name__ == "<run_path>":
    import uproot_browser.dirs

    fname = uproot_browser.dirs.filename(
        "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    )
    app = Browser(path=Path(fname))
