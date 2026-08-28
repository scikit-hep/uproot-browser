from __future__ import annotations

import dataclasses

import rich.console
import rich.traceback


@dataclasses.dataclass
class Error:
    exc: BaseException

    def __rich_console__(
        self, console: rich.console.Console, options: rich.console.ConsoleOptions
    ) -> rich.console.RenderResult:
        width = options.max_width or console.width

        yield rich.traceback.Traceback.from_exception(
            type(self.exc), self.exc, self.exc.__traceback__, width=width
        )
