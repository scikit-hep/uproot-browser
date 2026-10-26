"""
The directory backend: a local directory of files some backend can open.

Files are listed without opening them; a file opens (with its own backend)
the first time its contents are needed.
"""

from __future__ import annotations

__lazy_modules__ = {"pathlib", "typing"}

import dataclasses
import functools
import threading
from pathlib import Path
from typing import Any

import uproot_browser.backends
from uproot_browser.backends import split_spec
from uproot_browser.nodes import Folder, MetaDict, Node, Root, failed_meta, path_meta

__all__ = ("LazyRoot", "LocalDirectory", "matches", "open_spec")


def __dir__() -> tuple[str, ...]:
    return __all__


def matches(spec: str) -> bool:
    name, _ = split_spec(spec)
    return Path(name).is_dir()


def open_spec(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """Open a directory; a ``directory:key`` spec gives the node at ``key``."""
    name, obj_path = split_spec(spec)
    directory = LocalDirectory(Path(name), parent, key)
    return directory.resolve(obj_path) if obj_path else directory


def _listable(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    if path.is_file():
        return uproot_browser.backends.claims(str(path))
    return path.is_dir() and any(
        _listable(p)
        for p in path.rglob("*")
        if p.is_file() and not p.name.startswith(".")
    )


@dataclasses.dataclass(eq=False)
class LazyRoot(Root, Folder):
    """
    A file of a directory, opened on first use. It stays in the tree and
    forwards to the opened root, which has the same parent and key, so the
    paths and the file of the children are the same either way.
    """

    error: Exception | None = dataclasses.field(default=None, init=False, repr=False)
    """The exception of a failed open; the file then has no children."""
    _opened: Node | None = dataclasses.field(default=None, init=False, repr=False)
    _lock: threading.Lock = dataclasses.field(
        default_factory=threading.Lock, init=False, repr=False
    )

    @property
    def spec(self) -> str:
        return str(self.item)

    @property
    def name(self) -> str:
        return str(self.item.name)

    @property
    def is_loaded(self) -> bool:
        return self._opened is not None

    def open(self) -> Node:
        """The opened root; render workers and the UI thread can both get here."""
        with self._lock:
            if self._opened is None:
                try:
                    self._opened = uproot_browser.backends.open_path(
                        self.spec, parent=self.parent, key=self.key
                    )
                except Exception as err:
                    self.error = err
                    raise
            return self._opened

    def _folder(self) -> Folder:
        opened = self.open()
        if not isinstance(opened, Folder):
            msg = f"{self.spec!r} did not open as a folder"
            raise TypeError(msg)
        return opened

    def keys(self) -> list[str]:
        try:
            return self._folder().keys()
        except Exception:  # noqa: BLE001
            return []

    def lookup(self, key: str) -> Node:
        return self._folder().lookup(key)

    def classname_of(self, key: str) -> str:
        return self._folder().classname_of(key)

    def meta(self) -> MetaDict:
        if self.error is not None:
            return failed_meta(self.name, "", self.error)
        return path_meta(self.item, "📁 ")

    def open_source(self, var: str) -> str:
        return self.open().root.open_source(var)

    def lookup_source(self, file_var: str, keys: Any) -> str:
        return self.open().root.lookup_source(file_var, keys)

    def close(self) -> None:
        with self._lock:
            if self._opened is not None:
                self._opened.close()
                self._opened = None


@dataclasses.dataclass(eq=False)
class LocalDirectory(Folder):
    """
    A filesystem directory. Its keys are the files a backend claims and the
    subdirectories that contain such files.
    """

    _children: dict[str, Node] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    _lock: threading.Lock = dataclasses.field(
        default_factory=threading.Lock, init=False, repr=False
    )

    @property
    def name(self) -> str:
        return str(self.item.name)

    def keys(self) -> list[str]:
        return list(self._listing)

    @functools.cached_property
    def _listing(self) -> list[str]:
        return sorted(p.name for p in self.item.iterdir() if _listable(p))

    def lookup(self, key: str) -> Node:
        # The same node each time, so the tree widget sees the file open
        with self._lock:
            if key not in self._children:
                child = self.item / key
                if not child.exists():
                    raise KeyError(key)
                self._children[key] = (
                    LocalDirectory(child, self, key)
                    if child.is_dir()
                    else LazyRoot(child, self, key)
                )
            return self._children[key]

    def meta(self) -> MetaDict:
        return path_meta(self.item, "🗂️ ")

    def close(self) -> None:
        with self._lock:
            for child in self._children.values():
                child.close()
            self._children.clear()
