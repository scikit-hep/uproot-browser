import concurrent.futures
import io
import pathlib
import shutil
from collections.abc import Callable

import pytest
import rich.console
import rich.style
import rich.text
import skhep_testdata
import textual.geometry
import textual.pilot
import textual.widgets
import uproot

import uproot_browser.plot
import uproot_browser.plotext_compat
from uproot_browser.axis import AxisLimits
from uproot_browser.exceptions import EmptyTreeError
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.error import Error
from uproot_browser.tui.help import HelpScreen
from uproot_browser.tui.jump import JumpScreen
from uproot_browser.tui.left_panel import SCROLLOFF, UprootTree
from uproot_browser.tui.messages import (
    EmptyMessage,
    ErrorMessage,
    ExpressionErrorMessage,
    UprootSelected,
)
from uproot_browser.tui.plot import Plotext, render_canvas
from uproot_browser.tui.right_panel import RightPanel

LEAF_PATH = "//T/event/fFlag"
# Open //T, then //T/event (26 lines deep)
EXPAND_EVENT = (("down", "down", "l"), ("j", "l"))


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
    # A slow runner can need more cycles; the size is set as the worker starts
    await wait_until(
        pilot,
        lambda: (
            not isinstance(item := pilot.app.view_widget.item, Plotext)
            or item.size is not None
        ),
    )
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


