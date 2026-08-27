"""
Matplotlib image rendering for the TUI (``browse --image``).

Images display via textual-image (Sixel/TGP with a unicode fallback).
Matplotlib imports stay inside functions so this module is cheap to import
when the [image] extra is not installed.
"""

from __future__ import annotations

import dataclasses
import io
import warnings
from typing import TYPE_CHECKING, Any

from .plot import apply_selection, run_posting_errors
from .theme import DARK_BACKGROUND, DARK_TEXT, LIGHT_BACKGROUND, as_hex

if TYPE_CHECKING:
    import hist
    import PIL.Image

    from .browser import Browser


DPI = 100


def make_image(
    item: Any,
    histogram: hist.Hist[Any],
    *,
    dark: bool,
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
) -> PIL.Image.Image:
    """Draw an already-built histogram for ``item`` into a PIL image.

    ``size`` is the target size in pixels; the figure is built to match so the
    aspect ratio is right for the widget it will fill. ``scale`` renders the
    same pixels at a higher dpi, making text and lines proportionally larger.
    """
    import matplotlib as mpl

    mpl.use("agg")  # rendered to PNG off the main thread; never a GUI
    import matplotlib.pyplot as plt
    import PIL.Image

    import uproot_browser.plot_mpl

    dpi = DPI * scale
    figsize = (size[0] / dpi, size[1] / dpi) if size else (8.0, 5.0)
    background = as_hex(DARK_BACKGROUND if dark else LIGHT_BACKGROUND)
    overrides: dict[str, Any] = {
        "figure.facecolor": background,
        "axes.facecolor": background,
        "savefig.facecolor": background,
    }
    if dark:
        text = as_hex(DARK_TEXT)
        overrides |= {
            "text.color": text,
            "axes.labelcolor": text,
            "axes.titlecolor": text,
            "xtick.color": text,
            "ytick.color": text,
        }
    style = ["dark_background", overrides] if dark else ["default", overrides]
    with plt.style.context(style):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                uproot_browser.plot_mpl.draw_hist(item, histogram)
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
        finally:
            plt.close(fig)
    buf.seek(0)
    return PIL.Image.open(buf)


@dataclasses.dataclass
class _HistCache:
    """One-slot cache for the pre-expr histogram.

    Shared by reference across ``dataclasses.replace``, so a build finished by
    an already-superseded render worker still lands in the current item's
    cache, and the single-attribute write cannot be observed half-updated.
    """

    hist: hist.Hist[Any] | None = None


@dataclasses.dataclass
class MPLPlot:
    upfile: Any
    selection: str
    dark: bool
    app: Browser
    size: tuple[int, int] | None = None
    scale: float = 1.0
    expr: str = ""
    # theme/scale/expr/resize re-renders only redraw instead of re-reading data
    built: _HistCache = dataclasses.field(default_factory=_HistCache)

    def make_image(self) -> PIL.Image.Image | None:
        def build() -> PIL.Image.Image:
            import uproot_browser.plot
            import uproot_browser.plot_mpl

            *_, item = apply_selection(self.upfile, self.selection.split(":"))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                histogram = self.built.hist
                if histogram is None:
                    histogram = uproot_browser.plot_mpl.build_hist(item)
                    self.built.hist = histogram
                # copy so an in-place expr cannot corrupt the cache
                histogram = uproot_browser.plot.apply_expr(histogram.copy(), self.expr)
            return make_image(
                item, histogram, dark=self.dark, size=self.size, scale=self.scale
            )

        return run_posting_errors(self.app, build)
