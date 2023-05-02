"""
Display tools for TTrees.
"""

from __future__ import annotations

import dataclasses
import functools
from pathlib import Path
from typing import Any

import uproot
import uproot.reading
from rich.console import Console
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

from ._compat.typing import TypedDict

console = Console()

__all__ = (
    "make_tree",
    "process_item",
    "print_tree",
    "UprootEntry",
    "console",
    "MetaDict",
)


def __dir__() -> tuple[str, ...]:
    return __all__


class MetaDictRequired(TypedDict, total=True):
    label_text: Text
    label_icon: str


class MetaDict(MetaDictRequired, total=False):
    guide_style: str


@dataclasses.dataclass
class UprootEntry:
    path: str
    item: Any

    @property
    def is_dir(self) -> bool:
        if isinstance(self.item, uproot.reading.ReadOnlyDirectory):
            return True
        if isinstance(self.item, uproot.behaviors.TBranch.HasBranches):
            return len(self.item.branches) > 0
        return False

    def meta(self) -> MetaDict:
        return process_item(self.item)

    def label(self) -> Text:
        meta = self.meta()
        return Text.assemble(meta["label_icon"], meta["label_text"])

    def tree_args(self) -> dict[str, Any]:
        d: dict[str, Text | str] = {"label": self.label()}
        if "guide_style" in self.meta():
            d["guide_style"] = self.meta()["guide_style"]
        return d

    @property
    def children(self) -> list[UprootEntry]:
        if not self.is_dir:
            return []
        if isinstance(self.item, uproot.reading.ReadOnlyDirectory):
            items = {
                key.split(";")[0]
                for key in self.item.keys()  # noqa: SIM118
                if "/" not in key
            }
        elif isinstance(self.item, uproot.behaviors.TBranch.HasBranches):
            items = {item.name for item in self.item.branches}
        else:
            items = {obj.name.split(";")[0] for obj in self.item.branches}
        return [
            UprootEntry(f"{self.path}/{key}", self.item[key]) for key in sorted(items)
        ]


def make_tree(node: UprootEntry, *, tree: Tree | None = None) -> Tree:
    """
    Given an object, build a rich.tree.Tree output.
    """

    tree = Tree(**node.tree_args()) if tree is None else tree.add(**node.tree_args())

    for child in node.children:
        make_tree(child, tree=tree)

    return tree


@functools.singledispatch
def process_item(uproot_object: Any) -> MetaDict:
    """
    Given an unknown object, return a rich.tree.Tree output. Specialize for known objects.
    """
    name = getattr(uproot_object, "name", "<unnamed>")
    classname = getattr(uproot_object, "classname", uproot_object.__class__.__name__)
    label_text = Text.assemble(
        (f"{name} ", "bold"),
        (classname, "italic"),
    )
    return MetaDict(label_icon="❓ ", label_text=label_text)


@process_item.register
def _process_item_tfile(
    uproot_object: uproot.reading.ReadOnlyDirectory,
) -> MetaDict:
    """
    Given an TFile, return a rich.tree.Tree output.
    """
    path = Path(uproot_object.file_path)

    if uproot_object.path:
        # path is to a TDirectory on tree
        path_name = escape(uproot_object.path[0])
        link_text = f"file://{path}:/{path_name}"
    else:
        # path is the top of the tree: the file
        path_name = escape(path.name)
        link_text = f"file://{path}"

    label_text = Text.from_markup(f"[link {link_text}]{path_name}")

    return MetaDict(
        label_icon="📁 ",
        label_text=label_text,
        guide_style="bold bright_blue",
    )


@process_item.register
def _process_item_ttree(uproot_object: uproot.TTree) -> MetaDict:
    """
    Given an tree, return a rich.tree.Tree output.
    """
    label_text = Text.assemble(
        (f"{uproot_object.name} ", "bold"),
        f"({uproot_object.num_entries:g})",
    )

    return MetaDict(
        label_icon="🌴 ",
        label_text=label_text,
        guide_style="bold bright_green",
    )


@process_item.register
def _process_item_tbranch(uproot_object: uproot.TBranch) -> MetaDict:
    """
    Given an branch, return a rich.tree.Tree output.
    """

    jagged = isinstance(
        uproot_object.interpretation, uproot.interpretation.jagged.AsJagged
    )
    icon = "🍃 " if jagged else "🍁 "

    if len(uproot_object.branches):
        icon = "🌿 "

    label_text = Text.assemble(
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.typename}", "italic"),
    )

    return MetaDict(
        label_icon=icon,
        label_text=label_text,
        guide_style="bold bright_green",
    )


@process_item.register
def _process_item_th(uproot_object: uproot.behaviors.TH1.Histogram) -> MetaDict:
    """
    Given an histogram, return a rich.tree.Tree output.
    """
    icon = "📊 " if uproot_object.kind == "COUNT" else "📈 "
    sizes = " × ".join(f"{len(ax)}" for ax in uproot_object.axes)

    label_text = Text.assemble(
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.classname} ", "italic"),
        f"({sizes})",
    )
    return MetaDict(
        label_icon=icon,
        label_text=label_text,
    )


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string. Currently, that must be a
    single filename. Colons are not allowed currently in the filename.
    """

    upfile = uproot.open(entry)
    tree = make_tree(UprootEntry("/", upfile))
    console.print(tree)
