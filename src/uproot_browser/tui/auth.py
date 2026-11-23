"""The pelicanfs login (OIDC device flow) in a modal screen."""

from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "importlib",
    "queue",
    "rich.text",
    "textual.app",
    "textual.containers",
    "textual.widgets",
}

import contextlib
import importlib
import queue
from typing import TYPE_CHECKING, Any, ClassVar

import rich.text
import textual.app
import textual.binding
import textual.containers
import textual.screen
import textual.widgets

if TYPE_CHECKING:
    from collections.abc import Callable

PROTOCOLS = frozenset({"osdf", "pelican"})


def needs_auth(path: str) -> bool:
    """Can ``path`` go through pelicanfs? Chained protocols count."""
    protocol, sep, _ = path.partition("://")
    return bool(sep) and not PROTOCOLS.isdisjoint(protocol.split("::"))


class AuthCancelledError(Exception):
    """The user cancelled the login."""


class AuthScreen(textual.screen.ModalScreen[bool]):
    """The output of the login and its password prompt. Gives True on a cancel."""

    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("escape", "cancel", "Cancel", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._url = ""
        self._reply: Callable[[str], None] | None = None

    def compose(self) -> textual.app.ComposeResult:
        with textual.containers.Container(id="auth-dialog") as dialog:
            dialog.border_title = "Log in"
            yield textual.containers.VerticalScroll(id="auth-log")
            yield textual.widgets.Input(
                password=True, placeholder="Password", id="auth-password"
            )
            with textual.containers.Horizontal(id="auth-buttons"):
                yield textual.widgets.Button(
                    "Open in browser", variant="primary", id="auth-open"
                )
                yield textual.widgets.Button("Copy URL", id="auth-copy")
                yield textual.widgets.Button(
                    "Cancel", variant="error", id="auth-cancel"
                )

    def on_mount(self) -> None:
        for selector in ("#auth-password", "#auth-open", "#auth-copy"):
            self.query_one(selector).display = False

    def add_line(self, text: str, url: str | None = None) -> None:
        log = self.query_one("#auth-log", textual.containers.VerticalScroll)
        log.mount(textual.widgets.Static(rich.text.Text.from_ansi(text)))
        log.scroll_end(animate=False)
        if url:
            self._url = url
            self.query_one("#auth-open").display = True
            self.query_one("#auth-copy").display = True

    def ask_password(self, prompt: str, reply: Callable[[str], None]) -> None:
        self.add_line(prompt)
        self._reply = reply
        password = self.query_one("#auth-password", textual.widgets.Input)
        password.display = True
        password.focus()

    def on_input_submitted(self, event: textual.widgets.Input.Submitted) -> None:
        reply, self._reply = self._reply, None
        event.input.clear()
        event.input.display = False
        if reply is not None:
            reply(event.value)

    def on_button_pressed(self, event: textual.widgets.Button.Pressed) -> None:
        if event.button.id == "auth-open":
            self.app.open_url(self._url)
        elif event.button.id == "auth-copy":
            self.app.copy_to_clipboard(self._url)
            self.app.notify("The URL is on the clipboard")
        else:
            self.dismiss(True)  # noqa: FBT003

    def action_cancel(self) -> None:
        self.dismiss(True)  # noqa: FBT003


class AuthHandler:
    """
    A ``pelicanfs.AuthHandler`` that shows the login in an :class:`AuthScreen`.

    pelicanfs calls the public methods from the fsspec I/O thread. An exception
    from :meth:`show` or :meth:`ask_password` stops the login.
    """

    def __init__(self, app: textual.app.App[Any]) -> None:
        self._app = app
        self._screen: AuthScreen | None = None
        self._active = False
        self._cancelled = False
        self._waiting: queue.SimpleQueue[str | None] | None = None

    def show(self, text: str, url: str | None = None) -> None:
        self._call(self._show, text, url)

    def ask_password(self, prompt: str) -> str:
        reply: queue.SimpleQueue[str | None] = queue.SimpleQueue()
        self._call(self._ask, prompt, reply)
        password = reply.get()
        if password is None:
            raise AuthCancelledError
        return password

    def cancelled(self) -> bool:
        """pelicanfs polls this while pelican runs."""
        return self._cancelled

    def finish(self, success: bool) -> None:  # noqa: ARG002, FBT001
        """The login is over: the open that follows reports a failure."""
        with contextlib.suppress(RuntimeError):
            self._app.call_from_thread(self._finish)

    def close(self) -> None:
        """Release a thread that waits for the password."""
        self._cancelled = True
        self._answer(None)

    def _call(self, callback: Callable[..., Any], *args: Any) -> None:
        # RuntimeError if the app is not running, which also stops the login
        if not self._app.call_from_thread(callback, *args):
            raise AuthCancelledError

    # The methods below run on the UI thread.

    def _finish(self) -> None:
        screen, self._screen = self._screen, None
        self._active = self._cancelled = False
        # dismiss closes the top screen; another screen can be above this one
        if screen is not None and screen is self._app.screen:
            screen.dismiss(False)  # noqa: FBT003

    async def _open(self) -> AuthScreen | None:
        if self._cancelled:
            return None
        self._active = True
        if self._screen is None:
            self._screen = AuthScreen()
            await self._app.push_screen(self._screen, self._closed)
        return self._screen

    async def _show(self, text: str, url: str | None) -> bool:
        screen = await self._open()
        if screen is not None:
            screen.add_line(text, url)
        return screen is not None

    async def _ask(self, prompt: str, reply: queue.SimpleQueue[str | None]) -> bool:
        screen = await self._open()
        if screen is not None:
            self._waiting = reply
            screen.ask_password(prompt, self._answer)
        return screen is not None

    def _answer(self, password: str | None) -> None:
        waiting, self._waiting = self._waiting, None
        if waiting is not None:
            waiting.put(password)

    def _closed(self, cancelled: bool | None) -> None:  # noqa: FBT001
        if not cancelled:
            return
        self._screen = None
        # A screen that stayed open after the login has nothing to cancel
        self._cancelled = self._active
        self._answer(None)


def install(app: textual.app.App[Any]) -> Callable[[], None] | None:
    """
    Show the pelicanfs login in ``app``. Gives the function that removes the
    handler, or None if pelicanfs is not installed or too old.
    """
    try:
        pelicanfs = importlib.import_module("pelicanfs")
    except ImportError:
        return None
    set_auth_handler = getattr(pelicanfs, "set_auth_handler", None)
    if set_auth_handler is None:
        return None
    handler = AuthHandler(app)
    previous = set_auth_handler(handler)

    def uninstall() -> None:
        set_auth_handler(previous)
        handler.close()

    return uninstall
