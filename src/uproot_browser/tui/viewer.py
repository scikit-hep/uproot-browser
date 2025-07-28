from __future__ import annotations

from typing import Any

import textual.app
import textual.containers
import textual.reactive
import textual.widgets

from .error import Error
from .logo import LOGO_PANEL
from .plot import Plotext


class ViewWidget(textual.widgets.ContentSwitcher):
    item: textual.reactive.var[Error | Plotext | None] = textual.reactive.var(None)

    def __init__(self, **kargs: Any):
        self._item: Error | Plotext | None = None
        self.error_widget = textual.widgets.Static("", id="error")
        self.plot_widget = textual.widgets.Static("", id="plot")
        super().__init__(
            textual.widgets.Static(LOGO_PANEL, id="logo"),
            textual.containers.VerticalScroll(self.error_widget, id="error-scroll"),
            self.plot_widget,
            initial="logo",
            **kargs,
        )

    def watch_item(self, value: Plotext | Error | None) -> None:
        if isinstance(value, Plotext):
            self.plot_widget.update(value)
            self.current = "plot"
        elif isinstance(value, Error):
            self.error_widget.update(value)
            self.current = "error-scroll"
        else:
            self.current = "logo"
