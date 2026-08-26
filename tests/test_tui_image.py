import pytest
import skhep_testdata

pytest.importorskip("textual_image")
pytest.importorskip("matplotlib")

import textual.widgets
import uproot

from uproot_browser.tui.browser import Browser
from uproot_browser.tui.image_plot import MPLPlot, make_image
from uproot_browser.tui.messages import ImageScaleChanged


def test_make_image_object_branch() -> None:
    """A branch holding TH1 objects (AsObjects) is summed and plotted."""
    with uproot.open(skhep_testdata.data_path("uproot-Event.root")) as f:
        image = make_image(f["T"]["event"]["fH"], dark=True, size=(400, 300))
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


async def test_image_scale_tool() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root"), image=True
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        await pilot.pause()

        pilot.app.post_message(ImageScaleChanged(2.0))
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
