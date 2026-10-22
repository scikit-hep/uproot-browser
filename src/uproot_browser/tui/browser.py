from __future__ import annotations

__lazy_modules__ = {
    "dataclasses",
    "rich",
    "rich.markup",
    "rich.syntax",
    "rich.text",
    "textual.containers",
    "textual.events",
    "textual.lazy",
    "textual.widgets",
    "textual.worker",
    "uproot_browser.exceptions",
    f"{__spec__.parent}.error",
    f"{__spec__.parent}.header",
    f"{__spec__.parent}.help",
    f"{__spec__.parent}.image_plot",
    f"{__spec__.parent}.jump",
    f"{__spec__.parent}.left_panel",
    f"{__spec__.parent}.plot",
    f"{__spec__.parent}.right_panel",
    f"{__spec__.parent}.tools",
    f"{__spec__.parent}.viewer",
}

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

import rich.markup
import rich.syntax
import rich.text
import textual.app
import textual.binding
import textual.containers
import textual.events
import textual.lazy
import textual.widgets
import textual.worker
from textual.reactive import var

from uproot_browser.axis import NO_LIMITS, AxisLimits
from uproot_browser.exceptions import EmptyTreeError

from ..plotext_compat import add_theme
from .error import Error
from .header import Header
from .help import HelpScreen
from .image_plot import MPLPlot
from .jump import JumpScreen
from .left_panel import UprootTree
from .plot import Plotext, PlotItem, selection_source
from .right_panel import RightPanel
from .theme import DARK_BACKGROUND, DARK_TEXT, LIGHT_BACKGROUND
from .tools import Info
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
    from .messages import ErrorMessage, ExpressionErrorMessage, UprootSelected


class Browser(textual.app.App[None]):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("b", "toggle_files", "Navbar"),
        textual.binding.Binding("t", "toggle_right_panel", "Tools"),
        textual.binding.Binding("e", "toggle_entry_box", "Entry Box"),
        textual.binding.Binding("/", "jump", "Jump"),
        textual.binding.Binding("q", "quit", "Quit"),
        textual.binding.Binding("d", "quit_with_dump", "Dump & Quit"),
        textual.binding.Binding("f1", "help", "Help"),
        textual.binding.Binding("?", "help", "Help", show=False),
        textual.binding.Binding("escape", "quit", "Quit", show=False),
    ]

    show_tree = var(True)
    show_right_panel = var(True)
    show_entry_box = var(False)
    image_scale = var(1.5)
    axis_limits = var(NO_LIMITS)

    def __init__(
        self, path: str, *, image: bool = False, image_scale: float = 1.5, **kwargs: Any
    ) -> None:
        self.path = path
        self.image = image
        self._plot_rendered: tuple[Any, ...] | None = None
        self._image_rendered: tuple[Any, ...] | None = None
        # re-rendering a failed expression would only fail again
        self._failed_item: PlotItem | None = None
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
                with textual.widgets.TabPane("Info"):
                    yield textual.lazy.Lazy(Info())
            # main_panel
            yield self.view_widget
            yield RightPanel(id="right-panel")

        yield textual.widgets.Footer()
        yield textual.widgets.Static(id="navigation-count")

    def on_mount(self, _event: textual.events.Mount) -> None:
        tree = self.query_one("#tree-view", UprootTree)
        tree.focus()
        self.watch(tree, "count", self._show_count)

    def _show_count(self, count: str) -> None:
        status = self.query_one("#navigation-count", textual.widgets.Static)
        if count:
            status.update(f"Move: {count}")
        status.display = bool(count)

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

    def action_toggle_right_panel(self) -> None:
        """Toggle the typed axis controls and render scale panel."""
        self.show_right_panel = not self.show_right_panel

    def action_toggle_entry_box(self) -> None:
        """Toggle the plot expression entry box, focusing it when shown."""
        self.show_entry_box = not self.show_entry_box
        plot_input = self.view_widget.plot_input
        if self.show_entry_box:
            # The box lives in the plot window, which is hidden without a plot
            if isinstance(self.view_widget.item, PlotItem):
                plot_input.focus()
        elif plot_input.has_focus:
            self.query_one("#tree-view").focus()

    def watch_show_entry_box(self, show: bool) -> None:  # noqa: FBT001
        """Called when the entry box visibility changes."""
        self.view_widget.input_container.set_class(show, "-show-container")
        self.view_widget.call_after_refresh(self.view_widget.request_render)

    def watch_show_right_panel(self, show: bool) -> None:  # noqa: FBT001
        """Called when the right panel visibility changes."""
        self.set_class(not show, "-hide-right-panel")

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
        # Skip the watcher: it would re-render the old item
        self.set_reactive(Browser.axis_limits, NO_LIMITS)
        self.query_one("#right-panel", RightPanel).clear()
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

    def on_expression_error_message(self, message: ExpressionErrorMessage) -> None:
        item, error = message.source, message.error
        if self.view_widget.item is not item:
            return
        self._failed_item = item
        self.view_widget.plot_input.add_class("-needs-update")
        item.show_expression_error(self.view_widget)
        self.notify(
            rich.markup.escape(str(error) or type(error).__name__),
            title="Plot expression",
            severity="warning" if isinstance(error, EmptyTreeError) else "error",
        )

    def _is_failed(self, item: PlotItem) -> bool:
        if item is self._failed_item:
            return True
        # drop the reference so the item and its caches can be freed
        self._failed_item = None
        return False

    def on_request_plot(self) -> None:
        """Single render trigger: assigning a Plotext (or a resize) lands here."""
        item = self.view_widget.item
        if not isinstance(item, Plotext) or self._is_failed(item):
            return
        # The Static has a 1 cell padding, which content_size takes off already
        size = self.view_widget.plot_widget.content_size
        if not size.width or not size.height:
            return
        item.size = (size.width, size.height)
        key = (item.selection, item.expr, item.dark, item.size, item.axis_limits)
        if key != self._plot_rendered:
            self._plot_rendered = key
            self.view_widget.plot_widget.update(rich.text.Text("... plotting ..."))
            self.render_plot(item)

    def watch_image_scale(self, scale: float) -> None:
        item = self.view_widget.item
        if isinstance(item, MPLPlot) and item.scale != scale:
            self.view_widget.item = dataclasses.replace(item, scale=scale)

    def watch_axis_limits(self, limits: AxisLimits) -> None:
        item = self.view_widget.item
        if isinstance(item, PlotItem):
            self.view_widget.item = item.with_axis_limits(limits)

    def on_request_image(self) -> None:
        """Single render trigger: assigning an MPLPlot (or a resize) lands here."""
        item = self.view_widget.item
        if not isinstance(item, MPLPlot) or self._is_failed(item):
            return
        size = self.view_widget.image_pixel_size()
        if size is not None:
            item.size = size
        key = (
            item.selection,
            item.expr,
            item.dark,
            item.scale,
            item.size,
            item.axis_limits,
        )
        if key != self._image_rendered:
            self._image_rendered = key
            assert self.view_widget.image_widget is not None
            self.view_widget.image_widget.loading = True
            self.render_image(item)

    @textual.work(exclusive=True, thread=True)
    def render_plot(self, plot: Plotext) -> None:
        worker = textual.worker.get_current_worker()
        canvas = plot.make_plot()
        if worker.is_cancelled:
            return
        if canvas is None:
            # failed (empty/error message posted); allow a retry next request
            self._plot_rendered = None
            return
        self.call_from_thread(self.view_widget.plot_widget.update, canvas)

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
