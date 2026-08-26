from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"  # pylint: disable=redefined-builtin

import contextlib
import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

import plotext as plt
import rich.syntax
import textual.app
import textual.binding
import textual.containers
import textual.events
import textual.lazy
import textual.widgets
import textual.worker
from textual.reactive import var

from .error import Error
from .header import Header
from .help import HelpScreen
from .image_plot import MPLPlot
from .jump import JumpScreen
from .left_panel import UprootTree
from .plot import Plotext, apply_selection, make_dump
from .tools import Info, Tools
from .viewer import ViewWidget

# Registered under our own names to avoid overriding plotext's built-in themes
light_background = 0xF5, 0xF5, 0xF5
plt.add_theme(
    "uproot_light", canvas=light_background, text=((0, 0, 0), light_background)
)

dark_background = 0x1E, 0x1E, 0x1E
dark_text = 0xFF, 0xA6, 0x2B
plt.add_theme("uproot_dark", canvas=dark_background, text=(dark_text, dark_background))

if TYPE_CHECKING:
    from .messages import (
        ErrorMessage,
        ImageScaleChanged,
        RequestPlot,
        UprootSelected,
    )


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

    def __init__(
        self, path: str, *, image: bool = False, image_scale: float = 1.5, **kwargs: Any
    ) -> None:
        self.path = path
        self.image = image
        self.image_scale = image_scale
        self._image_rendered: MPLPlot | None = None
        super().__init__(**kwargs)

        self.view_widget = ViewWidget(id="plot-view", image=image)

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
        self.push_screen(JumpScreen(tree.all_entries()), self._on_jumped)

    def _on_jumped(self, path: str | None) -> None:
        if path is None:
            return
        self.query_one("#left-view", textual.widgets.TabbedContent).active = "tree-tab"
        self.query_one("#tree-view", UprootTree).select_path(path)

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def action_quit_with_dump(self) -> None:
        """Dump the current state of the application."""

        msg = f'\nimport uproot\nuproot_file = uproot.open("{self.path}")'

        items: list[Plotext | Error] = []
        if isinstance(self.view_widget.item, Error):
            items = [self.view_widget.item]
        elif isinstance(self.view_widget.item, Plotext):
            plotext = self.view_widget.item
            msg += f'\nitem = uproot_file["{plotext.selection.lstrip("/")}"]'
            *_, selected = apply_selection(plotext.upfile, plotext.selection.split(":"))
            size = plotext.size or ()
            with contextlib.suppress(RuntimeError):
                msg += f"\n{make_dump(selected, *size, expr=plotext.expr)}"
            items = [plotext]
        elif isinstance(self.view_widget.item, MPLPlot):
            mpl_item = self.view_widget.item
            msg += f'\nitem = uproot_file["{mpl_item.selection.lstrip("/")}"]'
            expr_arg = f", expr={mpl_item.expr!r}" if mpl_item.expr else ""
            msg += f"\n\nimport matplotlib.pyplot as plt\nimport uproot_browser.plot_mpl\n\nuproot_browser.plot_mpl.plot(item{expr_arg})\nplt.show()"

        theme = "ansi_dark" if self.current_theme.dark else "ansi_light"

        results = rich.console.Group(
            *items,
            rich.syntax.Syntax(f"\n{msg}\n", "python", theme=theme),
        )

        self.exit(message=results)

    def watch_theme(self) -> None:
        if isinstance(self.view_widget.item, Plotext):
            theme = "uproot_dark" if self.current_theme.dark else "uproot_light"
            # Reassign (rather than mutate) so that watchers fire and the
            # cached canvas is invalidated.
            self.view_widget.item = dataclasses.replace(
                self.view_widget.item, theme=theme, previous=None
            )
        elif isinstance(self.view_widget.item, MPLPlot):
            self.view_widget.item = dataclasses.replace(
                self.view_widget.item, dark=self.current_theme.dark
            )

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        self.view_widget.plot_input.value = ""
        if self.image:
            self.view_widget.item = MPLPlot(
                message.upfile,
                message.path,
                self.current_theme.dark,
                self,
                scale=self.image_scale,
            )
        else:
            theme = "uproot_dark" if self.current_theme.dark else "uproot_light"
            self.view_widget.item = Plotext(message.upfile, message.path, theme, self)

    def on_empty_message(self) -> None:
        self.view_widget.item = None

    def on_error_message(self, message: ErrorMessage) -> None:
        self.view_widget.item = message.err

    def on_request_plot(self, message: RequestPlot) -> None:
        self.render_plot(message.plot)

    def on_image_scale_changed(self, message: ImageScaleChanged) -> None:
        self.image_scale = message.scale
        item = self.view_widget.item
        if isinstance(item, MPLPlot) and item.scale != message.scale:
            self.view_widget.item = dataclasses.replace(item, scale=message.scale)

    def on_request_image(self) -> None:
        """Single render trigger: assigning an MPLPlot (or a resize) lands here."""
        item = self.view_widget.item
        if not isinstance(item, MPLPlot):
            return
        size = self.view_widget.image_pixel_size()
        if size is not None:
            item.size = size
        if item != self._image_rendered:
            self._image_rendered = dataclasses.replace(item)
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
