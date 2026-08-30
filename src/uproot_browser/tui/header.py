from __future__ import annotations

__lazy_modules__ = {"rich", "rich.text", "textual.app"}

import typing
from typing import Any

import rich.text
import textual.app
import textual.widget
import textual.widgets

if typing.TYPE_CHECKING:
    from .browser import Browser


class HeaderCloseIcon(textual.widgets.Button):
    def on_button_pressed(self, _: textual.widgets.Button.Pressed) -> None:
        self.app.exit()


class HeaderHelpIcon(textual.widgets.Button):
    app: Browser

    def on_button_pressed(self, _: textual.widgets.Button.Pressed) -> None:
        self.app.action_help()


class HeaderTitle(textual.widgets.Static):
    pass


class Header(textual.widget.Widget):
    DEFAULT_CLASSES = ""

    def __init__(self, title: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> textual.app.ComposeResult:
        yield HeaderCloseIcon("❌", tooltip="Close")
        yield HeaderTitle(rich.text.Text(self.title, no_wrap=True, overflow="ellipsis"))
        yield HeaderHelpIcon("❓", tooltip="Help")
