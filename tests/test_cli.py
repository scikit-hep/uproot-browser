from __future__ import annotations

import pytest
from click.testing import CliRunner

from uproot_browser.__main__ import get_testdata, main


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
