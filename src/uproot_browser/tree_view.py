from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import rich.console
import rich.repr
import textual.events
import textual.message
import textual.reactive
import textual.widgets
import uproot
from textual._types import MessageTarget

from .tree import UprootItem


@rich.repr.auto
class UprootClick(textual.message.Message, bubble=True):
    def __init__(self, sender: MessageTarget, path: str) -> None:
        self.path = path
        super().__init__(sender)


class TreeView(textual.widgets.TreeControl[UprootItem]):
    """A tree view for the uproot-browser"""

    def __init__(self, path: Path) -> None:
        self.upfile = uproot.open(path)
        data = UprootItem("/", self.upfile)
        super().__init__(name=path.name, label=path.stem, data=data)
        self.root.tree.guide_style = "black"

    has_focus: textual.reactive.Reactive[bool] = textual.reactive.Reactive(False)

    def on_focus(self) -> None:
        self.has_focus = True

    def on_blur(self) -> None:
        self.has_focus = False

    async def watch_hover_node(self, hover_node: textual.widgets.NodeID) -> None:
        for node in self.nodes.values():
            node.tree.guide_style = "bold" if node.id == hover_node else ""
        self.refresh(layout=True)

    def render_node(
        self, node: textual.widgets.TreeNode[UprootItem]
    ) -> rich.console.RenderableType:
        return render_tree_label(
            node,
            node.data.is_dir,
            node.expanded,
            node.is_cursor,
            node.id == self.hover_node,
            self.has_focus,
        )

    async def on_mount(
        self,
        event: textual.events.Mount,  # pylint: disable=unused-argument
    ) -> None:
        await self.load_directory(self.root)

    async def load_directory(self, node: textual.widgets.TreeNode[UprootItem]) -> None:
        children = node.data.children
        for child in children:
            await node.add(child.path, child)
        node.loaded = True
        await node.expand()
        self.refresh(layout=True)

    async def handle_tree_click(
        self, message: textual.widgets.TreeClick[UprootItem]
    ) -> None:
        item = message.node.data
        if not item.is_dir:
            await self.emit(UprootClick(self, item.path))
        else:
            if not message.node.loaded:
                await self.load_directory(message.node)
                await message.node.expand()
            else:
                await message.node.toggle()


@lru_cache(maxsize=1024 * 32)
def render_tree_label(
    node: textual.widgets.TreeNode[UprootItem],
    is_dir: bool,
    expanded: bool,
    is_cursor: bool,
    is_hover: bool,
    has_focus: bool,
) -> rich.console.RenderableType:
    meta = {
        "@click": f"click_label({node.id})",
        "tree_node": node.id,
        "cursor": node.is_cursor,
    }
    icon_label = node.data.meta()["label"]
    icon_label.apply_meta(meta)

    if is_hover:
        icon_label.stylize("underline")
    if is_cursor and has_focus:
        icon_label.stylize("reverse")
    if is_dir:
        icon_label.stylize("green4" if expanded else "spring_green3")

    return icon_label  # type: ignore[no-any-return]
