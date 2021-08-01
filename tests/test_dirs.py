from uproot_browser.dirs import filename, selections

def test_filename():
    r'Should handle C:\ too'
    assert "/file.root" == filename("/file.root")
    assert "/file.root" == filename("/file.root:dir")
    assert "/file.root" == filename("/file.root:dir:tree")

def test_selection():
    assert () == selections("/file.root")
    assert ("dir",) == selections("/file.root:dir")
    assert ("dir", "tree") == selections("/file.root:dir:tree")
