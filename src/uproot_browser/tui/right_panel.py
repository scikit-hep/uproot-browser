from __future__ import annotations

__lazy_modules__ = {"math", "textual.app", "uproot_browser.axis"}

import math
from typing import TYPE_CHECKING, cast

import textual.app
import textual.containers
import textual.widgets

from uproot_browser.axis import AxisLimits

if TYPE_CHECKING:
    from .browser import Browser


IMAGE_SCALES = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
LIMIT_IDS = ("x-min", "x-max", "y-min", "y-max")


class RightPanel(textual.containers.Container):
    """Typed X/Y range controls and image scale for the active plot."""

    status = ""  # the last message shown in #axis-status

    @property
    def browser(self) -> Browser:
        return cast("Browser", self.app)

    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Axis ranges", collapsed=False):
            yield textual.widgets.Static(
                "Blank values use the automatic range.", id="axis-help"
            )
            for axis in "XY":
                with textual.containers.Horizontal(classes="axis-row"):
                    yield textual.widgets.Label(axis, classes="axis-label")
                    for end in ("min", "max"):
                        yield textual.widgets.Input(
                            placeholder=end, id=f"{axis.lower()}-{end}"
                        )
            yield textual.widgets.Label("", id="axis-status")
            with textual.containers.Horizontal(id="axis-buttons"):
                yield textual.widgets.Button(
                    "Apply", id="axis-apply", variant="primary"
                )
                yield textual.widgets.Button("Reset", id="axis-reset")
        if self.browser.image:
            with textual.widgets.Collapsible(title="Render scale", collapsed=False):
                yield textual.widgets.Select(
                    [(f"{scale:g}×", scale) for scale in IMAGE_SCALES],
                    allow_blank=False,
                    value=self.browser.image_scale,
                    id="image-scale-select",
                )

    def _parse_limit(self, control_id: str) -> float | None:
        value = self.query_one(f"#{control_id}", textual.widgets.Input).value.strip()
        if not value:
            return None
        try:
            parsed = float(value)
        except ValueError:
            parsed = math.nan
        if not math.isfinite(parsed):
            msg = f"Axis limits must be finite numbers, not {value!r}."
            raise ValueError(msg)
        return parsed

    def _parse_range(self, axis: str) -> tuple[float | None, float | None]:
        lower = self._parse_limit(f"{axis}-min")
        upper = self._parse_limit(f"{axis}-max")
        if lower is not None and upper is not None and lower >= upper:
            msg = "Minimum must be smaller than maximum."
            raise ValueError(msg)
        return lower, upper

    def _set_status(self, message: str, *, error: bool = False) -> None:
        self.status = message
        status = self.query_one("#axis-status", textual.widgets.Label)
        status.update(message)
        status.set_class(error, "-error")

    def _apply_ranges(self) -> None:
        try:
            limits = AxisLimits(x=self._parse_range("x"), y=self._parse_range("y"))
        except ValueError as err:
            self._set_status(str(err), error=True)
            return
        # pylint: disable-next=attribute-defined-outside-init
        self.browser.axis_limits = limits
        self._set_status("Applied.")

    def clear(self) -> None:
        """Blank the fields and status (the limits no longer apply)."""
        for control_id in LIMIT_IDS:
            self.query_one(f"#{control_id}", textual.widgets.Input).value = ""
        self._set_status("")

    def _reset_ranges(self) -> None:
        self.clear()
        # pylint: disable-next=attribute-defined-outside-init
        self.browser.axis_limits = AxisLimits()
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
        # pylint: disable-next=attribute-defined-outside-init
        self.browser.image_scale = event.value
