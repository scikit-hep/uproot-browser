from __future__ import annotations

__lazy_modules__ = {
    "dataclasses",
    "rich.markup",
    "rich.syntax",
    "textual.containers",
    "textual.events",
    "textual.lazy",
    "textual.widgets",
    "textual.worker",
    "uproot_browser.exceptions",
    "uproot_browser.tui.error",
    "uproot_browser.tui.help",
    "uproot_browser.tui.image_plot",
    "uproot_browser.tui.jump",
    "uproot_browser.tui.left_panel",
    "uproot_browser.tui.plot",
    "uproot_browser.tui.right_panel",
    "uproot_browser.tui.splitter",
    "uproot_browser.tui.status",
    "uproot_browser.tui.tools",
    "uproot_browser.tui.viewer",
}

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

import rich.markup
import rich.syntax
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
from uproot_browser.plotext_compat import add_theme
from uproot_browser.tui.error import Error
from uproot_browser.tui.help import HelpScreen
from uproot_browser.tui.image_plot import MPLPlot
from uproot_browser.tui.jump import Candidate, JumpScreen
from uproot_browser.tui.left_panel import UprootTree
from uproot_browser.tui.plot import Plotext, PlotItem, dump_header
from uproot_browser.tui.right_panel import RightPanel
from uproot_browser.tui.splitter import Splitter
from uproot_browser.tui.status import StatusBar
from uproot_browser.tui.theme import DARK_BACKGROUND, DARK_TEXT, LIGHT_BACKGROUND
from uproot_browser.tui.tools import Info
from uproot_browser.tui.viewer import ViewWidget

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
    from collections.abc import Iterator

    from textual.screen import Screen

    from uproot_browser.nodes import Node
    from uproot_browser.tui.messages import (
        EmptyMessage,
        ErrorMessage,
        ExpressionErrorMessage,
        UprootSelected,
    )


def _plot_name(item: PlotItem) -> str:
    x, y = item.selection.removeprefix("/"), item.y_selection.removeprefix("/")
    # The displayed root itself (file.root:key) has an empty selection
    return (
        f"{y} vs {x}" if y else x or item.root.path.removeprefix("/") or item.root.name
    )


def _plot_label(item: PlotItem) -> str:
    return f"Plotting {_plot_name(item)}"


