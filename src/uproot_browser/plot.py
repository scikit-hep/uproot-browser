"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

__lazy_modules__ = {
    "ast",
    "awkward",
    "boost_histogram",
    "hist",
    "math",
    "numpy",
    "textwrap",
    "uproot_browser.backends",
    "uproot_browser.exceptions",
    "uproot_browser.nodes",
}

import ast
import dataclasses
import math
import textwrap
from typing import TYPE_CHECKING, Any

import awkward as ak
import boost_histogram as bh
import hist
import numpy as np

from uproot_browser.axis import NO_LIMITS, AxisLimits, AxisRange
from uproot_browser.backends import as_node
from uproot_browser.exceptions import ExpressionError
from uproot_browser.nodes import Column, FailedNode, Pair, Plottable, fill_finite
from uproot_browser.plotext_compat import PLOTEXT_6

if TYPE_CHECKING:
    from uproot_browser.plotext_compat import PlotextFigure


def make_hist_title(item: Any, histogram: hist.Hist[Any]) -> str:
    name = as_node(item).name
    # counts() equals values() for plain storage, but gives the entry count for
    # Mean storage (TProfile) and the effective entries for Weight storage.
    inner_sum = float(np.sum(histogram.counts()))
    full_sum = float(np.sum(histogram.counts(flow=True)))

    if math.isclose(inner_sum, full_sum):
        return f"{name} -- Entries: {inner_sum:g}"

    return f"{name} -- Entries: {inner_sum:g} ({full_sum:g} with flow)"


def plottable_node(item: Any) -> Plottable:
    """The node for ``item``, which must be plottable; a failed entry re-raises."""
    node = as_node(item)
    if isinstance(node, FailedNode):
        raise node.exception
    if not isinstance(node, Plottable):
        msg = f"This object ({type(node.item)}) is not plottable yet"
        raise RuntimeError(msg)  # noqa: TRY004
    return node


def to_histogram(item: Any, *, bins: int = 50) -> hist.Hist[Any]:
    """
    Build the histogram that :func:`plot` draws for this object.
    Each :class:`~uproot_browser.nodes.Plottable` implements it.
    """
    return plottable_node(item).to_histogram(bins=bins)


def BranchPair(x: Any, y: Any) -> Pair:  # noqa: N802
    """Two columns (raw objects or nodes) filled together into a 2D histogram."""
    x_node, y_node = as_node(x), as_node(y)
    for node in (x_node, y_node):
        if not isinstance(node, Column):
            msg = f"{node.name} does not hold numbers for a 2D plot"
            raise TypeError(msg)
    assert isinstance(x_node, Column)
    assert isinstance(y_node, Column)
    return Pair(x_node, y_node)


def containing_tree(item: Any) -> Any:
    """The TTree/RNTuple (raw object) that ``item`` lives in, else None."""
    tree = as_node(item).data_tree()
    return None if tree is None else tree.item


@dataclasses.dataclass(slots=True)
class ExprCache:
    """One-slot cache of an expression's raw result, keyed on the expression.

    Plot items share one by reference across copies, so a redraw (resize,
    theme, limits) does not read the tree again. The single attribute keeps a
    write atomic for concurrent render workers.
    """

    entry: tuple[str, Any] | None = None


def _uses_h(expr: str) -> bool:
    """Does the expression read ``h``, which changes with the bin count?"""
    return any(
        isinstance(node, ast.Name) and node.id == "h"
        for node in ast.walk(ast.parse(expr, mode="eval"))
    )


def evaluate_expr(expr: str, namespace: dict[str, Any]) -> Any:
    # pylint: disable-next=eval-used
    return eval(expr, namespace)


def apply_expr(
    histogram: hist.Hist[Any], expr: str, item: Any, *, cache: ExprCache | None = None
) -> hist.Hist[Any]:
    """
    Evaluate with ``h`` as the histogram and ``tree`` as the containing
    TTree/RNTuple (only when there is one), using uproot's normal API, e.g.
    ``tree["fPx"].array()[tree["fPy"].array() < 0]``. An array result is
    histogrammed with the bin count of ``h``.

    With a ``cache``, the result of an expression that does not use ``h`` is
    kept and only rebinned on later calls.

    Any failure is raised as :class:`ExpressionError` from the original error.
    """
    if not expr:
        return histogram
    try:
        if cache is not None and cache.entry is not None and cache.entry[0] == expr:
            result = cache.entry[1]
        else:
            namespace = {"h": histogram, "ak": ak, "hist": hist, "np": np}
            tree = as_node(item).data_tree()
            if tree is not None:
                namespace["tree"] = tree.item
            result = evaluate_expr(expr, namespace)
            if cache is not None and not _uses_h(expr):
                cache.entry = (expr, result)
        return _result_to_histogram(result, bins=len(histogram.axes[0]))
    except Exception as err:
        raise ExpressionError(str(err)) from err


