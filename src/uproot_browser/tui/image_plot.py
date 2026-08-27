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
class MPLPlot:
    upfile: Any
    selection: str
    dark: bool
    app: Browser
    size: tuple[int, int] | None = None
    scale: float = 1.0
    expr: str = ""
    # cache of the built histogram; carried across dataclasses.replace so
    # theme/scale/resize re-renders only redraw instead of re-reading data
    built: hist.Hist[Any] | None = None
    built_expr: str = ""

    def make_image(self) -> PIL.Image.Image | None:
        def build() -> PIL.Image.Image:
            import uproot_browser.plot_mpl

            *_, item = apply_selection(self.upfile, self.selection.split(":"))
            histogram = self.built
            if histogram is None or self.built_expr != self.expr:
                histogram = uproot_browser.plot_mpl.build_hist(item, expr=self.expr)
                self.built = histogram
                self.built_expr = self.expr
            return make_image(
                item, histogram, dark=self.dark, size=self.size, scale=self.scale
            )

        return run_posting_errors(self.app, build)