class Browser(textual.app.App[None]):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    TITLE = "uproot-browser"
    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("b", "toggle_left_panel", "Tree"),
        textual.binding.Binding("t", "toggle_right_panel", "Tools"),
        textual.binding.Binding("e", "toggle_entry_box", "Expression"),
        textual.binding.Binding("/", "jump", "Jump"),
        textual.binding.Binding("q", "quit", "Quit"),
        textual.binding.Binding("d", "quit_with_dump", "Dump & Quit"),
        textual.binding.Binding("f1", "help", "Help"),
        textual.binding.Binding("?", "help", "Help", show=False),
    ]

    show_left_panel = var(True)
    show_right_panel = var(True)
    show_entry_box = var(False)
    image_scale = var(1.5)
    axis_limits = var(NO_LIMITS)

    def __init__(
        self,
        path: str,
        *,
        root: Node | None = None,
        image: bool = False,
        image_scale: float = 1.5,
        **kwargs: Any,
    ) -> None:
        self.path = path
        self._root_node = root
        self.image = image
        self._plot_rendered: tuple[Any, ...] | None = None
        self._image_rendered: tuple[Any, ...] | None = None
        # re-rendering a failed expression would only fail again
        self._failed_item: PlotItem | None = None
        super().__init__(**kwargs)
        self.sub_title = path

        self.view_widget = ViewWidget(id="plot-view", image=image)
        self.status = StatusBar(id="status")
        self.set_reactive(Browser.image_scale, image_scale)

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield textual.widgets.Header()
        with textual.containers.Horizontal():
            # left_panel
            with textual.widgets.TabbedContent(id="left-view"):
                with textual.widgets.TabPane("Tree", id="tree-tab"):
                    yield UprootTree(self.path, root=self._root_node, id="tree-view")
                with textual.widgets.TabPane("Info"):
                    yield textual.lazy.Lazy(Info())
            yield Splitter("#left-view", grow_left=True, id="left-splitter")
            # main_panel
            yield self.view_widget
            yield Splitter("#right-panel", grow_left=False, id="right-splitter")
            yield RightPanel(
                image=self.image, image_scale=self.image_scale, id="right-panel"
            )

        yield textual.widgets.Footer()
        yield self.status

    def on_mount(self, _event: textual.events.Mount) -> None:
        tree = self.query_one("#tree-view", UprootTree)
        tree.focus()
        self.watch(tree, "count", self.status.show_count)
        self.watch(self.view_widget, "item", self.refresh_bindings, init=False)

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:  # noqa: ARG002
        if action == "toggle_entry_box":
            # The entry box is in the plot window, which shows only with a plot.
            # The footer asks before the mount, and a read of the item then
            # runs its watcher (Textual 5.0), which needs the children.
            view = self.view_widget
            return (view.is_mounted and isinstance(view.item, PlotItem)) or None
        return True

    def watch_show_left_panel(self, show: bool) -> None:  # noqa: FBT001
        """Called when the left panel visibility changes."""
        self.set_class(not show, "-hide-left-panel")

    def get_system_commands(
        self, screen: Screen[Any]
    ) -> Iterator[textual.app.SystemCommand]:
        yield textual.app.SystemCommand(
            "Help", "Show the uproot-browser help", self.action_help
        )
        yield from super().get_system_commands(screen)

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_jump(self) -> None:
        """Open the fuzzy finder to jump to a branch/field."""
        tree = self.query_one("#tree-view", UprootTree)
        tree.request_jump_candidates(self._show_jump)

    def _show_jump(self, candidates: list[Candidate]) -> None:
        self.push_screen(JumpScreen(candidates), self._on_jumped)

    def _on_jumped(self, path: str | None) -> None:
        if path is None:
            return
        self.query_one("#left-view", textual.widgets.TabbedContent).active = "tree-tab"
        self.query_one("#tree-view", UprootTree).select_path(path)

    def action_toggle_left_panel(self) -> None:
        """Toggle the tree and info panel."""
        self.show_left_panel = not self.show_left_panel

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

        item = self.view_widget.item
        root = self.query_one("#tree-view", UprootTree).root_node
        selection, y_selection = "", ""
        if isinstance(item, (Error, PlotItem)):
            selection, y_selection = item.selection, item.y_selection
        header, file_var = dump_header(root, selection, y_selection)
        msg = f"\n{header}"
        if isinstance(item, Error):
            return msg, [item]
        if not isinstance(item, PlotItem):
            return msg, []
        return msg + item.dump_source(file_var=file_var), list(item.dump_renderables())

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
                message.root,
                message.path,
                dark=dark,
                app=self,
                y_selection=message.y_path,
                scale=self.image_scale,
            )
            if self.image
            else Plotext(
                message.root,
                message.path,
                dark=dark,
                app=self,
                y_selection=message.y_path,
            )
        )

    def _render_failed(self, source: PlotItem) -> bool:
        """Is a failure report about the current item? Allow a retry if so.

        A cancelled render worker runs on; its report is dropped. The retry
        flag is reset here, in message order with the render requests, and
        not from the worker thread. A report during shutdown is dropped too,
        as the view's children can be gone.
        """
        if self._exit or not self.is_running or self.view_widget.item is not source:
            return False
        self._plot_rendered = None
        self._image_rendered = None
        return True

    def on_empty_message(self, message: EmptyMessage) -> None:
        if self._render_failed(message.source):
            self.view_widget.item = None
            self.notify(
                rich.markup.escape(
                    f"{_plot_name(message.source)} has no finite values to plot"
                ),
                severity="warning",
            )

    def on_error_message(self, message: ErrorMessage) -> None:
        if self._render_failed(message.source):
            self.view_widget.item = message.err

    def on_expression_error_message(self, message: ExpressionErrorMessage) -> None:
        item, error = message.source, message.error
        if not self._render_failed(item):
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
            # Not laid out yet, and no resize will follow: ask again later
            self.view_widget.call_after_refresh(self.view_widget.request_render)
            return
        item.size = (size.width, size.height)
        key = (
            item.selection,
            item.y_selection,
            item.expr,
            item.dark,
            item.size,
            item.axis_limits,
        )
        if key != self._plot_rendered:
            self._plot_rendered = key
            self.render_plot(item)

    def on_right_panel_limits_changed(self, message: RightPanel.LimitsChanged) -> None:
        self.axis_limits = message.limits

    def on_right_panel_scale_changed(self, message: RightPanel.ScaleChanged) -> None:
        self.image_scale = message.scale

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
            item.y_selection,
            item.expr,
            item.dark,
            item.scale,
            item.size,
            item.axis_limits,
        )
        if key != self._image_rendered:
            self._image_rendered = key
            self.render_image(item)

    @textual.work(exclusive=True, thread=True)
    def render_plot(self, plot: Plotext) -> None:
        worker = textual.worker.get_current_worker()
        with self.status.running(_plot_label(plot)):
            canvas = plot.make_plot()
        if worker.is_cancelled:
            return
        if canvas is not None:
            self.call_from_thread(self.view_widget.plot_widget.update, canvas)

    @textual.work(exclusive=True, thread=True)
    def render_image(self, plot: MPLPlot) -> None:
        worker = textual.worker.get_current_worker()
        with self.status.running(_plot_label(plot)):
            image = plot.make_image()
        if worker.is_cancelled:
            return
        self.call_from_thread(self.view_widget.update_image, image)


if __name__ in {"<run_path>", "__main__"}:
    fname = "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    app = Browser(path=fname)
    app.run()
