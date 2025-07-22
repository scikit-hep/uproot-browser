from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import contextlib
import sys
from typing import Any, ClassVar

import plotext as plt
import rich.syntax
import textual.app
import textual.binding
import textual.containers
import textual.events
import textual.widgets
from textual.reactive import var

with contextlib.suppress(AttributeError):
    light_background = 0xF5, 0xF5, 0xF5
    # pylint: disable-next=protected-access
    plt._dict.themes["default"][0] = light_background
    # pylint: disable-next=protected-access
    plt._dict.themes["default"][1] = light_background

    dark_background = 0x1E, 0x1E, 0x1E
    dark_text = 0xFF, 0xA6, 0x2B
    # pylint: disable-next=protected-access
    plt._dict.themes["dark"][0] = dark_background
    # pylint: disable-next=protected-access
    plt._dict.themes["dark"][1] = dark_background
    # pylint: disable-next=protected-access
    plt._dict.themes["dark"][2] = dark_text

from uproot_browser.exceptions import EmptyTreeError

from .header import Header
from .help import HelpScreen
from .left_panel import UprootSelected, UprootTree
from .right_panel import (
    EmptyWidget,
    Error,
    ErrorWidget,
    LogoWidget,
    Plotext,
    PlotWidget,
    make_plot,
)
from .tools import Info, Tools


class Browser(textual.app.App[object]):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS: ClassVar[
        list[textual.binding.Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        textual.binding.Binding("b", "toggle_files", "Navbar"),
        textual.binding.Binding("q", "quit", "Quit"),
        textual.binding.Binding("d", "quit_with_dump", "Dump & Quit"),
        textual.binding.Binding("f1", "help", "Help"),
        textual.binding.Binding("?", "help", "Help", show=False),
        textual.binding.Binding("escape", "quit", "Quit", show=False),
    ]

    show_tree = var(True)
    show_tools = var(False)

    def __init__(self, path: str, **kwargs: Any) -> None:
        self.path = path
        super().__init__(**kwargs)

        self.plot_widget = PlotWidget(id="plot")
        self.error_widget = ErrorWidget(id="error")

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Header("uproot-browser")
        with textual.containers.Container():
            # left_panel
            with textual.widgets.TabbedContent(id="left-view"):
                with textual.widgets.TabPane("Tree"):
                    yield UprootTree(self.path, id="tree-view")
                with textual.widgets.TabPane("Tools"):
                    yield Tools()
                with textual.widgets.TabPane("Info"):
                    yield Info()
            # main_panel
            with textual.widgets.ContentSwitcher(id="main-view", initial="logo"):
                yield LogoWidget(id="logo")
                yield self.plot_widget
                yield self.error_widget
                yield EmptyWidget(id="empty")
        yield textual.widgets.Footer()

    def on_mount(self, _event: textual.events.Mount) -> None:
        self.query_one("#tree-view").focus()

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-panel")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    @staticmethod
    def _is_dark(theme: str) -> bool:
        return not theme.endswith(("-light", "-latte", "-ansi"))

    def action_quit_with_dump(self) -> None:
        """Dump the current state of the application."""

        content_switcher = self.query_one("#main-view", textual.widgets.ContentSwitcher)
        err_widget = content_switcher.query_one("#error", ErrorWidget)

        msg = f'\nimport uproot\nuproot_file = uproot.open("{self.path}")'

        items: list[Plotext | Error] = []
        if content_switcher.current == "plot":
            assert self.plot_widget.item
            msg += (
                f'\nitem = uproot_file["{self.plot_widget.item.selection.lstrip("/")}"]'
            )
            items = [self.plot_widget.item]
        elif content_switcher.current == "error":
            assert err_widget.exc
            items = [err_widget.exc]

        theme = "ansi_dark" if self._is_dark(self.theme) else "ansi_light"

        results = rich.console.Group(
            *items,
            rich.syntax.Syntax(f"\n{msg}\n", "python", theme=theme),
        )

        self.exit(message=results)

    def watch_theme(self, _old: str, new: str) -> None:
        if self.plot_widget.item:
            self.plot_widget.item.theme = "dark" if self._is_dark(new) else "default"

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        content_switcher = self.query_one("#main-view", textual.widgets.ContentSwitcher)

        try:
            theme = "dark" if self._is_dark(self.theme) else "default"
            make_plot(message.upfile[message.path], theme, 20)
            self.plot_widget.item = Plotext(message.upfile, message.path, theme)
            content_switcher.current = "plot"

        except EmptyTreeError:
            content_switcher.current = "empty"

        except Exception:
            exc = sys.exc_info()
            assert exc[1]
            self.error_widget.exc = Error(exc)
            content_switcher.current = "error"


if __name__ in {"<run_path>", "__main__"}:
    fname = "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    app = Browser(path=fname)
    app.run()
