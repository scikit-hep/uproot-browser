import pytest
import skhep_testdata

pytest.importorskip("textual_image")
pytest.importorskip("matplotlib")

import textual.widgets
import uproot

import uproot_browser.plot_mpl
from uproot_browser.tui.browser import Browser
from uproot_browser.tui.image_plot import MPLPlot, make_image


def test_make_image_object_branch() -> None:
    """A branch holding TH1 objects (AsObjects) is summed and plotted."""
    with uproot.open(skhep_testdata.data_path("uproot-Event.root")) as f:
        item = f["T"]["event"]["fH"]
        histogram = uproot_browser.plot_mpl.build_hist(item)
        image = make_image(item, histogram, dark=True, size=(400, 300))
    assert (image.width, image.height) == (400, 300)


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
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        built = item.built.hist
        assert built is not None

        def fail(*_args: object, **_kwargs: object) -> None:
            msg = "histogram was rebuilt"
            raise AssertionError(msg)

        monkeypatch.setattr(uproot_browser.plot_mpl, "build_hist", fail)

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
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()
        await pilot.app.workers.wait_for_complete()
        await pilot.pause()
        item = pilot.app.view_widget.item
        assert isinstance(item, MPLPlot)
        built = item.built.hist
        assert built is not None

        def fail(*_args: object, **_kwargs: object) -> None:
            msg = "histogram was rebuilt"
            raise AssertionError(msg)

        monkeypatch.setattr(uproot_browser.plot_mpl, "build_hist", fail)

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
