import concurrent.futures
import sys
import threading
import types
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import skhep_testdata
import textual.pilot
import textual.widgets
from conftest import wait_for_tree, wait_until

import uproot_browser.tui.left_panel
from uproot_browser.backends import open_path
from uproot_browser.nodes import Node
from uproot_browser.tui import auth
from uproot_browser.tui.auth import AuthCancelledError, AuthHandler, AuthScreen
from uproot_browser.tui.browser import Browser

URL = "https://example.org/device?user_code=ABC"
EVENT = skhep_testdata.data_path("uproot-Event.root")


@pytest.fixture
def executor() -> Iterator[concurrent.futures.ThreadPoolExecutor]:
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        yield pool


def run_flow(handler: AuthHandler, flow: Callable[[], Any]) -> Any:
    """Run ``flow`` as pelicanfs does: ``finish`` follows on all paths."""
    success = False
    try:
        result = flow()
        success = True
        return result
    finally:
        handler.finish(success)


def lines(pilot: textual.pilot.Pilot[None]) -> list[str]:
    return [
        str(static.render())
        for static in pilot.app.screen.query("#auth-log Static").results(
            textual.widgets.Static
        )
    ]


async def result(pilot: textual.pilot.Pilot[None], future: Any) -> Any:
    await wait_until(pilot, future.done)
    return future.result()


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("osdf:///ospool/f.root", True),
        ("pelican://host/ns/f.root:tree", True),
        ("simplecache::osdf:///ospool/f.root", True),
        ("https://example.org/f.root", False),
        ("osdf/f.root", False),
        ("f.root", False),
    ],
)
def test_needs_auth(path: str, expected: bool) -> None:  # noqa: FBT001
    assert auth.needs_auth(path) == expected


async def test_auth_login(executor: concurrent.futures.ThreadPoolExecutor) -> None:
    async with Browser(EVENT).run_test() as pilot:
        handler = AuthHandler(pilot.app)

        def flow() -> str:
            handler.show("Starting")
            handler.show(f"Go to {URL}", URL)
            return handler.ask_password("Enter a password:")

        future = executor.submit(run_flow, handler, flow)
        await wait_until(pilot, lambda: pilot.app.focused is not None)
        await wait_until(
            pilot, lambda: getattr(pilot.app.focused, "id", "") == "auth-password"
        )
        assert isinstance(pilot.app.screen, AuthScreen)
        assert lines(pilot) == ["Starting", f"Go to {URL}", "Enter a password:"]
        assert pilot.app.screen.query_one("#auth-open").display

        await pilot.press(*"secret", "enter")
        assert await result(pilot, future) == "secret"
        # The end of the login closes the screen
        await wait_until(pilot, lambda: not isinstance(pilot.app.screen, AuthScreen))


async def test_auth_no_url(executor: concurrent.futures.ThreadPoolExecutor) -> None:
    async with Browser(EVENT).run_test() as pilot:
        handler = AuthHandler(pilot.app)
        hold = threading.Event()

        def flow() -> None:
            handler.show("Starting")
            hold.wait()

        future = executor.submit(run_flow, handler, flow)
        await wait_until(pilot, lambda: isinstance(pilot.app.screen, AuthScreen))
        await wait_until(pilot, lambda: lines(pilot) == ["Starting"])
        screen = pilot.app.screen
        assert not screen.query_one("#auth-open").display
        assert not screen.query_one("#auth-copy").display
        assert not screen.query_one("#auth-password").display
        hold.set()
        await result(pilot, future)


async def test_auth_cancel_password(
    executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    async with Browser(EVENT).run_test() as pilot:
        handler = AuthHandler(pilot.app)
        future = executor.submit(
            run_flow, handler, lambda: handler.ask_password("Password:")
        )
        await wait_until(
            pilot, lambda: getattr(pilot.app.focused, "id", "") == "auth-password"
        )
        await pilot.press("escape")
        with pytest.raises(AuthCancelledError):
            await result(pilot, future)
        assert not isinstance(pilot.app.screen, AuthScreen)

        # A later login opens the screen again
        future = executor.submit(run_flow, handler, lambda: handler.show("Again"))
        await result(pilot, future)


async def test_auth_cancel_wait(
    executor: concurrent.futures.ThreadPoolExecutor,
) -> None:
    async with Browser(EVENT).run_test() as pilot:
        handler = AuthHandler(pilot.app)
        hold = threading.Event()

        def flow() -> None:
            handler.show(f"Go to {URL}", URL)
            # pelicanfs polls while pelican waits for the browser login
            while not handler.cancelled():
                hold.wait(0.01)
            handler.show("After the cancel")

        future = executor.submit(run_flow, handler, flow)
        await wait_until(pilot, lambda: isinstance(pilot.app.screen, AuthScreen))
        await wait_until(pilot, lambda: bool(lines(pilot)))
        await pilot.click("#auth-cancel")
        await wait_until(pilot, lambda: not isinstance(pilot.app.screen, AuthScreen))
        with pytest.raises(AuthCancelledError):
            await result(pilot, future)
        assert not isinstance(pilot.app.screen, AuthScreen)

        shown = threading.Event()

        def again() -> None:
            handler.show("Again")
            shown.set()
            hold.wait()

        future = executor.submit(run_flow, handler, again)
        await wait_until(pilot, shown.is_set)
        assert lines(pilot) == ["Again"]
        assert not handler.cancelled()
        hold.set()
        await result(pilot, future)
        await wait_until(pilot, lambda: not isinstance(pilot.app.screen, AuthScreen))


async def test_auth_app_exit(executor: concurrent.futures.ThreadPoolExecutor) -> None:
    async with Browser(EVENT).run_test() as pilot:
        handler = AuthHandler(pilot.app)
        future = executor.submit(
            run_flow, handler, lambda: handler.ask_password("Password:")
        )
        await wait_until(
            pilot, lambda: getattr(pilot.app.focused, "id", "") == "auth-password"
        )
        handler.close()
        with pytest.raises(AuthCancelledError):
            await result(pilot, future)
    with pytest.raises(RuntimeError):
        handler.show("After the exit")


def fake_pelicanfs(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    module = types.ModuleType("pelicanfs")
    module.handler = None  # type: ignore[attr-defined]

    def set_auth_handler(handler: object) -> object:
        previous, module.handler = module.handler, handler  # type: ignore[attr-defined]
        return previous

    module.set_auth_handler = set_auth_handler  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pelicanfs", module)
    return module


async def test_auth_install(monkeypatch: pytest.MonkeyPatch) -> None:
    module = fake_pelicanfs(monkeypatch)
    at_open: list[object] = []

    def fake_open(_spec: str) -> Node:
        at_open.append(module.handler)
        return open_path(EVENT)

    monkeypatch.setattr(uproot_browser.tui.left_panel, "open_path", fake_open)
    async with Browser("osdf:///ospool/f.root").run_test() as pilot:
        await wait_for_tree(pilot)
        # The handler is set before the open
        assert [type(handler) for handler in at_open] == [AuthHandler]
        assert module.handler is at_open[0]
    assert module.handler is None


async def test_auth_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    module = fake_pelicanfs(monkeypatch)
    async with Browser(EVENT).run_test() as pilot:
        # A local file does not import pelicanfs
        assert module.handler is None
        monkeypatch.setitem(sys.modules, "pelicanfs", None)
        assert auth.install(pilot.app) is None
        monkeypatch.setitem(sys.modules, "pelicanfs", types.ModuleType("pelicanfs"))
        assert auth.install(pilot.app) is None
