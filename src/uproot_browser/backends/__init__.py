"""
The backend registry: which module opens a path.

A backend is a module with two functions, ``matches(spec: str) -> bool`` and
``open_spec(spec: str, *, parent: Folder | None, key: str) -> Node``. It must be
importable without its optional dependencies; ``open_spec`` raises
``ModuleNotFoundError`` for a missing extra. Built-in backends are listed in
:data:`BUILTIN`; other packages add one with an entry point in the
``uproot_browser.backends`` group. The uproot backend opens whatever no other
backend claims.
"""

from __future__ import annotations

__lazy_modules__ = {"importlib", "importlib.metadata", "pathlib"}

import dataclasses
import functools
import importlib
import importlib.metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from uproot_browser.nodes import Node

if TYPE_CHECKING:
    from uproot_browser.nodes import Folder

__all__ = (
    "BUILTIN",
    "FALLBACK",
    "Backend",
    "BackendModule",
    "as_node",
    "backends",
    "claims",
    "open_path",
    "split_spec",
)


def __dir__() -> tuple[str, ...]:
    return __all__


class BackendModule(Protocol):
    def matches(self, spec: str) -> bool: ...
    def open_spec(self, spec: str, *, parent: Folder | None, key: str) -> Node: ...


@dataclasses.dataclass(frozen=True)
class Backend:
    name: str
    module: str
    extra: str | None = None
    """The extra that installs the dependencies, for the error message."""

    def load(self) -> BackendModule:
        module: BackendModule = importlib.import_module(self.module)
        return module

    def open(self, spec: str, *, parent: Folder | None, key: str) -> Node:
        try:
            return self.load().open_spec(spec, parent=parent, key=key)
        except ModuleNotFoundError as err:
            if self.extra is None:
                raise
            msg = f"Install the [{self.extra}] extra to open {spec!r}"
            raise ModuleNotFoundError(msg) from err


BUILTIN = (Backend("directory", "uproot_browser.backends.directory"),)
FALLBACK = Backend("uproot", "uproot_browser.backends.uproot")


@functools.cache
def backends() -> tuple[Backend, ...]:
    """The built-in backends, then the entry points, then the fallback."""
    entry_points = importlib.metadata.entry_points(group="uproot_browser.backends")
    plugins = tuple(Backend(ep.name, ep.module) for ep in entry_points)
    return (*BUILTIN, *plugins, FALLBACK)


def _match(spec: str) -> Backend | None:
    return next((b for b in backends() if b.load().matches(spec)), None)


def claims(spec: str) -> bool:
    """Does some backend recognize this path (without opening it)?"""
    return _match(spec) is not None


def open_path(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """
    Open a ``path`` or ``path:key`` spec with the backend that claims it. The
    result is the top of a tree, or the node at ``key`` inside it.
    """
    backend = _match(spec) or FALLBACK
    return backend.open(spec, parent=parent, key=key)


def split_spec(spec: str) -> tuple[str, str]:
    """
    Split ``path:key`` at the first colon that ends an existing local path,
    since keys can contain colons. Returns ``(spec, "")`` if there is none.
    """
    if "://" in spec or Path(spec).exists():
        return spec, ""
    for i, char in enumerate(spec):
        if char != ":":
            continue
        path = Path(spec[:i])
        # Skip a Windows drive, like "C:"
        if path.drive != spec[: i + 1] and path.exists():
            return spec[:i], spec[i + 1 :]
    return spec, ""


@functools.singledispatch
def as_node(obj: Any) -> Node:
    """
    The node for a raw object, for callers that hold uproot objects directly.
    Backends register their types; nodes pass through.
    """
    # The uproot backend registers on import; it is the only one with raw types
    # that reach the plotting API without going through open_path.
    importlib.import_module("uproot_browser.backends.uproot")
    impl = as_node.dispatch(type(obj))
    if impl is _as_node_default:
        msg = f"No backend wraps {type(obj).__name__} objects"
        raise TypeError(msg)
    return impl(obj)


_as_node_default = as_node.dispatch(object)


@as_node.register
def _(obj: Node) -> Node:
    return obj
