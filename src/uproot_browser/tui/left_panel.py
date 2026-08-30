from __future__ import annotations

import contextlib
import functools
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar

import rich.panel
import rich.text
import textual.binding
import textual.css.query
import textual.events
import textual.widget
import textual.widgets
import textual.widgets.tree
import uproot

import uproot_browser.plot

from ..tree import UprootEntry
from .jump import Candidate
from .messages import UprootSelected

if TYPE_CHECKING:
    from rich.style import Style

SCROLLOFF = 2  # lines kept visible past the cursor, like vim's 'scrolloff'
MAX_COUNT_DIGITS = 4
COUNT_MOTIONS = frozenset({"up", "down", "j", "k"})


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
        self._count = ""
        super().__init__(name=str(file_path), data=data, label=file_path.stem, **args)

    @functools.cached_property
    def all_entries(self) -> list[Candidate]:
        """All jump targets in the file, built once and cached."""
        root = UprootEntry("/", self.upfile)
        return [
            Candidate(
                path=entry.path,
                name=PurePosixPath(entry.path).name,
                icon=entry.meta()["label_icon"],
                is_dir=entry.is_dir,
                plottable=uproot_browser.plot.plottable(entry.item),
            )
            for entry in root.walk()
        ]

    def select_path(self, target: str) -> None:
        """Navigate to (and reveal) the node at ``target``, plotting leaves."""
        node = self.root
        self.load_directory(node)
        assert node.data
        while node.data.path != target:
            child = next(
                (
                    c
                    for c in node.children
                    if c.data
                    and (c.data.path == target or target.startswith(c.data.path + "/"))
                ),
                None,
            )
            if child is None:
                return
            self.load_directory(child)
            node = child
            assert node.data
            if node.data.path != target:
                node.expand()

        target_node = node
        assert target_node.data

        def reveal() -> None:
            self.move_cursor(target_node)
            self.scroll_to_node(target_node)

        self.call_after_refresh(reveal)

        if target_node.data.is_dir:
            target_node.expand()
        else:
            self.post_message(UprootSelected(self.upfile, target_node.data.path))

    def scroll_to_line(self, line: int, animate: bool = True) -> None:  # noqa: FBT001, FBT002
        """Scroll to a line, keeping ``SCROLLOFF`` lines visible on both sides."""
        if self.scrollable_content_region.height > 2 * SCROLLOFF + 1:
            # Bring both edges into view; the second call moves the view further
            # only if the first one scrolled past the cursor.
            super().scroll_to_line(max(line - SCROLLOFF, 0), animate=animate)
            super().scroll_to_line(
                min(line + SCROLLOFF, self.last_line), animate=animate
            )
        super().scroll_to_line(line, animate=animate)

    def _set_count(self, count: str) -> None:
        """Store the pending count and echo it on the tab."""
        self._count = count
        with contextlib.suppress(textual.css.query.NoMatches):
            tabs = self.screen.query_one("#left-view", textual.widgets.TabbedContent)
            tabs.get_tab("tree-tab").label = f"Tree {count}" if count else "Tree"

    def _take_count(self) -> int:
        """Consume the pending count, defaulting to 1."""
        count = int(self._count or 1)
        self._set_count("")
        return count

    def on_key(self, event: textual.events.Key) -> None:
        """Collect a vim-style count prefix for the cursor motions."""
        character = event.character
        if character is not None and (
            character in "123456789" or (character == "0" and self._count)
        ):
            if len(self._count) < MAX_COUNT_DIGITS:
                self._set_count(self._count + character)
            event.stop()
            event.prevent_default()
        elif event.key not in COUNT_MOTIONS:
            self._set_count("")

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
        if not node.data.is_dir and not uproot_browser.plot.plottable(node.data.item):
            label.stylize("dim")
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

    def action_cursor_down(self) -> None:
        count = self._take_count()
        if self.cursor_line == -1:
            count -= 1
        self.cursor_line = max(self.cursor_line, 0) + count
        self.scroll_to_line(self.cursor_line, animate=False)

    def action_cursor_up(self) -> None:
        count = self._take_count()
        if self.cursor_line == -1:
            self.cursor_line = self.last_line - count + 1
        else:
            self.cursor_line -= count
        self.scroll_to_line(self.cursor_line, animate=False)

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
