from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "functools",
    "operator",
    "rich",
    "rich.text",
    "textwrap",
    "uproot_browser.exceptions",
    "uproot_browser.plotext_compat",
    f"{__spec__.parent}.error",
    f"{__spec__.parent}.messages",
}

import contextlib
import dataclasses
import functools
import operator
import textwrap
import threading
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

import rich.text

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import NO_LIMITS, AxisLimits
from uproot_browser.exceptions import EmptyTreeError, ExpressionError

from .error import Error
from .messages import EmptyMessage, ErrorMessage, ExpressionErrorMessage, RequestPlot

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

    app: Browser
    selection: str
    y_selection: str
    expr: str

    def display(self, view: ViewWidget) -> None:
        """Show this item in the view and trigger its (threaded) render."""

    def request_render(self, view: ViewWidget) -> None:
        """Ask the app to render this item at the current size of the view."""

    def with_theme(self, *, dark: bool) -> PlotItem:
        """A copy of this item re-themed for a dark/light terminal."""

    def with_expr(self, expr: str) -> PlotItem:
        """A copy of this item with a new slicing expression."""

    def with_axis_limits(self, limits: AxisLimits) -> PlotItem:
        """A copy of this item with typed display limits."""

    def show_expression_error(self, view: ViewWidget) -> None:
        """Show in the view that this item's expression failed."""

    def dump_source(self) -> str:
        """Python source for Dump & Quit (appended after `uproot_file = ...`)."""

    def dump_renderables(self) -> tuple[Any, ...]:
        """Renderables to print above the source on Dump & Quit."""


def run_posting_errors(source: PlotItem, fn: Callable[[], T]) -> T | None:
    """Run ``fn``, posting a message to the app of ``source`` on failure.

    The selection travels with the error so Dump & Quit can show the branch.
    A failed expression keeps ``source`` editable instead of replacing it.
    """
    try:
        return fn()
    except ExpressionError as err:
        source.app.post_message(ExpressionErrorMessage(source, err.__cause__ or err))
    except EmptyTreeError:
        source.app.post_message(EmptyMessage())
    except Exception as err:  # noqa: BLE001
        source.app.post_message(
            ErrorMessage(Error(err, source.selection, source.y_selection))
        )
    return None


def selection_source(selection: str, y_selection: str = "") -> str:
    """The ``item = ...`` line naming the selected branch, or ``x_item`` and
    ``y_item`` for a 2D selection."""
    if not y_selection:
        return f'\nitem = uproot_file["{selection.lstrip("/")}"]'
    return (
        f'\nx_item = uproot_file["{selection.lstrip("/")}"]'
        f'\ny_item = uproot_file["{y_selection.lstrip("/")}"]'
    )


def resolve_selection(tree: Any, selection: str) -> Any:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    return functools.reduce(operator.getitem, selection.split(":"), tree)


def resolve_item(upfile: Any, selection: str, y_selection: str = "") -> Any:
    """The selected object, or a :class:`~uproot_browser.plot.BranchPair` for 2D."""
    item = resolve_selection(upfile, selection)
    if not y_selection:
        return item
    return uproot_browser.plot.BranchPair(item, resolve_selection(upfile, y_selection))


# Binds ``item`` for dumped code that needs it after ``x_item``/``y_item``
PAIR_ITEM_SOURCE = "import uproot_browser.plot\nitem = uproot_browser.plot.BranchPair(x_item, y_item)\n"


# plotext draws on one global figure, and a cancelled thread worker keeps
# running, so renders must not overlap.
_PLOTEXT_LOCK = threading.Lock()


def render_canvas(
    item: Any,
    theme: str,
    *size: int,
    expr: str,
    limits: AxisLimits,
    cache: uproot_browser.plot.ExprCache | None = None,
) -> str:
    """Build the plotext canvas string for an item."""
    with _PLOTEXT_LOCK:
        fig = uproot_browser.plotext_compat.make_figure()
        fig.clear()
        fig.theme(theme)
        fig.plot_size(*size)
        uproot_browser.plot.plot(
            item, fig=fig, width=size[0] - 5, expr=expr, limits=limits, cache=cache
        )
        return str(fig.build())


