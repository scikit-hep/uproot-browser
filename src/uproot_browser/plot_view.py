from __future__ import annotations

from typing import Any

import plotext as plt
import rich.align
import rich.ansi
import rich.box
import rich.console
import rich.panel
import rich.pretty
import textual.view
import textual.widget
import uproot

import uproot_browser.dirs
import uproot_browser.plot

EMPTY = object()


def make_plot(item: Any, *size: int) -> plt.Figure:
    plt.clf()
    plt.plotsize(*size)
    plt.title("Plotext Integration in Rich - Test")
    uproot_browser.plot.plot(item)
    return plt.build()


class Plot:
    def __init__(self, item: Any) -> None:
        self.decoder = rich.ansi.AnsiDecoder()
        self.item: Any = item

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        self.width = options.max_width or console.width
        self.height = options.height or console.height
        canvas = make_plot(self.item, self.width, self.height)
        self.rich_canvas = rich.console.Group(*self.decoder.decode(canvas))
        yield self.rich_canvas


class PlotWidget(textual.widget.Widget):  # type: ignore[misc]
    height: textual.widget.Reactive[int | None] = textual.widget.Reactive(None)

    def __init__(self, uproot_file: uproot.ReadOnlyFile) -> None:
        super().__init__()
        self.file = uproot_file
        self.plot = EMPTY

    def set_plot(self, plot_path: str | None) -> None:
        if plot_path is None:
            self.plot = plot_path
        else:
            *_, item = uproot_browser.dirs.apply_selection(
                self.file, plot_path.split(":")
            )
            self.plot = Plot(item)

    async def update(self) -> None:
        self.refresh()

    def render(self) -> rich.console.RenderableType:
        if self.plot is None or self.plot is EMPTY:
            return rich.panel.Panel(
                rich.align.Align.center(
                    rich.pretty.Pretty(self, no_wrap=True, overflow="ellipsis"),
                    vertical="middle",
                ),
                title=self.__class__.__name__,
                border_style="green" if self.plot is EMPTY else "red",
                box=rich.box.ROUNDED,
                height=self.height,
            )

        return rich.panel.Panel(self.plot)  # type: ignore[arg-type]
