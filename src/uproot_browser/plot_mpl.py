"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

import functools
from typing import Any

import awkward as ak
import hist
import matplotlib.pyplot as plt
import numpy as np
import uproot
import uproot.behaviors.TH1

import uproot_browser.plot
from uproot_browser.exceptions import EmptyTreeError


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
    histogram: hist.Hist[Any] = hist.numpy.histogram(
        finite, bins=50, histogram=hist.Hist
    )
    histogram.plot()
    plt.title(uproot_browser.plot.make_hist_title(tree, histogram))


plot.register(uproot.models.RNTuple.RField)(plot_branch)  # type: ignore[no-untyped-call]


@plot.register
def plot_hist(tree: uproot.behaviors.TH1.Histogram) -> None:
    """
    Plot a 1-D Histogram.
    """
    histogram = hist.Hist(tree.to_hist())
    histogram.plot()
    plt.title(uproot_browser.plot.make_hist_title(tree, histogram))
