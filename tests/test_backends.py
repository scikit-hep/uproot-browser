from __future__ import annotations

import importlib.metadata
import os
import pathlib
import shutil
import sys
import threading
import types
from typing import TYPE_CHECKING, Any

import fsspec
import numpy as np
import pytest
import textual.widgets.tree
import uproot
from click.testing import CliRunner
from conftest import wait_for_workers
from skhep_testdata import data_path

import uproot_browser.backends
import uproot_browser.backends.directory
import uproot_browser.backends.uproot
import uproot_browser.plot
import uproot_browser.progress
from uproot_browser.__main__ import main
from uproot_browser.backends import Backend, open_path
from uproot_browser.backends.directory import Directory, LazyRoot
from uproot_browser.nodes import FILE_VAR, FailedNode, Node, Pair, Plottable
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.left_panel import UprootTree
from uproot_browser.tui.plot import Plotext

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
        ("https://example.com/set.root/", False),
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


def test_key_with_colon(tmp_path: pathlib.Path) -> None:
    """An object name can hold a colon; an exact key wins over a split."""
    path = tmp_path / "colon.root"
    with uproot.recreate(path) as out:
        out["h:a"] = np.histogram([1.0, 2.0])
    with open_path(f"{path}:h:a") as node:
        assert node.name == "h:a"
        assert node.keys_below_root == ["h:a"]
    with open_path(f"{data_path('uproot-Event.root')}:T:event/fFlag") as node:
        assert node.keys_below_root == ["T", "event", "fFlag"]


def test_selected_node_closes_file() -> None:
    with open_path(f"{data_path('uproot-Event.root')}:T") as tree:
        assert not tree.root.item.closed
    assert tree.root.item.closed


def test_missing_key_is_failed_node() -> None:
    with open_path(data_path("uproot-Event.root")) as root:
        missing = root.resolve("missing")
        assert isinstance(missing, FailedNode)
        assert missing.exception.__class__.__name__ == "KeyInFileError"


def test_failed_open_is_not_retried_for_classname(
    memory_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    opens: list[str] = []

    def fail(spec: str, **_: object) -> Node:
        opens.append(spec)
        msg = "simulated open failure"
        raise OSError(msg)

    with open_path(memory_dir) as directory:
        monkeypatch.setattr(uproot_browser.backends, "open_path", fail)
        failed = directory.resolve("a.root/hpx")
        assert isinstance(failed, FailedNode)
        assert isinstance(failed.exception, OSError)
        assert len(opens) == 1


@pytest.mark.usefixtures("memory_dir")
def test_filesystem_root_url() -> None:
    """The scheme stays whole when the directory is the top of a filesystem."""
    with open_path("memory://") as directory:
        lazy = directory.resolve("ub-test/a.root")
        assert isinstance(lazy, LazyRoot)
        assert lazy.spec == "memory://ub-test/a.root"
        assert directory.resolve("ub-test/a.root/hpx").name == "hpx"
    assert uproot_browser.backends.directory._join("file:///", "a.root") == (  # noqa: SLF001
        "file:///a.root"
    )


@pytest.mark.usefixtures("zzz_backend")
def test_claimed_directory_in_subtree(tmp_path: pathlib.Path) -> None:
    """A store that is a directory makes the directories above it visible."""
    store = tmp_path / "sub" / "data.zzz"
    store.mkdir(parents=True)
    (store / "chunk").write_text("")
    with open_path(str(tmp_path)) as directory:
        assert isinstance(directory, Directory)
        assert directory.keys() == ["sub"]
        assert isinstance(directory.resolve("sub/data.zzz"), LazyRoot)


def test_subtree_search_stops_at_first_claim(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "sub" / "deep").mkdir(parents=True)
    (tmp_path / "sub" / "a.root").write_text("")
    (tmp_path / "sub" / "deep" / "b.root").write_text("")
    scanned: list[str] = []
    scandir = os.scandir

    def recording(path: Any = ".") -> Any:
        scanned.append(os.fspath(path))
        return scandir(path)

    monkeypatch.setattr(os, "scandir", recording)
    with open_path(str(tmp_path)) as directory:
        assert directory.keys() == ["sub"]
    assert scanned
    assert not any(pathlib.Path(p).name == "deep" for p in scanned)


@pytest.mark.skipif(sys.platform.startswith("win"), reason="needs symlinks")
def test_symlink_to_directory(tmp_path: pathlib.Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), data / "a.root")
    top = tmp_path / "top"
    top.mkdir()
    (top / "link").symlink_to(data, target_is_directory=True)
    with open_path(str(top)) as directory:
        assert directory.keys() == ["link"]
        assert directory.resolve("link/a.root/hpx").name == "hpx"


