from __future__ import annotations

from typing import TYPE_CHECKING, Any

import rich.repr
import textual.message

if TYPE_CHECKING:
    from .error import Error
    from .plot import PlotItem


@rich.repr.auto
class UprootSelected(textual.message.Message, bubble=True):
    def __init__(self, upfile: Any, path: str, y_path: str = "") -> None:
        self.upfile = upfile
        self.path = path
        self.y_path = y_path
        super().__init__()


@rich.repr.auto
class EmptyMessage(textual.message.Message, bubble=True):
    """The render of ``source`` found nothing to plot."""

    def __init__(self, source: PlotItem) -> None:
        self.source = source
        super().__init__()


@rich.repr.auto
class ErrorMessage(textual.message.Message, bubble=True):
    """The render of ``source`` failed with a traceback to show."""

    def __init__(self, err: Error, source: PlotItem) -> None:
        self.err = err
        self.source = source
        super().__init__()


class ExpressionErrorMessage(textual.message.Message, bubble=True):
    """A failed expression whose selection and input should remain editable."""

    def __init__(self, source: PlotItem, error: BaseException) -> None:
        self.source = source
        self.error = error
        super().__init__()


@rich.repr.auto
class RequestPlot(textual.message.Message, bubble=True):
    """Ask the app to re-render the current text plot (e.g. after a resize)."""


@rich.repr.auto
class RequestImage(textual.message.Message, bubble=True):
    """Ask the app to re-render the current image plot (e.g. after a resize)."""
