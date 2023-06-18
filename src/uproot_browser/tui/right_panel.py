from __future__ import annotations

from typing import Any
import dataclasses

import rich.text
import textual.app
import textual.reactive
import textual.widget

class SideBarWidget(textual.widget.Widget):
    def render(self) -> rich.console.RenderableType:
        return "SIDEBAR"