from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

import rich.syntax
import textual.app
import textual.binding
import textual.containers
import textual.events
import textual.lazy
import textual.widgets
import textual.worker
from textual.reactive import var

from ..plotext_compat import add_theme
from .error import Error
from .header import Header
from .help import HelpScreen
from .image_plot import MPLPlot
from .jump import JumpScreen
from .left_panel import UprootTree
from .plot import Plotext, PlotItem, selection_source
from .theme import DARK_BACKGROUND, DARK_TEXT, LIGHT_BACKGROUND
from .tools import Info, Tools
from .viewer import ViewWidget

# Registered under our own names to avoid overriding plotext's built-in themes.
# The light theme uses the dark color variants, which read better on white.
add_theme(
    "uproot_light",
    canvas=LIGHT_BACKGROUND,
    text=((0, 0, 0), LIGHT_BACKGROUND),
    sequence=[4, 2, 1, 6, 5, 3],
)
add_theme("uproot_dark", canvas=DARK_BACKGROUND, text=(DARK_TEXT, DARK_BACKGROUND))

if TYPE_CHECKING:
    from .messages import ErrorMessage, RequestPlot, UprootSelected


class Browser(textual.app.App[None]):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("b", "toggle_files", "Navbar"),
        textual.binding.Binding("/", "jump", "Jump"),
        textual.binding.Binding("q", "quit", "Quit"),
        textual.binding.Binding("d", "quit_with_dump", "Dump & Quit"),
        textual.binding.Binding("f1", "help", "Help"),
        textual.binding.Binding("?", "help", "Help", show=False),
        textual.binding.Binding("escape", "quit", "Quit", show=False),
    ]

    show_tree = var(True)
    image_scale = var(1.5)

    def __init__(
        self, path: str, *, image: bool = False, image_scale: float = 1.5, **kwargs: Any
    ) -> None:
        self.path = path
        self.image = image
        self._image_rendered: tuple[Any, ...] | None = None
        super().__init__(**kwargs)

        self.view_widget = ViewWidget(id="plot-view", image=image)
        self.set_reactive(Browser.image_scale, image_scale)

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Header("uproot-browser")
        with textual.containers.Container():
            # left_panel
            with textual.widgets.TabbedContent(id="left-view"):
                with textual.widgets.TabPane("Tree", id="tree-tab"):
                    yield UprootTree(self.path, id="tree-view")
                with textual.widgets.TabPane("Tools"):
                    # Not lazy: lazy-mounting a Select races its internal mount
                    # (SelectCurrent.update queries "#label" before that child is
                    # mounted), which crashes on slow runners. Tools is cheap to
                    # build anyway; only the Info tab is worth deferring.
                    yield Tools()
                with textual.widgets.TabPane("Info"):
                    yield textual.lazy.Lazy(Info())
            # main_panel
            yield self.view_widget

        yield textual.widgets.Footer()

    def on_mount(self, _event: textual.events.Mount) -> None:
        self.query_one("#tree-view").focus()

    def watch_show_tree(self, show_tree: bool) -> None:  # noqa: FBT001
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-panel")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_jump(self) -> None:
        """Open the fuzzy finder to jump to a branch/field."""
        tree = self.query_one("#tree-view", UprootTree)
        self.push_screen(JumpScreen(tree.all_entries), self._on_jumped)

    def _on_jumped(self, path: str | None) -> None:
        if path is None:
            return
        self.query_one("#left-view", textual.widgets.TabbedContent).active = "tree-tab"
        self.query_one("#tree-view", UprootTree).select_path(path)

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def dump_source(self) -> tuple[str, list[Any]]:
        """The Dump & Quit source, and the renderables to show above it."""

        msg = f'\nimport uproot\nuproot_file = uproot.open("{self.path}")'

        item = self.view_widget.item
        items: list[Any] = []
        if isinstance(item, Error):
            items = [item]
            if item.selection:
                # Show which branch produced the traceback
                msg += selection_source(item.selection)
        elif isinstance(item, PlotItem):
            msg += item.dump_source()
            items = list(item.dump_renderables())

        return msg, items

    def action_quit_with_dump(self) -> None:
        """Dump the current state of the application."""

        msg, items = self.dump_source()

        theme = "ansi_dark" if self.current_theme.dark else "ansi_light"

        results = rich.console.Group(
            *items,
            rich.syntax.Syntax(f"\n{msg}\n", "python", theme=theme),
        )

        self.exit(message=results)

    def watch_theme(self) -> None:
        item = self.view_widget.item
        if isinstance(item, PlotItem):
            # Reassign (rather than mutate) so that watchers fire and any
            # cached rendering is invalidated.
            self.view_widget.item = item.with_theme(dark=self.current_theme.dark)

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        self.view_widget.plot_input.value = ""
        dark = self.current_theme.dark
        self.view_widget.item = (
            MPLPlot(
                message.upfile,
                message.path,
                dark=dark,
                app=self,
                scale=self.image_scale,
            )
            if self.image
            else Plotext(message.upfile, message.path, dark=dark, app=self)
        )

    def on_empty_message(self) -> None:
        self.view_widget.item = None

    def on_error_message(self, message: ErrorMessage) -> None:
        self.view_widget.item = message.err

    def on_request_plot(self, message: RequestPlot) -> None:
        self.render_plot(message.plot)

    def watch_image_scale(self, scale: float) -> None:
        item = self.view_widget.item
        if isinstance(item, MPLPlot) and item.scale != scale:
            self.view_widget.item = dataclasses.replace(item, scale=scale)

    def on_request_image(self) -> None:
        """Single render trigger: assigning an MPLPlot (or a resize) lands here."""
        item = self.view_widget.item
        if not isinstance(item, MPLPlot):
            return
        size = self.view_widget.image_pixel_size()
        if size is not None:
            item.size = size
        key = (item.selection, item.expr, item.dark, item.scale, item.size)
        if key != self._image_rendered:
            self._image_rendered = key
            assert self.view_widget.image_widget is not None
            self.view_widget.image_widget.loading = True
            self.render_image(item)

    @textual.work(exclusive=True, thread=True)
    def render_plot(self, plot: Plotext) -> None:
        worker = textual.worker.get_current_worker()
        new_plot = plot.make_plot()
        if new_plot and not worker.is_cancelled:
            self.call_from_thread(self.view_widget.plot_widget.update, new_plot)

    @textual.work(exclusive=True, thread=True)
    def render_image(self, plot: MPLPlot) -> None:
        worker = textual.worker.get_current_worker()
        image = plot.make_image()
        if worker.is_cancelled:
            return
        if image is None:
            # failed (empty/error message posted); allow a retry next request
            self._image_rendered = None
        self.call_from_thread(self.view_widget.update_image, image)


if __name__ in {"<run_path>", "__main__"}:
    fname = "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    app = Browser(path=fname)
    app.run()
