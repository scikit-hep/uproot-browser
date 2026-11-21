from __future__ import annotations

__lazy_modules__ = {
    "textual.app",
    "textual.containers",
    "textual.timer",
    "uproot_browser.tui.error",
    "uproot_browser.tui.logo",
    "uproot_browser.tui.messages",
    "uproot_browser.tui.plot",
}

from typing import TYPE_CHECKING, Any, ClassVar

import textual
import textual.app
import textual.binding
import textual.containers
import textual.message
import textual.reactive
import textual.timer
import textual.widget
import textual.widgets

if TYPE_CHECKING:
    from collections.abc import Callable

    import textual_image.widget

from uproot_browser.tui.error import Error
from uproot_browser.tui.logo import LOGO_PANEL
from uproot_browser.tui.messages import RequestRender
from uproot_browser.tui.plot import PlotItem


class PlotInput(textual.widgets.Input):
    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("escape", "app.toggle_entry_box", "Close", show=False),
    ]


class PlotResized(textual.message.Message):
    """The plot pane changed size. This can occur without a resize of the view."""


class ResizeNotifier(textual.widget.Widget):
    """Base for a plot widget. Posts `PlotResized`, as a Resize event does not bubble."""

    def on_resize(self) -> None:
        self.post_message(PlotResized())


class PlotCanvas(ResizeNotifier, textual.widgets.Static):
    """The text plot."""


class ViewWidget(textual.widgets.ContentSwitcher):
    item: textual.reactive.var[Error | PlotItem | None] = textual.reactive.var(None)

    def __init__(self, *, image: bool = False, **kargs: Any):
        self.error_widget = textual.widgets.Static("", id="error")
        self.plot_widget = PlotCanvas("", id="plot")
        self.plot_input = PlotInput(
            id="plot-input",
            placeholder="h[:] or tree['branch'].array()",
            tooltip=(
                "Use h for the histogram and tree for its containing "
                "TTree/RNTuple, when available. Press Enter to apply."
            ),
        )
        # The entry box goes into whichever window the active mode uses
        self.input_container = textual.containers.Container(
            textual.widgets.Button("Plot", id="plot-button"),
            self.plot_input,
            id="plot-input-container",
        )
        self.plot_window = textual.containers.Container(
            *([] if image else [self.input_container]),
            self.plot_widget,
            id="plot-window",
        )

        children = [
            textual.widgets.Static(LOGO_PANEL, id="logo"),
            textual.containers.VerticalScroll(self.error_widget, id="error-scroll"),
            self.plot_window,
        ]

        self.image_widget: textual_image.widget.Image | None = None
        self._get_cell_size: Callable[[], Any] | None = None
        self.resize_timer: textual.timer.Timer | None = None
        if image:
            # Deferred: importing textual_image queries the terminal, and the
            # matplotlib stack is only present with the [image] extra.
            import textual_image.widget  # noqa: PLC0415

            image_base = textual_image.widget.Image

            class PlotImage(
                ResizeNotifier,
                image_base,  # type: ignore[valid-type,misc]
                Renderable=image_base._Renderable,  # noqa: SLF001
            ):
                pass

            self._get_cell_size = textual_image.widget.get_cell_size
            self.image_widget = PlotImage(id="image-view")
            children.append(
                textual.containers.Container(
                    self.input_container, self.image_widget, id="image-window"
                )
            )

        super().__init__(*children, initial="logo", **kargs)

    def image_pixel_size(self) -> tuple[int, int] | None:
        """Content size of the image pane in terminal pixels, if known."""
        assert self._get_cell_size is not None
        assert self.image_widget is not None
        cell = self._get_cell_size()
        content = self.image_widget.content_size
        width, height = content.width, content.height
        if not width or not height:
            # The first display switches window and requests an image at once,
            # so the widget can have no layout yet: compute the area it gets.
            # Subtract the #image-window padding (1 cell on each side).
            width = self.container_size.width - 2
            height = self.container_size.height - 2
            if self.input_container.display:
                # the entry box docks at the bottom of the image window
                height -= self.input_container.outer_size.height
        if width <= 0 or height <= 0:
            return None
        return (width * cell.width, height * cell.height)

    def request_render(self) -> None:
        """Ask the app to render the current item at the size the view gives it now."""
        if isinstance(self.item, PlotItem):
            self.post_message(RequestRender())

    @textual.on(textual.widgets.Button.Pressed, "#plot-button")
    @textual.on(textual.widgets.Input.Submitted, "#plot-input")
    def apply_expression(self) -> None:
        """Plot the current item with the expression in the entry box."""
        if isinstance(self.item, PlotItem):
            # assigning item triggers watch_item, which updates the plot
            self.item = self.item.with_expr(self.plot_input.value)
            self.plot_input.set_class(False, "-needs-update")  # noqa: FBT003

    @textual.on(textual.widgets.Input.Changed, "#plot-input")
    def _expression_changed(self, event: textual.widgets.Input.Changed) -> None:
        if isinstance(self.item, PlotItem):
            needs_update = event.value not in {"", self.item.expr}
            self.plot_input.set_class(needs_update, "-needs-update")

    @textual.on(PlotResized)
    def on_resize(self) -> None:
        # Debounce so a drag-resize only renders the settled size
        if self.resize_timer is not None:
            self.resize_timer.stop()
        self.resize_timer = self.set_timer(0.2, self.request_render)

    def watch_item(self, value: PlotItem | Error | None) -> None:
        if value is None:
            self.current = "logo"
        elif isinstance(value, Error):
            self.error_widget.update(value)
            self.current = "error-scroll"
        else:
            value.display(self)
