import io
from collections.abc import Callable

import pytest
import rich.console
import rich.style
import skhep_testdata
import textual.geometry
import textual.pilot
import textual.widgets

from uproot_browser.axis import AxisLimits
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.error import Error
from uproot_browser.tui.jump import JumpScreen
from uproot_browser.tui.left_panel import SCROLLOFF, UprootTree
from uproot_browser.tui.plot import Plotext
from uproot_browser.tui.right_panel import RightPanel

LEAF_PATH = "//T/event/fFlag"
EXPAND_EVENT = ("down", "down", "l", "j", "l")  # open //T/event: 26 lines deep


async def wait_until(
    pilot: textual.pilot.Pilot[None],
    predicate: Callable[[], bool],
    *,
    tries: int = 100,
    delay: float | None = None,
) -> None:
    """Pump the event loop until predicate holds (or give up after `tries`).

    Lazy-mounted widgets can take a variable number of message cycles to settle,
    especially on slower CI runners, so poll instead of guessing a pause count.
    Give a `delay` to wait for something on a timer, which needs real time.
    """
    for _ in range(tries):
        if predicate():
            return
        await pilot.pause(delay)


def plot_text(app: Browser) -> str:
    """The text the plot widget paints at the moment."""
    widget = app.view_widget.plot_widget
    region = textual.geometry.Region(0, 0, *widget.container_size)
    return "\n".join(strip.text for strip in widget.render_lines(region))


async def settle_render(pilot: textual.pilot.Pilot[None]) -> None:
    """Let a request reach the render worker, then wait for the canvas."""
    await pilot.pause()  # the request is posted after a refresh
    await pilot.pause()  # process RequestPlot → spawn the render worker
    await pilot.app.workers.wait_for_complete()  # block on the thread
    await pilot.pause()  # drain the update the worker posted


async def settled_plot(pilot: textual.pilot.Pilot[None]) -> Plotext:
    """Select the first plottable branch and wait for the render to settle."""
    await pilot.press("down", "down", "down", "enter")
    await settle_render(pilot)
    item = pilot.app.view_widget.item
    assert isinstance(item, Plotext)
    return item


def assert_canvas(app: Browser, item: Plotext) -> str:
    """The plot widget shows a canvas built for its own size."""
    content = app.view_widget.plot_widget.content_size
    assert item.size == (content.width, content.height)
    text = plot_text(app)
    assert "plotting" not in text
    assert "┌" in text or "┐" in text
    return text


async def test_browse_logo() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        assert pilot.app.view_widget.item is None


async def test_right_panel_toggle() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        panel = pilot.app.query_one("#right-panel")
        assert panel.display

        await pilot.press("r")
        assert not pilot.app.show_right_panel
        assert not panel.display

        await pilot.press("r")
        assert pilot.app.show_right_panel
        assert panel.display


async def test_browse_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        # Dump & Quit source for the text mode rebuilds the histogram
        assert item.dump_source().startswith('\nitem = uproot_file["')


