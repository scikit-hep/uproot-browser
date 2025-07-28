from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import rich.panel
import rich.repr
import rich.text
import textual.binding
import textual.message
import textual.widget
import textual.widgets
import textual.widgets.tree
import uproot
from rich.style import Style

from ..tree import UprootEntry


@rich.repr.auto
class UprootSelected(textual.message.Message, bubble=True):
    def __init__(self, upfile: Any, path: str) -> None:
        self.upfile = upfile
        self.path = path
        super().__init__()


class UprootTree(textual.widgets.Tree[UprootEntry]):
    """currently just extending DirectoryTree, showing current path"""

    BINDINGS: ClassVar[
        list[textual.binding.Binding | tuple[str, str] | tuple[str, str, str]]
    ] = [
        textual.binding.Binding("h", "cursor_out", "Cursor out", show=False),
        textual.binding.Binding("j", "cursor_down", "Cursor Down", show=False),
        textual.binding.Binding("k", "cursor_up", "Cursor Up", show=False),
        textual.binding.Binding("l", "cursor_in", "Cursor in", show=False),
    ]

    def __init__(self, path: str, **args: Any) -> None:
        self.upfile = uproot.open(path)
        file_path = Path(self.upfile.file_path)
        data = UprootEntry("/", self.upfile)
        super().__init__(name=str(file_path), data=data, label=file_path.stem, **args)

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
        self, event: textual.widgets.Tree.NodeSelected[UprootEntry]
    ) -> None:
        event.stop()
        item = event.node.data
        assert item
        if item.is_dir:
            self.load_directory(event.node)

    def _node_expanded(
        self, node: textual.widgets.tree.TreeNode[UprootEntry]
    ) -> textual.widgets.Tree.NodeExpanded[UprootEntry]:
        try:
            return self.NodeExpanded(node)
        except TypeError:  # textual 0.24-0.26
            # pylint: disable-next=too-many-function-args
            return self.NodeExpanded(self, node)  # type:ignore[call-arg,arg-type]

    def _node_collapsed(
        self, node: textual.widgets.tree.TreeNode[UprootEntry]
    ) -> textual.widgets.Tree.NodeCollapsed[UprootEntry]:
        try:
            return self.NodeCollapsed(node)
        except TypeError:  # textual 0.24-0.26
            # pylint: disable-next=too-many-function-args
            return self.NodeCollapsed(self, node)  # type:ignore[call-arg,arg-type]

    def action_cursor_in(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and not node.is_expanded:
            node.expand()
            self.post_message(self._node_expanded(node))

    def action_cursor_out(self) -> None:
        node = self.cursor_node
        if node is None:
            return
        if node.allow_expand and node.is_expanded:
            node.collapse()
            self.post_message(self._node_collapsed(node))
        elif (
            node.parent is not None
            and node.parent.allow_expand
            and node.parent.is_expanded
        ):
            node.parent.collapse()
            self.post_message(self._node_collapsed(node))
            self.cursor_line = node.parent.line
            self.scroll_to_line(self.cursor_line)
