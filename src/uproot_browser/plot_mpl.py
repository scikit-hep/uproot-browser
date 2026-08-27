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


@functools.singledispatch
def build_hist(tree: Any, *, expr: str = "") -> hist.Hist[Any]:  # noqa: ARG001
    """
    Build the histogram for a plottable. The optional ``expr`` is evaluated
    with the histogram bound to ``h`` (e.g. ``h[::2j]``).
    Implement this for each type of plottable.
    """
    msg = "This object is not plottable yet"
    raise RuntimeError(msg)


@build_hist.register
def build_branch_hist(tree: uproot.TBranch, *, expr: str = "") -> hist.Hist[Any]:
    """
    Build a histogram from a single tree branch.
    """
    histogram = uproot_browser.plot.branch_hist(tree, bins=50)
    return uproot_browser.plot.apply_expr(histogram, expr)


build_hist.register(uproot.models.RNTuple.RField)(build_branch_hist)  # type: ignore[no-untyped-call]


@build_hist.register
def build_hist_hist(
    tree: uproot.behaviors.TH1.Histogram, *, expr: str = ""
) -> hist.Hist[Any]:
    """
    Build from a 1-D Histogram.
    """
    return uproot_browser.plot.apply_expr(hist.Hist(tree.to_hist()), expr)


def draw_hist(tree: Any, histogram: hist.Hist[Any]) -> None:
    """
    Draw an already-built histogram into the current matplotlib figure.
    """
    histogram.plot()
    plt.title(uproot_browser.plot.make_hist_title(tree, histogram))


def plot(tree: Any, *, expr: str = "") -> None:
    """
    Build and draw in one step. See :func:`build_hist` for ``expr``.
    """
    draw_hist(tree, build_hist(tree, expr=expr))
