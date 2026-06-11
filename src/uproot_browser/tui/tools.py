from __future__ import annotations

import importlib.metadata
from typing import TYPE_CHECKING

import textual.app
import textual.containers
import textual.widgets

from .. import __version__

if TYPE_CHECKING:
    from textual.theme import Theme


class Tools(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Theme", collapsed=False):
            themes = self.app.available_themes
            yield textual.widgets.Select(
                [(t, t) for t in themes], allow_blank=False, value=self.app.theme
            )
        with (
            textual.widgets.Collapsible(title="Plot", collapsed=False),
            textual.containers.Horizontal(),
        ):
            yield textual.widgets.Label("Entry box")
            yield textual.widgets.Switch()

    def on_mount(self) -> None:
        self.app.theme_changed_signal.subscribe(self, self._on_theme_change)

    def _on_theme_change(self, theme: Theme) -> None:
        self.query_one(textual.widgets.Select).value = theme.name

    @textual.on(textual.widgets.Switch.Changed)
    def switch_changed(self, event: textual.widgets.Switch.Changed) -> None:
        self.app.query_one("#plot-input-container").set_class(
            event.value, "-show-container"
        )

    @textual.on(textual.widgets.Select.Changed)
    def select_changed(self, event: textual.widgets.Select.Changed) -> None:
        # pylint: disable-next=attribute-defined-outside-init
        self.app.theme = str(event.value)


class Info(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="uproot-browser", collapsed=False):
            yield textual.widgets.Static(f"Version: [green]{__version__}[/green]")
        with textual.widgets.Collapsible(title="Packages", collapsed=False):
            for dist in importlib.metadata.distributions():
                yield textual.widgets.Static(
                    f"{dist.metadata['Name']} == [green]{dist.version}[/green]"
                )