async def test_axis_ranges_are_typed_in_right_panel() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        assert pilot.app.query_one("#y-min", textual.widgets.Input).display
        assert pilot.app.query_one("#y-max", textual.widgets.Input).display
        pilot.app.query_one("#x-min", textual.widgets.Input).value = "0.2"
        pilot.app.query_one("#x-max", textual.widgets.Input).value = "0.8"
        pilot.app.query_one("#y-min", textual.widgets.Input).value = "1"
        pilot.app.query_one("#y-max", textual.widgets.Input).value = "15"
        pilot.app.query_one("#x-min", textual.widgets.Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert pilot.app.axis_limits.x == (0.2, 0.8)
        assert pilot.app.axis_limits.y == (1.0, 15.0)
        panel = pilot.app.query_one(RightPanel)
        assert panel.status == "Applied."
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert "limits=AxisLimits(x=(0.2, 0.8), y=(1.0, 15.0))" in item.dump_source()

        # Selecting another node drops the limits and clears the panel
        pilot.app.query_one(UprootTree).focus()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert pilot.app.axis_limits == AxisLimits()
        assert pilot.app.query_one("#x-min", textual.widgets.Input).value == ""
        assert panel.status == ""


async def test_axis_range_rejects_bad_input() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        pilot.app.query_one("#x-max", textual.widgets.Input).value = "1,5"
        pilot.app.query_one("#x-max", textual.widgets.Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        panel = pilot.app.query_one(RightPanel)
        assert panel.status == "Axis limits must be finite numbers, not '1,5'."
        assert pilot.app.axis_limits == AxisLimits()


async def test_plot_canvas_matches_widget_size() -> None:
    """The finished canvas replaces the placeholder, built for the plot pane."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        assert_canvas(pilot.app, await settled_plot(pilot))


async def test_resize_replots_at_the_new_size() -> None:
    async with Browser(skhep_testdata.data_path("uproot-Event.root")).run_test(
        size=(80, 24)
    ) as pilot:
        item = await settled_plot(pilot)
        before_size = item.size
        before_text = assert_canvas(pilot.app, item)

        await pilot.resize_terminal(100, 40)
        # the resize render is debounced, so it needs some real time
        await wait_until(pilot, lambda: item.size != before_size, delay=0.05)
        await settle_render(pilot)

        assert assert_canvas(pilot.app, item) != before_text


async def test_expr_replots_and_clears_flag() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        before_text = assert_canvas(pilot.app, await settled_plot(pilot))

        plot_input = pilot.app.view_widget.plot_input
        plot_input.value = "h[::2j]"
        await pilot.pause()
        assert plot_input.has_class("-needs-update")

        plot_input.apply_expression()
        await settle_render(pilot)
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert item.expr == "h[::2j]"
        assert not plot_input.has_class("-needs-update")
        await wait_until(pilot, lambda: plot_text(pilot.app) != before_text, delay=0.05)

        assert assert_canvas(pilot.app, item) != before_text


async def test_branch_array_cut_replots() -> None:
    """Branch-array cuts render through the same input as histogram slices."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        pilot.app.query_one("#tree-view", UprootTree).select_path("//T/event/fNtrack")
        await settle_render(pilot)
        view = pilot.app.view_widget
        original = view.item
        assert isinstance(original, Plotext)
        before = assert_canvas(pilot.app, original)

        expression = 't["fTracks.fPx"][t["fTracks.fPy"] < 0]'
        view.plot_input.value = expression
        view.plot_input.apply_expression()
        await settle_render(pilot)

        item = view.item
        assert isinstance(item, Plotext)
        assert item.selection == original.selection
        assert item.expr == expression
        assert assert_canvas(pilot.app, item) != before


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


async def test_nonplottable_grayed_but_errors() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press("down")  # ProcessID0: a TProcessID, not plottable
        node = tree.cursor_node
        assert node is not None
        assert node.data is not None
        assert node.data.path == "//ProcessID0"

        label = tree.render_label(node, rich.style.Style(), rich.style.Style())
        assert any(span.style == "dim" for span in label.spans)

        # selecting still tries to plot, showing the error in the plot window
        await pilot.press("enter")
        await pilot.pause()  # process RequestPlot → spawn the render worker
        await pilot.app.workers.wait_for_complete()  # block on the thread
        await pilot.pause()  # drain the ErrorMessage the worker posted
        assert isinstance(pilot.app.view_widget.item, Error)


async def test_theme_switch_updates_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        item_before = pilot.app.view_widget.item
        assert isinstance(item_before, Plotext)
        assert item_before.theme == "uproot_dark"

        pilot.app.theme = "textual-light"
        await pilot.pause()
        item_after = pilot.app.view_widget.item
        assert isinstance(item_after, Plotext)
        # the item must be replaced, not mutated, so the plot re-renders
        assert item_after is not item_before
        assert item_after.theme == "uproot_light"


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
        expected = len(pilot.app.query_one("#tree-view", UprootTree).all_entries)
        await pilot.press("/")
        assert isinstance(pilot.app.screen, JumpScreen)
        results = pilot.app.screen.query_one(
            "#jump-results", textual.widgets.OptionList
        )
        # on_mount population can lag on slow runners; let it settle
        for _ in range(10):
            if results.option_count:
                break
            await pilot.pause()
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


async def test_count_prefix_motion() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press(*EXPAND_EVENT)
        await pilot.pause()
        assert tree.cursor_line == 3

        await pilot.press("1", "2", "j")
        await pilot.pause()
        assert tree.cursor_line == 15

        await pilot.press("5", "k")
        await pilot.pause()
        assert tree.cursor_line == 10

        await pilot.press("k")  # no count: single step
        await pilot.pause()
        assert tree.cursor_line == 9


async def test_count_prefix_shown_and_reset() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tabs = pilot.app.query_one("#left-view", textual.widgets.TabbedContent)
        await pilot.press(*EXPAND_EVENT)
        await pilot.pause()

        await pilot.press("4")
        await pilot.pause()
        assert tabs.get_tab("tree-tab").label_text == "Tree 4"

        await pilot.press("left_shift")  # bare modifiers keep the count
        await pilot.pause()
        assert tabs.get_tab("tree-tab").label_text == "Tree 4"

        await pilot.press("x")  # any other key discards the count
        await pilot.pause()
        assert tabs.get_tab("tree-tab").label_text == "Tree"

        line = tree.cursor_line
        await pilot.press("j")
        await pilot.pause()
        assert tree.cursor_line == line + 1


async def test_scrolloff_keeps_context_visible() -> None:
    async with Browser(skhep_testdata.data_path("uproot-Event.root")).run_test(
        size=(80, 24)
    ) as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press(*EXPAND_EVENT)
        await pilot.pause()
        height = tree.scrollable_content_region.height
        assert tree.last_line > height  # the tree must overflow for this to matter

        await pilot.press("1", "5", "j")  # down, past the fold
        await pilot.pause()
        last_visible = tree.scroll_offset.y + height - 1
        assert tree.cursor_line + SCROLLOFF <= last_visible

        await pilot.press("9", "9", "j")  # clamp to the last line
        await pilot.pause()
        assert tree.cursor_line == tree.last_line
        top = tree.scroll_offset.y

        await pilot.press(*str(tree.cursor_line - top), "k")  # up to the view top
        await pilot.pause()
        assert tree.cursor_line - SCROLLOFF >= tree.scroll_offset.y


async def test_help_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("?")
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"


async def test_dump_error_shows_branch() -> None:
    """Dump & Quit names the branch that produced the traceback."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "enter")  # ProcessID0 is not plottable
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()  # drain the ErrorMessage the worker posted
        item = pilot.app.view_widget.item
        assert isinstance(item, Error)
        msg, items = pilot.app.dump_source()
        assert items == [item]
        assert 'item = uproot_file["ProcessID0"]' in msg


async def test_dump_plot_renders_canvas() -> None:
    """Dump & Quit prints the plot, not the "... plotting ..." placeholder."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        _, items = pilot.app.dump_source()
        console = rich.console.Console(
            width=40, file=io.StringIO(), force_terminal=True
        )
        with console.capture() as capture:
            console.print(*items)
        out = capture.get()
        assert "plotting" not in out
        assert "┌" in out or "┐" in out


async def test_dump_survives_render_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dump & Quit stays alive if the plot cannot be rendered."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        def raise_error(*_args: object, **_kwargs: object) -> str:
            msg = "render failed"
            raise ValueError(msg)

        monkeypatch.setattr("uproot_browser.tui.plot.render_canvas", raise_error)
        _, items = pilot.app.dump_source()
        assert items == []