@pytest.mark.parametrize("obj", [None, 3, "text"])
def test_wrap_unregistered_object(obj: object) -> None:
    node = uproot_browser.backends.uproot.wrap(obj)
    assert not isinstance(node, Plottable)
    with pytest.raises(RuntimeError, match="not plottable yet"):
        uproot_browser.plot.plottable_node(node)


async def test_browse_selected_subtree() -> None:
    """Selections are relative to the displayed root, here a tree in a file."""
    path = data_path("uproot-Event.root")
    async with Browser(f"{path}:T").run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tree.select_path("//T/event/fFlag")
        await wait_for_workers(pilot)
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        msg, _ = pilot.app.dump_source()
        assert f'uproot.open("{path}")' in msg
        assert 'item = file["T/event/fFlag"]' in msg


async def test_jump_to_unopened_file_loads_off_ui_thread(
    root_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    threads: list[threading.Thread] = []
    keys = LazyRoot.keys

    def recording(self: Any) -> list[str]:
        threads.append(threading.current_thread())
        return keys(self)

    monkeypatch.setattr(LazyRoot, "keys", recording)
    async with Browser(str(root_dir)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tree.select_path("//a.root")
        await wait_for_workers(pilot)
        target = next(
            c for c in tree.root.children if c.data and c.data.key == "a.root"
        )
        assert any(c.data and c.data.path == "//a.root/hpx" for c in target.children)
        assert threads
        assert threading.main_thread() not in threads


def test_directory_named_like_a_file(tmp_path: pathlib.Path) -> None:
    """A directory with a format suffix (a rucio dataset) is still a directory."""
    dataset = tmp_path / "user.out.root"
    dataset.mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), dataset / "a.root")
    with open_path(str(dataset)) as directory:
        assert isinstance(directory, Directory)
        assert directory.keys() == ["a.root"]
    with open_path(str(tmp_path)) as directory:
        assert isinstance(directory.resolve("user.out.root"), Directory)
        assert directory.resolve("user.out.root/a.root/hpx").name == "hpx"


def test_remote_directory_named_like_a_file() -> None:
    fs = fsspec.filesystem("memory")
    data = pathlib.Path(data_path("uproot-hepdata-example.root")).read_bytes()
    fs.pipe("/ub-set/user.out.root/a.root", data)
    try:
        with open_path("memory://ub-set") as directory:
            assert isinstance(directory.resolve("user.out.root"), Directory)
            assert directory.resolve("user.out.root/a.root/hpx").name == "hpx"
    finally:
        fs.rm("/ub-set", recursive=True)


async def test_jump_on_failed_remote_listing() -> None:
    """A directory that did not list has no jump targets and is not listed again."""
    async with Browser("memory://ub-no-such-dir/").run_test() as pilot:
        await wait_for_workers(pilot)
        tree = pilot.app.query_one("#tree-view", UprootTree)
        assert tree.jump_candidates() == []
        tree.select_path("//a.root")
        await wait_for_workers(pilot)
        await pilot.press("/")
        assert pilot.app.is_running


def test_key_with_slash(tmp_path: pathlib.Path) -> None:
    """A branch name can hold a slash; the longest run that is a key wins."""
    path = tmp_path / "slash.root"
    with uproot.recreate(path) as out:
        out.mktree("t", {"a/b": np.float64, "c": np.float64})
    with open_path(str(path)) as root:
        node = root.resolve("//t/a/b")
        assert not isinstance(node, FailedNode)
        assert node.keys_below_root == ["t", "a/b"]
        assert root.resolve("//t/c").keys_below_root == ["t", "c"]


def test_key_with_double_colon() -> None:
    selection = "//Beam/Beam./Beam.GMAD::BeamBase/Beam.GMAD::BeamBase.beamEnergy"
    with open_path(data_path("uproot-issue371.root")) as root:
        node = root.resolve(selection)
        assert not isinstance(node, FailedNode)
        assert node.key == "Beam.GMAD::BeamBase.beamEnergy"


@pytest.fixture
def bad_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "bad.root").write_text("not a ROOT file")
    return tmp_path


