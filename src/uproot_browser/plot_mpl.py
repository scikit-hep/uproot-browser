"""
Display tools for making plots via matplotlib.
"""

from __future__ import annotations

__lazy_modules__ = {
    "PIL",
    "PIL.Image",
    "io",
    "matplotlib",
    "matplotlib.axes",
    "matplotlib.backends",
    "matplotlib.backends.backend_agg",
    "matplotlib.figure",
    "matplotlib.pyplot",
    "matplotlib.style",
    "uproot_browser.plot",
    "warnings",
}

import io
import warnings
from typing import TYPE_CHECKING, Any

import matplotlib.axes
import matplotlib.figure
import matplotlib.pyplot as plt
import matplotlib.style
import PIL.Image
from matplotlib.backends.backend_agg import FigureCanvasAgg

import uproot_browser.plot

if TYPE_CHECKING:
    import hist

DPI = 100
ASPECT_RATIO = 5 / 8  # height / width of the default figure


def _draw_on(ax: matplotlib.axes.Axes, histogram: hist.Hist[Any], title: str) -> None:
    """
    Draw an already-built histogram into the given axes.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if len(histogram.axes) == 2:
            # hist makes its colorbar with pyplot, and grows the figure to
            # hold it, which changes the image size. Make it here instead.
            mesh = histogram.plot2d(ax=ax, cbar=False)[0]
            ax.figure.colorbar(mesh, ax=ax)
        else:
            histogram.plot(ax=ax)
    ax.set_title(title)


def draw_hist(histogram: hist.Hist[Any], title: str) -> None:
    """
    Draw an already-built histogram into the current matplotlib axes.
    """
    _draw_on(plt.gca(), histogram, title)


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
    with matplotlib.style.context(style):
        fig = matplotlib.figure.Figure(figsize=figsize, dpi=dpi)
        # hist sets the pyplot current axes for a 2D plot. Attach an Agg canvas
        # first, or pyplot attaches a GUI one, which a worker thread cannot do.
        FigureCanvasAgg.new_manager(fig, 0)
        try:
            _draw_on(fig.subplots(), histogram, title)
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
        finally:
            plt.close(fig)  # release the figure if hist registered it
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
