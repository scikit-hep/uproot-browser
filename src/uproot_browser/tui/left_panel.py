from __future__ import annotations

__lazy_modules__ = {
    "contextlib",
    "functools",
    "rich.panel",
    "rich.text",
    "textual.events",
    "textual.widget",
    "textual.widgets.tree",
    "uproot_browser.backends",
    "uproot_browser.backends.directory",
    "uproot_browser.tui.jump",
    "uproot_browser.tui.messages",
    "uproot_browser.tui.status",
}

import contextlib
import functools
from typing import TYPE_CHECKING, Any, ClassVar

import rich.panel
import rich.text
import textual
import textual.binding
import textual.events
import textual.widget
import textual.widgets
import textual.widgets.tree
from textual.reactive import var

from uproot_browser.backends import open_path
from uproot_browser.backends.directory import LazyRoot
from uproot_browser.nodes import Column, Node, Plottable
from uproot_browser.tui.jump import Candidate
from uproot_browser.tui.messages import UprootSelected
from uproot_browser.tui.status import StatusBar

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from rich.style import Style

SCROLLOFF = 2  # lines kept visible past the cursor, like vim's 'scrolloff'
MAX_COUNT_DIGITS = 4
COUNT_MOTIONS = frozenset({"up", "down", "j", "k"})
MODIFIERS = ("shift", "control", "alt", "super", "hyper", "meta")


def _in_file(node: Node) -> bool:
    try:
        node.root  # noqa: B018
    except LookupError:
        return False
    return True


def _plottable(node: Node) -> bool:
    """Can the node plot? An empty branch is only found when it reads."""
    return isinstance(node, Plottable) and node.plottable


def make_candidate(node: Node) -> Candidate:
    return Candidate(
        path=node.path,
        name=node.key,
        icon=node.meta()["label_icon"],
        is_dir=node.is_dir,
        plottable=_plottable(node),
    )


