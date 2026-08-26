"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

import functools
import operator
from typing import Any

import awkward as ak
import hist
import matplotlib.pyplot as plt
import numpy as np
import uproot
import uproot.behaviors.TH1
import uproot.interpretation.objects

import uproot_browser.plot
from uproot_browser.exceptions import EmptyTreeError


def _draw_hist(tree: Any, histogram: hist.Hist[Any], expr: str) -> None:
    if expr:
        # pylint: disable-next=eval-used
        histogram = eval(expr, {"h": histogram})
    histogram.plot()
    plt.title(uproot_browser.plot.make_hist_title(tree, histogram))


@functools.singledispatch
def plot(tree: Any, *, expr: str = "") -> None:  # noqa: ARG001
    """
    Implement this for each type of plottable. The optional ``expr`` is
    evaluated with the histogram bound to ``h`` (e.g. ``h[::2j]``).
    """
    msg = "This object is not plottable yet"
    raise RuntimeError(msg)


@plot.register
def plot_branch(tree: uproot.TBranch, *, expr: str = "") -> None:
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
        histogram: hist.Hist[Any] = functools.reduce(
            operator.add, (h.to_hist() for h in arr)
        )
    else:
        array = tree.array()
        values = ak.flatten(array) if array.ndim > 1 else array
        finite = values[np.isfinite(values)]
        if len(finite) < 1:
            msg = f"Branch {tree.name} is empty."
            raise EmptyTreeError(msg)
        histogram = hist.numpy.histogram(finite, bins=50, histogram=hist.Hist)
    _draw_hist(tree, histogram, expr)


plot.register(uproot.models.RNTuple.RField)(plot_branch)  # type: ignore[no-untyped-call]


@plot.register
def plot_hist(tree: uproot.behaviors.TH1.Histogram, *, expr: str = "") -> None:
    """
    Plot a 1-D Histogram.
    """
    histogram = hist.Hist(tree.to_hist())
    _draw_hist(tree, histogram, expr)
