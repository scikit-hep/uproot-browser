"""
The directory backend: a directory of files some format backend can open.

The directory is on any fsspec filesystem, local or remote. Files are listed
without opening them; a file opens (with its own backend) the first time its
contents are needed.
"""

from __future__ import annotations

__lazy_modules__ = {
    "fsspec.core",
    "fsspec.implementations.local",
    "pathlib",
    "typing",
    "uproot_browser.backends",
}

import dataclasses
import functools
import threading
from pathlib import Path
from typing import Any

from fsspec.core import url_to_fs
from fsspec.implementations.local import LocalFileSystem

import uproot_browser.backends
from uproot_browser.backends import split_spec
from uproot_browser.nodes import (
    Folder,
    MetaDict,
    Node,
    Root,
    failed_meta,
    path_meta,
    spec_name,
)

__all__ = ("Directory", "LazyRoot", "matches", "open_spec")


def __dir__() -> tuple[str, ...]:
    return __all__


# Listing an HTTP URL downloads it, so these are never probed
_NO_PROBE = ("http://", "https://")


def matches(spec: str) -> bool:
    """
    Is this a directory? A remote URL that ends with ``/`` is one without any
    I/O; other remote URLs are asked from the filesystem.
    """
    name, _ = split_spec(spec)
    if "://" not in name:
        return Path(name).is_dir()
    if name.endswith("/"):
        return True
    if name.startswith(_NO_PROBE):
        return False
    try:
        fs, path = url_to_fs(name)
        return bool(fs.isdir(path))
    except Exception:  # noqa: BLE001
        return False


def open_spec(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """Open a directory; a ``directory:key`` spec gives the node at ``key``."""
    name, obj_path = split_spec(spec)
    directory = Directory(name, parent, key)
    return directory.resolve(obj_path) if obj_path else directory


def _join(spec: str, key: str) -> str:
    return f"{spec.rstrip('/')}/{key}" if "://" in spec else str(Path(spec, key))


def _basename(path: str) -> str:
    """The last segment of a path as fsspec gives it (``/`` on every system)."""
    return path.rstrip("/").rpartition("/")[2]


@dataclasses.dataclass(eq=False)
class LazyRoot(Root, Folder):
    """
    A file of a directory, opened on first use. It stays in the tree and
    forwards to the opened root, which has the same parent and key, so the
    paths and the file of the children are the same either way.

    ``item`` is the path or URL of the file.
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
        return spec_name(self.spec)

    @property
    def is_loaded(self) -> bool:
        return self._opened is not None

    def open(self) -> Node:
        """The opened root; render workers and the UI thread can both get here."""
        with self._lock:
            if self._opened is None:
                self._opened = uproot_browser.backends.open_path(
                    self.spec, parent=self.parent, key=self.key
                )
            return self._opened

    def _folder(self) -> Folder:
        try:
            opened = self.open()
            if not isinstance(opened, Folder):
                msg = f"{self.spec!r} did not open as a folder"
                raise TypeError(msg)  # noqa: TRY301
        except Exception as err:
            self.error = err
            raise
        return opened

    def keys(self) -> list[str]:
        try:
            return self._folder().keys()
        except Exception:  # noqa: BLE001
            # Shown as a failed entry, from the error _folder recorded
            return []

    def lookup(self, key: str) -> Node:
        return self._folder().lookup(key)

    def classname_of(self, key: str) -> str:
        return self._folder().classname_of(key)

    def meta(self) -> MetaDict:
        if self.error is not None:
            return failed_meta(self.name, "", self.error)
        return path_meta(self.spec, "📁 ")

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
class Directory(Folder):
    """
    A directory on an fsspec filesystem. Its keys are the entries a format
    claims and the subdirectories. A local subdirectory is listed only if it
    contains such a file; a remote one is not searched, so it always lists.

    ``item`` is the path or URL of the directory.
    """

    _children: dict[str, Node] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )
    _lock: threading.Lock = dataclasses.field(
        default_factory=threading.Lock, init=False, repr=False
    )

    @property
    def spec(self) -> str:
        return str(self.item)

    @property
    def name(self) -> str:
        return spec_name(self.spec)

    @functools.cached_property
    def _fs(self) -> tuple[Any, str]:
        fs, path = url_to_fs(self.spec)
        return fs, path

    @property
    def is_local(self) -> bool:
        return isinstance(self._fs[0], LocalFileSystem)

    @property
    def is_loaded(self) -> bool:
        return self.is_local or "_entries" in self.__dict__

    @functools.cached_property
    def _entries(self) -> dict[str, bool]:
        """Every visible entry: its name, and whether it is a directory."""
        fs, path = self._fs
        return {
            name: info["type"] == "directory"
            for info in fs.ls(path, detail=True)
            if not (name := _basename(info["name"])).startswith(".")
        }

    def _listable(self, key: str, *, is_dir: bool) -> bool:
        if uproot_browser.backends.claims(_join(self.spec, key)):
            return True
        if not is_dir:
            return False
        if not self.is_local:
            return True
        fs, path = self._fs
        return any(
            not _basename(found).startswith(".")
            and uproot_browser.backends.claims(found)
            for found in fs.find(f"{path}/{key}")
        )

    @functools.cached_property
    def _listing(self) -> list[str]:
        return sorted(
            key
            for key, is_dir in self._entries.items()
            if self._listable(key, is_dir=is_dir)
        )

    def keys(self) -> list[str]:
        return list(self._listing)

    def lookup(self, key: str) -> Node:
        # The same node each time, so the tree widget sees the file open
        with self._lock:
            if key not in self._children:
                if key not in self._entries:
                    raise KeyError(key)
                child = _join(self.spec, key)
                # A format can claim a directory (a Zarr store, for example)
                browse = self._entries[key] and not uproot_browser.backends.claims(
                    child
                )
                self._children[key] = (
                    Directory(child, self, key)
                    if browse
                    else LazyRoot(child, self, key)
                )
            return self._children[key]

    def meta(self) -> MetaDict:
        return path_meta(self.spec, "🗂️ ")

    def close(self) -> None:
        with self._lock:
            for child in self._children.values():
                child.close()
            self._children.clear()
