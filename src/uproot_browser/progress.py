"""
Progress of a long operation, from the code that does the work to a listener
(the status line of the TUI). The listener is set for a block of code in one
thread; without one, a report does nothing. A report is also the point where
the work can be cancelled.
"""

from __future__ import annotations

import contextlib
import contextvars
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

__all__ = (
    "CancelledError",
    "active",
    "cancel_when",
    "report",
    "reporting",
    "span",
)


def __dir__() -> tuple[str, ...]:
    return __all__


class CancelledError(BaseException):
    """A report found the work cancelled.

    Like :class:`asyncio.CancelledError`, it is not an :class:`Exception`, so
    handlers for the errors of the work let it through.
    """


_reporter: contextvars.ContextVar[Callable[[float], object] | None] = (
    contextvars.ContextVar("reporter", default=None)
)


def active() -> bool:
    """Is there a listener? Work is only split into steps if there is one."""
    return _reporter.get() is not None


def report(fraction: float) -> None:
    """Give the fraction (0 to 1) of the current operation that is done."""
    reporter = _reporter.get()
    if reporter is not None:
        reporter(fraction)


@contextlib.contextmanager
def reporting(reporter: Callable[[float], object]) -> Iterator[None]:
    """Send the reports of the block to ``reporter``."""
    token = _reporter.set(reporter)
    try:
        yield
    finally:
        _reporter.reset(token)


@contextlib.contextmanager
def span(start: float, stop: float) -> Iterator[None]:
    """Map the reports of the block into ``start`` to ``stop`` of the operation."""
    outer = _reporter.get()
    if outer is None:
        yield
        return
    with reporting(lambda fraction: outer(start + (stop - start) * fraction)):
        yield


@contextlib.contextmanager
def cancel_when(cancelled: Callable[[], bool]) -> Iterator[None]:
    """A report in the block raises :class:`CancelledError` once ``cancelled()`` is true."""
    outer = _reporter.get()

    def reporter(fraction: float) -> None:
        if cancelled():
            raise CancelledError
        if outer is not None:
            outer(fraction)

    with reporting(reporter):
        yield
