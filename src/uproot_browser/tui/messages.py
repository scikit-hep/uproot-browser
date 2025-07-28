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
