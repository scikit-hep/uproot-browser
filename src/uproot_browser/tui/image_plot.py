"""
Matplotlib image rendering for the TUI (``browse --image``).

Images display via textual-image (Sixel/TGP with a unicode fallback).
Matplotlib imports stay inside functions so this module is cheap to import
when the [image] extra is not installed.
"""

from __future__ import annotations

__lazy_modules__ = {
    "warnings",
    f"{__spec__.parent}.messages",
    f"{__spec__.parent}.plot",
    f"{__spec__.parent}.theme",
}

import dataclasses
import warnings
from typing import TYPE_CHECKING, Any

from .messages import RequestImage
from .plot import resolve_selection, run_posting_errors, selection_source
from .theme import DARK_BACKGROUND, DARK_TEXT, LIGHT_BACKGROUND, as_hex

if TYPE_CHECKING:
    import hist
    import PIL.Image

    from .browser import Browser
    from .viewer import ViewWidget


def make_image(
    histogram: hist.Hist[Any],
    *,
    title: str,
    dark: bool,
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
) -> PIL.Image.Image:
    """Draw an already-built histogram into a PIL image.

    ``size`` is the target size in pixels; the figure is built to match so the
    aspect ratio is right for the widget it will fill. ``scale`` renders the
    same pixels at a higher dpi, making text and lines proportionally larger.
    """
    import uproot_browser.plot_mpl

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
    return uproot_browser.plot_mpl.render_image(
        histogram, title, size=size, scale=scale, style=style
    )


@dataclasses.dataclass(slots=True)
class _HistCache:
    """One-slot cache for the resolved item and its pre-expr histogram.

    Shared by reference across ``dataclasses.replace``, so a build finished by
    an already-superseded render worker still lands in the current item's
    cache, and a single-attribute write cannot be observed half-updated.
    """

    item: Any = None
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

    def display(self, view: ViewWidget) -> None:
        view.current = "image-window"
        view.post_message(RequestImage())

    def handle_resize(self, view: ViewWidget) -> None:
        # Debounce so a drag-resize only renders the settled size
        if view.resize_timer is not None:
            view.resize_timer.stop()
        view.resize_timer = view.set_timer(
            0.2, lambda: view.post_message(RequestImage())
        )

    def with_theme(self, *, dark: bool) -> MPLPlot:
        return dataclasses.replace(self, dark=dark)

    def with_expr(self, expr: str) -> MPLPlot:
        return dataclasses.replace(self, expr=expr)

    def dump_source(self) -> str:
        msg = selection_source(self.selection)
        expr_arg = f", expr={self.expr!r}" if self.expr else ""
        return (
            msg
            + f"\n\nimport matplotlib.pyplot as plt\nimport uproot_browser.plot_mpl\n\nuproot_browser.plot_mpl.plot(item{expr_arg})\nplt.show()"
        )

    def dump_renderables(self) -> tuple[Any, ...]:
        return ()

    def make_image(self) -> PIL.Image.Image | None:
        def build() -> PIL.Image.Image:
            import uproot_browser.plot

            item = self.built.item
            if item is None:
                item = resolve_selection(self.upfile, self.selection)
                self.built.item = item
            histogram = self.built.hist
            if histogram is None:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    histogram = uproot_browser.plot.to_histogram(item)
                self.built.hist = histogram
            if self.expr:
                # copy so an in-place expr cannot corrupt the cache
                histogram = uproot_browser.plot.apply_expr(histogram.copy(), self.expr)
            return make_image(
                histogram,
                title=uproot_browser.plot.make_hist_title(item, histogram),
                dark=self.dark,
                size=self.size,
                scale=self.scale,
            )

        return run_posting_errors(self.app, build, self.selection)
