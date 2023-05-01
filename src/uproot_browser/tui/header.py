from __future__ import annotations

from typing import Any

import rich.text
import textual.app
import textual.reactive
import textual.widget


class HeaderCloseIcon(textual.widget.Widget):
    DEFAULT_CSS = """
    HeaderCloseIcon {
        dock: left;
        padding: 0 1;
        width: 4;
        content-align: left middle;
    }
    HeaderCloseIcon:hover {
        background: $panel-lighten-2;
    }
    """

    icon = textual.reactive.Reactive("❌")

    def render(self) -> textual.app.RenderResult:
        return self.icon

    def on_click(self) -> None:
        self.app.exit()


class HeaderTitle(textual.widget.Widget):
    DEFAULT_CSS = """
    HeaderTitle {
        content-align: center middle;
        width: 100%;
    }
    """

    text = textual.reactive.Reactive("")
    sub_text = textual.reactive.Reactive("")

    def render(self) -> textual.app.RenderResult:
        text = rich.text.Text(self.text, no_wrap=True, overflow="ellipsis")
        if self.sub_text:
            text.append(" — ")
            text.append(self.sub_text, "dim")
        return text


class HeaderSpace(textual.widget.Widget):
    DEFAULT_CSS = """
    HeaderSpace {
        dock: right;
        width: 4;
        content-align: left middle;
    }
    """

    def render(self) -> textual.app.RenderResult:
        return ""


class Header(textual.widget.Widget):
    DEFAULT_CSS = """
    Header {
        dock: top;
        width: 100%;
        background: $foreground 5%;
        color: $text;
        height: 1;
    }
    """

    DEFAULT_CLASSES = ""

    def __init__(self, title: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> textual.app.ComposeResult:
        yield HeaderCloseIcon()
        yield HeaderTitle()
        yield HeaderSpace()

    def on_mount(self) -> None:
        self.query_one(HeaderTitle).text = self.title
