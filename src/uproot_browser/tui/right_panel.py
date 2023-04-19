from __future__ import annotations
import dataclasses
from typing import Any

import numpy as np
import plotext as plt  # plots in text
import rich.panel
import rich.text
import textual.widget
import uproot
from uproot_browser.exceptions import EmptyTreeError

import uproot_browser.plot

LOGO = """\
Scikit-HEP
┬ ┬┌─┐┬─┐┌─┐┌─┐┌┬┐5 ┌┐ ┬─┐┌─┐┬ ┬┌─┐┌─┐┬─┐
│ │├─┘├┬┘│ ││ │ │───├┴┐├┬┘│ ││││└─┐├┤ ├┬┘
└─┘┴  ┴└─└─┘└─┘ ┴   └─┘┴└─└─┘└┴┘└─┘└─┘┴└─
                Powered by Textual & Hist"""

LOGO_PANEL = rich.text.Text.from_ansi(LOGO, no_wrap=True)


placeholder = np.random.rand(1000)

# # dummy make_plot
# def make_plot(item, width, height) -> str:
#     plt.clf()  # clears screen
#     plt.plotsize(width, height)
#     plt.hist(item)  # plots a histogram
#     return plt.build()  # returns a text plot

# print(make_plot(placeholder))


#good make_plot
def make_plot(item: Any, *size: int) -> Any:
    plt.clf()
    plt.plotsize(*size)
    uproot_browser.plot.plot(item)
    return plt.build()

# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    item: Any

    # this function makes the plot a rich.console.RenderableType
    def __rich_console__(self, console, options):
        if self.item is None:
            yield rich.text.Text()
            return
        width = options.max_width or console.width  # console.width is the screen width
        height = options.height or console.height  # same

        canvas = make_plot(self.item, width, height)
        yield rich.text.Text.from_ansi(canvas)


class PlotWidget(textual.widget.Widget):

    def __init__(self, uproot_item=None, **kargs):
        super().__init__(**kargs)
        self.item = Plotext(uproot_item)

    # def set_plot(self, plot_path: str | None) -> None:
    #     self.plot_path = plot_path
    #     if plot_path is None:
    #         self.plot = plot_path
    #     else:
    #         *_, item = uproot_browser.dirs.apply_selection(
    #             self.file, plot_path.split(":")
    #         )
    #         self.plot = Plotext(item)

    def render(self) -> rich.console.RenderableType:
        return self.item


class EmptyWidget(textual.widget.Widget):
    ''' if the plot is empty'''
    def render(self) -> rich.console.RenderableType:
        return rich.text.Text("Plot is Empty")


class LogoWidget(textual.widget.Widget):
    def render(self) -> rich.console.RenderableType:
        return LOGO_PANEL


@dataclasses.dataclass
class Error:
    exc: tuple

    # this function makes the plot a rich.console.RenderableType
    def __rich_console__(self, console, options):
        # if self.exc is None:
        #     yield rich.text.Text()
        #     return
        width = options.max_width or console.width

        yield rich.traceback.Traceback.from_exception(*self.exc, width = width)

class ErrorWidget(textual.widget.Widget):
    _exc: Error

    @property
    def exc(self) -> Error:
        return self._exc
    
    @exc.setter
    def exc(self, value: tuple) -> None:
        self._exc = Error(value)
        self.refresh()

    def __init__(self, **kargs):
        super().__init__(**kargs)
        self._exc = None

    def render(self) -> rich.console.RenderableType:
        if self._exc is None:
            return rich.text.Text("No Exception set!")
        return self.exc