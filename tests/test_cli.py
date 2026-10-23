from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from skhep_testdata import data_path

from uproot_browser.__main__ import get_testdata, main

if TYPE_CHECKING:
    from pathlib import Path


def test_missing_local_file() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["tree", "does-not-exist.root"])
    assert result.exit_code != 0
    assert "does-not-exist.root" in result.output
    assert "does not exist" in result.output
    assert "Traceback" not in result.output


def test_testdata_did_you_mean() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["tree", "--testdata", "Uproot-Event.root"])
    assert result.exit_code != 0
    assert "Did you mean" in result.output
    assert "uproot-Event.root" in result.output
    assert "Traceback" not in result.output


def test_testdata_list_files() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["tree", "--testdata"])
    assert result.exit_code != 0
    assert "uproot-Event.root" in result.output


def test_missing_filename() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["tree"])
    assert result.exit_code != 0
    assert "FILENAME" in result.output


def test_remote_url_not_checked_locally() -> None:
    url = "https://example.com/a.root:events"
    assert get_testdata(url, testdata=False) == url


def test_tree_lz4_compressed_file() -> None:
    """Guards LZ4 decompression, which uproot handles itself via cramjam and
    xxhash (lz4 is not a dependency of this package)."""
    runner = CliRunner()
    result = runner.invoke(main, ["tree", "--testdata", "uproot-Zmumu-lz4.root"])
    assert result.exit_code == 0
    assert "px1" in result.output


def test_plot_text() -> None:
    """The default text plot writes bars through Python stdout (not the plotext
    kernel's wcout, which truncates and is invisible to CliRunner)."""
    runner = CliRunner()
    result = runner.invoke(main, ["plot", "--testdata", "uproot-Event.root:hstat"])
    assert result.exit_code == 0
    assert "hstat" in result.output
    assert "█" in result.output


def test_plot_image() -> None:
    pytest.importorskip("textual_image")
    pytest.importorskip("matplotlib")

    runner = CliRunner()
    result = runner.invoke(
        main, ["plot", "--image", "--testdata", "uproot-Event.root:hstat"]
    )
    assert result.exit_code == 0
    # Non-tty falls back to the unicode renderer; just check something rendered
    assert result.output.strip()


def test_plot_save(tmp_path: Path) -> None:
    pytest.importorskip("matplotlib")
    pil_image = pytest.importorskip("PIL.Image")

    out = tmp_path / "plot.png"
    runner = CliRunner()
    result = runner.invoke(
        main, ["plot", "--save", str(out), "--testdata", "uproot-Event.root:hstat"]
    )
    assert result.exit_code == 0
    with pil_image.open(out) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((2, 2))[-1] == 0  # transparent background


def test_tree_directory(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "sub" / "b.root")
    result = CliRunner().invoke(main, ["tree", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "b.root" in result.output
    assert "hpx" in result.output


def test_plot_directory_selection(tmp_path: Path) -> None:
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "b.root")
    result = CliRunner().invoke(main, ["plot", f"{tmp_path}:b.root/hpx"])
    assert result.exit_code == 0, result.output
    assert "hpx" in result.output


def test_colon_in_object_name() -> None:
    """ROOT object names can hold colons; only the file path must exist."""
    spec = f"{data_path('uproot-hepdata-example.root')}:h:a"
    assert get_testdata(spec, testdata=False) == spec
