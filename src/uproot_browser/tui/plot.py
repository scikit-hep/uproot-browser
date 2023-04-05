from __future__ import annotations

import numpy as np
import plotext as plt  # plots in text
import rich.panel
import rich.text
import textual.widget

placeholder = np.random.rand(1000)


def make_plot(item, width, height) -> str:
    plt.clf()  # clears screen
    plt.plotsize(width, height)
    plt.hist(item)  # plots a histogram
    return plt.build()  # returns a text plot


# print(make_plot(placeholder))


# protocol class
class Plot:
    def __init__(self):
        pass

    # this function makes the plot a rich.console.RenderableType
    def __rich_console__(self, console, options):
        width = options.max_width or console.width  # console.width is the screen width
        height = options.height or console.height  # same

        canvas = make_plot(placeholder, width, height)
        yield rich.text.Text.from_ansi(canvas)


class PlotWidget(textual.widget.Widget):
    def render(self) -> rich.console.RenderableType:
        return Plot()