async def expand_event(pilot: textual.pilot.Pilot[None]) -> None:
    """Open //T/event and wait for its children, which load lazily."""
    tree = pilot.app.query_one("#tree-view", UprootTree)
    # Each expansion must load before the cursor moves into it
    for keys in EXPAND_EVENT:
        await pilot.press(*keys)
        await wait_until(
            pilot,
            lambda: tree.cursor_node is not None and bool(tree.cursor_node.children),
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


TREE_CUT_EXPR = 'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]'


def raise_error(*_args: object, **_kwargs: object) -> None:
    msg = "render failed"
    raise RuntimeError(msg)


async def test_right_panel_toggle() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        assert pilot.app.view_widget.item is None
        panel = pilot.app.query_one("#right-panel")
        assert panel.display
        # the image scale tool only exists in image mode
        assert not pilot.app.query("#right-panel #image-scale-select")

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
        tree = pilot.app.query_one("#tree-view")
        assert not entry_box.display
        assert tree.has_focus

        # The entry box is part of the plot window, which is not shown yet,
        # so the tree keeps the focus
        await pilot.press("e")
        assert pilot.app.show_entry_box
        assert tree.has_focus
        await pilot.press("e")
        assert not pilot.app.show_entry_box

        item = await settled_plot(pilot)
        assert item.size is not None
        _, height = item.size
        await pilot.press("e")
        assert pilot.app.show_entry_box
        assert entry_box.display
        assert plot_input.has_focus
        # the plot re-renders in the space the box leaves
        await wait_until(pilot, lambda: item.size is not None and item.size[1] < height)

        # Typing "e" in the box must not close it; escape does
        await pilot.press("e")
        assert entry_box.display
        assert plot_input.value == "e"

        await pilot.press("escape")
        assert not pilot.app.show_entry_box
        assert not entry_box.display
        assert tree.has_focus

        await pilot.press("e", "tab")
        assert not plot_input.has_focus
        await pilot.press("e")
        assert not entry_box.display


async def test_help_screen() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("f1", "e", "t", "b", "d")
        assert isinstance(pilot.app.screen, HelpScreen)
        assert not pilot.app.show_entry_box
        assert pilot.app.show_right_panel
        assert pilot.app.show_tree
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"

        await pilot.press("escape")
        assert not isinstance(pilot.app.screen, HelpScreen)
        await pilot.press("?")
        assert isinstance(pilot.app.screen, HelpScreen)


async def test_plot_first_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The finished canvas replaces the placeholder, built for the plot pane."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        item = await settled_plot(pilot)
        assert item.theme == "uproot_dark"
        assert_canvas(pilot.app, item)
        # Dump & Quit source for the text mode rebuilds and draws the histogram
        msg, items = pilot.app.dump_source()
        assert '\nitem = uproot_file["' in msg
        assert "import plotext as plt" in msg
        assert "uproot_browser" not in msg

        # Dump & Quit prints the plot, not the "... plotting ..." placeholder
        console = rich.console.Console(
            width=40, file=io.StringIO(), force_terminal=True
        )
        with console.capture() as capture:
            console.print(*items)
        out = capture.get()
        assert "plotting" not in out
        assert "┌" in out or "┐" in out

        # A theme change replaces the item, not mutates it, so the plot re-renders
        pilot.app.theme = "textual-light"
        await pilot.pause()
        item_after = pilot.app.view_widget.item
        assert isinstance(item_after, Plotext)
        assert item_after is not item
        assert item_after.theme == "uproot_light"
        await settle_render(pilot)
        assert_canvas(pilot.app, item_after)

        # Dump & Quit stays alive if the plot cannot be rendered
        monkeypatch.setattr("uproot_browser.tui.plot.render_canvas", raise_error)
        _, items = pilot.app.dump_source()
        assert items == []


async def test_axis_ranges_are_typed_in_right_panel() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        panel = pilot.app.query_one(RightPanel)
        assert pilot.app.query_one("#y-min", textual.widgets.Input).display
        assert pilot.app.query_one("#y-max", textual.widgets.Input).display

        pilot.app.query_one("#x-max", textual.widgets.Input).value = "1,5"
        pilot.app.query_one("#x-max", textual.widgets.Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert panel.status == "Axis limits must be finite numbers, not '1,5'."
        assert pilot.app.axis_limits == AxisLimits()

        pilot.app.query_one("#x-min", textual.widgets.Input).value = "0.2"
        pilot.app.query_one("#x-max", textual.widgets.Input).value = "0.8"
        pilot.app.query_one("#y-min", textual.widgets.Input).value = "1"
        pilot.app.query_one("#y-max", textual.widgets.Input).value = "15"
        pilot.app.query_one("#x-min", textual.widgets.Input).focus()
        await pilot.press("enter")
        await pilot.pause()
        assert pilot.app.axis_limits.x == (0.2, 0.8)
        assert pilot.app.axis_limits.y == (1.0, 15.0)
        assert panel.status == "Applied."
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        source = item.dump_source()
        assert "lim(0.2, 0.8)" in source
        assert "lim(1.0, 15.0)" in source

        # Selecting another node drops the limits and clears the panel
        pilot.app.query_one(UprootTree).focus()
        await pilot.press("down", "enter")
        await pilot.pause()
        assert pilot.app.axis_limits == AxisLimits()
        assert pilot.app.query_one("#x-min", textual.widgets.Input).value == ""
        assert panel.status == ""


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


async def test_plot_renders_after_late_layout() -> None:
    """A request that arrives before the plot widget has a size is retried."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        plot_widget = pilot.app.view_widget.plot_widget
        plot_widget.display = False
        await jump_to(pilot, LEAF_PATH)
        await pilot.pause()
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert item.size is None

        plot_widget.display = True
        await settle_render(pilot)
        assert_canvas(pilot.app, item)


async def test_expr_replots_and_clears_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await jump_to(pilot, "//T/event/fNtrack")
        await settle_render(pilot)
        view = pilot.app.view_widget
        assert isinstance(view.item, Plotext)
        before_text = assert_canvas(pilot.app, view.item)

        for expr in ("h[::2j]", TREE_CUT_EXPR):
            view.plot_input.value = expr
            await pilot.pause()
            assert view.plot_input.has_class("-needs-update")

            view.plot_input.apply_expression()
            await settle_render(pilot)
            item = view.item
            assert isinstance(item, Plotext)
            assert item.expr == expr
            assert not view.plot_input.has_class("-needs-update")
            await wait_until(
                pilot,
                lambda before=before_text: plot_text(pilot.app) != before,
                delay=0.05,
            )
            text = assert_canvas(pilot.app, item)
            assert text != before_text
            before_text = text

        # A redraw reuses the evaluated tree expression instead of re-reading data
        def fail_eval(*_args: object, **_kwargs: object) -> None:
            msg = "expression was evaluated"
            raise AssertionError(msg)

        monkeypatch.setattr(uproot_browser.plot, "evaluate_expr", fail_eval)
        pilot.app.theme = "textual-light"
        await settle_render(pilot)
        # a re-evaluation would have raised, replacing the item with an Error
        item = view.item
        assert isinstance(item, Plotext)
        assert_canvas(pilot.app, item)


@pytest.mark.parametrize(
    "keys", [("down", "space", "down", "enter"), ("j", "l", "j", "enter")]
)
async def test_browse_empty(keys: tuple[str, ...]) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press(*keys)
        await settle_render(pilot)  # the worker posts an EmptyMessage
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
        await settle_render(pilot)  # the worker posts an ErrorMessage
        item = pilot.app.view_widget.item
        assert isinstance(item, Error)

        # Dump & Quit names the branch that produced the traceback
        msg, items = pilot.app.dump_source()
        assert items == [item]
        assert 'item = uproot_file["ProcessID0"]' in msg


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


async def test_jump_screen() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        # Grab the tree before opening the modal: older Textual scopes
        # app.query_one to the active screen, so #tree-view is unreachable
        # once the JumpScreen is on top.
        expected = len(pilot.app.query_one("#tree-view", UprootTree).jump_candidates())
        await pilot.press("/")
        assert isinstance(pilot.app.screen, JumpScreen)
        results = pilot.app.screen.query_one(
            "#jump-results", textual.widgets.OptionList
        )
        # on_mount population can lag on slow runners; let it settle
        await wait_until(pilot, lambda: bool(results.option_count), tries=10)
        assert results.option_count == expected

        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(pilot.app.screen, JumpScreen)
        assert pilot.app.view_widget.item is None

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


async def test_count_prefix_motion() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await expand_event(pilot)
        assert tree.cursor_line == 3

        for down, up in (("down", "up"), ("j", "k")):
            line = tree.cursor_line
            await pilot.press("1", "2", down)
            await pilot.pause()
            assert tree.cursor_line == line + 12
            assert not pilot.app.query_one("#navigation-count").display

            await pilot.press("5", up)
            await pilot.pause()
            assert tree.cursor_line == line + 7

            await pilot.press(up)  # no count: single step
            await pilot.pause()
            assert tree.cursor_line == line + 6


async def test_count_prefix_after_click() -> None:
    async with Browser(skhep_testdata.data_path("uproot-Event.root")).run_test(
        size=(160, 50)
    ) as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await expand_event(pilot)
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


async def test_count_prefix_display() -> None:
    """The pending count shows in a status line that does not move the layout."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        tabs = pilot.app.query_one("#left-view", textual.widgets.TabbedContent)
        status = pilot.app.query_one("#navigation-count", textual.widgets.Static)
        await expand_event(pilot)
        await pilot.pause()  # let the tree layout settle
        views = [pilot.app.query_one(f"#{name}") for name in ("left-view", "plot-view")]
        before = [view.region for view in views]
        tree_height = tree.scrollable_content_region.height
        assert not status.display

        await pilot.press("4")
        await pilot.pause()
        assert tabs.get_tab("tree-tab").label_text == "Tree"
        assert status.display
        region = textual.geometry.Region(0, 0, *status.content_size)
        assert (
            "".join(line.text for line in status.render_lines(region)).strip()
            == "Move: 4"
        )
        footer = pilot.app.query_one(textual.widgets.Footer)
        assert status.region.bottom == footer.region.y
        assert status.region.height == 1
        assert [view.region for view in views] == before
        assert tree.scrollable_content_region.height == tree_height

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

        # losing the focus also discards the count
        await pilot.press("2")
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
        await expand_event(pilot)
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


async def apply_failing_expression(pilot: textual.pilot.Pilot[None], expr: str) -> None:
    view = pilot.app.view_widget
    view.input_container.add_class("-show-container")
    await settle_render(pilot)
    view.plot_input.value = expr
    view.plot_input.apply_expression()
    await settle_render(pilot)


async def test_expression_failure_can_be_corrected() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        original = await settled_plot(pilot)
        view = pilot.app.view_widget

        for expr in ("42", "h[", "np.array([])"):
            await apply_failing_expression(pilot, expr)
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


async def test_expression_error_notification_text() -> None:
    cases = [
        (
            'int("[/x] h[bold]")',
            "invalid literal for int() with base 10: '[/x] h[bold]'",
        ),
        ('exec("raise KeyError")', "KeyError"),
    ]
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await settled_plot(pilot)
        for count, (expr, message) in enumerate(cases, 1):
            await apply_failing_expression(pilot, expr)
            notifications = list(pilot.app._notifications)  # noqa: SLF001
            assert len(notifications) == count
            # The message is shown as written, not parsed as markup.
            assert (
                rich.text.Text.from_markup(notifications[-1].message).plain == message
            )

        # A resize re-renders, but must not repeat the error
        await pilot.resize_terminal(100, 40)
        await pilot.pause(0.3)
        await settle_render(pilot)
        assert len(pilot.app._notifications) == len(cases)  # noqa: SLF001


async def test_draw_error_with_expression_shows_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        await jump_to(pilot, "//T/event/fEventName")
        await pilot.press("m")  # not numeric: refused with a notification
        assert tree.marks == []
        await pilot.pause()  # the notification arrives as a message
        assert pilot.app._notifications  # noqa: SLF001

        await jump_to(pilot, "//T/event/fNtrack")
        await pilot.press("m")
        x_node = tree.cursor_node
        assert tree.marks == [x_node]
        assert label_text(tree, x_node).startswith("x: ")
        await pilot.press("m")  # toggles off
        assert tree.marks == []
        await pilot.press("m")
        assert tree.marks == [x_node]

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


async def test_shift_click_pairs_with_cursor() -> None:
    """Shift+click plots the branch at the cursor (x) against the clicked one (y)."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        await expand_event(pilot)  # the cursor stays on //T/event
        flag = node_at(tree.cursor_node, LEAF_PATH)
        await click_label(pilot, flag, shift=True)  # needs a numeric cursor
        assert tree.marks == []
        assert pilot.app.view_widget.item is None
        assert pilot.app._notifications  # noqa: SLF001

        await jump_to(pilot, "//T/event/fNtrack")
        x_node = tree.cursor_node
        assert x_node is not None
        await click_label(pilot, flag, shift=True)
        await pilot.pause()

        assert tree.cursor_node is flag
        assert tree.marks == [x_node, flag]
        item = pilot.app.view_widget.item
        assert item is not None
        assert (item.selection, item.y_selection) == ("//T/event/fNtrack", LEAF_PATH)


def test_render_canvas_is_thread_safe() -> None:
    # A cancelled thread worker keeps running, so two renders can overlap
    # on plotext's shared global figure.
    item = uproot.open(skhep_testdata.data_path("uproot-Event.root"))["hstat"]

    def render() -> str:
        return render_canvas(item, "dark", 80, 24, expr="", limits=AxisLimits())

    expected = render()
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        results = list(pool.map(lambda _: render(), range(200)))
    assert results == [expected] * 200


async def test_browse_directory(tmp_path: pathlib.Path) -> None:
    """A directory lists its ROOT files; the dump opens the selected file."""
    shutil.copy(skhep_testdata.data_path("uproot-Event.root"), tmp_path / "a.root")
    (tmp_path / "sub").mkdir()
    nested = tmp_path / "sub" / "b.root"
    shutil.copy(skhep_testdata.data_path("uproot-hepdata-example.root"), nested)

    async with Browser(str(tmp_path)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        assert [c.data.path for c in tree.root.children if c.data] == [
            "//a.root",
            "//sub",
        ]
        await jump_to(pilot, "//sub/b.root/hpx")
        await settle_render(pilot)
        item = pilot.app.view_widget.item
        assert isinstance(item, Plotext)
        assert_canvas(pilot.app, item)

        msg, _ = pilot.app.dump_source()
        assert f'uproot_file = uproot.open("{nested}")' in msg
        assert 'item = uproot_file["hpx"]' in msg


async def test_jump_directory_is_lazy(root_dir: pathlib.Path) -> None:
    """Jump lists the files of a directory, and enters only the opened ones."""
    async with Browser(str(root_dir)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        assert [c.path for c in tree.jump_candidates()] == [
            "//a.root",
            "//sub",
            "//sub/b.root",
        ]
        assert not tree.upfile["a.root"].is_open
        assert not tree.upfile["sub/b.root"].is_open

        await jump_to(pilot, "//sub/b.root/hpx")
        await settle_render(pilot)
        paths = [c.path for c in tree.jump_candidates()]
        assert "//sub/b.root/hpx" in paths
        assert not any(p.startswith("//a.root/") for p in paths)


@pytest.mark.parametrize(("y_file", "same"), [("a.root", True), ("b.root", False)])
async def test_dump_directory_pair(
    tmp_path: pathlib.Path,
    y_file: str,
    same: bool,  # noqa: FBT001
) -> None:
    for name in ("a.root", "b.root"):
        shutil.copy(skhep_testdata.data_path("uproot-Event.root"), tmp_path / name)

    async with Browser(str(tmp_path)).run_test() as pilot:
        tree = pilot.app.query_one("#tree-view", UprootTree)
        x_path = "//a.root/T/event/fNtrack"
        y_path = f"//{y_file}{LEAF_PATH[1:]}"
        tree.post_message(UprootSelected(tree.upfile, x_path, y_path))
        await settle_render(pilot)

        msg, _ = pilot.app.dump_source()
        if same:
            assert f'uproot.open("{tmp_path / "a.root"}")' in msg
            assert 'x_item = uproot_file["T/event/fNtrack"]' in msg
            assert f'y_item = uproot_file["{LEAF_PATH.lstrip("/")}"]' in msg
        else:
            assert "uproot_browser" not in msg
            assert f'x_file = uproot.open("{tmp_path / "a.root"}")' in msg
            assert f'y_file = uproot.open("{tmp_path / y_file}")' in msg
            assert 'x_item = x_file["T/event/fNtrack"]' in msg
            assert f'y_item = y_file["{LEAF_PATH.lstrip("/")}"]' in msg


async def test_escape_in_right_panel_returns_to_tree() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        pilot.app.query_one("#x-min", textual.widgets.Input).focus()
        await pilot.press("1", "escape")
        await pilot.pause()
        assert pilot.app.is_running
        assert isinstance(pilot.app.focused, UprootTree)

        pilot.app.query_one("#theme-select", textual.widgets.Select).focus()
        await pilot.press("escape")
        await pilot.pause()
        assert pilot.app.is_running
        assert isinstance(pilot.app.focused, UprootTree)


async def test_superseded_render_errors_are_ignored() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        original = await settled_plot(pilot)
        view = pilot.app.view_widget
        view.item = original.with_expr("h[::2j]")
        await settle_render(pilot)
        before = plot_text(pilot.app)

        stale = Error(RuntimeError("old"), original.selection)
        pilot.app.post_message(ErrorMessage(stale, original))
        await pilot.pause()
        assert view.item is not stale
        assert plot_text(pilot.app) == before

        pilot.app.post_message(EmptyMessage(original))
        await pilot.pause()
        assert view.item is not None
        assert plot_text(pilot.app) == before
