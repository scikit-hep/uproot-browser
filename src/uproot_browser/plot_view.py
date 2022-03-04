from __future__ import annotations

import plotext as plt
import rich.ansi
import rich.console
import rich.jupyter


def make_plot(*size):
    plt.clf()
    plt.scatter(plt.sin(1000, 3))
    plt.plotsize(*size)
    plt.title("Plotext Integration in Rich - Test")
    return plt.build()


class plotextMixin(rich.jupyter.JupyterMixin):
    def __init__(self):
        self.decoder = rich.ansi.AnsiDecoder()

    def __rich_console__(self, console, options):
        self.width = options.max_width or console.width
        self.height = options.height or console.height
        canvas = make_plot(self.width, self.height)
        self.rich_canvas = rich.console.RenderGroup(*self.decoder.decode(canvas))
        yield self.rich_canvas
