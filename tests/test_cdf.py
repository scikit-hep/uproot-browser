from __future__ import annotations

import ast
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
import rich.console
from click.testing import CliRunner

from uproot_browser.__main__ import main

xr = pytest.importorskip("xarray")
cdflib_xarray = pytest.importorskip("cdflib.xarray")

from test_tui import plot_text, settle_render, wait_until  # noqa: E402

import uproot_browser.plot  # noqa: E402
import uproot_browser.tree  # noqa: E402
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
    assert uproot_browser.tree.split_spec(cdf_file) == (cdf_file, "")
    assert uproot_browser.tree.split_spec(f"{cdf_file}:rates") == (
        cdf_file,
        "rates",
    )


def test_open_path(cdf_file: str) -> None:
    dataset = uproot_browser.tree.open_path(cdf_file)
    assert isinstance(dataset, xr.Dataset)
    assert uproot_browser.tree.source_path(dataset) == str(Path(cdf_file).resolve())
    assert uproot_browser.tree.is_dir(dataset)
    assert uproot_browser.tree.get_children(dataset) == {
        "counts",
        "filled",
        "rates",
        "label",
        "epoch",
        "step",
    }

    variable = uproot_browser.tree.open_path(f"{cdf_file}:rates")
    assert isinstance(variable, xr.DataArray)
    assert variable.name == "rates"


def test_open_path_without_extra(
    cdf_file: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "uproot_browser.cdf", None)
    with pytest.raises(ModuleNotFoundError, match=r"\[cdf\] extra"):
        uproot_browser.tree.open_path(cdf_file)


def test_plottable(cdf_file: str) -> None:
    dataset = uproot_browser.tree.open_path(cdf_file)
    assert uproot_browser.plot.plottable(dataset["counts"])
    assert uproot_browser.plot.plottable(dataset["rates"])
    assert uproot_browser.plot.array_plottable(dataset["rates"])
    assert not uproot_browser.plot.plottable(dataset["label"])
    assert not uproot_browser.plot.plottable(dataset["epoch"])
    assert not uproot_browser.plot.array_plottable(dataset["epoch"])


def test_to_histogram(cdf_file: str) -> None:
    dataset = uproot_browser.tree.open_path(cdf_file)
    histogram = uproot_browser.plot.to_histogram(dataset["rates"], bins=15)
    assert histogram.sum() == 15
    with pytest.raises(TypeError, match="cannot be plotted"):
        uproot_browser.plot.to_histogram(dataset["label"])


def test_integer_fill_values_dropped(cdf_file: str) -> None:
    dataset = uproot_browser.tree.open_path(cdf_file)
    histogram = uproot_browser.plot.to_histogram(dataset["filled"], bins=5)
    assert histogram.sum() == 3
    assert histogram.axes[0].edges[-1] < 100


def test_pair_histogram(cdf_file: str) -> None:
    dataset = uproot_browser.tree.open_path(cdf_file)
    pair = uproot_browser.plot.BranchPair(dataset["step"], dataset["counts"])
    with pytest.raises(ValueError, match="entries"):
        uproot_browser.plot.to_histogram(pair)
    pair = uproot_browser.plot.BranchPair(dataset["counts"], dataset["counts"])
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
def test_plot_cli_colon_in_path(cdf_file: str, tmp_path: Path) -> None:
    # Like a Windows drive letter: a colon before the file:selection one
    target = tmp_path / "C:" / "sample.cdf"
    target.parent.mkdir()
    shutil.copy(cdf_file, target)
    result = CliRunner().invoke(main, ["plot", f"{target}:counts"])
    assert result.exit_code == 0, result.output
    assert "counts -- Entries: 5" in result.output


@pytest.mark.parametrize("name", ["sample.cdf", "sample.root"])
def test_open_source_backslashes(name: str) -> None:
    path = rf"C:\Users\new\{name}"
    tree = ast.parse(uproot_browser.tree.open_source(path))
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
        assert 'item = uproot_file["rates"]' in source
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
