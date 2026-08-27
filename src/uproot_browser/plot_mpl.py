"""
Display tools for making plots via matplotlib.
"""

from __future__ import annotations

import functools
from typing import Any

import hist
import matplotlib.pyplot as plt
import uproot
import uproot.behaviors.TH1

import uproot_browser.plot


def _draw_hist(tree: Any, histogram: hist.Hist[Any], expr: str) -> None:
    histogram = uproot_browser.plot.apply_expr(histogram, expr)
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
    histogram = uproot_browser.plot.branch_hist(tree, bins=50)
    _draw_hist(tree, histogram, expr)


plot.register(uproot.models.RNTuple.RField)(plot_branch)  # type: ignore[no-untyped-call]


@plot.register
def plot_hist(tree: uproot.behaviors.TH1.Histogram, *, expr: str = "") -> None:
    """
    Plot a 1-D Histogram.
    """
    _draw_hist(tree, hist.Hist(tree.to_hist()), expr)
