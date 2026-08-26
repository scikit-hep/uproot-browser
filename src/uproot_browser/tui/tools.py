from __future__ import annotations

import importlib.metadata

import textual.app
import textual.containers
import textual.widgets

from .. import __version__
from .messages import ImageScaleChanged

IMAGE_SCALES = [1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


class Tools(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Theme", collapsed=False):
            themes = self.app.available_themes
            yield textual.widgets.Select(
                [(t, t) for t in themes],
                allow_blank=False,
                value=self.app.theme,
                id="theme-select",
            )
        with (
            textual.widgets.Collapsible(title="Plot", collapsed=False),
            textual.containers.Horizontal(),
        ):
            yield textual.widgets.Label("Entry box")
            yield textual.widgets.Switch()
        if getattr(self.app, "image", False):
            with textual.widgets.Collapsible(title="Image scale", collapsed=False):
                yield textual.widgets.Select(
                    [(f"{s:g}×", s) for s in IMAGE_SCALES],
                    allow_blank=False,
                    value=getattr(self.app, "image_scale", 1.5),
                    id="image-scale-select",
                )

    def on_mount(self) -> None:
        # Keep the Select in sync with the app theme. init=True syncs the value
        # immediately, so this also catches a theme set before this lazy widget
        # mounted — no race between mounting and tracking.
        self.watch(self.app, "theme", self._sync_theme)

    def _sync_theme(self, theme: str) -> None:
        self.query_one("#theme-select", textual.widgets.Select).value = theme

    @textual.on(textual.widgets.Switch.Changed)
    def switch_changed(self, event: textual.widgets.Switch.Changed) -> None:
        self.app.query_one("#plot-input-container").set_class(
            event.value, "-show-container"
        )

    @textual.on(textual.widgets.Select.Changed, "#theme-select")
    def theme_changed(self, event: textual.widgets.Select.Changed) -> None:
        # pylint: disable-next=attribute-defined-outside-init
        self.app.theme = str(event.value)

    @textual.on(textual.widgets.Select.Changed, "#image-scale-select")
    def image_scale_changed(self, event: textual.widgets.Select.Changed) -> None:
        assert isinstance(event.value, float)
        self.post_message(ImageScaleChanged(event.value))


class Info(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="uproot-browser", collapsed=False):
            yield textual.widgets.Static(f"Version: [green]{__version__}[/green]")
        with textual.widgets.Collapsible(title="Packages", collapsed=False):
            for dist in importlib.metadata.distributions():
                yield textual.widgets.Static(
                    f"{dist.metadata['Name']} == [green]{dist.version}[/green]"
                )