def make_dump(
    item: Any, *size: int, expr: str = "", limits: AxisLimits = NO_LIMITS
) -> str:
    """Standalone Python source rebuilding the plotted histogram as ``h``.

    Typed axis limits are a display setting, not part of ``h``, so they add a
    block that draws the plot the way the TUI did.
    """
    width = size[0] - 5 if size else 100
    code = uproot_browser.plot.dump(item, width=width)
    if expr:
        # Self-contained: the exported script must not need uproot_browser.
        code += f"\n\n{uproot_browser.plot.dump_expr(item, expr)}"
    if limits != NO_LIMITS:
        if isinstance(item, uproot_browser.plot.BranchPair):
            code += f"\n\n{PAIR_ITEM_SOURCE}"
        code += textwrap.dedent(f"""

            import uproot_browser.plot
            import uproot_browser.plotext_compat
            from uproot_browser.axis import AxisLimits
            fig = uproot_browser.plotext_compat.make_figure()
            uproot_browser.plot.draw_hist(fig, item, h, limits={limits!r})
            print(fig.build())""")
    return code


# What to plot with plotext, and the size the view gives it
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    dark: bool
    app: Browser
    y_selection: str = ""
    expr: str = ""
    size: tuple[int, int] | None = None
    axis_limits: AxisLimits = NO_LIMITS
    # shared by reference across copies, so a redraw reuses the expression result
    cache: uproot_browser.plot.ExprCache = dataclasses.field(
        default_factory=uproot_browser.plot.ExprCache
    )

    @property
    def theme(self) -> str:
        return "uproot_dark" if self.dark else "uproot_light"

    def display(self, view: ViewWidget) -> None:
        view.current = "plot-window"
        # After the refresh, so the request measures the widget that is laid out
        view.call_after_refresh(self.request_render, view)

    def request_render(self, view: ViewWidget) -> None:
        view.post_message(RequestPlot())

    def with_theme(self, *, dark: bool) -> Plotext:
        return dataclasses.replace(self, dark=dark)

    def with_expr(self, expr: str) -> Plotext:
        return dataclasses.replace(self, expr=expr)

    def with_axis_limits(self, limits: AxisLimits) -> Plotext:
        return dataclasses.replace(self, axis_limits=limits)

    def show_expression_error(self, view: ViewWidget) -> None:
        view.plot_widget.update(
            "Expression could not be plotted. Edit the expression and try again."
        )

    def dump_source(self) -> str:
        msg = selection_source(self.selection, self.y_selection)
        selected = resolve_item(self.upfile, self.selection, self.y_selection)
        size = self.size or ()
        with contextlib.suppress(RuntimeError):
            msg += f"\n{make_dump(selected, *size, expr=self.expr, limits=self.axis_limits)}"
        return msg

    def dump_renderables(self) -> tuple[Any, ...]:
        # Render synchronously: the worker hands the finished canvas to the
        # widget, and the exit console has a different size than the widget.
        size = self.size or (100, 30)
        try:
            selected = resolve_item(self.upfile, self.selection, self.y_selection)
            canvas = render_canvas(
                selected,
                self.theme,
                *size,
                expr=self.expr,
                limits=self.axis_limits,
                cache=self.cache,
            )
        except Exception:  # noqa: BLE001
            # The render worker can still be in flight, so this item can be one
            # that fails. Quit with the source only instead of crashing.
            return ()
        return (rich.text.Text.from_ansi(canvas),)

    def make_plot(self) -> rich.text.Text | None:
        size = self.size
        assert size

        def build() -> rich.text.Text:
            item = resolve_item(self.upfile, self.selection, self.y_selection)
            canvas = render_canvas(
                item,
                self.theme,
                *size,
                expr=self.expr,
                limits=self.axis_limits,
                cache=self.cache,
            )
            return rich.text.Text.from_ansi(canvas)

        return run_posting_errors(self, build)
