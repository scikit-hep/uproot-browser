"""
Display tools for making plots via matplotlib.
"""

from __future__ import annotations

import io
import warnings
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import PIL.Image

import uproot_browser.plot

if TYPE_CHECKING:
    import hist

DPI = 100
ASPECT_RATIO = 5 / 8  # height / width of the default figure


def draw_hist(histogram: hist.Hist[Any], title: str) -> None:
    """
    Draw an already-built histogram into the current matplotlib figure.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        histogram.plot()
    plt.title(title)


def plot(tree: Any, *, expr: str = "") -> None:
    """
    Build and draw in one step. The optional ``expr`` is evaluated with the
    histogram bound to ``h`` (e.g. ``h[::2j]``).
    """
    histogram = uproot_browser.plot.apply_expr(
        uproot_browser.plot.to_histogram(tree), expr
    )
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
    figsize = (size[0] / dpi, size[1] / dpi) if size else (8.0, 8.0 * ASPECT_RATIO)
    with plt.style.context(style):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        try:
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
    style: Any = "default",
) -> PIL.Image.Image:
    """
    Build and render to a PIL image in one step.
    """
    histogram = uproot_browser.plot.apply_expr(
        uproot_browser.plot.to_histogram(tree), expr
    )
    return render_image(
        histogram,
        uproot_browser.plot.make_hist_title(tree, histogram),
        size=size,
        scale=scale,
        style=style,
    )
