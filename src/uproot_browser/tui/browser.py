from __future__ import annotations

if not __package__:
    __package__ = "uproot_browser.tui"

import contextlib
import sys
from pathlib import Path
from typing import Any

import plotext as plt
import rich.syntax
import textual.app
import textual.containers
import textual.widget
from textual.reactive import var
from textual.widgets import Footer, Header

with contextlib.suppress(AttributeError):
    light_background = 0xDF, 0xDF, 0xDF  # $surface-darken-1
    plt._dict.themes["default"][0] = light_background
    plt._dict.themes["default"][1] = light_background


from uproot_browser.exceptions import EmptyTreeError

from .left_panel import UprootSelected, UprootTree
from .right_panel import (
    EmptyWidget,
    ErrorWidget,
    LogoWidget,
    Plotext,
    PlotWidget,
    make_plot,
)

from .tab import PlotTabs, UpTabs, UpTab

NAMES = [
    "LOGO"
]

class Browser(textual.app.App):
    """A basic implementation of the uproot-browser TUI"""

    CSS_PATH = "browser.css"
    BINDINGS = [
        ("b", "toggle_files", "Toggle sidebar"),
        ("q", "quit", "Quit"),
        ("d", "quit_with_dump", "Quit with dump"),
        ("t", "toggle_theme", "Toggle light/dark theme"),
        ("a", "action_add", "Add Tab"),
        ("r", "action_remove", "Remove Tab"),
    ]

    show_tree = var(True)

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-tree")

    def __init__(self, path: Path, **kwargs: Any) -> None:
        self.path = path
        super().__init__(**kwargs)

        # self.uptree = UprootTree(self.path)

    def compose(self) -> textual.app.ComposeResult:
        """Compose our UI."""
        yield Header()
        with textual.containers.Container():
            # tabs
            yield PlotTabs()
            # left_panel
            yield UprootTree(self.path, id="tree-view")
            # right_panel
            # yield textual.widgets.ContentSwitcher(
            #     LogoWidget(id="logo"),
            #     PlotWidget(id="plot"),
            #     ErrorWidget(id="error"),
            #     EmptyWidget(id="empty"),
            #     id="main-view",
            #     initial="logo",
            # )
        yield Footer()

    def action_add(self) -> None:
        tabs = self.query_one(UpTabs)
        plot = tabs.active_tab.widget
        mode = tabs.active_tab.label
        # content_switcher = self.query_one("#main=view")
        label = tabs.active_tab.tab.tab
        tabs.add_tab(UpTab(tab=label, widget=plot, mode=mode))
        # if mode is "empty":
        #     tabs.add_tab(UpTab(mode, plot))
        # if mode is "error":
        #     tab = textual.widgets.Tab(mode)
        #     tabs.add_tab(tab, tabs.widget)
        # # if mode is "error":
        # # tab =

    def on_tabs_tab_activated(self, event: UpTabs.TabActivated) -> None:
        """Handle TabActivated message sent by Tabs."""
        plot = event.tab.widget
        content_switcher = self.query_one("#main-view")
        if event.tab is None:
            # When the tabs are cleared, event.tab will be None
            content_switcher.current = "logo"
        else:
            plot.visible = True
            content_switcher.current = event.tab.label


    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def action_quit_with_dump(self):
        """Dump the current state of the application."""

        content_switcher = self.query_one("#main-view")
        plot_widget = content_switcher.query_one("#plot")
        err_widget = content_switcher.query_one("#error")

        msg = f'\nimport uproot\nuproot_file = uproot.open("{self.path}")'

        items = []
        if content_switcher.current == "plot":
            msg += f'\nitem = uproot_file["{plot_widget.item.selection.lstrip("/")}"]'
            items = [plot_widget.item]
        elif content_switcher.current == "error":
            items = [err_widget.exc]

        theme = "rrt" if self.dark else "default"


        results = rich.console.Group(
            *items,
            rich.syntax.Syntax(f"\n{msg}\n", "python", theme=theme),
        )

        self.exit(message=results)

    def action_toggle_theme(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark
        content_switcher = self.query_one("#main-view")
        plot_widget = content_switcher.query_one("#plot")
        if plot_widget.item:
            plot_widget.item.theme = "dark" if self.dark else "default"
            plot_widget.refresh()

    def on_uproot_selected(self, message: UprootSelected) -> None:
        """A message sent by the tree when a file is clicked."""

        # # content_switcher = self.query_one("#main-view")
        #
        # try:
        #     make_plot(message.upfile[message.path], 10, 10)
        #     plot_widget = self.query_one(textual.widget.Widget)
        #     theme = "dark" if self.dark else "default"
        #     plot_widget.item = Plotext(message.upfile[message.path], theme)
        #     tabs = self.query_one(textual.widgets.Tabs)
        #     tabs.add_tab(message.path)
        #     textual.widgets.Tab.id = message.path
        #
        #
        # except EmptyTreeError:
        #     tabs = self.query_one(textual.widgets.Tabs)
        #     tabs.add_tab("EmptyTree")
        #     textual.widget.Widget(
        #         EmptyWidget(id="empty"),
        #     )
        #
        # except Exception:
        #     # error_widget = content_switcher.query_one("#error")
        #     # error_widget.exc = sys.exc_info()
        #     # content_switcher.current = "error"
        #     tabs = self.query_one(textual.widgets.Tabs)
        #     tabs.add_tab("Error")
        #     textual.widget.Widget(
        #         ErrorWidget(exc=sys.exc_info(), id="error")
        #     )

        content_switcher = self.query_one("#main-view")
        print(message)

        try:
            make_plot(message.upfile[message.path], 10, 10)
            plot_widget = content_switcher.query_one("#plot")
            theme = "dark" if self.dark else "default"
            plot_widget.item = Plotext(message.upfile[message.path], theme)
            tab = self.query_one(UpTab)
            tab.widget = PlotWidget(plot_widget)
            tab.tab = message.path
            tab.mode = "plot"
            content_switcher.current = tab.mode


        except EmptyTreeError:
            tab = self.query_one(UpTab)
            tab.widget = EmptyWidget()
            tab.tab = message.path
            tab.mode = "empty"
            content_switcher.current = "empty"



        except Exception:
            error_widget = content_switcher.query_one("#error")
            error_widget.exc = sys.exc_info()
            tab = self.query_one(UpTab)
            tab.widget = ErrorWidget()
            tab.tab = message.path
            tab.mode = "error"
            content_switcher.current = "error"



if __name__ == "<run_path>":
    import uproot_browser.dirs

    fname = uproot_browser.dirs.filename(
        "../scikit-hep-testdata/src/skhep_testdata/data/uproot-Event.root"
    )
    app = Browser(path=Path(fname))
