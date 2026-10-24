import concurrent.futures
import functools

import pytest
import skhep_testdata

pytest.importorskip("textual_image")
pytest.importorskip("matplotlib")

import hist
import matplotlib.pyplot as plt
import textual.pilot
import textual.widgets
import textual_image.widget
import uproot

import uproot_browser.plot
import uproot_browser.plot_mpl
from uproot_browser.axis import AxisLimits
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.image_plot import MPLPlot, make_image
from uproot_browser.tui.left_panel import UprootTree
from uproot_browser.tui.messages import RequestImage


def test_make_image_object_branch() -> None:
    """A branch holding TH1 objects (AsObjects) is summed and plotted."""
    with uproot.open(skhep_testdata.data_path("uproot-Event.root")) as f:
        histogram = uproot_browser.plot.to_histogram(f["T"]["event"]["fH"])
    image = make_image(histogram, title="fH", dark=True, size=(400, 300))
    assert (image.width, image.height) == (400, 300)


def test_render_image_touches_no_pyplot_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendering builds its own Figure, so it is safe on a worker thread."""

    def no_pyplot(*_args: object, **_kwargs: object) -> None:
        msg = "render_image used pyplot"
        raise AssertionError(msg)

    monkeypatch.setattr(plt, "figure", no_pyplot)
    monkeypatch.setattr(plt, "gca", no_pyplot)
    with uproot.open(skhep_testdata.data_path("uproot-Event.root")) as f:
        histogram = uproot_browser.plot.to_histogram(f["hstat"])
    figures = plt.get_fignums()
    image = uproot_browser.plot_mpl.render_image(histogram, "t", size=(200, 100))
    assert (image.width, image.height) == (200, 100)
    assert plt.get_fignums() == figures


@pytest.mark.parametrize("scale", [1.0, 1.5, 2.0])
@pytest.mark.parametrize("width", [110, 123, 220, 388])
def test_render_image_exact_size(width: int, scale: float) -> None:
    """Floating point in figsize * dpi must not lose a pixel to truncation."""
    histogram = hist.Hist.new.Reg(4, 0, 1).Double()
    image = uproot_browser.plot_mpl.render_image(
        histogram, "t", size=(width, 301), scale=scale
    )
    assert (image.width, image.height) == (width, 301)


def test_render_image_2d() -> None:
    """The colorbar stays inside the image, and pyplot keeps no figure."""
    histogram = hist.Hist.new.Reg(4, 0, 1).Reg(4, 0, 1).Double()
    histogram.fill([0.1, 0.6], [0.2, 0.7])
    figures = plt.get_fignums()
    image = uproot_browser.plot_mpl.render_image(histogram, "t", size=(200, 100))
    assert (image.width, image.height) == (200, 100)
    assert plt.get_fignums() == figures


# singledispatch so plottable()'s to_histogram.dispatch probe still works
@functools.singledispatch
def _fail_build(*_args: object, **_kwargs: object) -> None:
    msg = "histogram was rebuilt"
    raise AssertionError(msg)


async def _settle(pilot: textual.pilot.Pilot[object]) -> None:
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()


async def _apply_expression(pilot: textual.pilot.Pilot[object], expr: str) -> None:
    view = pilot.app.view_widget
    view.input_container.add_class("-show-container")
    await pilot.pause()
    view.plot_input.value = expr
    view.plot_input.apply_expression()
    await _settle(pilot)


async def _open_settled_plot(pilot: textual.pilot.Pilot[object]) -> MPLPlot:
    """Select the first plottable branch and wait for the render to settle."""
    await pilot.press("down", "down", "down", "enter")
    await _settle(pilot)
    item = pilot.app.view_widget.item
    assert isinstance(item, MPLPlot)
    return item


async def test_browse_image_plot(monkeypatch: pytest.MonkeyPatch) -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        assert pilot.app.query("#right-panel #image-scale-select")
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert pilot.app.view_widget.current == "image-window"

        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        image_widget = pilot.app.view_widget.image_widget
        assert image_widget is not None
        assert image_widget.image is not None

        # the figure is built at the widget's pixel size, so the aspect is right
        assert item.size is not None
        assert (image_widget.image.width, image_widget.image.height) == item.size

        pilot.app.query_one(
            "#right-panel #image-scale-select", textual.widgets.Select
        ).value = 2.0
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert item.scale == 2.0
        assert pilot.app.image_scale == 2.0
        await _settle(pilot)

        # A theme change redraws the cached histogram without re-reading data
        built = item.built.hist
        assert built is not None
        monkeypatch.setattr(uproot_browser.plot, "to_histogram", _fail_build)
        pilot.app.theme = "textual-light"
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert not item.dark
        assert item.built.hist is built

        await _settle(pilot)
        # a rebuild would have raised, replacing the item with an Error
        assert isinstance(pilot.app.view_widget.item, MPLPlot)
        assert image_widget.image is not None


async def test_image_size_matches_visible_area() -> None:
    """The image is requested at the size of the pane the entry box leaves."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test(size=(120, 40)) as pilot:
        await _open_settled_plot(pilot)

        # the entry box docks inside the image window and makes the pane shorter
        pilot.app.show_entry_box = True
        await pilot.pause()
        pilot.app.view_widget.post_message(RequestImage())
        await _settle(pilot)

        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        image_widget = pilot.app.view_widget.image_widget
        assert image_widget is not None
        cell = textual_image.widget.get_cell_size()
        content = image_widget.content_size
        assert item.size == (content.width * cell.width, content.height * cell.height)


