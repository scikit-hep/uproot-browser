"""
Matplotlib image rendering for the TUI (``browse --image``).

Images display via textual-image (Sixel/TGP with a unicode fallback).
Matplotlib imports stay inside functions so this module is cheap to import
when the [image] extra is not installed.
"""

from __future__ import annotations

__lazy_modules__ = {"contextlib", "uproot_browser.tui.theme"}

import contextlib
import dataclasses
from typing import TYPE_CHECKING, Any, ClassVar

from uproot_browser.axis import NO_LIMITS, AxisLimits
from uproot_browser.nodes import FILE_VAR
from uproot_browser.tui.plot import PlotItem, make_dump, resolve_item
from uproot_browser.tui.theme import (
    DARK_BACKGROUND,
    DARK_TEXT,
    LIGHT_BACKGROUND,
    as_hex,
)

if TYPE_CHECKING:
    import hist
    import PIL.Image

    from uproot_browser.tui.viewer import ViewWidget


def make_image(
    histogram: hist.Hist[Any],
    *,
    title: str,
    dark: bool,
    size: tuple[int, int] | None = None,
    scale: float = 1.0,
    limits: AxisLimits = NO_LIMITS,
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
        histogram,
        title,
        size=size,
        scale=scale,
        style=style,
        limits=limits,
    )


@dataclasses.dataclass(slots=True)
class _HistCache:
    """One-slot cache for the resolved item and its histogram.

    Shared by reference across ``dataclasses.replace``, so a build finished by
    an already-superseded render worker still lands in the current item's
    cache, and a single-attribute write cannot be observed half-updated.
    """

    item: Any = None
    hist: hist.Hist[Any] | None = None


@dataclasses.dataclass(frozen=True)
class MPLPlot(PlotItem):
    """An image plot drawn with matplotlib, sized in pixels."""

    window: ClassVar[str] = "image-window"

    scale: float = 1.0
    # theme/scale/expr/resize re-renders only redraw instead of re-reading data
    built: _HistCache = dataclasses.field(default_factory=_HistCache, compare=False)

    def display(self, view: ViewWidget) -> None:
        view.current = self.window
        view.request_render()

    def with_view_size(self, view: ViewWidget) -> MPLPlot:
        size = view.image_pixel_size()
        return self if size is None else self.with_size(size)

    def render(self) -> PIL.Image.Image:
        import uproot_browser.plot

        item = self.built.item
        if item is None:
            item = resolve_item(self.root, self.selection, self.y_selection)
            self.built.item = item
        histogram = self.built.hist
        if histogram is None:
            histogram = uproot_browser.plot.plottable_node(item).to_histogram()
            self.built.hist = histogram
        if self.expr:
            # copy so an in-place expr cannot corrupt the cache
            histogram = uproot_browser.plot.apply_expr(
                histogram.copy(), self.expr, item, cache=self.cache
            )
        return make_image(
            histogram,
            title=uproot_browser.plot.make_hist_title(item, histogram),
            dark=self.dark,
            size=self.size,
            scale=self.scale,
            limits=self.axis_limits,
        )

    def show(self, view: ViewWidget, result: Any) -> None:
        assert view.image_widget is not None
        view.image_widget.image = result

    def show_expression_error(self, view: ViewWidget) -> None:
        assert view.image_widget is not None
        view.image_widget.image = None

    def dump_source(self, *, file_var: str = FILE_VAR) -> str:
        selected = resolve_item(self.root, self.selection, self.y_selection)
        with contextlib.suppress(RuntimeError):
            return f"\n{make_dump(selected, expr=self.expr, limits=self.axis_limits, image=True, file_var=file_var)}"
        return ""
