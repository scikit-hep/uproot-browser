from __future__ import annotations

import ast
import shutil
import sys
from typing import TYPE_CHECKING

import numpy as np
import pytest
import rich.console
from click.testing import CliRunner

from uproot_browser.__main__ import main

if TYPE_CHECKING:
    import pathlib

xr = pytest.importorskip("xarray")
cdflib_xarray = pytest.importorskip("cdflib.xarray")

from test_tui import plot_text, settle_render, wait_until  # noqa: E402

import uproot_browser.plot  # noqa: E402
import uproot_browser.tree  # noqa: E402
from uproot_browser.backends import open_path, split_spec  # noqa: E402
from uproot_browser.backends.cdf import CdfFile, CdfVariable  # noqa: E402
from uproot_browser.tui.browser import Browser  # noqa: E402
from uproot_browser.tui.left_panel import UprootTree  # noqa: E402
from uproot_browser.tui.plot import Plotext  # noqa: E402


@pytest.fixture(scope="module")
def cdf_file(tmp_path_factory: pytest.TempPathFactory) -> str:
    """A small CDF: two coordinates, numeric data, and a text variable."""
    epoch = np.datetime64("2026-01-01T00:00:00", "ns") + np.arange(5) * np.timedelta64(
        1, "s"
    )
    dataset = xr.Dataset(
        {
            "counts": (
                "epoch",
                np.array([1, 2, 3, 4, 5], dtype=np.int32),
                {"DEPEND_0": "epoch", "VAR_TYPE": "data"},
            ),
            "filled": (
                "epoch",
                np.array([1, 2, 65535, 4, 65535], dtype=np.int32),
                {"DEPEND_0": "epoch", "VAR_TYPE": "data", "FILLVAL": 65535},
            ),
            "rates": (
                ("epoch", "step"),
                np.arange(15.0).reshape(5, 3),
                {"DEPEND_0": "epoch", "DEPEND_1": "step", "VAR_TYPE": "data"},
            ),
            "label": ("step", np.array(["a", "b", "c"]), {"VAR_TYPE": "metadata"}),
        },
        coords={
            "epoch": ("epoch", epoch, {"VAR_TYPE": "support_data"}),
            "step": (
                "step",
                np.arange(3, dtype=np.uint8),
                {"VAR_TYPE": "support_data"},
            ),
        },
    )
    path = tmp_path_factory.mktemp("cdf") / "sample.cdf"
    cdflib_xarray.xarray_to_cdf(dataset, str(path), istp=False)
    return str(path)


def test_split_spec(cdf_file: str) -> None:
    assert split_spec(cdf_file) == (cdf_file, "")
    assert split_spec(f"{cdf_file}:rates") == (cdf_file, "rates")


def test_open_path(cdf_file: str) -> None:
    with open_path(cdf_file) as root:
        assert isinstance(root, CdfFile)
        assert root.is_dir
        assert sorted(root.keys()) == [
            "counts",
            "epoch",
            "filled",
            "label",
            "rates",
            "step",
        ]

    with open_path(f"{cdf_file}:rates") as variable:
        assert isinstance(variable, CdfVariable)
        assert variable.name == "rates"
        assert variable.path == "//rates"


def test_open_path_without_extra(
    cdf_file: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "cdflib.xarray", None)
    with pytest.raises(ModuleNotFoundError, match=r"\[cdf\] extra"):
        open_path(cdf_file)


def test_plottable(cdf_file: str) -> None:
    with open_path(cdf_file) as root:
        assert uproot_browser.plot.plottable(root.resolve("counts"))
        assert uproot_browser.plot.plottable(root.resolve("rates"))
        assert uproot_browser.plot.array_plottable(root.resolve("rates"))
        assert not uproot_browser.plot.plottable(root.resolve("label"))
        assert not uproot_browser.plot.plottable(root.resolve("epoch"))
        assert not uproot_browser.plot.array_plottable(root.resolve("epoch"))


def test_to_histogram(cdf_file: str) -> None:
    with open_path(cdf_file) as root:
        histogram = uproot_browser.plot.to_histogram(root.resolve("rates"), bins=15)
        assert histogram.sum() == 15
        with pytest.raises(TypeError, match="cannot be plotted"):
            uproot_browser.plot.to_histogram(root.resolve("label"))


