import skhep_testdata
import textual.widgets

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
        await pilot.pause()
        assert isinstance(pilot.app.view_widget.item, Plotext)


async def test_browse_empty() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("down", "space", "down", "enter")
        await pilot.pause()  # process RequestPlot → spawn the render worker
        await pilot.app.workers.wait_for_complete()  # block on the thread
        await pilot.pause()  # drain the EmptyMessage the worker posted
        assert pilot.app.view_widget.item is None


async def test_browse_empty_vim() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("j", "l", "j", "enter")
        await pilot.pause()  # process RequestPlot → spawn the render worker
        await pilot.app.workers.wait_for_complete()  # block on the thread
        await pilot.pause()  # drain the EmptyMessage the worker posted
        assert pilot.app.view_widget.item is None


async def test_theme_switch_updates_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        item_before = pilot.app.view_widget.item
        assert isinstance(item_before, Plotext)
        assert item_before.theme == "dark"

        pilot.app.theme = "textual-light"
        await pilot.pause()
        item_after = pilot.app.view_widget.item
        assert isinstance(item_after, Plotext)
        # the item must be replaced, not mutated, so the plot re-renders
        assert item_after is not item_before
        assert item_after.theme == "default"


async def test_theme_select_tracks_theme() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        # Tools tab is lazy-loaded; activate it first so Select is mounted
        pilot.app.query_one(
            "#left-view", textual.widgets.TabbedContent
        ).active = "tab-2"
        await pilot.pause()
        await pilot.pause()  # second pause lets the lazy content finish mounting
        select = pilot.app.query_one(textual.widgets.Select)
        assert select.value == pilot.app.theme

        pilot.app.theme = "nord"
        await pilot.pause()
        assert select.value == "nord"


async def test_help_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("?")
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"
