from __future__ import annotations

__lazy_modules__ = {
    "pathlib",
    "rich",
    "rich.panel",
    "rich.text",
    "textual.events",
    "textual.widget",
    "textual.widgets.tree",
    "uproot_browser.plot",
    f"{__spec__.parent}.jump",
    f"{__spec__.parent}.messages",
}

from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, ClassVar

import rich.panel
import rich.text
import textual.binding
import textual.events
import textual.widget
import textual.widgets
import textual.widgets.tree
from textual.reactive import var

import uproot_browser.plot

from ..tree import LocalDirectory, LocalFile, UprootEntry, open_path
from .jump import Candidate
from .messages import UprootSelected

if TYPE_CHECKING:
    from collections.abc import Iterator

    from rich.style import Style

SCROLLOFF = 2  # lines kept visible past the cursor, like vim's 'scrolloff'
MAX_COUNT_DIGITS = 4
COUNT_MOTIONS = frozenset({"up", "down", "j", "k"})
MODIFIERS = ("shift", "control", "alt", "super", "hyper", "meta")


def make_candidate(entry: UprootEntry) -> Candidate:
    return Candidate(
        path=entry.path,
        name=PurePosixPath(entry.path).name,
        icon=entry.meta()["label_icon"],
        is_dir=entry.is_dir,
        plottable=uproot_browser.plot.plottable(entry.item),
    )


class UprootTree(textual.widgets.Tree[UprootEntry]):
    """currently just extending DirectoryTree, showing current path"""

    BINDINGS: ClassVar[list[textual.binding.BindingType]] = [
        textual.binding.Binding("h", "cursor_out", "Cursor out", show=False),
        textual.binding.Binding("j", "cursor_down", "Cursor Down", show=False),
        textual.binding.Binding("k", "cursor_up", "Cursor Up", show=False),
        textual.binding.Binding("l", "cursor_in", "Cursor in", show=False),
        textual.binding.Binding("m", "mark", "Mark 2D"),
    ]

    count = var("")
    """Pending vim-style count prefix."""

    def __init__(self, path: str, **args: Any) -> None:
        self.upfile = open_path(path)
        file_path = Path(self.upfile.file_path)
        data = UprootEntry("/", self.upfile)
        self._candidates: dict[str, list[Candidate]] = {}
        super().__init__(name=str(file_path), data=data, label=file_path.stem, **args)
        self.marks: list[textual.widgets.tree.TreeNode[UprootEntry]] = []
        """The x (and y, once plotted) branches of a 2D plot."""

    def jump_candidates(self) -> list[Candidate]:
        """
        All jump targets. The files of a directory are listed, but only
        entered after they are opened, so a jump does not open every file.
        """
        root = UprootEntry("/", self.upfile)
        if isinstance(self.upfile, LocalDirectory):
            return list(self._directory_candidates(root))
        return self._file_candidates(root)

    def _directory_candidates(self, entry: UprootEntry) -> Iterator[Candidate]:
        for child in entry.children:
            yield make_candidate(child)
            if not isinstance(child.item, LocalFile):
                yield from self._directory_candidates(child)
            elif child.item.is_open:
                yield from self._file_candidates(child)

    def _file_candidates(self, entry: UprootEntry) -> list[Candidate]:
        """The jump targets in one file, built once and cached."""
        if entry.path not in self._candidates:
            self._candidates[entry.path] = [make_candidate(e) for e in entry.walk()]
        return self._candidates[entry.path]

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
            self._select(target_node.data.path)

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

    def _take_count(self) -> int:
        """Consume the pending count, defaulting to 1."""
        count = int(self.count or 1)
        self.count = ""
        return count

    def on_key(self, event: textual.events.Key) -> None:
        """Collect a vim-style count prefix for the cursor motions."""
        character = event.character
        if character is not None and (
            character in "123456789" or (character == "0" and self.count)
        ):
            if len(self.count) < MAX_COUNT_DIGITS:
                self.count += character
            event.stop()
            event.prevent_default()
        elif event.key not in COUNT_MOTIONS and not event.key.endswith(MODIFIERS):
            self.count = ""

    async def _on_click(self, event: textual.events.Click) -> None:
        """Shift+click plots the branch at the cursor (x) against the clicked one (y)."""
        meta = event.style.meta
        if not event.shift or "line" not in meta or meta.get("toggle", False):
            return
        # Textual calls the handler of each class in the MRO; this stops Tree's
        event.prevent_default()
        x_node = self.cursor_node
        y_node = self.get_node_at_line(meta["line"])
        if x_node is None or y_node is None or x_node is y_node:
            return
        if self._pairable(x_node) and self._pairable(y_node):
            self.cursor_line = meta["line"]
            self._set_marks(x_node, y_node)

    def on_blur(self) -> None:
        """Discard pending navigation when focus leaves the tree."""
        self.count = ""

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
        if node in self.marks:
            axis = "xy"[self.marks.index(node)]
            label = rich.text.Text.assemble((f"{axis}: ", "bold"), label)
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
            self._select(item.path)

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

    def action_mark(self) -> None:
        """Mark the x branch; marking a second one plots the pair in 2D."""
        node = self.cursor_node
        if node is None or node.data is None or node.data.is_dir:
            return
        if node in self.marks:
            self._set_marks()
        elif self._pairable(node):
            self._set_marks(*self.marks[:1], node)

    def _pairable(self, node: textual.widgets.tree.TreeNode[UprootEntry]) -> bool:
        """Can ``node`` be one axis of a 2D plot? Warns if not."""
        if node.data is not None and uproot_browser.plot.array_plottable(
            node.data.item
        ):
            return True
        self.app.notify(
            "Only numeric branches and fields can be plotted in 2D.",
            severity="warning",
        )
        return False

    def _set_marks(self, *nodes: textual.widgets.tree.TreeNode[UprootEntry]) -> None:
        """Replace the marks (relabeling old and new); two marks plot in 2D."""
        old, self.marks = self.marks, list(nodes)
        for node in (*old, *nodes):
            node.refresh()
        if len(nodes) == 2:
            x_node, y_node = nodes
            assert x_node.data
            assert y_node.data
            self.post_message(
                UprootSelected(self.upfile, x_node.data.path, y_node.data.path)
            )

    def _select(self, path: str) -> None:
        """Plot one item, which replaces a plotted pair but keeps a lone x mark."""
        if len(self.marks) == 2:
            self._set_marks()
        self.post_message(UprootSelected(self.upfile, path))

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
