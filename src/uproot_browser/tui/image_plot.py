"""
Matplotlib image rendering for the TUI (``browse --image``).

Images display via textual-image (Sixel/TGP with a unicode fallback).
Matplotlib imports stay inside functions so this module is cheap to import
when the [image] extra is not installed.
"""

from __future__ import annotations

import dataclasses
import io
import sys
import warnings
from typing import TYPE_CHECKING, Any

from uproot_browser.exceptions import EmptyTreeError

from .error import Error
from .messages import EmptyMessage, ErrorMessage
from .plot import apply_selection

if TYPE_CHECKING:
    import PIL.Image

    from .browser import Browser


DPI = 100

# Matches the uproot_light / uproot_dark plotext themes in browser.py
LIGHT_BACKGROUND = "#F5F5F5"
DARK_BACKGROUND = "#1E1E1E"
DARK_TEXT = "#FFA62B"


def make_image(
    item: Any,
    *,
    dark: bool,
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
    expr: str = "",
) -> PIL.Image.Image:
    """Render the item with the plot_mpl dispatch into a PIL image.

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
    background = DARK_BACKGROUND if dark else LIGHT_BACKGROUND
    overrides: dict[str, Any] = {
        "figure.facecolor": background,
        "axes.facecolor": background,
        "savefig.facecolor": background,
    }
    if dark:
        overrides |= {
            "text.color": DARK_TEXT,
            "axes.labelcolor": DARK_TEXT,
            "axes.titlecolor": DARK_TEXT,
            "xtick.color": DARK_TEXT,
            "ytick.color": DARK_TEXT,
        }
    style = ["dark_background", overrides] if dark else ["default", overrides]
    with plt.style.context(style):
        fig = plt.figure(figsize=figsize, dpi=dpi)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                uproot_browser.plot_mpl.plot(item, expr=expr)
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

    def make_image(self) -> PIL.Image.Image | None:
        *_, item = apply_selection(self.upfile, self.selection.split(":"))
        try:
            return make_image(
                item, dark=self.dark, size=self.size, scale=self.scale, expr=self.expr
            )
        except EmptyTreeError:
            self.app.post_message(EmptyMessage())
            return None
        except Exception:  # noqa: BLE001
            exc = sys.exc_info()
            assert exc[1]
            self.app.post_message(ErrorMessage(Error(exc)))
            return None
