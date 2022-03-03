"""
Display tools for TTrees.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any, Dict, Tuple

import rich
import uproot
from rich.markup import escape
from rich.text import Text
from rich.tree import Tree

__all__ = ("make_tree", "process_item", "print_tree")


def __dir__() -> tuple[str, ...]:
    return __all__


def make_tree(uproot_object: Any, *, tree: Tree | None = None) -> Tree:
    """
    Given an object, build a rich.tree.Tree output.
    """
    result, insides = process_items(uproot_object)

    if tree is None:
        tree = Tree(**result)
    else:
        tree = tree.add(**result)

    for inside in insides:
        make_tree(inside, tree=tree)

    return tree


RetTuple = Tuple[Dict[str, Any], Tuple[Any, ...]]

"""
mydir
- mytree
   - mybranch
   - mybranch2
- mytree2
    - mybranch
    - mybranch2

TreeNode(id="mydir:mytree:mybranch", data=DirEntry(path="mydir:mytree:mybranch", is_dir=False))
TreeNode(id="mydir:mytree", data=DirEntry(path="mydir:mytree", is_dir=True))
"""


def process_items(item: Any) -> RetTuple:
    """
    Given an item, return a dict and a tuple of items.
    """

    if isinstance(item, (uproot.reading.ReadOnlyDirectory, uproot.TTree)):
        items = {key.split(";")[0] for key in item}
        insides = tuple(item[key] for key in sorted(items))
        return process_item(item), tuple(process_item(child) for child in insides)

    return process_item(item), ()


@functools.singledispatch
def process_item(uproot_object: Any) -> dict[str, Any]:
    """
    Given an unknown object, return a rich.tree.Tree output. Specialize for known objects.
    """
    name = getattr(uproot_object, "name", "<unnamed>")
    classname = getattr(uproot_object, "classname", uproot_object.__class__.__name__)

    label = Text.assemble(
        "❓ ",
        (f"{name} ", "bold"),
        (classname, "italic"),
    )
    result = {"label": label}
    return result


@process_item.register
def _process_item_tfile(
    uproot_object: uproot.reading.ReadOnlyDirectory,
) -> dict[str, Any]:
    """
    Given an TFile, return a rich.tree.Tree output.
    """
    path = Path(uproot_object.file_path)
    result = {
        "label": f":file_folder: [link file://{path}]{escape(path.name)}",
        "guide_style": "bold bright_blue",
    }
    return result


@process_item.register
def _process_item_ttree(uproot_object: uproot.TTree) -> dict[str, Any]:
    """
    Given an tree, return a rich.tree.Tree output.
    """
    label = Text.assemble(
        "🌴 ",
        (f"{uproot_object.name} ", "bold"),
        f"({uproot_object.num_entries:g})",
    )

    result = {
        "label": label,
        "guide_style": "bold bright_green",
    }
    return result


@process_item.register
def _process_item_tbranch(uproot_object: uproot.TBranch) -> dict[str, Any]:
    """
    Given an branch, return a rich.tree.Tree output.
    """

    jagged = isinstance(
        uproot_object.interpretation, uproot.interpretation.jagged.AsJagged
    )
    icon = "🍃 " if jagged else "🍁 "

    label = Text.assemble(
        icon,
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.typename} ", "italic"),
    )
    result = {"label": label}
    return result


@process_item.register
def _process_item_th(uproot_object: uproot.behaviors.TH1.Histogram) -> dict[str, Any]:
    """
    Given an histogram, return a rich.tree.Tree output.
    """
    icon = "📊 " if uproot_object.kind == "COUNT" else "📈 "
    sizes = " × ".join(f"{len(ax)}" for ax in uproot_object.axes)

    label = Text.assemble(
        icon,
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.classname} ", "italic"),
        f"({sizes})",
    )
    result = {"label": label}
    return result


def print_tree(entry: str) -> None:
    """
    Prints a tree given a specification string. Currently, that must be a
    single filename. Colons are not allowed currently in the filename.
    """

    upfile = uproot.open(entry)
    tree = make_tree(upfile)
    rich.print(tree)
