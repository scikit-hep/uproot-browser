import contextlib
import pathlib
import shutil
from collections.abc import Iterator

import pytest
import textual.message_pump
import textual.pilot
import textual.worker
from skhep_testdata import data_path
from textual import _wait

from uproot_browser.tui.browser import Browser

# Textual's pilot polls for an idle process in 20 ms steps after every key
# press and pause. A finer step makes those waits as short as the real work.
_wait.SLEEP_GRANULARITY = 0.001
_wait.SLEEP_IDLE = _wait.SLEEP_GRANULARITY / 20.0


def _pumps(
    pilot: textual.pilot.Pilot[object],
) -> Iterator[textual.message_pump.MessagePump]:
    app = pilot.app
    yield app
    for screen in app.screen_stack:
        yield from screen.walk_children(with_self=True)


def _drained(pilot: textual.pilot.Pilot[object]) -> bool:
    return all(pump._message_queue.empty() for pump in _pumps(pilot))  # noqa: SLF001


async def settle(pilot: textual.pilot.Pilot[object], *, hops: int = 50) -> None:
    """Wait until no widget has a pending message, then flush the layout.

    The pilot's own waits decide the app is idle from a CPU-time heuristic,
    and ``_wait_for_screen`` covers one hop only. A key press fans out over
    several hops (app, screen, widget, action, deferred focus, notification),
    so on a loaded runner the pilot returns with messages still queued. This
    waits hop by hop until a pass finds every queue empty before and after
    the layout flush. An app that keeps posting (a render retry loop) gets
    ``hops`` hops, which is more than any direct chain needs.
    """
    for _ in range(hops):
        if _drained(pilot):
            pilot.app.screen._on_timer_update()  # noqa: SLF001
            if _drained(pilot):
                return
        await pilot._wait_for_screen()  # noqa: SLF001


async def wait_for_workers(pilot: textual.pilot.Pilot[object]) -> None:
    """Settle, then wait for the workers that started, until none runs.

    ``workers.wait_for_complete`` raises for a cancelled worker, and an
    exclusive worker cancels the one before it.
    """
    for _ in range(50):
        await settle(pilot)
        running = [worker for worker in pilot.app.workers if worker.is_running]
        if not running:
            return
        for worker in running:
            with contextlib.suppress(textual.worker.WorkerCancelled):
                await worker.wait()
    msg = "The app kept starting workers."
    raise TimeoutError(msg)


async def _pause(
    pilot: textual.pilot.Pilot[object], delay: float | None = None
) -> None:
    if delay is not None:
        await _wait.sleep(delay)
    await settle(pilot)


async def _press(pilot: textual.pilot.Pilot[object], *keys: str) -> None:
    # One key at a time: a key's deferred effects must land before the next
    for key in keys:
        await _original_press(pilot, key)
        await settle(pilot)


_original_press = textual.pilot.Pilot.press
textual.pilot.Pilot.pause = _pause  # type: ignore[method-assign]
textual.pilot.Pilot.press = _press  # type: ignore[method-assign]

# Tests read app._notifications, which drops expired entries. Slow CI runners
# can take longer than the default 5 s timeout between notify and the assert.
Browser.NOTIFICATION_TIMEOUT = 600


@pytest.fixture
def root_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory with a ROOT file, a nested one, and entries to skip."""
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "a.root")
    (tmp_path / "sub").mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "sub" / "b.root")
    (tmp_path / "empty").mkdir()
    (tmp_path / "notes.txt").write_text("not ROOT")
    (tmp_path / ".hidden.root").write_text("")
    return tmp_path
