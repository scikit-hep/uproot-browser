import importlib.metadata

import textual.containers
import textual.widgets

from .. import __version__


class Tools(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Theme", collapsed=False):
            themes = self.app.available_themes
            yield textual.widgets.Select([(t, t) for t in themes], allow_blank=False)
        with textual.widgets.Collapsible(title="Plot", collapsed=False):
            with textual.containers.Horizontal():
                yield textual.widgets.Label("Entry box")
                yield textual.widgets.Switch()

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
