from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "functools",
    "operator",
    "rich",
    "rich.text",
    "uproot_browser.exceptions",
    "uproot_browser.plot",
    "uproot_browser.plotext_compat",
    f"{__spec__.parent}.error",
    f"{__spec__.parent}.messages",
}

import contextlib
import dataclasses
import functools
import operator
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

import rich.text

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.exceptions import EmptyTreeError

from .error import Error
from .messages import EmptyMessage, ErrorMessage, RequestPlot

if TYPE_CHECKING:
    from collections.abc import Callable

    from .browser import Browser
    from .viewer import ViewWidget

T = TypeVar("T")


@runtime_checkable
class PlotItem(Protocol):
    """The interface a ViewWidget rendering mode implements.

    Both `Plotext` (text plots) and `MPLPlot` (image plots) satisfy this;
    a new rendering mode only needs to provide these members plus a
    factory in `Browser` and a window in `ViewWidget`.
    """

    expr: str

    def display(self, view: ViewWidget) -> None:
        """Show this item in the view and trigger its (threaded) render."""

    def handle_resize(self, view: ViewWidget) -> None:
        """React to the view being resized (no-op if handled elsewhere)."""

    def with_theme(self, *, dark: bool) -> PlotItem:
        """A copy of this item re-themed for a dark/light terminal."""

    def with_expr(self, expr: str) -> PlotItem:
        """A copy of this item with a new slicing expression."""

    def dump_source(self) -> str:
        """Python source for Dump & Quit (appended after `uproot_file = ...`)."""

    def dump_renderables(self) -> tuple[Any, ...]:
        """Renderables to print above the source on Dump & Quit."""


def run_posting_errors(
    app: Browser, fn: Callable[[], T], selection: str = ""
) -> T | None:
    """Run ``fn``, posting an Empty/Error message to the app on failure.

    ``selection`` travels with the error so Dump & Quit can show the branch.
    """
    try:
        return fn()
    except EmptyTreeError:
        app.post_message(EmptyMessage())
        return None
    except Exception as err:  # noqa: BLE001
        app.post_message(ErrorMessage(Error(err, selection)))
        return None


def selection_source(selection: str) -> str:
    """The ``item = ...`` line naming the selected branch."""
    return f'\nitem = uproot_file["{selection.lstrip("/")}"]'


def resolve_selection(tree: Any, selection: str) -> Any:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    return functools.reduce(operator.getitem, selection.split(":"), tree)


def render_canvas(item: Any, theme: str, *size: int, expr: str) -> str:
    """Build the plotext canvas string for an item."""
    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.theme(theme)
    fig.plot_size(*size)
    uproot_browser.plot.plot(item, fig=fig, width=size[0] - 5, expr=expr)
    return str(fig.build())


def make_dump(item: Any, *size: int, expr: str = "") -> str:
    """Standalone Python source rebuilding the plotted histogram as ``h``."""
    width = size[0] - 5 if size else 100
    code = uproot_browser.plot.dump(item, width=width)
    if expr:
        code += f"\nh = {expr}"
    return code


# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    dark: bool
    app: Browser
    expr: str = ""
    size: tuple[int, int] | None = None
    previous: rich.text.Text | None = None
    old_expr: str = ""

    @property
    def theme(self) -> str:
        return "uproot_dark" if self.dark else "uproot_light"

    def display(self, view: ViewWidget) -> None:
        view.plot_widget.update(self)
        view.current = "plot-window"

    def handle_resize(self, view: ViewWidget) -> None:
        """No-op: the Static re-renders us, and __rich_console__ re-plots."""

    def with_theme(self, *, dark: bool) -> Plotext:
        # Drop the cached canvas so the plot re-renders in the new theme.
        return dataclasses.replace(self, dark=dark, previous=None)

    def with_expr(self, expr: str) -> Plotext:
        return dataclasses.replace(self, expr=expr)

    def dump_source(self) -> str:
        msg = selection_source(self.selection)
        selected = resolve_selection(self.upfile, self.selection)
        size = self.size or ()
        with contextlib.suppress(RuntimeError):
            msg += f"\n{make_dump(selected, *size, expr=self.expr)}"
        return msg

    def dump_renderables(self) -> tuple[Any, ...]:
        return (self,)

    def make_plot(self) -> Plotext | None:
        size = self.size
        assert size

        def build() -> Plotext:
            item = resolve_selection(self.upfile, self.selection)
            canvas = render_canvas(item, self.theme, *size, expr=self.expr)
            return dataclasses.replace(self, previous=rich.text.Text.from_ansi(canvas))

        return run_posting_errors(self.app, build, self.selection)

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width
        height = options.height or console.height

        if (
            self.size
            and (width, height) == self.size
            and self.previous is not None
            and self.old_expr == self.expr
        ):
            yield self.previous

        else:
            self.size = (width, height)
            self.previous = rich.text.Text("... plotting ...")
            self.old_expr = self.expr
            yield self.previous
            self.app.post_message(RequestPlot(self))
