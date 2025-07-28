from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import contextlib
from typing import Any, ClassVar

import plotext as plt
import rich.syntax
import textual.app
import textual.binding
import textual.containers
import textual.events
import textual.widgets
import textual.worker
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


from .error import Error
from .header import Header
from .help import HelpScreen
from .left_panel import UprootTree
from .messages import ErrorMessage, RequestPlot, UprootSelected
from .plot import Plotext
from .tools import Info, Tools
from .viewer import ViewWidget


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

    def __init__(self, path: str, **kwargs: Any) -> None:
        self.path = path
        super().__init__(**kwargs)

        self.view_widget = ViewWidget(id="plot-view")

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
            yield self.view_widget

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

        msg = f'\nimport uproot\nuproot_file = uproot.open("{self.path}")'

        items: list[Plotext | Error] = []
        if isinstance(self.view_widget.item, Error):
            items = [self.view_widget.item]
        elif isinstance(self.view_widget.item, Plotext):
            msg += (
                f'\nitem = uproot_file["{self.view_widget.item.selection.lstrip("/")}"]'
            )
            items = [self.view_widget.item]

        theme = "ansi_dark" if self._is_dark(self.theme) else "ansi_light"

        results = rich.console.Group(
            *items,
            rich.syntax.Syntax(f"\n{msg}\n", "python", theme=theme),
        )

        self.exit(message=results)

    def watch_theme(self, _old: str, new: str) -> None:
        if isinstance(self.view_widget.item, Plotext):
            self.view_widget.item.theme = "dark" if self._is_dark(new) else "default"

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        theme = "dark" if self._is_dark(self.theme) else "default"
        self.view_widget.plot_input.value = ""
        self.view_widget.item = Plotext(message.upfile, message.path, theme, self)

    def on_empty_message(self) -> None:
        self.view_widget.item = None

    def on_error_message(self, message: ErrorMessage) -> None:
        self.view_widget.item = message.err

    def on_request_plot(self, message: RequestPlot) -> None:
        self.render_plot(message.plot)

    @textual.work(exclusive=True, thread=True)
    def render_plot(self, plot: Plotext) -> None:
        worker = textual.worker.get_current_worker()
        new_plot = plot.make_plot()
        if new_plot and not worker.is_cancelled:
            self.call_from_thread(self.view_widget.plot_widget.update, new_plot)


if __name__ in {"<run_path>", "__main__"}:
    fname = "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    app = Browser(path=fname)
    app.run()
