from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import ClassVar

import rich.panel
import rich.repr
import rich.text
import textual.message
import textual.widget
import textual.widgets
import textual.widgets.tree
import uproot
from rich.style import Style

from ..tree import UprootEntry


@rich.repr.auto
class UprootSelected(textual.message.Message, bubble=True):
    def __init__(self, upfile: UprootEntry, path: str) -> None:
        self.upfile = upfile
        self.path = path
        super().__init__()


class UprootTree(textual.widgets.Tree[UprootEntry]):
    """currently just extending DirectoryTree, showing current path"""

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "uproot-tree--folder",
        "uproot-tree--file",
        "uproot-tree--extension",
        "uproot-tree--hidden",
    }

    def __init__(self, path: Path, **args) -> None:
        self.upfile = uproot.open(path)
        data = UprootEntry("/", self.upfile)
        super().__init__(name=path.name, data=data, label=path.stem, **args)

    def render_label(
        self,
        node: textual.widgets.tree.TreeNode[UprootEntry],
        base_style: Style,
        style: Style,
    ) -> rich.console.RenderableType:
        return render_tree_label(
            node,
            node.data.is_dir,
            node.is_expanded,
            self.has_focus,
        )

    def on_mount(self) -> None:
        self.load_directory(self.root)

    def load_directory(self, node: textual.widgets.tree.TreeNode[UprootEntry]) -> None:
        children = node.data.children
        for child in children:
            node.add(child.path, child)
        node.loaded = True
        node.expand()
        self.refresh(layout=True)

    def on_tree_node_selected(self, event: textual.widgets.Tree.NodeSelected) -> None:
        event.stop()
        item = event.node.data
        if not item.is_dir:
            self.post_message(UprootSelected(self.upfile, item.path))

    def on_tree_node_expanded(self, event: textual.widgets.Tree.NodeSelected) -> None:
        event.stop()
        item = event.node.data
        if item.is_dir:
            self.load_directory(event.node)


@lru_cache(maxsize=1024 * 32)
def render_tree_label(
    node: textual.widgets.tree.TreeNode[UprootEntry],
    is_dir: bool,
    expanded: bool,
    has_focus: bool,
) -> rich.console.RenderableType:
    meta = {
        "@click": f"click_label({node.id})",
        "tree_node": node.id,
    }
    icon_label = node.data.meta()["label"]
    icon_label.apply_meta(meta)

    return icon_label  # type: ignore[no-any-return]
