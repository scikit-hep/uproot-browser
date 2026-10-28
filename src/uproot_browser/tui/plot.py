from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "rich",
    "rich.text",
    "uproot_browser.exceptions",
    "uproot_browser.plotext_compat",
    f"{__spec__.parent}.error",
    f"{__spec__.parent}.messages",
}

import contextlib
import dataclasses
import threading
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

import rich.text

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import NO_LIMITS, AxisLimits
from uproot_browser.exceptions import EmptyTreeError, ExpressionError
from uproot_browser.nodes import Root

from .error import Error
from .messages import EmptyMessage, ErrorMessage, ExpressionErrorMessage, RequestPlot

if TYPE_CHECKING:
    from collections.abc import Callable

    from uproot_browser.nodes import Node

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

    def dump_source(self, *, file_var: str = "uproot_file") -> str:
        """Python source for Dump & Quit (appended after the ``item = ...`` lines)."""

    def dump_renderables(self) -> tuple[Any, ...]:
        """Renderables to print above the source on Dump & Quit."""


def run_posting_errors(source: PlotItem, fn: Callable[[], T]) -> T | None:
    """Run ``fn``, posting a message to the app of ``source`` on failure.

    The selection travels with the error so Dump & Quit can show the branch.
    A failed expression keeps ``source`` editable instead of replacing it.
    The app drops messages from a render that another item has superseded.
    """
    try:
        return fn()
    except ExpressionError as err:
        source.app.post_message(ExpressionErrorMessage(source, err.__cause__ or err))
    except EmptyTreeError:
        source.app.post_message(EmptyMessage(source))
    except Exception as err:  # noqa: BLE001
        source.app.post_message(
            ErrorMessage(Error(err, source.selection, source.y_selection), source)
        )
    return None


def dump_header(root: Node, selection: str, y_selection: str = "") -> tuple[str, str]:
    """
    The lines of Dump & Quit that open the file(s) and bind ``item`` (or
    ``x_item`` and ``y_item``), and the variable the x file is bound to.
    """
    file_var = "uproot_file"
    try:
        if not selection:
            return root.root.open_source(file_var), file_var
        x = root.resolve(selection)
        if not y_selection:
            lines = [x.root.open_source(file_var), x.bind_source("item")]
            return "\n".join(lines), file_var
        y = root.resolve(y_selection)
        if x.root is y.root:
            lines = [
                x.root.open_source(file_var),
                x.bind_source("x_item"),
                y.bind_source("y_item"),
            ]
            return "\n".join(lines), file_var
    except LookupError:
        # Not opened from a file, or a path through a leaf (which produced the
        # traceback): name the selection from the paths alone
        return _path_header(root, file_var, selection, y_selection), file_var
    # Two files: open both, but write the shared import lines once
    x_open = x.root.open_source("x_file").splitlines()
    y_open = [
        line for line in y.root.open_source("y_file").splitlines() if line not in x_open
    ]
    lines = [
        *x_open,
        *y_open,
        x.bind_source("x_item", "x_file"),
        y.bind_source("y_item", "y_file"),
    ]
    return "\n".join(lines), "x_file"


def _path_header(root: Node, file_var: str, selection: str, y_selection: str) -> str:
    if not isinstance(root, Root):
        return ""
    binds = [("x_item", selection), ("y_item", y_selection)] if y_selection else []
    lines = [root.open_source(file_var)]
    for var, path in binds or [("item", selection)]:
        keys = path.strip("/").split("/")
        lines.append(f"{var} = {root.lookup_source(file_var, keys)}")
    return "\n".join(lines)


def resolve_item(root: Node, selection: str, y_selection: str = "") -> Node:
    """The selected node, or a :class:`~uproot_browser.nodes.Pair` for 2D."""
    item = root.resolve(selection)
    if not y_selection:
        return item
    return uproot_browser.plot.BranchPair(item, root.resolve(y_selection))


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
    item: Any,
    *size: int,
    expr: str = "",
    limits: AxisLimits = NO_LIMITS,
    image: bool = False,
    file_var: str = "uproot_file",
) -> str:
    """Standalone Python source rebuilding the plotted histogram as ``h`` and
    drawing it the way the TUI did. It never imports uproot_browser.
    """
    # plot_mpl builds with the to_histogram default bins
    width = 50 if image else (size[0] - 5 if size else 100)
    code = uproot_browser.plot.dump(item, width=width)
    if expr:
        code += f"\n\n{uproot_browser.plot.dump_expr(item, expr, file_var=file_var)}"
    draw = uproot_browser.plot.dump_mpl if image else uproot_browser.plot.dump_plotext
    return f"{code}\n\n{draw(item, limits=limits)}"


# What to plot with plotext, and the size the view gives it
@dataclasses.dataclass
class Plotext:
    root: Node
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

    def dump_source(self, *, file_var: str = "uproot_file") -> str:
        selected = resolve_item(self.root, self.selection, self.y_selection)
        size = self.size or ()
        with contextlib.suppress(RuntimeError):
            return f"\n{make_dump(selected, *size, expr=self.expr, limits=self.axis_limits, file_var=file_var)}"
        return ""

    def dump_renderables(self) -> tuple[Any, ...]:
        # Render synchronously: the worker hands the finished canvas to the
        # widget, and the exit console has a different size than the widget.
        size = self.size or (100, 30)
        try:
            selected = resolve_item(self.root, self.selection, self.y_selection)
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
            item = resolve_item(self.root, self.selection, self.y_selection)
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
