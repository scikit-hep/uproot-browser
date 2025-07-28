from __future__ import annotations

from typing import Any

import textual.app
import textual.containers
import textual.widgets

from .error import Error
from .logo import LOGO_PANEL
from .plot import Plotext


class ViewWidget(textual.containers.Container):
    def __init__(self, **kargs: Any):
        super().__init__(**kargs)
        self._item: Error | Plotext | None = None

    @property
    def item(self) -> Plotext | Error | None:
        return self._item

    @item.setter
    def item(self, value: Plotext | Error | None) -> None:
        self._item = value
        self.refresh(recompose=True)

    def compose(self) -> textual.app.ComposeResult:
        if self.item is None:
            yield textual.widgets.Static(LOGO_PANEL, id="logo")
        elif isinstance(self.item, Error):
            yield textual.containers.VerticalScroll(
                textual.widgets.Static(self.item, id="error")
            )
        else:
            yield textual.widgets.Static(self.item, id="plot")
