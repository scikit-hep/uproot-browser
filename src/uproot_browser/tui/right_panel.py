from __future__ import annotations

__lazy_modules__ = {
    "textual.app",
    "textual.validation",
    "typing",
    "uproot_browser.axis",
}

from typing import Any, ClassVar

import textual.app
import textual.binding
import textual.containers
import textual.message
import textual.validation
import textual.widgets

from uproot_browser.axis import AxisLimits

IMAGE_SCALES = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
LIMIT_IDS = ("x-min", "x-max", "y-min", "y-max")


class RightPanel(textual.containers.Container):
    """Typed X/Y range controls, image scale, and theme selector."""

    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        # Otherwise escape reaches the app binding and quits mid-edit
        textual.binding.Binding("escape", "focus_tree", "Back to tree", show=False),
    ]

    class LimitsChanged(textual.message.Message):
        """The user applied or reset the axis limits."""

        def __init__(self, limits: AxisLimits) -> None:
            super().__init__()
            self.limits = limits

    class ScaleChanged(textual.message.Message):
        """The user selected an image render scale."""

        def __init__(self, scale: float) -> None:
            super().__init__()
            self.scale = scale

    status = ""  # the last message shown in #axis-status

    def __init__(
        self, *, image: bool = False, image_scale: float = 1.5, **kwargs: Any
    ) -> None:
        super().__init__(**kwargs)
        self.image = image
        self.image_scale = image_scale

    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Axis ranges", collapsed=False):
            yield textual.widgets.Static(
                "Blank values use the automatic range.", id="axis-help"
            )
            for axis in "XY":
                with textual.containers.Horizontal(classes="axis-row"):
                    yield textual.widgets.Label(axis, classes="axis-label")
                    for end in ("min", "max"):
                        # Not type="number": it drops typed characters
                        # such as the comma in "1,5", which gives 15
                        yield textual.widgets.Input(
                            placeholder=end,
                            validators=[textual.validation.Number()],
                            valid_empty=True,
                            id=f"{axis.lower()}-{end}",
                        )
            yield textual.widgets.Label("", id="axis-status")
            with textual.containers.Horizontal(id="axis-buttons"):
                yield textual.widgets.Button(
                    "Apply", id="axis-apply", variant="primary"
                )
                yield textual.widgets.Button("Reset", id="axis-reset")
        if self.image:
            with textual.widgets.Collapsible(title="Render scale", collapsed=False):
                yield textual.widgets.Select(
                    [(f"{scale:g}×", scale) for scale in IMAGE_SCALES],
                    allow_blank=False,
                    value=self.image_scale,
                    id="image-scale-select",
                )
        with textual.widgets.Collapsible(title="Theme", collapsed=False):
            yield textual.widgets.Select(
                [(theme, theme) for theme in self.app.available_themes],
                allow_blank=False,
                value=self.app.theme,
                id="theme-select",
            )

    def on_mount(self) -> None:
        self.watch(self.app, "theme", self._sync_theme)

    def action_focus_tree(self) -> None:
        self.screen.query_one("#tree-view").focus()

    def _sync_theme(self, theme: str) -> None:
        self.query_one("#theme-select", textual.widgets.Select).value = theme

    def _parse_limit(self, control_id: str) -> float | None:
        field = self.query_one(f"#{control_id}", textual.widgets.Input)
        value = field.value.strip()
        if not value:
            return None
        result = field.validate(value)
        if result is not None and not result.is_valid:
            msg = "Axis limits must be finite numbers."
            raise ValueError(msg)
        return float(value)

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

    def clear(self) -> None:
        """Blank the fields and status (the limits no longer apply)."""
        for control_id in LIMIT_IDS:
            self.query_one(f"#{control_id}", textual.widgets.Input).value = ""
        self._set_status("")

    @textual.on(textual.widgets.Input.Submitted)
    @textual.on(textual.widgets.Button.Pressed, "#axis-apply")
    def _apply_ranges(self) -> None:
        try:
            limits = AxisLimits(x=self._parse_range("x"), y=self._parse_range("y"))
        except ValueError as err:
            self._set_status(str(err), error=True)
            return
        self.post_message(self.LimitsChanged(limits))
        self._set_status("Applied.")

    @textual.on(textual.widgets.Button.Pressed, "#axis-reset")
    def _reset_ranges(self) -> None:
        self.clear()
        self.post_message(self.LimitsChanged(AxisLimits()))
        self._set_status("Automatic ranges restored.")

    @textual.on(textual.widgets.Select.Changed, "#image-scale-select")
    def _image_scale_changed(self, event: textual.widgets.Select.Changed) -> None:
        assert isinstance(event.value, float)
        self.post_message(self.ScaleChanged(event.value))

    @textual.on(textual.widgets.Select.Changed, "#theme-select")
    def _theme_changed(self, event: textual.widgets.Select.Changed) -> None:
        # pylint: disable-next=attribute-defined-outside-init
        self.app.theme = str(event.value)