class UprootTree(textual.widgets.Tree[Node]):
    """The tree of nodes, with vim-style movement and marks for 2D plots."""

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
        # A remote URL opens in a load worker, with the app on screen; with a
        # "/" it is a directory, which opens without I/O
        remote = "://" in path and not path.endswith("/")
        self.root_node = LazyRoot(path) if remote else open_path(path)
        self._candidates: dict[str, list[Candidate]] = {}
        self._loading: set[int] = set()
        """The ids of the tree nodes with a load in progress."""
        self._filled: set[int] = set()
        """The ids of the tree nodes that have their children."""
        self._jump_requested = False
        self._pending_jump = ""
        """The target of a jump that waits for a load on its way."""
        super().__init__(
            name=path, data=self.root_node, label=self.root_node.name, **args
        )
        self.marks: list[textual.widgets.tree.TreeNode[Node]] = []
        """The x (and y, once plotted) branches of a 2D plot."""

    def jump_candidates(self) -> list[Candidate]:
        """
        All jump targets. The files of a directory are listed, but only
        entered after they are opened, so a jump does not open every file.
        This can read whole files: call it off the UI thread.
        """
        return list(self._candidates_below(self.root_node))

    def request_jump_candidates(
        self, callback: Callable[[list[Candidate]], None]
    ) -> None:
        """Build the jump targets in a worker, then give them to ``callback``."""
        if not self._jump_requested:
            self._jump_requested = True
            self._candidates_in_thread(callback)

    @textual.work(thread=True, group="jump")
    def _candidates_in_thread(
        self, callback: Callable[[list[Candidate]], None]
    ) -> None:
        try:
            with self.app.query_one(StatusBar).running("Listing jump targets"):
                candidates = self.jump_candidates()
        except Exception as err:  # noqa: BLE001
            call: Any = functools.partial(self._jump_failed, err)
        else:
            call = functools.partial(self._jump_ready, callback, candidates)
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(call)

    def _jump_ready(
        self, callback: Callable[[list[Candidate]], None], candidates: list[Candidate]
    ) -> None:
        self._jump_requested = False
        callback(candidates)

    def _jump_failed(self, err: Exception) -> None:
        self._jump_requested = False
        self.app.notify(f"Cannot list the jump targets: {err}", severity="error")

    def _candidates_below(self, node: Node) -> Iterator[Candidate]:
        # Not loaded: the children need I/O, which a load worker does
        if not node.is_loaded:
            return
        if _in_file(node):
            yield from self._file_candidates(node)
            return
        for child in node.children:
            yield make_candidate(child)
            yield from self._candidates_below(child)

    def _file_candidates(self, node: Node) -> list[Candidate]:
        """The jump targets in one file, built once and cached."""
        if node.path not in self._candidates:
            self._candidates[node.path] = [make_candidate(e) for e in node.walk()]
        return self._candidates[node.path]

    def select_path(self, target: str) -> None:
        """Navigate to (and reveal) the node at ``target``, plotting leaves."""
        self._pending_jump = ""
        node = self.root
        assert node.data
        if self._needs_load(node):
            self._wait_for_load(node, target)
            return
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
            node = child
            assert node.data
            if node.data.path != target:
                node.expand()
                if self._needs_load(node):
                    self._wait_for_load(node, target)
                    return

        target_node = node
        assert target_node.data

        def reveal() -> None:
            self.move_cursor(target_node)
            self.scroll_to_node(target_node)

        self.call_after_refresh(reveal)

        if target_node.data.is_dir:
            target_node.expand()
        else:
            self._select(target_node.data)

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
        node: textual.widgets.tree.TreeNode[Node],
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
        if not node.data.is_dir and not _plottable(node.data):
            label.stylize("dim")
        return label

    def on_mount(self) -> None:
        # The expand event loads the children in a worker
        self.root.expand()

    def _needs_load(self, node: textual.widgets.tree.TreeNode[Node]) -> bool:
        """Must ``node`` read its children? A failed load tries again."""
        assert node.data
        return node.data.is_dir and node.id not in self._filled

    def _fill_node(
        self, node: textual.widgets.tree.TreeNode[Node], children: list[Node]
    ) -> None:
        self._loading.discard(node.id)
        assert node.data
        # A file gives no children if its open or listing failed
        error = node.data.error if isinstance(node.data, LazyRoot) else None
        if error is not None:
            self.app.notify(f"{node.data.name}: {error}", severity="error")
        else:
            self._filled.add(node.id)
        if not node.children:
            for child in children:
                node.add(child.path, child)
        # A file that failed to open has a new label
        node.refresh()
        target = self._take_jump(node)
        # A jump does not try a failed load again
        if target and error is None:
            self.select_path(target)

    def _wait_for_load(
        self, node: textual.widgets.tree.TreeNode[Node], target: str
    ) -> None:
        """Load ``node`` in a worker; :meth:`_fill_node` then continues the jump."""
        self._pending_jump = target
        self._request_load(node)

    def _take_jump(self, node: textual.widgets.tree.TreeNode[Node]) -> str:
        """The pending jump that waits for ``node`` (then cleared), else empty."""
        assert node.data
        if not self._pending_jump.startswith(f"{node.data.path}/"):
            return ""
        target, self._pending_jump = self._pending_jump, ""
        return target

    def _load_failed(
        self, node: textual.widgets.tree.TreeNode[Node], err: Exception
    ) -> None:
        assert node.data
        self._loading.discard(node.id)
        self._take_jump(node)
        self.app.notify(f"{node.data.name}: {err}", severity="error")

    @textual.work(thread=True, group="load")
    def _load_in_thread(self, node: textual.widgets.tree.TreeNode[Node]) -> None:
        """Read the children (a listing, a file open, the objects) off the UI thread."""
        assert node.data
        try:
            with self.app.query_one(StatusBar).running(f"Loading {node.data.name}"):
                children = node.data.children
        except Exception as err:  # noqa: BLE001
            call: Any = functools.partial(self._load_failed, node, err)
        else:
            call = functools.partial(self._fill_node, node, children)
        # The app can exit while the load runs
        with contextlib.suppress(RuntimeError):
            self.app.call_from_thread(call)

    def on_tree_node_selected(
        self, event: textual.widgets.Tree.NodeSelected[Node]
    ) -> None:
        event.stop()
        item = event.node.data
        assert item
        if not item.is_dir:
            self._select(item)

    def on_tree_node_expanded(
        self, event: textual.widgets.Tree.NodeExpanded[Node]
    ) -> None:
        event.stop()
        if self._needs_load(event.node):
            self._request_load(event.node)

    def _request_load(self, node: textual.widgets.tree.TreeNode[Node]) -> None:
        if node.id not in self._loading:
            self._loading.add(node.id)
            self._load_in_thread(node)

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

    def _pairable(self, node: textual.widgets.tree.TreeNode[Node]) -> bool:
        """Can ``node`` be one axis of a 2D plot? Warns if not."""
        if isinstance(node.data, Column) and node.data.numeric:
            return True
        self.app.notify(
            "Only numeric branches and fields can be plotted in 2D.",
            severity="warning",
        )
        return False

    def _set_marks(self, *nodes: textual.widgets.tree.TreeNode[Node]) -> None:
        """Replace the marks (relabeling old and new); two marks plot in 2D."""
        old, self.marks = self.marks, list(nodes)
        for node in (*old, *nodes):
            node.refresh()
        if len(nodes) == 2:
            x_node, y_node = nodes
            assert x_node.data
            assert y_node.data
            self.post_message(
                UprootSelected(
                    self.root_node,
                    self._below_root(x_node.data),
                    self._below_root(y_node.data),
                )
            )

    def _below_root(self, node: Node) -> str:
        """The path a node has with the displayed root (maybe inside a file) as the top."""
        return f"/{node.path.removeprefix(self.root_node.path)}"

    def _select(self, node: Node) -> None:
        """Plot one item, which replaces a plotted pair but keeps a lone x mark."""
        if len(self.marks) == 2:
            self._set_marks()
        self.post_message(UprootSelected(self.root_node, self._below_root(node)))

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
