from __future__ import annotations

import uproot
import functools
import plotext as plt
import hist
import numpy as np
import awkward as ak


@functools.singledispatch
def plot(tree: Any, command: str = "") -> None:
    raise RuntimeError("This object is not plottable yet")


@plot.register
def plot_branch(tree: uproot.TBranch, command: str = "") -> None:
    h = hist.numpy.histogram(ak.flatten(tree.array()), bins=80, histogram=hist.Hist)
    plt.clear_figure()
    plt.bar(h.axes[0].centers, h.values(), marker='small')
    plt.show()