async def test_browse_image_empty() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root"), image=True
    ).run_test() as pilot:
        await pilot.press("down", "space", "down", "enter")
        await _settle(pilot)
        assert pilot.app.view_widget.item is None
        assert pilot.app.view_widget.current == "logo"


async def test_image_expr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Expressions redraw the cached histogram, and a bad one can be corrected."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        pilot.app.query_one("#tree-view", UprootTree).select_path("//T/event/fNtrack")
        await pilot.pause()
        await _settle(pilot)
        view = pilot.app.view_widget
        assert isinstance(view.item, MPLPlot)
        built = view.item.built.hist
        assert built is not None
        monkeypatch.setattr(uproot_browser.plot, "to_histogram", _fail_build)

        view.plot_input.value = "h[::2j]"
        view.plot_input.apply_expression()
        await pilot.pause()
        item = view.item
        assert isinstance(item, MPLPlot)
        assert item.expr == "h[::2j]"
        # Dump & Quit source for the image mode carries the expression
        source = item.dump_source()
        assert "result = h[::2j]" in source
        assert "h.plot()" in source
        assert "uproot_browser" not in source
        pilot.app.axis_limits = AxisLimits(y=(None, 15.0))
        await pilot.pause()
        item = view.item
        assert isinstance(item, MPLPlot)
        assert "plt.ylim(None, 15.0)" in item.dump_source()
        await _settle(pilot)
        # a rebuild would have raised, replacing the item with an Error
        assert isinstance(view.item, MPLPlot)
        assert view.item.built.hist is built  # the cache keeps the unsliced histogram
        pilot.app.axis_limits = AxisLimits()
        await _settle(pilot)

        expr = 'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]'
        view.plot_input.value = expr
        view.plot_input.apply_expression()
        await _settle(pilot)
        item = view.item
        assert isinstance(item, MPLPlot)
        assert item.expr == expr
        assert item.built.hist is built


async def test_image_expression_failure_can_be_corrected() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        pilot.app.query_one("#tree-view", UprootTree).select_path("//T/event/fNtrack")
        await pilot.pause()
        await _settle(pilot)
        view = pilot.app.view_widget
        for expr in ("42", 'tree["fNtrack"].array()[tree["fNtrack"].array() > 1e99]'):
            await _apply_expression(pilot, expr)
            assert isinstance(view.item, MPLPlot)
            assert view.current == "image-window"
            assert view.plot_input.region.height > 0
            assert view.plot_input.has_class("-needs-update")
            assert view.image_widget is not None
            assert view.image_widget.image is None
            assert not view.image_widget.loading

        view.plot_input.value = 'tree["fNtrack"].array()[tree["fNtrack"].array() > 0]'
        view.plot_input.apply_expression()
        await _settle(pilot)
        assert isinstance(view.item, MPLPlot)
        assert view.item.expr == view.plot_input.value
        assert not view.plot_input.has_class("-needs-update")
        assert view.image_widget.image is not None


def test_render_image_is_thread_safe() -> None:
    # catch_warnings and style contexts change global state, so overlapping
    # renders could leak a warning that the render should silence.
    tree = uproot.open(skhep_testdata.data_path("uproot-Event.root"))["T"]
    histogram = uproot_browser.plot.to_histogram(tree["event/fNtrack"])

    def render(_: int) -> tuple[int, int]:
        return uproot_browser.plot_mpl.render_image(histogram, "t", size=(100, 80)).size

    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        assert list(pool.map(render, range(100))) == [(100, 80)] * 100
