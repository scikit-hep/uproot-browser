import skhep_testdata

from uproot_browser.tui.browser import Browser
from uproot_browser.tui.plot import Plotext


async def test_browse_logo() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        assert pilot.app.view_widget.item is None


async def test_browse_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        assert isinstance(pilot.app.view_widget.item, Plotext)


async def test_browse_empty() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("down", "space", "down", "enter")
        assert pilot.app.view_widget.item is None


async def test_browse_empty_vim() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("j", "l", "j", "enter")
        assert pilot.app.view_widget.item is None


async def test_help_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("?")
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"
