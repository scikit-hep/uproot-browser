from __future__ import annotations

import dataclasses
from types import TracebackType

import rich.console
import rich.traceback


@dataclasses.dataclass
class Error:
    exc: tuple[type[BaseException], BaseException, TracebackType]

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width

        yield rich.traceback.Traceback.from_exception(*self.exc, width=width)
