from __future__ import annotations

import dataclasses
import sys
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import plotext as plt  # plots in text
import rich.text

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


def make_plot(item: Any, theme: str, *size: int) -> Any:
    plt.clf()
    plt.plotsize(*size)
    uproot_browser.plot.plot(item)
    plt.theme(theme)
    return plt.build()


# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    theme: str
    app: Browser

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        *_, item = apply_selection(self.upfile, self.selection.split(":"))

        if item is None:
            self.app.view_widget.item = None
            return

        width = options.max_width or console.width
        height = options.height or console.height

        try:
            canvas = make_plot(item, self.theme, width, height)
            yield rich.text.Text.from_ansi(canvas)
        except EmptyTreeError:
            self.app.post_message(EmptyMessage())
        except Exception:
            exc = sys.exc_info()
            assert exc[1]
            self.app.post_message(ErrorMessage(Error(exc)))
