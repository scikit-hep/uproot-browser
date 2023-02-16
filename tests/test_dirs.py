from __future__ import annotations

from uproot_browser.dirs import filename, selections


def test_filename():
    r"Should handle C:\ too"
    assert filename("/file.root") == "/file.root"
    assert filename("/file.root:dir") == "/file.root"
    assert filename("/file.root:dir:tree") == "/file.root"


def test_selection():
    assert selections("/file.root") == ()
    assert selections("/file.root:dir") == ("dir",)
    assert selections("/file.root:dir:tree") == ("dir", "tree")