async def test_failed_open_updates_label(
    bad_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    refreshed: list[str] = []
    refresh = textual.widgets.tree.TreeNode.refresh

    def recording(self: Any) -> None:
        refreshed.append(self.data.key)
        refresh(self)

    async with Browser(str(bad_dir)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        monkeypatch.setattr(textual.widgets.tree.TreeNode, "refresh", recording)
        tree.root.children[0].expand()
        await wait_for_workers(pilot)
        assert refreshed == ["bad.root"]
        assert tree.root.children[0].data.meta()["label_icon"] == "‼️ "


async def test_jump_into_failed_file_stops(
    bad_dir: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opens: list[str] = []
    open_file = LazyRoot.open

    def recording(self: LazyRoot) -> Node:
        opens.append(self.spec)
        return open_file(self)

    monkeypatch.setattr(LazyRoot, "open", recording)
    async with Browser(str(bad_dir)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tree.select_path("//bad.root/x")
        await wait_for_workers(pilot)
        assert len(opens) == 1
        assert tree._pending_jump == ""  # noqa: SLF001


def test_missing_key_in_spec_raises() -> None:
    spec = f"{data_path('uproot-Event.root')}:missing"
    with pytest.raises(uproot.KeyInFileError):
        open_path(spec)
    assert CliRunner().invoke(main, ["tree", spec]).exit_code != 0


def test_missing_key_in_directory_spec_raises(root_dir: pathlib.Path) -> None:
    with pytest.raises(KeyError):
        open_path(f"{root_dir}:a.root/missing")


def test_lazy_root_clears_failure(
    memory_dir: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(spec: str, **_: object) -> Node:
        raise TimeoutError(spec)

    with open_path(memory_dir) as directory:
        lazy = directory.resolve("a.root")
        assert isinstance(lazy, LazyRoot)
        with monkeypatch.context() as patch:
            patch.setattr(uproot_browser.backends, "open_path", fail)
            assert lazy.keys() == []
        assert lazy.meta()["label_icon"] == "‼️ "
        assert lazy.keys().count("hpx") == 1
        assert lazy.meta()["label_icon"] == "📁 "


def test_pair_with_failed_node_raises_its_error() -> None:
    with open_path(data_path("uproot-Event.root")) as root:
        x = root.resolve("T/event/fNtrack")
        missing = root.resolve("T/missing")
        with pytest.raises(uproot.KeyInFileError):
            Pair(x, missing)


def test_progress_span() -> None:
    assert not uproot_browser.progress.active()
    uproot_browser.progress.report(0.5)  # no listener: nothing happens
    seen: list[float] = []
    with uproot_browser.progress.reporting(seen.append):
        assert uproot_browser.progress.active()
        with uproot_browser.progress.span(0.5, 1):
            uproot_browser.progress.report(0.5)
        uproot_browser.progress.report(1)
    assert seen == [0.75, 1]
    assert not uproot_browser.progress.active()


def test_read_reports_progress(tmp_path: pathlib.Path) -> None:
    """With a listener, a branch reads basket by basket and gives the same array."""
    path = tmp_path / "baskets.root"
    with uproot.recreate(path) as out:
        out.mktree("t", {"x": np.float64})
        for start in range(0, 50, 10):
            out["t"].extend({"x": np.arange(start, start + 10, dtype=np.float64)})
    with open_path(f"{path}:t/x") as node:
        assert isinstance(node, uproot_browser.backends.uproot.UprootBranch)
        seen: list[float] = []
        with uproot_browser.progress.reporting(seen.append):
            array = node.read()
        assert seen == [0.2, 0.4, 0.6, 0.8, 1.0]
        assert array.tolist() == node.read().tolist() == list(range(50))


def test_read_limits_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(uproot_browser.backends.uproot, "MAX_STEPS", 2)
    monkeypatch.setattr(
        uproot_browser.backends.uproot.UprootField,
        "_entry_edges",
        property(lambda self: [*range(0, self.entry_count, 500), self.entry_count]),
    )
    with open_path(
        f"{data_path('ntpl001_staff_rntuple_v1-0-0-0.root')}:Staff/Age"
    ) as node:
        assert isinstance(node, uproot_browser.backends.uproot.UprootField)
        seen: list[float] = []
        with uproot_browser.progress.reporting(seen.append):
            array = node.read()
        assert len(seen) == 2
        assert seen[-1] == 1
        assert array.tolist() == node.read().tolist()


async def test_remote_file_opens_in_worker(memory_dir: str) -> None:
    async with Browser(f"{memory_dir}/a.root").run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        assert isinstance(tree.root_node, LazyRoot)
        await wait_for_workers(pilot)
        assert tree.root_node.is_loaded
        assert "//hpx" in [c.data.path for c in tree.root.children if c.data]
