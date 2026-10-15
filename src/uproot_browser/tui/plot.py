from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "functools",
    "operator",
    "rich",
    "rich.text",
    "textwrap",
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
import textwrap
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, runtime_checkable

import rich.text

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import NO_LIMITS, AxisLimits
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

    def request_render(self, view: ViewWidget) -> None:
        """Ask the app to render this item at the current size of the view."""

    def with_theme(self, *, dark: bool) -> PlotItem:
        """A copy of this item re-themed for a dark/light terminal."""

    def with_expr(self, expr: str) -> PlotItem:
        """A copy of this item with a new slicing expression."""

    def with_axis_limits(self, limits: AxisLimits) -> PlotItem:
        """A copy of this item with typed display limits."""

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


def render_canvas(
    item: Any, theme: str, *size: int, expr: str, limits: AxisLimits
) -> str:
    """Build the plotext canvas string for an item."""
    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.theme(theme)
    fig.plot_size(*size)
    uproot_browser.plot.plot(item, fig=fig, width=size[0] - 5, expr=expr, limits=limits)
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
        # Keep the exported tree view self-contained: analysis scripts should
        # only need uproot, awkward, numpy and hist installed.
        code += textwrap.dedent(f"""

            import awkward as ak
            import hist
            import numpy as np
            import uproot

            class TreeView:
                def __init__(self, selected):
                    self.selected = selected
                    tree = selected
                    while isinstance(tree, uproot.models.RNTuple.RField):
                        tree = tree.parent
                    if isinstance(tree, uproot.TBranch):
                        tree = tree.tree
                    self.tree = tree if isinstance(
                        tree, (uproot.TTree, uproot.behaviors.RNTuple.RNTuple)
                    ) else None

                def __getitem__(self, name):
                    if self.tree is None:
                        raise AttributeError("Selected object has no TTree/RNTuple")
                    member = self.tree[name]
                    return member.array() if hasattr(member, "array") else member

                def __getattr__(self, name):
                    return getattr(self.selected, name)

                def keys(self):
                    return () if self.tree is None else self.tree.keys()

            t = TreeView(item)
            bins = len(h.axes[0])
            result = {expr}
            if isinstance(result, hist.Hist):
                h = result
            elif isinstance(result, (ak.Array, np.ndarray)):
                values = ak.ravel(result)
                finite = values[np.isfinite(values)]
                if len(finite) == 0:
                    raise ValueError("Expression produced no finite values.")
                h = hist.numpy.histogram(finite, bins=bins, histogram=hist.Hist)
            else:
                raise RuntimeError(
                    "Expression must produce a hist.Hist or an awkward/numpy array, "
                    f"got {{type(result).__name__}}."
                )""")
    if limits != NO_LIMITS:
        code += textwrap.dedent(f"""

            import uproot_browser.plot
            import uproot_browser.plotext_compat
            from uproot_browser.axis import AxisLimits
            fig = uproot_browser.plotext_compat.make_figure()
            uproot_browser.plot.plot(item, fig=fig, width={width}, expr={expr!r}, limits={limits!r})
            print(fig.build())""")
    return code


# What to plot with plotext, and the size the view gives it
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    dark: bool
    app: Browser
    expr: str = ""
    size: tuple[int, int] | None = None
    axis_limits: AxisLimits = NO_LIMITS

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

    def dump_source(self) -> str:
        msg = selection_source(self.selection)
        selected = resolve_selection(self.upfile, self.selection)
        size = self.size or ()
        with contextlib.suppress(RuntimeError):
            msg += f"\n{make_dump(selected, *size, expr=self.expr, limits=self.axis_limits)}"
        return msg

    def dump_renderables(self) -> tuple[Any, ...]:
        # Render synchronously: the worker hands the finished canvas to the
        # widget, and the exit console has a different size than the widget.
        size = self.size or (100, 30)
        try:
            selected = resolve_selection(self.upfile, self.selection)
            canvas = render_canvas(
                selected, self.theme, *size, expr=self.expr, limits=self.axis_limits
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
            item = resolve_selection(self.upfile, self.selection)
            canvas = render_canvas(
                item, self.theme, *size, expr=self.expr, limits=self.axis_limits
            )
            return rich.text.Text.from_ansi(canvas)

        return run_posting_errors(self.app, build, self.selection)
