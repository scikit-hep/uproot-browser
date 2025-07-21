import skhep_testdata

from uproot_browser.tui.browser import Browser


async def test_browse_logo() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        assert pilot.app.query_one("#main-view").current == "logo"


async def test_browse_plot() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        assert pilot.app.query_one("#main-view").current == "plot"


async def test_theme_switch() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-Event.root")
    ).run_test() as pilot:
        await pilot.press("down", "down", "down", "enter")
        browser_theme = pilot.app.theme
        plot_theme = pilot.app.theme
        await pilot.press("t")
        new_browser_theme = pilot.app.theme
        new_plot_theme = pilot.app.theme
        assert browser_theme != new_browser_theme
        assert plot_theme != new_plot_theme


async def test_browse_empty() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("down", "space", "down", "enter")
        assert pilot.app.query_one("#main-view").current == "empty"


async def test_browse_empty_vim() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("j", "l", "j", "enter")
        assert pilot.app.query_one("#main-view").current == "empty"


async def test_help_focus() -> None:
    async with Browser(
        skhep_testdata.data_path("uproot-empty.root")
    ).run_test() as pilot:
        await pilot.press("?")
        focus_chain = [widget.id for widget in pilot.app.screen.focus_chain]
        assert len(focus_chain) == 3
        assert focus_chain[-1] == "help-done"
