from __future__ import annotations

__lazy_modules__ = {"math", "textual.app", f"{__spec__.parent}.axis"}

import math
from typing import TYPE_CHECKING, cast

import textual.app
import textual.containers
import textual.widgets

from .axis import AxisLimits, AxisRange

if TYPE_CHECKING:
    from ..browser import Browser


IMAGE_SCALES = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


class AxisControls(textual.containers.Container):
    """Typed X/Y range controls and image scale for the active plot."""

    def compose(self) -> textual.app.ComposeResult:
        yield textual.widgets.Label("Axis scaling", id="axis-title")
        yield textual.widgets.Static(
            "Type numeric limits and press Enter. Blank values use the automatic range.",
            id="axis-help",
        )
        with textual.containers.Vertical(classes="axis-section"):
            yield textual.widgets.Label("X range", classes="axis-label")
            with textual.containers.Horizontal(classes="axis-row"):
                yield textual.widgets.Input(placeholder="X min", id="x-min")
                yield textual.widgets.Input(placeholder="X max", id="x-max")
            yield textual.widgets.Label("Y range", classes="axis-label")
            with textual.containers.Horizontal(classes="axis-row"):
                yield textual.widgets.Input(placeholder="Y min", id="y-min")
                yield textual.widgets.Input(placeholder="Y max", id="y-max")
        yield textual.widgets.Label("", id="axis-status")
        yield textual.widgets.Button("Apply ranges", id="axis-apply", variant="primary")
        yield textual.widgets.Button("Reset to automatic", id="axis-reset")
        app = cast("Browser", self.app)
        if app.image:
            with textual.containers.Vertical(
                classes="axis-section image-scale-section"
            ):
                yield textual.widgets.Label("Render scale", classes="axis-label")
                yield textual.widgets.Select(
                    [(f"{scale:g}×", scale) for scale in IMAGE_SCALES],
                    allow_blank=False,
                    value=app.image_scale,
                    id="image-scale-select",
                )

    def _parse_range(self, minimum_id: str, maximum_id: str) -> AxisRange:
        values: list[float | None] = []
        for control_id in (minimum_id, maximum_id):
            value = self.query_one(
                f"#{control_id}", textual.widgets.Input
            ).value.strip()
            parsed = float(value) if value else None
            if parsed is not None and not math.isfinite(parsed):
                msg = "Axis limits must be finite numbers."
                raise ValueError(msg)
            values.append(parsed)
        result = (values[0], values[1])
        if result[0] is not None and result[1] is not None and result[0] >= result[1]:
            msg = "Minimum must be smaller than maximum."
            raise ValueError(msg)
        return result

    def _set_status(self, message: str, *, error: bool = False) -> None:
        status = self.query_one("#axis-status", textual.widgets.Label)
        status.update(message)
        status.set_class(error, "-error")

    def _apply_ranges(self) -> None:
        try:
            limits = AxisLimits(
                x=self._parse_range("x-min", "x-max"),
                y=self._parse_range("y-min", "y-max"),
            )
        except ValueError as err:
            self._set_status(str(err), error=True)
            return
        cast("Browser", self.app).axis_limits = limits  # pylint: disable=attribute-defined-outside-init
        self._set_status("Applied.")

    def _reset_ranges(self) -> None:
        for control_id in ("x-min", "x-max", "y-min", "y-max"):
            self.query_one(f"#{control_id}", textual.widgets.Input).value = ""
        cast("Browser", self.app).axis_limits = AxisLimits()  # pylint: disable=attribute-defined-outside-init
        self._set_status("Automatic ranges restored.")

    def on_input_submitted(self, _event: textual.widgets.Input.Submitted) -> None:
        self._apply_ranges()

    def on_button_pressed(self, event: textual.widgets.Button.Pressed) -> None:
        if event.button.id == "axis-apply":
            self._apply_ranges()
        elif event.button.id == "axis-reset":
            self._reset_ranges()

    @textual.on(textual.widgets.Select.Changed, "#image-scale-select")
    def image_scale_changed(self, event: textual.widgets.Select.Changed) -> None:
        assert isinstance(event.value, float)
        cast("Browser", self.app).image_scale = event.value  # pylint: disable=attribute-defined-outside-init