def _result_to_histogram(result: Any, *, bins: int) -> hist.Hist[Any]:
    """Coerce an expression result into a hist.Hist. Mirrored in :func:`dump_expr`."""
    if hasattr(result, "to_hist"):
        result = result.to_hist()
    if isinstance(result, hist.Hist):
        return result
    if isinstance(result, bh.Histogram):
        return hist.Hist(result)
    if isinstance(result, (ak.Array, np.ndarray)):
        return fill_finite(
            result,
            bins=bins,
            empty_msg="Expression produced no finite values.",
        )
    msg = (
        "Expression must produce a hist.Hist or an awkward/numpy array, "
        f"got {type(result).__name__}."
    )
    raise RuntimeError(msg)


def dump_expr(item: Any, expr: str, *, file_var: str = "uproot_file") -> str:
    """Self-contained source that applies ``expr`` to ``h`` like :func:`apply_expr`."""
    tree_source = as_node(item).data_tree_source("item", file_var)
    tree_line = "" if tree_source is None else f"tree = {tree_source}\n\n"
    imports = textwrap.dedent("""\
        import awkward as ak
        import boost_histogram as bh
        import hist
        import numpy as np

        """)
    body = textwrap.dedent(f"""\
        result = {expr}
        if hasattr(result, "to_hist"):
            result = result.to_hist()
        if isinstance(result, bh.Histogram) and not isinstance(result, hist.Hist):
            result = hist.Hist(result)
        if isinstance(result, (ak.Array, np.ndarray)):
            if isinstance(result, np.ndarray) and result.dtype == object:
                flat = np.concatenate([np.ravel(x) for x in result]) if len(result) else result
                result = ak.from_iter(result) if flat.dtype == object else flat
            values = ak.ravel(result)
            finite = values[np.isfinite(values)]
            if len(finite) < 1:
                msg = "Expression produced no finite values."
                raise ValueError(msg)
            result = hist.numpy.histogram(finite, bins=len(h.axes[0]), histogram=hist.Hist)
        if not isinstance(result, hist.Hist):
            msg = f"Expression must produce a hist.Hist or an awkward/numpy array, got {{type(result).__name__}}."
            raise TypeError(msg)
        h = result""")
    return imports + tree_line + body


def _bin_ticks(
    axis: Any, visible: AxisRange = (None, None), count: int = 5
) -> tuple[list[int], list[str]]:
    """Tick positions (bin indices) and labels spread over the visible index range."""
    lower, upper = visible
    first = 0 if lower is None else max(0, math.ceil(lower))
    last = len(axis) - 1 if upper is None else min(len(axis) - 1, math.floor(upper))
    positions = np.unique(
        np.linspace(first, last, min(count, last - first + 1)).round().astype(int)
    )
    return positions.tolist(), [f"{axis.centers[i]:g}" for i in positions]


def _index_range(axis: Any, lim: AxisRange) -> AxisRange:
    """Map a data-unit range onto bin-index coordinates (bar i spans i±0.5)."""
    positions = np.arange(len(axis) + 1) - 0.5
    return tuple(  # type: ignore[return-value]
        None if v is None else float(np.interp(v, axis.edges, positions)) for v in lim
    )


def _set_lim(fig: PlotextFigure, axis: str, lim: AxisRange) -> None:
    # lim(None, None) would undo an earlier default, so only set typed limits
    if lim != (None, None):
        fig.ruler(axis).lim(*lim)


