from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING, Any

import plotext as plt  # plots in text
import rich.text

import uproot_browser.plot
from uproot_browser.exceptions import EmptyTreeError

from .error import Error
from .messages import EmptyMessage, ErrorMessage, RequestPlot

if TYPE_CHECKING:
    from collections.abc import Iterable

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
    uproot_browser.plot.plot(item, width=(size[0] - 5) * 4, expr=expr)
    return plt.build()


# wrapper for plotext into a textual widget
@dataclasses.dataclass
class Plotext:
    upfile: Any
    selection: str
    theme: str
    app: Browser
    expr: str = ""
    size: tuple[int, int] | None = None
    previous: rich.text.Text | None = None
    old_expr: str = ""

    def make_plot(self) -> Plotext | None:
        *_, item = apply_selection(self.upfile, self.selection.split(":"))
        assert self.size
        try:
            canvas = make_plot(item, self.theme, *self.size, expr=self.expr)
            return dataclasses.replace(self, previous=rich.text.Text.from_ansi(canvas))
        except EmptyTreeError:
            self.app.post_message(EmptyMessage())
            return None
        except Exception:  # noqa: BLE001
            exc = sys.exc_info()
            assert exc[1]
            self.app.post_message(ErrorMessage(Error(exc)))
            return None

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

        if (
            self.size
            and (width, height) == self.size
            and self.previous is not None
            and self.old_expr == self.expr
        ):
            yield self.previous

        else:
            self.size = (width, height)
            self.previous = rich.text.Text("... plotting ...")
            self.old_expr = self.expr
            yield self.previous
            self.app.post_message(RequestPlot(self))
