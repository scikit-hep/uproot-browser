from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pytest
import uproot
from click.testing import CliRunner
from conftest import wait_for_workers
from skhep_testdata import data_path

import uproot_browser.plot
from uproot_browser.__main__ import main
from uproot_browser.backends import open_path
from uproot_browser.nodes import FailedNode
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.left_panel import UprootTree
from uproot_browser.tui.plot import Plotext

if TYPE_CHECKING:
    import pathlib


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


def test_selected_node_closes_file() -> None:
    with open_path(f"{data_path('uproot-Event.root')}:T") as tree:
        assert not tree.root.item.closed
    assert tree.root.item.closed


def test_missing_key_is_failed_node() -> None:
    with open_path(data_path("uproot-Event.root")) as root:
        missing = root.resolve("missing")
        assert isinstance(missing, FailedNode)
        assert missing.exception.__class__.__name__ == "KeyInFileError"


def test_missing_key_in_spec_raises() -> None:
    spec = f"{data_path('uproot-Event.root')}:missing"
    with pytest.raises(uproot.KeyInFileError):
        open_path(spec)
    assert CliRunner().invoke(main, ["tree", spec]).exit_code != 0


def test_missing_key_in_directory_spec_raises(root_dir: pathlib.Path) -> None:
    with pytest.raises(KeyError):
        open_path(f"{root_dir}:a.root/missing")


def test_pair_with_failed_node_raises_its_error() -> None:
    with open_path(data_path("uproot-Event.root")) as root:
        x = root.resolve("T/event/fNtrack")
        missing = root.resolve("T/missing")
        with pytest.raises(uproot.KeyInFileError):
            uproot_browser.plot.BranchPair(x, missing)


@pytest.mark.parametrize("obj", [None, 3, "text"])
def test_plottable_unregistered_object(obj: object) -> None:
    assert uproot_browser.plot.plottable(obj) is False
    assert uproot_browser.plot.array_plottable(obj) is False


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
        assert 'item = uproot_file["T/event/fFlag"]' in msg
