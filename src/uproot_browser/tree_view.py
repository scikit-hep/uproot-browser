from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import rich.repr
import textual.events
import uproot
from rich.console import RenderableType
from rich.text import Text
from textual._types import MessageTarget
from textual.message import Message
from textual.reactive import Reactive
from textual.widgets import NodeID, TreeControl, TreeNode

from .tree import Node


@rich.repr.auto
class UprootClick(Message, bubble=True):
    def __init__(self, sender: MessageTarget, path: str) -> None:
        self.path = path
        super().__init__(sender)


class TreeView(TreeControl[Node]):
    """A tree view for the uproot-browser"""

    def __init__(self, path: Path) -> None:
        self.upfile = uproot.open(path)
        data = Node("/", self.upfile)
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

    def render_node(self, node: TreeNode[Node]) -> RenderableType:
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
        node: TreeNode[Node],
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
        return icon_label

    async def on_mount(self, event: textual.events.Mount) -> None:
        await self.load_directory(self.root)

    async def load_directory(self, node: TreeNode[Node]):
        children = node.children
        for child in children:
            await node.add(child.name, child.data)
        node.loaded = True
        await node.expand()
        self.refresh(layout=True)

    async def handle_tree_click(self, message: UprootClick[Node]) -> None:
        node = message.node.data
        if not node.is_dir:
            await self.emit(UprootClick(self, node.path))
        else:
            if not message.node.loaded:
                await self.load_directory(message.node)
                await message.node.expand()
            else:
                await message.node.toggle()
