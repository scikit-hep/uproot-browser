from __future__ import annotations

import typing

import textual.app
import textual.binding
import textual.containers
import textual.screen
import textual.widgets

if typing.TYPE_CHECKING:
    from .browser import Browser

    # 0.18's ModalScreen is not subscriptable. Later versions are.
    ModalScreen = textual.screen.ModalScreen[None]
else:
    ModalScreen = textual.screen.ModalScreen

from .._compat.importlib.resources import files


class HelpScreen(ModalScreen):
    BINDINGS = [
        textual.binding.Binding("d", "", "Nothing", show=False),
        textual.binding.Binding("b", "", "Nothing", show=False),
        textual.binding.Binding("f1", "", "Nothing", show=False),
        textual.binding.Binding("q", "done", "Done", show=True),
        textual.binding.Binding("esc", "done", "Done", show=True),
        textual.binding.Binding("t", "toggle_theme", "Theme", show=True),
    ]

    app: Browser

    def compose(self) -> textual.app.ComposeResult:
        markdown = files("uproot_browser.tui").joinpath("README.md").read_text()
        with textual.containers.Container(id="help-dialog", classes="dialog"):
            yield textual.widgets.MarkdownViewer(markdown, id="help-text")
            with textual.containers.Container(id="help-buttons"):
                yield textual.widgets.Button("Done", variant="primary", id="help-done")

    def on_mount(self) -> None:
        self.query_one(textual.widgets.Markdown).focus()

    def on_button_pressed(self, _event: textual.widgets.Button.Pressed) -> None:
        self.app.pop_screen()

    def action_done(self) -> None:
        self.app.pop_screen()

    def action_toggle_theme(self) -> None:
        self.app.action_toggle_theme()
