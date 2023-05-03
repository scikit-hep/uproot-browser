"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

import functools
import math
from typing import Any

import awkward as ak
import hist
import numpy as np
import plotext as plt
import uproot

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


def make_hist_title(item: Any, histogram: hist.Hist) -> str:
    inner_sum = np.sum(histogram.values())
    full_sum = np.sum(histogram.values(flow=True))

    if math.isclose(inner_sum, full_sum):
        return f"{item.name} -- Entries: {inner_sum:g}"

    return f"{item.name} -- Entries: {inner_sum:g} ({full_sum:g} with flow)"


@functools.singledispatch
def plot(tree: Any) -> None:  # noqa: ARG001
    """
    Implement this for each type of plottable.
    """
    msg = "This object is not plottable yet"
    raise RuntimeError(msg)


@plot.register
def plot_branch(tree: uproot.TBranch) -> None:
    """
    Plot a single tree branch.
    """
    array = tree.array()
    values = ak.flatten(array) if array.ndim > 1 else array
    finite = values[np.isfinite(values)]
    if len(finite) < 1:
        msg = f"Branch {tree.name} is empty."
        raise EmptyTreeError(msg)
    histogram: hist.Hist = hist.numpy.histogram(finite, bins=100, histogram=hist.Hist)
    plt.bar(histogram.axes[0].centers, histogram.values().astype(float))
    plt.ylim(lower=0)
    plt.xticks(np.linspace(histogram.axes[0][0][0], histogram.axes[0][-1][-1], 5))
    plt.xlabel(histogram.axes[0].name)
    plt.title(make_hist_title(tree, histogram))


@plot.register
def plot_hist(tree: uproot.behaviors.TH1.Histogram) -> None:
    """
    Plot a 1-D Histogram.
    """
    histogram = hist.Hist(tree.to_hist())
    plt.bar(histogram.axes[0].centers, histogram.values().astype(float))
    plt.ylim(lower=0)
    plt.xticks(np.linspace(histogram.axes[0][0][0], histogram.axes[0][-1][-1], 5))
    plt.xlabel(histogram.axes[0].name)
    plt.title(make_hist_title(tree, histogram))
