from __future__ import annotations

__lazy_modules__ = {"importlib", "importlib.metadata", "textual.app"}

import importlib.metadata

import textual.app
import textual.containers
import textual.widgets

from .. import __version__


class Info(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="uproot-browser", collapsed=False):
            yield textual.widgets.Static(f"Version: [green]{__version__}[/green]")
        with textual.widgets.Collapsible(title="Packages", collapsed=False):
            for dist in importlib.metadata.distributions():
                yield textual.widgets.Static(
                    f"{dist.metadata['Name']} == [green]{dist.version}[/green]"
                )
