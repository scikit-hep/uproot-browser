from __future__ import annotations

import dataclasses
import sys
from typing import TYPE_CHECKING, Any, TypeVar

import plotext as plt  # plots in text
import rich.text

import uproot_browser.plot
from uproot_browser.exceptions import EmptyTreeError

from .error import Error
from .messages import EmptyMessage, ErrorMessage, RequestPlot

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from .browser import Browser

T = TypeVar("T")


def run_posting_errors(app: Browser, fn: Callable[[], T]) -> T | None:
    """Run ``fn``, posting an Empty/Error message to the app on failure."""
    try:
        return fn()
    except EmptyTreeError:
        app.post_message(EmptyMessage())
        return None
    except Exception:  # noqa: BLE001
        exc = sys.exc_info()
        assert exc[1]
        app.post_message(ErrorMessage(Error(exc)))
        return None


def apply_selection(tree: Any, selection: Iterable[str]) -> Iterable[Any]:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    for sel in selection:
        tree = tree[sel]
        yield tree


def make_plot(item: Any, theme: str, *size: int, expr: str) -> Any:
    fig = plt.figure
    fig.clear()
    fig.theme(theme)
    fig.plot_size(*size)
    uproot_browser.plot.plot(item, fig=fig, width=size[0] - 5, expr=expr)
    return str(fig.build())


def make_dump(item: Any, *size: int, expr: str = "") -> str:
    """Standalone Python source rebuilding the plotted histogram as ``h``."""
    width = size[0] - 5 if size else 100
    code = uproot_browser.plot.dump(item, width=width)
    if expr:
        code += f"\nh = {expr}"
    return code


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
        size = self.size
        assert size

        def build() -> Plotext:
            *_, item = apply_selection(self.upfile, self.selection.split(":"))
            canvas = make_plot(item, self.theme, *size, expr=self.expr)
            return dataclasses.replace(self, previous=rich.text.Text.from_ansi(canvas))

        return run_posting_errors(self.app, build)

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
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
