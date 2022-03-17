from __future__ import annotations

from typing import Any

import plotext as plt
import rich.align
import rich.box
import rich.console
import rich.panel
import rich.pretty
import rich.text
import textual.widget
import uproot

import uproot_browser.dirs
import uproot_browser.plot

EMPTY = object()

LOGO = """\
Scikit-HEP
┬ ┬┌─┐┬─┐┌─┐┌─┐┌┬┐4 ┌┐ ┬─┐┌─┐┬ ┬┌─┐┌─┐┬─┐
│ │├─┘├┬┘│ ││ │ │───├┴┐├┬┘│ ││││└─┐├┤ ├┬┘
└─┘┴  ┴└─└─┘└─┘ ┴   └─┘┴└─└─┘└┴┘└─┘└─┘┴└─
                Powered by Textual & Hist"""


LOGO_PANEL = rich.panel.Panel(
    rich.align.Align.center(
        rich.text.Text.from_ansi(LOGO, no_wrap=True), vertical="middle"
    ),
    border_style="green",
    box=rich.box.ROUNDED,
)


def make_plot(item: Any, *size: int) -> Any:
    plt.clf()
    plt.plotsize(*size)
    uproot_browser.plot.plot(item)
    return plt.build()


class Plot:
    def __init__(self, item: Any) -> None:
        self.item: Any = item
        self.max_frames = 2

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width
        height = options.height or console.height
        try:
            canvas = make_plot(self.item, width, height)
            yield rich.text.Text.from_ansi(canvas)
        except Exception:
            tb = rich.traceback.Traceback(
                extra_lines=1,
                max_frames=self.max_frames,  # Can't be less than 4 frames
                width=width,
            )
            tb.max_frames = self.max_frames
            yield tb


class PlotWidget(textual.widget.Widget):
    def __init__(self, uproot_file: uproot.ReadOnlyFile) -> None:
        super().__init__()
        self.file = uproot_file
        self.plot: rich.panel.Panel | Plot | None = LOGO_PANEL
        self.plot_path: str | None = None

    def set_plot(self, plot_path: str | None) -> None:
        self.plot_path = plot_path
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
        if self.plot is None:
            return rich.panel.Panel(
                rich.align.Align.center(
                    rich.pretty.Pretty(
                        "No plot selected!", no_wrap=True, overflow="ellipsis"
                    ),
                    vertical="middle",
                ),
                border_style="red",
                box=rich.box.ROUNDED,
            )

        if isinstance(self.plot, rich.panel.Panel):
            return self.plot

        return rich.panel.Panel(self.plot)
