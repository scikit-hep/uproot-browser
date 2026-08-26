"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

import functools
import math
import operator
from typing import Any

import awkward as ak
import hist
import numpy as np
import uproot
import uproot.behaviors.TH1
import uproot.interpretation.objects
import uproot.models.RNTuple

from uproot_browser.exceptions import EmptyTreeError


def make_hist_title(item: Any, histogram: hist.Hist[Any]) -> str:
    inner_sum = float(np.sum(histogram.values()))
    full_sum = float(np.sum(histogram.values(flow=True)))

    if math.isclose(inner_sum, full_sum):
        return f"{item.name} -- Entries: {inner_sum:g}"

    return f"{item.name} -- Entries: {inner_sum:g} ({full_sum:g} with flow)"


def _bin_ticks(axis: Any, count: int = 5) -> tuple[list[int], list[str]]:
    positions = np.unique(
        np.linspace(0, len(axis) - 1, min(count, len(axis))).round().astype(int)
    )
    return positions.tolist(), [f"{axis.centers[i]:g}" for i in positions]


def _draw_hist_2d(fig: Any, tree: Any, histogram: hist.Hist[Any]) -> None:
    xaxis, yaxis = histogram.axes
    values = histogram.values().astype(float)
    # heatmap rows draw top-to-bottom; flip so y increases upward
    fig.draw(fig.heatmap(values.T[::-1].tolist(), map="viridis", fill=True))
    fig.ruler("x").ticks(*_bin_ticks(xaxis))
    fig.ruler("y").ticks(*_bin_ticks(yaxis))
    fig.label(xaxis.name, axis="x")
    fig.label(yaxis.name, axis="y")
    fig.title(make_hist_title(tree, histogram))


def _draw_hist_1d(fig: Any, tree: Any, histogram: hist.Hist[Any]) -> None:
    axis = histogram.axes[0]
    fig.draw(fig.bar(axis.centers, histogram.values().astype(float)))
    fig.ruler("y").lim(lower=0)
    fig.ruler("x").ticks(np.linspace(axis.edges[0], axis.edges[-1], 5))
    fig.label(axis.name, axis="x")
    fig.title(make_hist_title(tree, histogram))


def _draw_hist(fig: Any, tree: Any, histogram: hist.Hist[Any]) -> None:
    match len(histogram.axes):
        case 1:
            _draw_hist_1d(fig, tree, histogram)
        case 2:
            _draw_hist_2d(fig, tree, histogram)
        case ndim:
            msg = f"Histograms with {ndim} dimensions are not plottable; reduce to 1 or 2 first"
            raise RuntimeError(msg)


@functools.singledispatch
def plot(tree: Any, *, fig: Any, width: int = 100, expr: str = "") -> None:  # noqa: ARG001
    """
    Plot ``tree`` into the given plotext figure.
    Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


# Simpler in Python 3.11+
@plot.register(uproot.TBranch)
def plot_branch(
    tree: uproot.TBranch | uproot.models.RNTuple.RField,
    *,
    fig: Any,
    width: int = 100,
    expr: str = "",
) -> None:
    """
    Plot a single tree branch.
    """
    # RField has no `interpretation`; it is always read as an array.
    interpretation = getattr(tree, "interpretation", None)
    if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
        arr = tree.array(library="np")
        if len(arr) == 0:
            msg = f"Branch {tree.name} is empty."
            raise EmptyTreeError(msg)
        if not isinstance(arr[0], uproot.behaviors.TH1.Histogram):
            msg = f"Branch {tree.name} ({tree.typename}) contains objects that cannot be plotted"
            raise TypeError(msg)
        histograms = [h.to_hist() for h in arr]
        histogram: hist.Hist[Any] = functools.reduce(operator.add, histograms)
    else:
        array = tree.array()
        values = ak.flatten(array) if array.ndim > 1 else array
        finite = values[np.isfinite(values)]
        if len(finite) < 1:
            msg = f"Branch {tree.name} is empty."
            raise EmptyTreeError(msg)
        histogram = hist.numpy.histogram(finite, bins=width, histogram=hist.Hist)
    if expr:
        # pylint: disable-next=eval-used
        histogram = eval(expr, {"h": histogram})
    _draw_hist(fig, tree, histogram)


plot.register(uproot.models.RNTuple.RField)(plot_branch)  # type: ignore[no-untyped-call]


@functools.singledispatch
def dump(tree: Any, *, width: int = 100) -> str:  # noqa: ARG001
    """
    Return standalone Python source that rebuilds the plotted histogram as ``h``
    from an object bound to ``item``. Mirrors :func:`plot` for the "Dump & Quit"
    output. Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


# Simpler in Python 3.11+
@dump.register(uproot.TBranch)
def dump_branch(
    tree: uproot.TBranch | uproot.models.RNTuple.RField,
    *,
    width: int = 100,
) -> str:
    """
    Source for rebuilding a single tree branch as a histogram.
    """
    # RField has no `interpretation`; it is always read as an array.
    interpretation = getattr(tree, "interpretation", None)
    if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
        return (
            "import functools\n"
            "import operator\n"
            'arr = item.array(library="np")\n'
            "h = functools.reduce(operator.add, [x.to_hist() for x in arr])"
        )
    return (
        "import awkward as ak\n"
        "import hist\n"
        "import numpy as np\n"
        "array = item.array()\n"
        "values = ak.flatten(array) if array.ndim > 1 else array\n"
        "finite = values[np.isfinite(values)]\n"
        f"h = hist.numpy.histogram(finite, bins={width}, histogram=hist.Hist)"
    )


dump.register(uproot.models.RNTuple.RField)(dump_branch)  # type: ignore[no-untyped-call]


@dump.register
def dump_hist(
    tree: uproot.behaviors.TH1.Histogram,  # noqa: ARG001
    *,
    width: int = 100,  # noqa: ARG001
) -> str:
    """
    Source for rebuilding a 1-D histogram.
    """
    return "import hist\nh = hist.Hist(item.to_hist())"


@plot.register
def plot_hist(
    tree: uproot.behaviors.TH1.Histogram,
    *,
    fig: Any,
    width: int = 100,  # noqa: ARG001
    expr: str = "",
) -> None:
    """
    Plot a 1-D Histogram.
    """
    histogram = hist.Hist(tree.to_hist())
    if expr:
        # pylint: disable-next=eval-used
        histogram = eval(expr, {"h": histogram})
    _draw_hist(fig, tree, histogram)
