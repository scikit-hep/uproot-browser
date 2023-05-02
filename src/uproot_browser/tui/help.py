from __future__ import annotations

import typing
from typing import ClassVar

import textual.app
import textual.binding
import textual.containers
import textual.screen
import textual.widgets

if typing.TYPE_CHECKING:
    from .browser import Browser

MD = """

# Uproot Browser

Welcome to uproot-browser!

## Navigation

Use the arrow keys to navigate the tree view. Press `enter` to select a
something to plot. Press `spacebar` to open/close a directory or tree. You can
also use the VIM keys: `j` to move down, `k` to move up, `l` to open a folder,
and `h` to close a folder.

## Plotting

Histograms, rectangular simple data (e.g. TTree's), and jagged arrays can
be plotted. Click on an item or press `enter` to plot. If something can't
be plotted, you'll see a scrollable error traceback.

## Themes

You can press `t` to toggle light and dark mode.

## Leaving

You can press `q` to quit. You can also press `d` to quit with a dump of the
current plot and how to get the object being plotted in Python uproot code.

## Exiting the help.

You can press `esc` or `q` to exit this help screen. You can also use `tab` to
switch between the panes in the help screen.

# Credits

Uproot browser was created by Henry Schreiner and Aman Goel. It was rewritten
by Elie Svoll and Jose Garcia to use the modern CSS-based Textaul library.

Uproot browser is made possible by the Scikit-HEP ecosystem, including uproot
and awkward-array for data reading, hist and boost-histogram for computation.
The TUI (terminal user interface) was built using the Textual library.
Text-based plotting is provided by plotext.
"""


class HelpScreen(textual.screen.ModalScreen[None]):
    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("q", "done", "Done", show=False),
        textual.binding.Binding("esc", "done", "Done", show=False),
        textual.binding.Binding(
            "t", "toggle_theme", "Toggle light/dark theme", show=False
        ),
    ]

    app: Browser

    def compose(self) -> textual.app.ComposeResult:
        with textual.containers.Container(id="help-dialog", classes="dialog"):
            yield textual.widgets.MarkdownViewer(MD, id="help-text")
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
