"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

import functools
from typing import Any

import awkward as ak
import hist
import plotext as plt
import uproot


@functools.singledispatch
def plot(tree: Any) -> None:
    """
    Implement this for each type of plottable.
    """
    raise RuntimeError("This object is not plottable yet")


@plot.register
def plot_branch(tree: uproot.TBranch) -> None:
    """
    Plot a single tree branch.
    """
    array = tree.array()
    histogram = hist.numpy.histogram(
        ak.flatten(array) if array.ndim > 1 else array, bins=50, histogram=hist.Hist
    )
    plt.clear_figure()
    plt.bar(histogram.axes[0].centers, histogram.values().astype(float))
    plt.show()


@plot.register
def plot_hist(tree: uproot.behaviors.TH1.Histogram) -> None:
    """
    Plot a 1-D Histogram.
    """
    histogram = tree.to_hist()
    plt.clear_figure()
    plt.bar(histogram.axes[0].centers, histogram.values().astype(float))
    plt.show()
