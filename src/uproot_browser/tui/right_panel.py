from __future__ import annotations

import rich.text
import textual.app
import textual.containers
import textual.reactive
import textual.widget
from textual.containers import Horizontal, Vertical
from textual.widgets import RadioButton, RadioSet


class SideBarWidget(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Stats(id="stats")
        yield Controls(id="controls")

    # def render(self) -> rich.console.RenderableType:
    #     return  "SIDEBAR"


# # wrapper for plotext into a textual widget
# @dataclasses.dataclass
# class Stats:

#     def __rich_console__(
#             self, console: rich.console.Console, options: rich.console.ConsoleOptions
#         ) -> rich.console.RenderResult:

#             yield textual.containers.Container(id="stats")

# class StatsWidget(textual.widget.Widget):
#     def render(self) -> rich.console.RenderableType:
#         return "MEAN \n STD DEV"


class Stats(textual.widget.Widget):
    def render(self) -> rich.console.RenderableType:
        return "\n Mean: \n\n Std Dev:"

    def on_mount(self) -> None:
        self.border_title = "Statistics"


class Controls(textual.widget.Widget):
    def compose(self) -> textual.app.ComposeResult:
        with Horizontal(), Vertical():
            # A RadioSet built up from RadioButtons.
            with RadioSet(id="one"):
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
                yield RadioButton("")
            yield textual.widgets.Label("Zoom")

    def render(self) -> rich.console.RenderableType:
        return "CONTROLS"

    def on_mount(self) -> None:
        self.border_title = "Controls"
