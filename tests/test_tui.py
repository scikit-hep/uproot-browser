from collections.abc import Callable

import skhep_testdata
import textual.pilot
import textual.widgets

from uproot_browser.tui.browser import Browser
from uproot_browser.tui.jump import JumpScreen
from uproot_browser.tui.left_panel import UprootTree
from uproot_browser.tui.plot import Plotext

LEAF_PATH = "//T/event/fFlag"


async def wait_until(
    pilot: textual.pilot.Pilot[None],
    predicate: Callable[[], bool],
    *,
    tries: int = 100,
) -> None:
    """Pump the event loop until predicate holds (or give up after `tries`).

    Lazy-mounted widgets can take a variable number of message cycles to settle,
    especially on slower CI runners, so poll instead of guessing a pause count.
    """
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause()


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
        # Activate the Tools tab and wait for the Select to settle (Tools.on_mount
        # sets up the watcher that keeps it in sync with the theme).
        pilot.app.query_one(
            "#left-view", textual.widgets.TabbedContent
        ).active = "tab-2"
        await wait_until(
            pilot,
            lambda: (
                bool(pilot.app.query(textual.widgets.Select))
                and pilot.app.query_one(textual.widgets.Select).value
                != textual.widgets.Select.BLANK
            ),
        )
        select = pilot.app.query_one(textual.widgets.Select)
        assert select.value == pilot.app.theme

        pilot.app.theme = "nord"
        await wait_until(pilot, lambda: select.value == "nord")
        assert select.value == "nord"


async def test_jump_opens_and_lists_all() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        # Grab the tree before opening the modal: older Textual scopes
        # app.query_one to the active screen, so #tree-view is unreachable
        # once the JumpScreen is on top.
        expected = len(pilot.app.query_one("#tree-view", UprootTree).all_entries())
        await pilot.press("/")
        assert isinstance(pilot.app.screen, JumpScreen)
        results = pilot.app.screen.query_one(
            "#jump-results", textual.widgets.OptionList
        )
        assert results.option_count == expected


async def test_jump_filters_and_plots() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("/")
        await pilot.press(*"fflag")  # fuzzy-matches only fFlag
        await pilot.pause()
        results = pilot.app.screen.query_one(
            "#jump-results", textual.widgets.OptionList
        )
        assert results.get_option_at_index(0).id == LEAF_PATH

        await pilot.press("enter")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, JumpScreen)
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert item.selection == LEAF_PATH


async def test_jump_expands_ancestors() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tree.select_path(LEAF_PATH)
        await wait_until(
            pilot,
            lambda: (
                tree.cursor_node is not None
                and tree.cursor_node.data is not None
                and tree.cursor_node.data.path == LEAF_PATH
            ),
        )
        node = tree.cursor_node
        assert node is not None
        assert node.data is not None
        assert node.data.path == LEAF_PATH


async def test_jump_cancel() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("/")
        assert isinstance(pilot.app.screen, JumpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, JumpScreen)
        assert pilot.app.view_widget.item is None


async def test_help_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("?")
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"
