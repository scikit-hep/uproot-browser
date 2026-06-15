from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import rich.panel
import rich.text
import textual.binding
import textual.widget
import textual.widgets
import textual.widgets.tree
import uproot

from ..tree import UprootEntry
from .jump import Candidate
from .messages import UprootSelected

if TYPE_CHECKING:
    from rich.style import Style


class UprootTree(textual.widgets.Tree[UprootEntry]):
    """currently just extending DirectoryTree, showing current path"""

    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("h", "cursor_out", "Cursor out", show=False),
        textual.binding.Binding("j", "cursor_down", "Cursor Down", show=False),
        textual.binding.Binding("k", "cursor_up", "Cursor Up", show=False),
        textual.binding.Binding("l", "cursor_in", "Cursor in", show=False),
    ]

    def __init__(self, path: str, **args: Any) -> None:
        self.upfile = uproot.open(path)
        file_path = Path(self.upfile.file_path)
        data = UprootEntry("/", self.upfile)
        self._candidates: list[Candidate] | None = None
        super().__init__(name=str(file_path), data=data, label=file_path.stem, **args)

    def all_entries(self) -> list[Candidate]:
        """All jump targets in the file, built once and cached."""
        if self._candidates is None:
            root = UprootEntry("/", self.upfile)
            self._candidates = [
                Candidate(
                    path=entry.path,
                    name=entry.path.rstrip("/").rsplit("/", 1)[-1],
                    icon=entry.meta()["label_icon"],
                    is_dir=entry.is_dir,
                )
                for entry in root.walk()
            ]
        return self._candidates

    def select_path(self, target: str) -> None:
        """Navigate to (and reveal) the node at ``target``, plotting leaves."""
        node = self.root
        self.load_directory(node)
        while node.data is not None and node.data.path != target:
            child = next(
                (
                    c
                    for c in node.children
                    if c.data is not None
                    and (c.data.path == target or target.startswith(c.data.path + "/"))
                ),
                None,
            )
            if child is None:
                return
            self.load_directory(child)
            if child.data is not None and child.data.path != target:
                child.expand()
            node = child

        target_node = node

        def reveal() -> None:
            self.move_cursor(target_node)
            self.scroll_to_node(target_node)

        self.call_after_refresh(reveal)

        if target_node.data is not None:
            if target_node.data.is_dir:
                target_node.expand()
            else:
                self.post_message(UprootSelected(self.upfile, target_node.data.path))

    def render_label(
        self,
        node: textual.widgets.tree.TreeNode[UprootEntry],
        base_style: Style,
        style: Style,  # ,
    ) -> rich.text.Text:
        assert node.data
        meta = node.data.meta()
        label_icon = rich.text.Text(meta["label_icon"])
        label_icon.stylize(base_style)

        label = rich.text.Text.assemble(label_icon, meta["label_text"])
        label.stylize(style)
        return label

    def on_mount(self) -> None:
        self.load_directory(self.root)
        self.root.expand()

    def load_directory(self, node: textual.widgets.tree.TreeNode[UprootEntry]) -> None:
        assert node.data
        if not node.children:
            children = node.data.children
            for child in children:
                node.add(child.path, child)

    def on_tree_node_selected(
        self, event: textual.widgets.Tree.NodeSelected[UprootEntry]
    ) -> None:
        event.stop()
        item = event.node.data
        assert item
        if not item.is_dir:
            self.post_message(UprootSelected(self.upfile, item.path))

    def on_tree_node_expanded(
        self, event: textual.widgets.Tree.NodeExpanded[UprootEntry]
    ) -> None:
        event.stop()
        item = event.node.data
        assert item
        if item.is_dir:
            self.load_directory(event.node)

    def action_cursor_in(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and not node.is_expanded:
            node.expand()

    def action_cursor_out(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
        elif (
            node.parent is not None
            and node.parent.allow_expand
            and node.parent.is_expanded
        ):
            node.parent.collapse()
            self.cursor_line = node.parent.line
            self.scroll_to_line(self.cursor_line)
