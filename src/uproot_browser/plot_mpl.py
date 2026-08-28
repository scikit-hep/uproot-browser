"""
Display tools for making plots via matplotlib.
"""

from __future__ import annotations

import functools
import io
import warnings
from typing import Any

import hist
import matplotlib.pyplot as plt
import PIL.Image
import uproot
import uproot.behaviors.TH1

import uproot_browser.plot

DPI = 100


@functools.singledispatch
def build_hist(tree: Any) -> hist.Hist[Any]:  # noqa: ARG001
    """
    Build the histogram for a plottable.
    Implement this for each type of plottable.
    """
    msg = "This object is not plottable yet"
    raise RuntimeError(msg)


@build_hist.register
def build_branch_hist(tree: uproot.TBranch) -> hist.Hist[Any]:
    """
    Build a histogram from a single tree branch.
    """
    return uproot_browser.plot.branch_hist(tree, bins=50)


build_hist.register(uproot.models.RNTuple.RField)(build_branch_hist)  # type: ignore[no-untyped-call]


@build_hist.register
def build_hist_hist(tree: uproot.behaviors.TH1.Histogram) -> hist.Hist[Any]:
    """
    Build from a 1-D Histogram.
    """
    return hist.Hist(tree.to_hist())


def draw_hist(histogram: hist.Hist[Any], title: str) -> None:
    """
    Draw an already-built histogram into the current matplotlib figure.
    """
    histogram.plot()
    plt.title(title)


def plot(tree: Any, *, expr: str = "") -> None:
    """
    Build and draw in one step. The optional ``expr`` is evaluated with the
    histogram bound to ``h`` (e.g. ``h[::2j]``).
    """
    histogram = uproot_browser.plot.apply_expr(build_hist(tree), expr)
    draw_hist(histogram, uproot_browser.plot.make_hist_title(tree, histogram))


def render_image(
    histogram: hist.Hist[Any],
    title: str,
    *,
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
    style: Any = "default",
) -> PIL.Image.Image:
    """Draw an already-built histogram into a PIL image.

    ``size`` is the target size in pixels; the figure is built to match so the
    aspect ratio is right for the area it will fill. ``scale`` renders the
    same pixels at a higher dpi, making text and lines proportionally larger.
    ``style`` is any matplotlib style context spec (name, dict, or list).
    """
    dpi = DPI * scale
    figsize = (size[0] / dpi, size[1] / dpi) if size else (8.0, 5.0)
    with plt.style.context(style):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                draw_hist(histogram, title)
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
        finally:
            plt.close(fig)
    buf.seek(0)
    return PIL.Image.open(buf)


def make_image(
    tree: Any,
    *,
    expr: str = "",
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
) -> PIL.Image.Image:
    """
    Build and render to a PIL image in one step.
    """
    histogram = uproot_browser.plot.apply_expr(build_hist(tree), expr)
    return render_image(
        histogram,
        uproot_browser.plot.make_hist_title(tree, histogram),
        size=size,
        scale=scale,
    )