def test_integer_fill_values_dropped(cdf_file: str) -> None:
    with open_path(cdf_file) as root:
        histogram = uproot_browser.plot.to_histogram(root.resolve("filled"), bins=5)
    assert histogram.sum() == 3
    assert histogram.axes[0].edges[-1] < 100


def test_pair_histogram(cdf_file: str) -> None:
    with open_path(cdf_file) as root:
        pair = uproot_browser.plot.BranchPair(
            root.resolve("step"), root.resolve("counts")
        )
        with pytest.raises(ValueError, match="entries"):
            uproot_browser.plot.to_histogram(pair)
        pair = uproot_browser.plot.BranchPair(
            root.resolve("counts"), root.resolve("counts")
        )
        histogram = uproot_browser.plot.to_histogram(pair, bins=5)
        assert histogram.sum() == 5
        assert 'x_item.attrs.get("FILLVAL")' in uproot_browser.plot.dump(pair)


def test_tree_cli(cdf_file: str) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["tree", cdf_file])
    assert result.exit_code == 0, result.output
    assert "sample.cdf" in result.output
    assert "rates" in result.output
    assert "float64" in result.output
    assert "epoch: 5, step: 3" in result.output


def test_plot_cli(cdf_file: str) -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["plot", f"{cdf_file}:counts"])
    assert result.exit_code == 0, result.output
    assert "counts -- Entries: 5" in result.output
    assert "█" in result.output


@pytest.mark.skipif(sys.platform == "win32", reason="colon not allowed in names")
def test_plot_cli_colon_in_path(cdf_file: str, tmp_path: pathlib.Path) -> None:
    # Like a Windows drive letter: a colon before the file:selection one
    target = tmp_path / "C:" / "sample.cdf"
    target.parent.mkdir()
    shutil.copy(cdf_file, target)
    result = CliRunner().invoke(main, ["plot", f"{target}:counts"])
    assert result.exit_code == 0, result.output
    assert "counts -- Entries: 5" in result.output


def test_open_source_backslashes() -> None:
    path = r"C:\Users\new\sample.cdf"
    tree = ast.parse(CdfFile(None, spec=path).open_source("file"))
    literals = [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]
    assert path in literals


async def test_browse(cdf_file: str) -> None:
    app = Browser(cdf_file)
    async with app.run_test(size=(120, 40)) as pilot:
        tree = app.query_one("#tree-view", UprootTree)
        children = [c.data.path for c in tree.root.children if c.data]
        assert children == [
            "//counts",
            "//epoch",
            "//filled",
            "//label",
            "//rates",
            "//step",
        ]

        tree.select_path("//rates")
        await settle_render(pilot)
        item = app.view_widget.item
        assert isinstance(item, Plotext)
        assert item.selection == "//rates"
        # The render worker can finish after settle_render on slow runners
        await wait_until(pilot, lambda: "rates -- Entries: 15" in plot_text(app))
        assert "rates -- Entries: 15" in plot_text(app)

        source, _ = app.dump_source()
        assert "cdflib.xarray.cdf_to_xarray(" in source
        assert 'item = file["rates"]' in source
        assert 'item.attrs.get("FILLVAL")' in source


async def test_browse_dump_runs(cdf_file: str) -> None:
    app = Browser(cdf_file)
    async with app.run_test(size=(120, 40)) as pilot:
        app.query_one("#tree-view", UprootTree).select_path("//filled")
        await settle_render(pilot)
        source, _ = app.dump_source()
    namespace: dict[str, object] = {}
    exec(source, namespace)
    h = namespace["h"]
    assert h.sum() == 3  # type: ignore[attr-defined]


def test_print_tree_icons(cdf_file: str) -> None:
    console = rich.console.Console(record=True, width=120)
    uproot_browser.tree.print_tree(cdf_file, console=console)
    text = console.export_text()
    assert "📁 sample.cdf" in text
    assert "📏 epoch datetime64[ns] (epoch: 5)" in text
    assert "🔢 rates float64 (epoch: 5, step: 3)" in text