def _draw_hist_2d(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    xaxis, yaxis = histogram.axes
    values = histogram.values().astype(float)
    # heatmap rows draw top-to-bottom; flip so y increases upward
    fig.draw(fig.heatmap(values.T[::-1].tolist(), map="viridis", fill=True))
    # The heatmap draws against bin indices, so limits must be mapped too
    xlim, ylim = _index_range(xaxis, limits.x), _index_range(yaxis, limits.y)
    fig.ruler("x").ticks(*_bin_ticks(xaxis, xlim))
    fig.ruler("y").ticks(*_bin_ticks(yaxis, ylim))
    _set_lim(fig, "x", xlim)
    _set_lim(fig, "y", ylim)
    fig.label(xaxis.label, axis="x")
    fig.label(yaxis.label, axis="y")
    fig.title(make_hist_title(tree, histogram))


def _collapses_in_float32(lower: float, upper: float) -> bool:
    """Is the range too narrow to survive plotext's internal float32 rescale?"""
    with np.errstate(over="ignore"):
        low32, high32 = np.float32(lower), np.float32(upper)
    return bool(low32 == high32 or not np.isfinite(low32) or not np.isfinite(high32))


def _draw_hist_1d(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    axis = histogram.axes[0]
    values = histogram.values().astype(float)
    if _collapses_in_float32(axis.edges[0], axis.edges[-1]):
        # Positions rescale to NaN in float32; draw against bin indices instead
        # and put the real values in the tick labels.
        fig.draw(fig.bar(np.arange(len(axis)).tolist(), values))
        xlim = _index_range(axis, limits.x)
        fig.ruler("x").ticks(*_bin_ticks(axis, xlim))
        _set_lim(fig, "x", xlim)
    else:
        fig.draw(fig.bar(axis.centers, values))
        fig.ruler("x").ticks(np.linspace(axis.edges[0], axis.edges[-1], 5))
        _set_lim(fig, "x", limits.x)
    lower, upper = limits.y
    fig.ruler("y").lim(0 if lower is None else lower, upper)
    fig.label(axis.label, axis="x")
    fig.title(make_hist_title(tree, histogram))


def draw_hist(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    """Draw an already-built histogram into the figure, titled for ``tree``."""
    match len(histogram.axes):
        case 1:
            _draw_hist_1d(fig, tree, histogram, limits=limits)
        case 2:
            _draw_hist_2d(fig, tree, histogram, limits=limits)
        case ndim:
            msg = f"Histograms with {ndim} dimensions are not plottable; reduce to 1 or 2 first"
            raise RuntimeError(msg)


def plot(
    tree: Any,
    *,
    fig: PlotextFigure,
    width: int = 100,
    expr: str = "",
    limits: AxisLimits = NO_LIMITS,
    cache: ExprCache | None = None,
) -> None:
    """
    Plot ``tree`` into the given plotext figure.
    Support new types by registering a :func:`to_histogram` overload.
    """
    histogram = to_histogram(tree, bins=width)
    draw_hist(fig, tree, apply_expr(histogram, expr, tree, cache=cache), limits=limits)


def array_plottable(item: Any) -> bool:
    """Does ``item`` read as a numeric array (not histogram objects)?"""
    node = as_node(item)
    return isinstance(node, Column) and node.numeric


def plottable(item: Any) -> bool:
    """
    True if :func:`plot` has an implementation for this object that can
    succeed. Some failures (like an empty branch) are only found by reading
    the data, so this is a necessary but not sufficient check.
    """
    node = as_node(item)
    return isinstance(node, Plottable) and node.plottable


def dump(item: Any, *, width: int = 100) -> str:
    """
    Return standalone Python source that rebuilds the plotted histogram as ``h``
    from an object bound to ``item``. Mirrors :func:`plot` for the "Dump & Quit"
    output. Each :class:`~uproot_browser.nodes.Plottable` implements it.
    """
    return plottable_node(item).dump_hist(width=width)


def _dump_ndim(item: Any) -> int:
    """The dimensions of the histogram :func:`dump` builds, without reading data."""
    return plottable_node(item).ndim


def _dump_title(item: Any) -> str:
    """Source for the plot title; the flow count of :func:`make_hist_title` is omitted."""
    return plottable_node(item).title_source()


def _lim_args(lim: AxisRange) -> str:
    return ", ".join("None" if v is None else repr(float(v)) for v in lim)


def dump_plotext(item: Any, *, limits: AxisLimits = NO_LIMITS) -> str:
    """Source that draws ``h`` with plotext like :func:`draw_hist` (ticks omitted)."""
    xlabel = "h.axes[0].label"
    if _dump_ndim(item) == 2 or PLOTEXT_6:
        lines = [
            "import numpy as np",
            "import plotext as plt",
            "",
            "fig = plt.figure",
        ]
        if _dump_ndim(item) == 2:
            # Heatmap rows draw top-to-bottom; flip so y increases upward
            lines += [
                "values = h.values().T[::-1].tolist()",
                'fig.draw(fig.heatmap(values, map="viridis", fill=True))',
                f'fig.label({xlabel}, axis="x")',
                'fig.label(h.axes[1].label, axis="y")',
            ]
        else:
            lines.append("fig.draw(fig.bar(h.axes[0].centers, h.values()))")
            if limits.x != (None, None):
                lines.append(f'fig.ruler("x").lim({_lim_args(limits.x)})')
            lower, upper = limits.y
            lines += [
                f'fig.ruler("y").lim({_lim_args((0 if lower is None else lower, upper))})',
                f'fig.label({xlabel}, axis="x")',
            ]
        lines += [f"fig.title({_dump_title(item)})", "print(fig.build())"]
        return "\n".join(lines)

    lines = [
        "import numpy as np",
        "import plotext as plt",
        "",
        "plt.bar(h.axes[0].centers, h.values())",
    ]
    if limits.x != (None, None):
        lines.append(f"plt.xlim({_lim_args(limits.x)})")
    lower, upper = limits.y
    lines += [
        f"plt.ylim({_lim_args((0 if lower is None else lower, upper))})",
        f"plt.xlabel({xlabel})",
        f"plt.title({_dump_title(item)})",
        "plt.show()",
    ]
    return "\n".join(lines)


def dump_mpl(item: Any, *, limits: AxisLimits = NO_LIMITS) -> str:
    """Source that draws ``h`` with matplotlib like :mod:`uproot_browser.plot_mpl`."""
    lines = [
        "import matplotlib.pyplot as plt",
        "import numpy as np",
        "",
        "h.plot()",
        f"plt.title({_dump_title(item)})",
    ]
    if limits.x != (None, None):
        lines.append(f"plt.xlim({_lim_args(limits.x)})")
    if limits.y != (None, None):
        lines.append(f"plt.ylim({_lim_args(limits.y)})")
    lines.append("plt.show()")
    return "\n".join(lines)
