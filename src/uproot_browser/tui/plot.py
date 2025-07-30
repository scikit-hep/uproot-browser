from __future__ import annotations

import dataclasses
import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import plotext as plt  # plots in text
import rich.text
import textual.widgets

import uproot_browser.plot
from uproot_browser.exceptions import EmptyTreeError

from .error import Error
from .messages import EmptyMessage, ErrorMessage

if TYPE_CHECKING:
    from .browser import Browser


def apply_selection(tree: Any, selection: Iterable[str]) -> Iterable[Any]:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    for sel in selection:
        tree = tree[sel]
        yield tree


def make_plot(item: Any, theme: str, *size: int, expr: str) -> Any:
    plt.clf()
    plt.theme(theme)
    plt.plotsize(*size)
    uproot_browser.plot.plot(item, expr=expr)
    return plt.build()


# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    theme: str
    app: Browser
    expr: str = ""

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        *_, item = apply_selection(
            self.upfile, [s for s in self.selection.split("/") if s]
        )

        if item is None:
            self.app.post_message(EmptyMessage())
            return

        width = options.max_width or console.width
        height = options.height or console.height

        try:
            canvas = make_plot(item, self.theme, width, height, expr=self.expr)
            yield rich.text.Text.from_ansi(canvas)
        except EmptyTreeError:
            self.app.post_message(EmptyMessage())
        except Exception:
            self.app.query_one("#plot-input", textual.widgets.Input).value = ""
            exc = sys.exc_info()
            assert exc[1]
            self.app.post_message(ErrorMessage(Error(exc)))
