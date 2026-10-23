import io
from collections.abc import Callable

import pytest
import rich.console
import rich.style
import rich.text
import skhep_testdata
import textual.geometry
import textual.pilot
import textual.widgets

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import AxisLimits
from uproot_browser.exceptions import EmptyTreeError
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.error import Error
from uproot_browser.tui.help import HelpScreen
from uproot_browser.tui.jump import JumpScreen
from uproot_browser.tui.left_panel import SCROLLOFF, UprootTree
from uproot_browser.tui.messages import ExpressionErrorMessage
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


async def jump_to(pilot: textual.pilot.Pilot[None], path: str) -> None:
    """Select ``path`` and wait for the cursor, which moves after a refresh."""
    tree = pilot.app.query_one("#tree-view", UprootTree)
    tree.select_path(path)
    await wait_until(
        pilot,
        lambda: (
            tree.cursor_node is not None
            and tree.cursor_node.data is not None
            and tree.cursor_node.data.path == path
        ),
    )


def node_at(parent: object, path: str) -> object:
    """The child of ``parent`` whose entry has ``path``."""
    return next(
        node
        for node in parent.children  # type: ignore[attr-defined]
        if node.data is not None and node.data.path == path
    )


def label_text(tree: UprootTree, node: object) -> str:
    style = rich.style.Style()
    return tree.render_label(node, style, style).plain  # type: ignore[arg-type]


