"""
The backend registry: which module opens a path.

A backend is a module with two functions, ``matches(spec: str) -> bool`` and
``open_spec(spec: str, *, parent: Folder | None, key: str) -> Node``. It must be
importable without its optional dependencies; ``open_spec`` raises
``ModuleNotFoundError`` for a missing extra. Every backend, built-in or not, is
an entry point in the ``uproot_browser.backends`` group, like
``name = "package.module [extra]"``.

There are two roles. A format backend claims a spec from its text alone (a
suffix); formats are asked first, in name order. The ``directory`` backend is a
container: it is asked last, lists what the formats claim, and opens each entry
with :func:`open_path`. The ``uproot`` backend opens what nothing claims.
"""

from __future__ import annotations

__lazy_modules__ = {
    "importlib",
    "importlib.metadata",
    "pathlib",
    "uproot_browser.nodes",
}

import dataclasses
import functools
import importlib
import importlib.metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from uproot_browser.nodes import FailedNode, Node

if TYPE_CHECKING:
    from uproot_browser.nodes import Folder

__all__ = (
    "CONTAINER",
    "FALLBACK",
    "Backend",
    "BackendModule",
    "as_node",
    "backends",
    "claims",
    "open_path",
    "select_key",
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
            msg = f"{err}; install the [{self.extra}] extra to open {spec!r}"
            raise ModuleNotFoundError(msg, name=err.name) from err


CONTAINER = "directory"
"""The backend that lists a directory; asked after every format."""

FALLBACK = "uproot"
"""The backend that opens a path no backend claims."""


@functools.cache
def backends() -> tuple[Backend, ...]:
    """The registered backends: formats by name, then the container."""
    entry_points = importlib.metadata.entry_points(group="uproot_browser.backends")
    return tuple(
        Backend(ep.name, ep.module, ep.extras[0] if ep.extras else None)
        for ep in sorted(entry_points, key=lambda ep: (ep.name == CONTAINER, ep.name))
    )


@functools.cache
def _load_all() -> tuple[BackendModule, ...]:
    """Import every backend; each registers its raw types with :func:`as_node`."""
    return tuple(b.load() for b in backends())


def _match(spec: str, *, container: bool = True) -> Backend | None:
    return next(
        (
            b
            for b in backends()
            if (container or b.name != CONTAINER) and b.load().matches(spec)
        ),
        None,
    )


def _fallback() -> Backend:
    backend = next((b for b in backends() if b.name == FALLBACK), None)
    if backend is None:
        msg = f"The {FALLBACK!r} backend is not registered; reinstall uproot-browser"
        raise RuntimeError(msg)
    return backend


def claims(spec: str) -> bool:
    """Does some format recognize this path (without any I/O)?"""
    return _match(spec, container=False) is not None


def open_path(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """
    Open a ``path`` or ``path:key`` spec with the backend that claims it. The
    result is the top of a tree, or the node at ``key`` inside it.
    """
    backend = _match(spec) or _fallback()
    return backend.open(spec, parent=parent, key=key)


def select_key(root: Node, key: str) -> Node:
    """
    The node at ``key`` below a root that was just opened, for a ``path:key``
    spec. A key that does not load closes the root and raises.
    """
    if not key:
        return root
    try:
        node = root.resolve(key)
    except BaseException:
        root.close()
        raise
    if isinstance(node, FailedNode):
        root.close()
        raise node.exception
    return node


def split_spec(spec: str) -> tuple[str, str]:
    """
    Split ``path:key`` at the first colon that ends an existing local path,
    since keys can contain colons. Returns ``(spec, "")`` if there is none.
    """
    if ":" not in spec or "://" in spec or Path(spec).exists():
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
    _load_all()
    impl = as_node.dispatch(type(obj))
    if impl is _as_node_default:
        msg = f"No backend wraps {type(obj).__name__} objects"
        raise TypeError(msg)
    return impl(obj)


_as_node_default = as_node.dispatch(object)


@as_node.register
def _(obj: Node) -> Node:
    return obj
