from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Any

import textual.app
import textual.containers
import textual.events
import textual.reactive
import textual.widgets

if TYPE_CHECKING:
    import textual_image.widget

from .error import Error
from .image_plot import MPLPlot
from .logo import LOGO_PANEL
from .messages import RequestImage
from .plot import Plotext


class PlotButton(textual.widgets.Button):
    def on_button_pressed(self) -> None:
        self.app.query_one("#plot-input", PlotInput).apply_expression()


class PlotInput(textual.widgets.Input):
    def watch_value(self, value: str) -> None:
        plot = self.app.query_one("#plot-view", ViewWidget)
        if isinstance(plot.item, Plotext):
            self.set_class(value not in {"", plot.item.expr}, "-needs-update")

    def on_input_submitted(self) -> None:
        self.apply_expression()

    def apply_expression(self) -> None:
        plot = self.app.query_one("#plot-view", ViewWidget)
        if isinstance(plot.item, Plotext):
            # assigning item triggers watch_item, which updates the plot
            plot.item = dataclasses.replace(plot.item, expr=self.value)
            self.set_class(False, "-needs-update")  # noqa: FBT003


class ViewWidget(textual.widgets.ContentSwitcher):
    item: textual.reactive.var[Error | Plotext | MPLPlot | None] = textual.reactive.var(
        None
    )

    def __init__(self, *, image: bool = False, **kargs: Any):
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

        children = [
            textual.widgets.Static(LOGO_PANEL, id="logo"),
            textual.containers.VerticalScroll(self.error_widget, id="error-scroll"),
            self.plot_window,
        ]

        self.image_widget: textual_image.widget.Image | None = None
        if image:
            # Deferred: importing textual_image queries the terminal, and the
            # matplotlib stack is only present with the [image] extra.
            import textual_image.widget  # noqa: PLC0415

            self.image_widget = textual_image.widget.Image(id="image-view")
            children.append(
                textual.containers.Container(self.image_widget, id="image-window")
            )

        super().__init__(*children, initial="logo", **kargs)

    def update_image(self, image: Any) -> None:
        assert self.image_widget is not None
        self.image_widget.image = image

    def image_pixel_size(self) -> tuple[int, int] | None:
        """Content size of the image pane in terminal pixels, if known."""
        import textual_image.widget  # noqa: PLC0415

        cell = textual_image.widget.get_cell_size()
        # subtract the #image-window padding (1 cell on each side)
        width = self.container_size.width - 2
        height = self.container_size.height - 2
        if width <= 0 or height <= 0:
            return None
        return (width * cell.width, height * cell.height)

    def on_resize(self, _event: textual.events.Resize) -> None:
        if isinstance(self.item, MPLPlot):
            self.post_message(RequestImage())

    def watch_item(self, value: Plotext | MPLPlot | Error | None) -> None:
        if isinstance(value, Plotext):
            self.plot_widget.update(value)
            self.current = "plot-window"
        elif isinstance(value, MPLPlot):
            self.current = "image-window"
        elif isinstance(value, Error):
            self.error_widget.update(value)
            self.current = "error-scroll"
        else:
            self.current = "logo"
