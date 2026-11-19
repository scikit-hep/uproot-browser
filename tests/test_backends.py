from __future__ import annotations

import importlib.metadata
import pathlib
import sys
import threading
import types
from typing import TYPE_CHECKING, Any

import fsspec
import pytest
from conftest import wait_for_workers
from skhep_testdata import data_path

import uproot_browser.backends
import uproot_browser.backends.directory
import uproot_browser.backends.uproot
from uproot_browser.backends import Backend, open_path
from uproot_browser.backends.directory import Directory, LazyRoot
from uproot_browser.nodes import FILE_VAR, Node
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.left_panel import UprootTree

if TYPE_CHECKING:
    from collections.abc import Iterator

# The memory filesystem of old fsspec versions (the minimums session)
pytestmark = pytest.mark.filterwarnings(
    "ignore:datetime.datetime.utcnow:DeprecationWarning"
)


@pytest.fixture
def memory_dir() -> Iterator[str]:
    """A directory of ROOT files on fsspec's in-memory filesystem."""
    fs = fsspec.filesystem("memory")
    data = pathlib.Path(data_path("uproot-hepdata-example.root")).read_bytes()
    fs.pipe("/ub-test/a.root", data)
    fs.pipe("/ub-test/sub/b.root", data)
    fs.pipe("/ub-test/notes.txt", b"text")
    fs.pipe("/ub-test/.hidden.root", data)
    yield "memory://ub-test"
    fs.rm("/ub-test", recursive=True)


class _FakeNode(Node):
    def meta(self) -> Any:
        raise NotImplementedError


@pytest.fixture
def zzz_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    """A format backend whose name sorts after every built-in backend."""
    module = types.ModuleType("zzz_backend")
    module.matches = lambda spec: spec.endswith(".zzz")  # type: ignore[attr-defined]
    module.open_spec = lambda spec, *, parent, key: _FakeNode(spec, parent, key)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "zzz_backend", module)

    real = importlib.metadata.entry_points

    def entry_points(**kwargs: Any) -> Any:
        extra = importlib.metadata.EntryPoint(
            "zzz", "zzz_backend", "uproot_browser.backends"
        )
        return [*real(**kwargs), extra]

    monkeypatch.setattr(importlib.metadata, "entry_points", entry_points)
    uproot_browser.backends.backends.cache_clear()
    yield
    monkeypatch.undo()
    uproot_browser.backends.backends.cache_clear()


@pytest.mark.usefixtures("zzz_backend")
def test_format_backend_gets_remote_url() -> None:
    """The fallback does not claim a URL before a format backend sees it."""
    node = open_path("memory://nowhere/data.zzz")
    assert isinstance(node, _FakeNode)
    assert uproot_browser.backends.claims("memory://nowhere/data.zzz")


def test_backend_order() -> None:
    """Formats are asked before the directory backend."""
    names = [b.name for b in uproot_browser.backends.backends()]
    assert names[-1] == "directory"


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("file.root", True),
        ("https://example.com/file.root", True),
        ("https://example.com/file.root:tree/branch", True),
        ("https://example.com/store.zarr", False),
        ("https://example.com/", False),
    ],
)
def test_uproot_matches(spec: str, expected: bool) -> None:  # noqa: FBT001
    assert uproot_browser.backends.uproot.matches(spec) is expected


def test_http_is_not_probed(monkeypatch: pytest.MonkeyPatch) -> None:
    """An HTTP listing would download the file, so only a ``/`` marks a directory."""

    def fail(*_: object, **__: object) -> None:
        msg = "probed the network"
        raise AssertionError(msg)

    monkeypatch.setattr(uproot_browser.backends.directory, "url_to_fs", fail)
    assert not uproot_browser.backends.directory.matches("https://example.com/file")
    assert uproot_browser.backends.directory.matches("https://example.com/dir/")


def test_missing_extra_names_module(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("needs_extra")

    def open_spec(*_: object, **__: object) -> Node:
        import not_a_real_module  # noqa: PLC0415

        raise AssertionError(not_a_real_module)

    module.open_spec = open_spec  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "needs_extra", module)
    backend = Backend("needs", "needs_extra", "extra")
    with pytest.raises(ModuleNotFoundError, match=r"not_a_real_module.*\[extra\]"):
        backend.open("x", parent=None, key="")


def test_remote_directory(memory_dir: str) -> None:
    with open_path(memory_dir) as directory:
        assert isinstance(directory, Directory)
        assert directory.name == "ub-test"
        assert not directory.is_loaded
        assert directory.keys() == ["a.root", "sub"]
        assert directory.is_loaded

        hpx = directory.resolve("sub/b.root/hpx")
        assert hpx.name == "hpx"
        assert hpx.path == "//sub/b.root/hpx"
        assert hpx.root.open_source("f") == (
            f'import uproot\nf = uproot.open("{memory_dir}/sub/b.root")'
        )
        assert hpx.bind_source() == f'item = {FILE_VAR}["hpx"]'
        assert directory.resolve("a.root").meta()["label_text"].plain == "a.root"


def test_lazy_root_records_failure(memory_dir: str) -> None:
    """A file that does not open as a folder lists nothing and shows as failed."""
    with open_path(memory_dir) as directory:
        lazy = directory.resolve("a.root")
        assert isinstance(lazy, LazyRoot)
        lazy._opened = _FakeNode(None)  # noqa: SLF001
        assert lazy.keys() == []
        assert isinstance(lazy.error, TypeError)
        assert lazy.meta()["label_icon"] == "‼️ "


async def test_tree_loads_off_ui_thread(
    memory_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listing or a file open that is not done yet runs in a worker."""
    threads: list[threading.Thread] = []
    for cls in (Directory, LazyRoot):
        keys = cls.keys

        def recording(self: Any, keys: Any = keys) -> list[str]:
            threads.append(threading.current_thread())
            return keys(self)  # type: ignore[no-any-return]

        monkeypatch.setattr(cls, "keys", recording)

    async with Browser(memory_dir).run_test() as pilot:
        await wait_for_workers(pilot)
        tree = pilot.app.query_one("#tree-view", UprootTree)
        assert [c.data.path for c in tree.root.children if c.data] == [
            "//a.root",
            "//sub",
        ]
        tree.root.children[0].expand()
        await wait_for_workers(pilot)
        paths = [c.data.path for c in tree.root.children[0].children if c.data]
        assert "//a.root/hpx" in paths
        assert len(threads) >= 2
        assert threading.main_thread() not in threads
