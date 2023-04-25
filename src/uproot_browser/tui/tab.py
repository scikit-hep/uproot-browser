from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Label, Tabs, Tab
import textual.widget
import rich.repr
from textual.message import Message

from .right_panel import (
    EmptyWidget,
    ErrorWidget,
    LogoWidget,
    Plotext,
    PlotWidget,
    make_plot,
)


class UpTab(textual.widgets.Tab):
    widget: any
    mode: any
    id: str | None = None

    def __init__(self, label, **kargs):
        self.tab = label
        super().__init__(label, id=self.id, **kargs)


class UpTabs(textual.widgets.Tabs):
    tab: UpTab

    def __init__(self, tab, **kargs):
        super().__init__(tab, **kargs)

    class TabActivated(Message):
        """Sent when a new tab is activated."""

        tab: UpTab
        """The tab that was activated."""

        def __init__(self, tab: UpTab) -> None:
            self.tab = tab
            super().__init__()

        def __rich_repr__(self) -> rich.repr.Result:
            yield self.tab


class PlotTabs(textual.widget.Widget):
    widget: LogoWidget(id="logo")

    def compose(self):
        tab = UpTab("default")
        tab.widget = LogoWidget(id="logo")
        tab.tab = "Default"
        yield UpTabs(tab)
        yield textual.widgets.ContentSwitcher(
            LogoWidget(id="logo"),
            PlotWidget(id="plot"),
            ErrorWidget(id="error"),
            EmptyWidget(id="empty"),
            id="main-view",
            initial="logo",
        )

    def __init__(self, **kargs):
        super().__init__(**kargs)

    # def on_tabs_tab_activated(self, event: Tabs.TabActivated):
    #     label = self.query_one(Label)
    #     if event.tab is None:
    #         label.visible = False
    #     else:
    #         label.visible = True
    #         label.update(event.tab.label)

