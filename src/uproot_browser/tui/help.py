from __future__ import annotations

import typing
from importlib.resources import files
from typing import ClassVar

import textual.app
import textual.binding
import textual.containers
import textual.screen
import textual.widgets

if typing.TYPE_CHECKING:
    from .browser import Browser


class HelpScreen(textual.screen.ModalScreen[None]):
    BINDINGS: ClassVar[
        list[textual.binding.Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        textual.binding.Binding("d", "", "Nothing", show=False),
        textual.binding.Binding("b", "", "Nothing", show=False),
        textual.binding.Binding("f1", "", "Nothing", show=False),
        textual.binding.Binding("q", "done", "Done", show=True),
        textual.binding.Binding("escape", "done", "Done", show=True),
    ]

    app: Browser

    def compose(self) -> textual.app.ComposeResult:
        markdown = files("uproot_browser.tui").joinpath("README.md").read_text()
        with textual.containers.Container(id="help-dialog", classes="dialog"):
            yield textual.widgets.MarkdownViewer(markdown, id="help-text")
            with textual.containers.Container(id="help-buttons"):
                yield textual.widgets.Button("Done", variant="primary", id="help-done")

    def on_mount(self) -> None:
        self.query_one("#help-text", textual.widgets.MarkdownViewer).focus()

    def on_button_pressed(self, _event: textual.widgets.Button.Pressed) -> None:
        self.app.pop_screen()

    def action_done(self) -> None:
        self.app.pop_screen()
