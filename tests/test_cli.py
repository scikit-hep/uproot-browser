from __future__ import annotations

from click.testing import CliRunner

from uproot_browser.__main__ import main


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
