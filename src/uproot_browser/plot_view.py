from __future__ import annotations

from typing import Any

import numpy as np
import plotext as plt
import rich.align
import rich.ansi
import rich.box
import rich.console
import rich.panel
import rich.pretty
import rich.text
import textual.view
import textual.widget
import uproot

import uproot_browser.dirs
import uproot_browser.plot

EMPTY = object()


def make_plot(item: Any, *size: int) -> Any:
    plt.clf()
    plt.plotsize(*size)
    h = uproot_browser.plot.plot(item)
    if math.isclose(np.sum(h.values()), np.sum(h.values(flow=True))):
        plt.title(f"{item.name} - Entries = {np.sum(h.values()):g}")
    else:
        plt.title(
            f"{item.name} - Entries = {np.sum(h.values()):g} ({np.sum(h.values(flow=True))} with flow)"
        )
    plt.xlabel(f"{h.axes[0].name}")
    return plt.build()


class Plot:
    def __init__(self, item: Any) -> None:
        self.decoder = rich.ansi.AnsiDecoder()
        self.item: Any = item

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width
        height = options.height or console.height
        try:
            canvas = make_plot(self.item, width, height)
            yield rich.console.Group(*self.decoder.decode(canvas))
        except Exception:
            rich_canvas = rich.traceback.Traceback(
                extra_lines=1,
                max_frames=4,  # Can't be less than 4 frames
            )

            if options.height is not None:
                options.height -= 4
            yield from rich_canvas.__rich_console__(console, options)


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
                height=self.height,
            )

        if self.plot is EMPTY:
            return rich.panel.Panel(
                rich.align.Align.center(
                    rich.text.Text.from_ansi(
                        """
┬ ┬┌─┐┬─┐┌─┐┌─┐┌┬┐4 ┌┐ ┬─┐┌─┐┬ ┬┌─┐┌─┐┬─┐
│ │├─┘├┬┘│ ││ │ │───├┴┐├┬┘│ ││││└─┐├┤ ├┬┘
└─┘┴  ┴└─└─┘└─┘ ┴   └─┘┴└─└─┘└┴┘└─┘└─┘┴└─
                          powered by Hist""",
                        no_wrap=True,
                    ),
                    vertical="middle",
                ),
                border_style="green",
                box=rich.box.ROUNDED,
                height=self.height,
            )

        return rich.panel.Panel(self.plot)  # type: ignore[arg-type]
