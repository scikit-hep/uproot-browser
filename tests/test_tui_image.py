import functools

import pytest
import skhep_testdata

pytest.importorskip("textual_image")
pytest.importorskip("matplotlib")

import hist
import matplotlib.pyplot as plt
import textual.pilot
import textual.widgets
import uproot

import uproot_browser.plot
import uproot_browser.plot_mpl
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.image_plot import MPLPlot, make_image


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


async def _open_settled_plot(pilot: textual.pilot.Pilot[object]) -> MPLPlot:
    """Select the first plottable branch and wait for the render to settle."""
    await pilot.press("down", "down", "down", "enter")
    await pilot.pause()
    await pilot.app.workers.wait_for_complete()
    await pilot.pause()
    item = pilot.app.view_widget.item
    assert isinstance(item, MPLPlot)
    return item


async def test_browse_image_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
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


async def test_browse_image_empty() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root"), image=True
    ).run_test() as pilot:
        await pilot.press("down", "space", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        assert pilot.app.view_widget.item is None
        assert pilot.app.view_widget.current == "logo"


async def test_image_expr() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()

        pilot.app.view_widget.plot_input.value = "h[::2j]"
        pilot.app.view_widget.plot_input.apply_expression()
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert item.expr == "h[::2j]"
        # Dump & Quit source for the image mode carries the expression
        assert "uproot_browser.plot_mpl.plot(item, expr='h[::2j]')" in (
            item.dump_source()
        )

        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        # still an image plot (the expression evaluated without error)
        assert isinstance(pilot.app.view_widget.item, MPLPlot)


async def test_image_hist_cached_across_expr_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An expr edit slices the cached histogram without re-reading data."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        built = (await _open_settled_plot(pilot)).built.hist
        assert built is not None
        monkeypatch.setattr(uproot_browser.plot, "to_histogram", _fail_build)

        pilot.app.view_widget.plot_input.value = "h[::2j]"
        pilot.app.view_widget.plot_input.apply_expression()
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        # a rebuild would have raised, replacing the item with an Error
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert item.expr == "h[::2j]"
        # the cache keeps the unsliced histogram
        assert item.built.hist is built


async def test_image_hist_cached_across_theme_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A theme change redraws the cached histogram without re-reading data."""
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        built = (await _open_settled_plot(pilot)).built.hist
        assert built is not None
        monkeypatch.setattr(uproot_browser.plot, "to_histogram", _fail_build)

        pilot.app.theme = "textual-light"
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert not item.dark
        assert item.built.hist is built

        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        # a rebuild would have raised, replacing the item with an Error
        assert isinstance(pilot.app.view_widget.item, MPLPlot)
        image_widget = pilot.app.view_widget.image_widget
        assert image_widget is not None
        assert image_widget.image is not None


async def test_image_scale_tool() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()

        pilot.app.query_one("#image-scale-select", textual.widgets.Select).value = 2.0
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        assert item.scale == 2.0
        assert pilot.app.image_scale == 2.0


async def test_image_scale_select_only_in_image_mode() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        pilot.app.query_one(
            "#left-view", textual.widgets.TabbedContent
        ).active = "tab-2"
        await pilot.pause()
        assert pilot.app.query("#image-scale-select")

    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        pilot.app.query_one(
            "#left-view", textual.widgets.TabbedContent
        ).active = "tab-2"
        await pilot.pause()
        assert not pilot.app.query("#image-scale-select")
