from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import rich.repr
import textual.events
import uproot
from rich.console import RenderableType
from textual._types import MessageTarget
from textual.message import Message
from textual.reactive import Reactive
from textual.widgets import NodeID, TreeControl, TreeNode

from .tree import UprootItem


@rich.repr.auto
class UprootClick(Message, bubble=True):  # type: ignore[call-arg, misc]
    def __init__(self, sender: MessageTarget, path: str) -> None:
        self.path = path
        super().__init__(sender)


class TreeView(TreeControl[UprootItem]):  # type: ignore[misc]
    """A tree view for the uproot-browser"""

    def __init__(self, path: Path) -> None:
        self.upfile = uproot.open(path)
        data = UprootItem("/", self.upfile)
        super().__init__(name=path.name, label=path.stem, data=data)
        self.root.tree.guide_style = "black"

    has_focus: Reactive[bool] = Reactive(False)

    def on_focus(self) -> None:
        self.has_focus = True

    def on_blur(self) -> None:
        self.has_focus = False

    async def watch_hover_node(self, hover_node: NodeID) -> None:
        for node in self.nodes.values():
            node.tree.guide_style = (
                "bold not dim red" if node.id == hover_node else "black"
            )
        self.refresh(layout=True)

    def render_node(self, node: TreeNode[UprootItem]) -> RenderableType:
        return self.render_tree_label(
            node,
            node.data.is_dir,
            node.expanded,
            node.is_cursor,
            node.id == self.hover_node,
            self.has_focus,
        )

    @lru_cache(maxsize=1024 * 32)
    def render_tree_label(
        self,
        node: TreeNode[UprootItem],
        is_dir: bool,
        expanded: bool,
        is_cursor: bool,
        is_hover: bool,
        has_focus: bool,
    ) -> RenderableType:
        meta = {
            "@click": f"click_label({node.id})",
            "tree_node": node.id,
            "cursor": node.is_cursor,
        }
        icon_label = node.data.meta()["label"]
        icon_label.apply_meta(meta)
        return icon_label  # type: ignore[no-any-return]

    async def on_mount(self, event: textual.events.Mount) -> None:
        await self.load_directory(self.root)

    async def load_directory(self, node: TreeNode[UprootItem]) -> None:
        children = node.data.children
        for child in children:
            await node.add(child.path, child)
        node.loaded = True
        await node.expand()
        self.refresh(layout=True)

    async def handle_tree_click(self, message: UprootClick[UprootItem]) -> None:  # type: ignore[type-arg]
        item = message.node.data
        if not item.is_dir:
            await self.emit(UprootClick(self, item.path))
        else:
            if not message.node.loaded:
                await self.load_directory(message.node)
                await message.node.expand()
            else:
                await message.node.toggle()
