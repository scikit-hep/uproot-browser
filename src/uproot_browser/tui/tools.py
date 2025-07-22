import importlib.metadata

import textual.containers
import textual.widgets

from .. import __version__


class Tools(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="Theme", collapsed=False):
            themes = self.app.available_themes
            yield textual.widgets.Select([(t, t) for t in themes], allow_blank=False)

    @textual.on(textual.widgets.Select.Changed)
    def select_changed(self, event: textual.widgets.Select.Changed) -> None:
        # pylint: disable-next=attribute-defined-outside-init
        self.app.theme = str(event.value)


class Info(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="uproot-browser", collapsed=False):
            yield textual.widgets.Label(f"Version: [green]{__version__}[/green]")
        with textual.widgets.Collapsible(title="Packages", collapsed=False):
            for dist in importlib.metadata.distributions():
                yield textual.widgets.Label(
                    f"{dist.metadata['Name']} == [green]{dist.version}[/green]"
                )
