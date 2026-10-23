import pathlib
import shutil

import pytest
from skhep_testdata import data_path
from textual import _wait

from uproot_browser.tui.browser import Browser

# Textual's pilot polls for an idle process in 20 ms steps after every key
# press and pause. A finer step makes those waits as short as the real work.
_wait.SLEEP_GRANULARITY = 0.001
_wait.SLEEP_IDLE = _wait.SLEEP_GRANULARITY / 20.0

# Tests read app._notifications, which drops expired entries. Slow CI runners
# can take longer than the default 5 s timeout between notify and the assert.
Browser.NOTIFICATION_TIMEOUT = 600


@pytest.fixture
def root_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory with a ROOT file, a nested one, and entries to skip."""
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "a.root")
    (tmp_path / "sub").mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "sub" / "b.root")
    (tmp_path / "empty").mkdir()
    (tmp_path / "notes.txt").write_text("not ROOT")
    (tmp_path / ".hidden.root").write_text("")
    return tmp_path