async def click_label(
    pilot: textual.pilot.Pilot[None], node: object, **kwargs: bool
) -> None:
    tree = pilot.app.query_one("#tree-view", UprootTree)
    label = tree._get_label_region(node.line)  # type: ignore[attr-defined]  # noqa: SLF001
    assert label is not None
    offset = tree.content_region.offset - tree.region.offset - tree.scroll_offset
    await pilot.click(
        tree,
        offset=(label.x + label.width // 2 + offset.x, label.y + offset.y),
        **kwargs,
    )
    await pilot.pause()


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

        await pilot.press("t")
        assert not pilot.app.show_right_panel
        assert not panel.display

        await pilot.press("t")
        assert pilot.app.show_right_panel
        assert panel.display


async def test_entry_box_toggle() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        entry_box = pilot.app.query_one("#plot-input-container")
        plot_input = pilot.app.view_widget.plot_input
        assert not entry_box.display

        await settled_plot(pilot)
        await pilot.press("e")
        assert pilot.app.show_entry_box
        assert entry_box.display
        assert plot_input.has_focus

        # Typing "e" in the box must not close it; escape does
        await pilot.press("e")
        assert entry_box.display
        assert plot_input.value == "e"

        await pilot.press("escape")
        assert not pilot.app.show_entry_box
        assert not entry_box.display
        assert pilot.app.query_one("#tree-view").has_focus

        await pilot.press("e", "tab")
        assert not plot_input.has_focus
        await pilot.press("e")
        assert not entry_box.display


async def test_entry_box_toggle_without_plot_keeps_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view")
        assert tree.has_focus

        # The entry box is part of the plot window, which is not shown yet
        await pilot.press("e")
        assert pilot.app.show_entry_box
        assert tree.has_focus


async def test_entry_box_toggle_rerenders_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        item = await settled_plot(pilot)
        assert item.size is not None
        _, height = item.size

        await pilot.press("e")
        await wait_until(pilot, lambda: item.size is not None and item.size[1] < height)
        assert item.size is not None
        assert item.size[1] < height


async def test_help_blocks_panel_keys() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("f1", "e", "t", "b", "d")
        assert isinstance(pilot.app.screen, HelpScreen)
        assert not pilot.app.show_entry_box
        assert pilot.app.show_right_panel
        assert pilot.app.show_tree


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


@pytest.mark.parametrize(
    "expr", ["h[::2j]", 'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]']
)
async def test_expr_replots_and_clears_flag(expr: str) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await jump_to(pilot, "//T/event/fNtrack")
        await settle_render(pilot)
        original = pilot.app.view_widget.item
        assert isinstance(original, Plotext)
        before_text = assert_canvas(pilot.app, original)

        plot_input = pilot.app.view_widget.plot_input
        plot_input.value = expr
        await pilot.pause()
        assert plot_input.has_class("-needs-update")

        plot_input.apply_expression()
        await settle_render(pilot)
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert item.expr == expr
        assert not plot_input.has_class("-needs-update")
        await wait_until(pilot, lambda: plot_text(pilot.app) != before_text, delay=0.05)

        assert assert_canvas(pilot.app, item) != before_text


async def test_expr_cached_across_theme_change(monkeypatch: pytest.MonkeyPatch) -> None:
    """A redraw reuses the evaluated tree expression instead of re-reading data."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await jump_to(pilot, "//T/event/fNtrack")
        await settle_render(pilot)
        plot_input = pilot.app.view_widget.plot_input
        plot_input.value = (
            'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]'
        )
        plot_input.apply_expression()
        await settle_render(pilot)
        assert isinstance(pilot.app.view_widget.item, Plotext)

        def fail_eval(*_args: object, **_kwargs: object) -> None:
            msg = "expression was evaluated"
            raise AssertionError(msg)

        monkeypatch.setattr(uproot_browser.plot, "evaluate_expr", fail_eval)
        pilot.app.theme = "textual-light"
        await settle_render(pilot)
        # a re-evaluation would have raised, replacing the item with an Error
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert_canvas(pilot.app, item)


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
        select = pilot.app.query_one("#theme-select", textual.widgets.Select)
        await wait_until(pilot, lambda: select.value != textual.widgets.Select.BLANK)
        assert select.value == pilot.app.theme

        pilot.app.theme = "nord"
        await wait_until(pilot, lambda: select.value == "nord")
        assert select.value == "nord"

        select.value = "textual-light"
        await wait_until(pilot, lambda: pilot.app.theme == "textual-light")
        assert pilot.app.theme == "textual-light"


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
        await jump_to(pilot, LEAF_PATH)


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


@pytest.mark.parametrize(("down", "up"), [("down", "up"), ("j", "k")])
async def test_count_prefix_motion(down: str, up: str) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press(*EXPAND_EVENT)
        await pilot.pause()
        assert tree.cursor_line == 3

        await pilot.press("1", "2", down)
        await pilot.pause()
        assert tree.cursor_line == 15
        assert not pilot.app.query_one("#navigation-count").display

        await pilot.press("5", up)
        await pilot.pause()
        assert tree.cursor_line == 10

        await pilot.press("k")  # no count: single step
        await pilot.pause()
        assert tree.cursor_line == 9


async def test_count_prefix_after_click() -> None:
    async with Browser(skhep_testdata.data_path("uproot-Event.root")).run_test(
        size=(160, 50)
    ) as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press(*EXPAND_EVENT)
        await pilot.pause()
        assert tree.cursor_node is not None
        flag = node_at(tree.cursor_node, LEAF_PATH)
        await click_label(pilot, flag)
        assert tree.cursor_node is flag

        await pilot.press("2", "down")
        await pilot.pause()
        assert tree.cursor_node is not None
        assert tree.cursor_node.data is not None
        assert tree.cursor_node.data.path == "//T/event/fHighPt"
        assert not pilot.app.query_one("#navigation-count").display


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
        assert tabs.get_tab("tree-tab").label_text == "Tree"
        status = pilot.app.query_one("#navigation-count", textual.widgets.Static)
        assert status.display
        region = textual.geometry.Region(0, 0, *status.content_size)
        assert (
            "".join(line.text for line in status.render_lines(region)).strip()
            == "Move: 4"
        )
        footer = pilot.app.query_one(textual.widgets.Footer)
        assert status.region.bottom == footer.region.y
        assert status.region.height == 1

        await pilot.press("left_shift")  # bare modifiers keep the count
        await pilot.pause()
        assert status.display

        await pilot.press("x")  # any other key discards the count
        await pilot.pause()
        assert tabs.get_tab("tree-tab").label_text == "Tree"
        assert not status.display

        line = tree.cursor_line
        await pilot.press("j")
        await pilot.pause()
        assert tree.cursor_line == line + 1


async def test_count_prefix_keeps_layout() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        views = [pilot.app.query_one(f"#{name}") for name in ("left-view", "plot-view")]
        before = [view.region for view in views]
        tree_height = tree.scrollable_content_region.height

        await pilot.press("2")
        await pilot.pause()
        assert pilot.app.query_one("#navigation-count").display
        assert [view.region for view in views] == before
        assert tree.scrollable_content_region.height == tree_height


async def test_count_prefix_cleared_on_blur() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        status = pilot.app.query_one("#navigation-count", textual.widgets.Static)
        assert not status.display
        await pilot.press("down", "2")
        await pilot.pause()
        assert status.display

        pilot.app.set_focus(None)
        await pilot.pause()
        assert not status.display

        tree.focus()
        await pilot.pause()
        line = tree.cursor_line
        await pilot.press("down")
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


async def apply_failing_expression(pilot: textual.pilot.Pilot[None], expr: str) -> None:
    view = pilot.app.view_widget
    view.input_container.add_class("-show-container")
    await settle_render(pilot)
    view.plot_input.value = expr
    view.plot_input.apply_expression()
    await settle_render(pilot)


@pytest.mark.parametrize("expr", ["42", "h[", "np.array([])"])
async def test_expression_failure_can_be_corrected(expr: str) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        original = await settled_plot(pilot)
        await apply_failing_expression(pilot, expr)
        view = pilot.app.view_widget

        assert isinstance(view.item, Plotext)
        assert view.item.selection == original.selection
        assert view.current == "plot-window"
        assert view.plot_input.region.height > 0
        assert view.plot_input.has_class("-needs-update")

        # Clearing the input restores the original plot without reselecting it.
        view.plot_input.value = ""
        view.plot_input.apply_expression()
        await settle_render(pilot)
        assert isinstance(view.item, Plotext)
        assert view.item.expr == ""
        assert_canvas(pilot.app, view.item)
        assert not view.plot_input.has_class("-needs-update")


async def test_superseded_expression_error_is_ignored() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        original = await settled_plot(pilot)
        view = pilot.app.view_widget
        view.item = original.with_expr("h[::2j]")
        await settle_render(pilot)
        before = plot_text(pilot.app)

        pilot.app.post_message(ExpressionErrorMessage(original, EmptyTreeError("old")))
        await pilot.pause()
        assert plot_text(pilot.app) == before
        assert not view.plot_input.has_class("-needs-update")


@pytest.mark.parametrize(
    ("expr", "message"),
    [
        (
            'int("[/x] h[bold]")',
            "invalid literal for int() with base 10: '[/x] h[bold]'",
        ),
        ('exec("raise KeyError")', "KeyError"),
    ],
)
async def test_expression_error_notification_text(expr: str, message: str) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await settled_plot(pilot)
        await apply_failing_expression(pilot, expr)
        (notification,) = pilot.app._notifications  # noqa: SLF001
        # The message is shown as written, not parsed as markup.
        assert rich.text.Text.from_markup(notification.message).plain == message


async def test_expression_error_not_repeated_on_resize() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await settled_plot(pilot)
        await apply_failing_expression(pilot, "h[")
        await pilot.resize_terminal(100, 40)
        await pilot.pause(0.3)
        await settle_render(pilot)
        assert len(pilot.app._notifications) == 1  # noqa: SLF001


async def test_draw_error_with_expression_shows_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_error(*_args: object, **_kwargs: object) -> None:
        msg = "draw failed"
        raise RuntimeError(msg)

    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await settled_plot(pilot)
        monkeypatch.setattr(uproot_browser.plot, "draw_hist", raise_error)
        await apply_failing_expression(pilot, "h[::2j]")
        assert isinstance(pilot.app.view_widget.item, Error)
        assert not pilot.app.view_widget.plot_input.has_class("-needs-update")


async def test_splitter_drag_resizes_panels() -> None:
    async with Browser(skhep_testdata.data_path("uproot-Event.root")).run_test(
        size=(120, 30)
    ) as pilot:
        await pilot.press("f")
        await pilot.pause()
        left = pilot.app.query_one("#left-view")
        right = pilot.app.query_one("#right-panel")
        view = pilot.app.query_one("#plot-view")
        left_width = left.region.width
        right_width = right.region.width
        total = view.region.width

        # Screen coordinates: the bar moves with the panel while dragging.
        bar = pilot.app.query_one("#left-splitter").region
        await pilot.mouse_down(offset=(bar.x, bar.y + 1))
        await pilot.hover(offset=(bar.x + 10, bar.y + 1))
        await pilot.mouse_up(offset=(bar.x + 10, bar.y + 1))
        await pilot.pause()
        assert left.region.width == left_width + 10
        assert view.region.width == total - 10

        bar = pilot.app.query_one("#right-splitter").region
        await pilot.mouse_down(offset=(bar.x, bar.y + 1))
        await pilot.hover(offset=(bar.x - 5, bar.y + 1))
        await pilot.mouse_up(offset=(bar.x - 5, bar.y + 1))
        await pilot.pause()
        assert right.region.width == right_width + 5
        assert view.region.width == total - 15


async def test_click_toggles_directory() -> None:
    """A plain click on a tree opens it, and a second click closes it."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        node = node_at(tree.root, "//T")
        assert not node.is_expanded
        await click_label(pilot, node)
        assert node.is_expanded
        await click_label(pilot, node)
        assert not node.is_expanded


async def test_mark_two_branches_plots_2d() -> None:
    """Marking a second branch plots the pair; both keep their axis labels."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await jump_to(pilot, "//T/event/fNtrack")
        await pilot.press("m")
        x_node = tree.cursor_node
        assert tree.marks == [x_node]
        assert label_text(tree, x_node).startswith("x: ")
        await jump_to(pilot, LEAF_PATH)
        await pilot.press("m")
        y_node = tree.cursor_node
        await settle_render(pilot)

        item = pilot.app.view_widget.item
        if uproot_browser.plotext_compat.PLOTEXT_6:
            assert isinstance(item, Plotext)
            assert (item.selection, item.y_selection) == (
                "//T/event/fNtrack",
                LEAF_PATH,
            )
            text = plot_text(pilot.app)
            assert "fNtrack" in text
            assert "fFlag" in text
        else:
            assert isinstance(item, Error)
            assert "plotext 6" in str(item.exc)
        assert tree.marks == [x_node, y_node]
        assert label_text(tree, x_node).startswith("x: ")
        assert label_text(tree, y_node).startswith("y: ")
        msg, _ = pilot.app.dump_source()
        assert 'x_item = uproot_file["T/event/fNtrack"]' in msg
        assert f'y_item = uproot_file["{LEAF_PATH.lstrip("/")}"]' in msg

        # A single plot replaces the pair, but keeps a pending x mark
        await pilot.press("enter")
        await pilot.pause()
        assert tree.marks == []
        await pilot.press("m")
        assert tree.marks == [y_node]
        await pilot.press("enter")
        await pilot.pause()
        assert tree.marks == [y_node]


async def test_mark_toggles_and_rejects_non_numeric() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await jump_to(pilot, "//T/event/fNtrack")
        await pilot.press("m")
        assert tree.marks
        await pilot.press("m")
        assert tree.marks == []

        await jump_to(pilot, "//T/event/fEventName")
        await pilot.press("m")
        assert tree.marks == []
        assert pilot.app._notifications  # noqa: SLF001


async def test_shift_click_pairs_with_cursor() -> None:
    """Shift+click plots the branch at the cursor (x) against the clicked one (y)."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await jump_to(pilot, "//T/event/fNtrack")
        x_node = tree.cursor_node
        assert x_node is not None
        flag = node_at(x_node.parent, LEAF_PATH)
        await click_label(pilot, flag, shift=True)
        await pilot.pause()

        assert tree.cursor_node is flag
        assert tree.marks == [x_node, flag]
        item = pilot.app.view_widget.item
        assert item is not None
        assert (item.selection, item.y_selection) == ("//T/event/fNtrack", LEAF_PATH)


async def test_shift_click_needs_numeric_cursor() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await pilot.press(*EXPAND_EVENT)  # the cursor stays on //T/event
        await pilot.pause()
        flag = node_at(tree.cursor_node, LEAF_PATH)
        await click_label(pilot, flag, shift=True)
        assert tree.marks == []
        assert pilot.app.view_widget.item is None
        assert pilot.app._notifications  # noqa: SLF001
