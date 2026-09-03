from __future__ import annotations

from typing import TYPE_CHECKING, Any

import rich.repr
import textual.message

if TYPE_CHECKING:
    from .error import Error


@rich.repr.auto
class UprootSelected(textual.message.Message, bubble=True):
    def __init__(self, upfile: Any, path: str) -> None:
        self.upfile = upfile
        self.path = path
        super().__init__()


@rich.repr.auto
class EmptyMessage(textual.message.Message, bubble=True):
    pass


@rich.repr.auto
class ErrorMessage(textual.message.Message, bubble=True):
    def __init__(self, err: Error) -> None:
        self.err = err
        super().__init__()


@rich.repr.auto
class RequestPlot(textual.message.Message, bubble=True):
    """Ask the app to re-render the current text plot (e.g. after a resize)."""


@rich.repr.auto
class RequestImage(textual.message.Message, bubble=True):
    """Ask the app to re-render the current image plot (e.g. after a resize)."""
