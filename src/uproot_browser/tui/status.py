from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "dataclasses",
    "itertools",
    "uproot_browser.progress",
}

import contextlib
import dataclasses
import itertools
from typing import TYPE_CHECKING, Any

import textual.containers
import textual.widgets

import uproot_browser.progress

if TYPE_CHECKING:
    from collections.abc import Iterator

    import textual.app

DELAY = 0.25
"""Seconds a task runs before it shows, so a fast one does not flash."""


@dataclasses.dataclass
class _Task:
    label: str
    fraction: float | None = None
    shown: bool = False


class StatusBar(textual.containers.Horizontal):
    """
    One line above the footer: the pending count of the tree, and the newest
    running task with its progress bar. Hidden when it has nothing to show.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tasks: dict[int, _Task] = {}
        self._ids = itertools.count()
        self._count = textual.widgets.Static(id="navigation-count")
        self._count.display = False
        self._label = textual.widgets.Static(id="task-label")
        self._bar = textual.widgets.ProgressBar(id="task-bar", show_eta=False)

    def compose(self) -> textual.app.ComposeResult:
        yield self._count
        yield self._label
        yield self._bar

    def on_mount(self) -> None:
        self._update()

    def show_count(self, count: str) -> None:
        if count:
            self._count.update(f"Move: {count}")
        self._count.display = bool(count)
        self._update()

    @contextlib.contextmanager
    def running(self, label: str) -> Iterator[None]:
        """
        Show ``label`` while the block runs. For a worker thread: the block
        must not run on the UI thread, which draws the bar. The reports to
        :mod:`uproot_browser.progress` in the block set the bar.
        """
        key = next(self._ids)
        # call_later is thread-safe, and does nothing once the app is closed
        self.call_later(self._start, key, label)
        try:
            with uproot_browser.progress.reporting(
                lambda fraction: self.call_later(
                    self._advance, key, fraction=fraction
                )
            ):
                yield
        finally:
            self.call_later(self._finish, key)

    def _start(self, key: int, label: str) -> None:
        self._tasks[key] = _Task(label)
        self.set_timer(DELAY, lambda: self._advance(key, shown=True))

    def _advance(self, key: int, **changes: Any) -> None:
        # The task is gone if the timer or a report comes after its end
        if key in self._tasks:
            self._tasks[key] = dataclasses.replace(self._tasks[key], **changes)
            self._update()

    def _finish(self, key: int) -> None:
        self._tasks.pop(key, None)
        self._update()

    def _update(self) -> None:
        shown = [t for t in self._tasks.values() if t.shown]
        self._label.display = self._bar.display = bool(shown)
        self.display = bool(shown) or self._count.display
        if shown:
            task = shown[-1]
            self._label.update(task.label)
            # No total gives the animated bar of an unknown duration
            self._bar.total = None if task.fraction is None else 1
            self._bar.progress = task.fraction or 0
