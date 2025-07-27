from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from types import TracebackType
from typing import Any

import numpy as np
import plotext as plt  # plots in text
import rich.panel
import rich.text
import rich.traceback
import textual.widget
import textual.widgets

try:
    from textual.widgets import RichLog
except ImportError:
    from textual.widgets import (  # type: ignore[attr-defined,no-redef]
        TextLog as RichLog,
    )

import uproot_browser.plot

LOGO = """\
Scikit-HEP
┬ ┬┌─┐┬─┐┌─┐┌─┐┌┬┐5 ┌┐ ┬─┐┌─┐┬ ┬┌─┐┌─┐┬─┐
│ │├─┘├┬┘│ ││ │ │───├┴┐├┬┘│ ││││└─┐├┤ ├┬┘
└─┘┴  ┴└─└─┘└─┘ ┴   └─┘┴└─└─┘└┴┘└─┘└─┘┴└─
                Powered by Textual & Hist"""

LOGO_PANEL = rich.text.Text.from_ansi(LOGO, no_wrap=True)


placeholder = np.random.rand(1000)


def apply_selection(tree: Any, selection: Iterable[str]) -> Iterable[Any]:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    for sel in selection:
        tree = tree[sel]
        yield tree


def make_plot(item: Any, theme: str, *size: int) -> Any:
    plt.clf()
    plt.plotsize(*size)
    uproot_browser.plot.plot(item)
    plt.theme(theme)
    return plt.build()


# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    theme: str

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        *_, item = apply_selection(self.upfile, self.selection.split(":"))

        if item is None:
            yield rich.text.Text()
            return
        width = options.max_width or console.width
        height = options.height or console.height

        canvas = make_plot(item, self.theme, width, height)
        yield rich.text.Text.from_ansi(canvas)


class PlotWidget(textual.containers.Container):
    def __init__(self, **kargs: Any):
        super().__init__(**kargs)
        self._item: Error | Plotext | None = None

    @property
    def item(self) -> Plotext | Error | None:
        return self._item

    @item.setter
    def item(self, value: Plotext) -> None:
        self._item = value
        self.refresh(recompose=True)

    def compose(self) -> rich.console.RenderableType:
        if self.item is None:
            yield textual.widgets.Static(LOGO_PANEL, id="logo")
        elif isinstance(self.item, Error):
            yield textual.containers.VerticalScroll(textual.widgets.Static(self.item, id="error"))
        else:
            yield textual.widgets.Static(self.item, id="plot")


@dataclasses.dataclass
class Error:
    exc: tuple[type[BaseException], BaseException, TracebackType]

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width

        yield rich.traceback.Traceback.from_exception(*self.exc, width=width)

