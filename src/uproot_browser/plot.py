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
import plotext as plt
import uproot
import uproot.behaviors.TH1
import uproot.interpretation.objects
import uproot.models.RNTuple

from uproot_browser.exceptions import EmptyTreeError


def clf() -> None:
    """
    Clear the plot.
    """
    plt.clf()


def show() -> None:
    """
    Show the plot.
    """
    plt.show()


def make_hist_title(item: Any, histogram: hist.Hist[Any]) -> str:
    inner_sum = float(np.sum(histogram.values()))
    full_sum = float(np.sum(histogram.values(flow=True)))

    if math.isclose(inner_sum, full_sum):
        return f"{item.name} -- Entries: {inner_sum:g}"

    return f"{item.name} -- Entries: {inner_sum:g} ({full_sum:g} with flow)"


@functools.singledispatch
def plot(tree: Any, *, width: int = 100, expr: str = "") -> None:  # noqa: ARG001
    """
    Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


# Simpler in Python 3.11+
@plot.register(uproot.TBranch)
def plot_branch(
    tree: uproot.TBranch | uproot.models.RNTuple.RField,
    *,
    width: int = 100,
    expr: str = "",
) -> None:
    """
    Plot a single tree branch.
    """
    if isinstance(tree.interpretation, uproot.interpretation.objects.AsObjects):
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
    plt.bar(
        histogram.axes[0].centers,
        histogram.values().astype(float),
    )
    plt.ylim(lower=0)
    plt.xticks(np.linspace(histogram.axes[0].edges[0], histogram.axes[0].edges[-1], 5))
    plt.xlabel(histogram.axes[0].name)
    plt.title(make_hist_title(tree, histogram))


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
    if isinstance(tree.interpretation, uproot.interpretation.objects.AsObjects):
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
    plt.bar(histogram.axes[0].centers, histogram.values().astype(float))
    plt.ylim(lower=0)
    plt.xticks(np.linspace(histogram.axes[0].edges[0], histogram.axes[0].edges[-1], 5))
    plt.xlabel(histogram.axes[0].name)
    plt.title(make_hist_title(tree, histogram))
