from __future__ import annotations

import typing
from typing import Any

import rich.text
import textual.app
import textual.reactive
import textual.widget
import textual.widgets

if typing.TYPE_CHECKING:
    from .browser import Browser


class HeaderCloseIcon(textual.widgets.Button):
    def on_click(self) -> None:
        self.app.exit()


class HeaderHelpIcon(textual.widgets.Button):
    app: Browser

    def on_click(self) -> None:
        self.app.action_help()


class HeaderTitle(textual.widget.Widget):
    text = textual.reactive.Reactive("")
    sub_text = textual.reactive.Reactive("")

    def render(self) -> textual.app.RenderResult:
        text = rich.text.Text(self.text, no_wrap=True, overflow="ellipsis")
        if self.sub_text:
            text.append(" — ")
            text.append(self.sub_text, "dim")
        return text


class Header(textual.widget.Widget):
    DEFAULT_CLASSES = ""

    def __init__(self, title: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> textual.app.ComposeResult:
        yield HeaderCloseIcon("❌", tooltip="Close")
        yield HeaderTitle()
        yield HeaderHelpIcon("❓", tooltip="Help")

    def on_mount(self) -> None:
        self.query_one(HeaderTitle).text = self.title
