from __future__ import annotations

import dataclasses
from typing import Any

import textual.app
import textual.containers
import textual.reactive
import textual.widgets

from .error import Error
from .logo import LOGO_PANEL
from .plot import Plotext


class PlotButton(textual.widgets.Button):
    def on_button_pressed(self) -> None:
        plot_input = self.app.query_one("#plot-input", PlotInput)
        plot_input.on_input_submitted()


class PlotInput(textual.widgets.Input):
    def watch_value(self, value: str) -> None:
        plot = self.app.query_one("#plot-view", ViewWidget)
        if isinstance(plot.item, Plotext):
            self.set_class(value not in {"", plot.item.expr}, "-needs-update")

    def on_input_submitted(self) -> None:
        plot = self.app.query_one("#plot-view", ViewWidget)
        if isinstance(plot.item, Plotext):
            plot.item = dataclasses.replace(plot.item, expr=self.value)
            self.set_class(False, "-needs-update")  # noqa: FBT003
            plot.plot_widget.update(plot.item)


class ViewWidget(textual.widgets.ContentSwitcher):
    item: textual.reactive.var[Error | Plotext | None] = textual.reactive.var(None)

    def __init__(self, **kargs: Any):
        self._item: Error | Plotext | None = None
        self.error_widget = textual.widgets.Static("", id="error")
        self.plot_widget = textual.widgets.Static("", id="plot")
        self.plot_input = PlotInput(
            id="plot-input",
            placeholder="h[:]",
            tooltip="The histogram is 'h', you can slice it. Experimental.",
        )
        self.plot_window = textual.containers.Container(
            textual.containers.Container(
                PlotButton("Plot", id="plot-button"),
                self.plot_input,
                id="plot-input-container",
            ),
            self.plot_widget,
            id="plot-window",
        )

        super().__init__(
            textual.widgets.Static(LOGO_PANEL, id="logo"),
            textual.containers.VerticalScroll(self.error_widget, id="error-scroll"),
            self.plot_window,
            initial="logo",
            **kargs,
        )

    def watch_item(self, value: Plotext | Error | None) -> None:
        if isinstance(value, Plotext):
            self.plot_widget.update(value)
            self.current = "plot-window"
        elif isinstance(value, Error):
            self.error_widget.update(value)
            self.current = "error-scroll"
        else:
            self.current = "logo"
