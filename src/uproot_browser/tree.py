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
    result, insides = process_item(uproot_object)

    if tree is None:
        tree = Tree(**result)
    else:
        tree = tree.add(**result)

    for inside in insides:
        make_tree(inside, tree=tree)

    return tree


RetTuple = Tuple[Dict[str, Any], Tuple[Any, ...]]


@functools.singledispatch
def process_item(uproot_object: Any) -> RetTuple:
    name = getattr(uproot_object, "name", "<unnamed>")
    classname = getattr(uproot_object, "classname", uproot_object.__class__.__name__)

    label = Text.assemble(
        "❓ ",
        (f"{name} ", "bold"),
        (classname, "italic"),
    )
    result = {"label": label}
    return result, ()


@process_item.register
def _process_item_TFile(uproot_object: uproot.reading.ReadOnlyDirectory) -> RetTuple:
    path = Path(uproot_object.file_path)
    result = {
        "label": f":file_folder: [link file://{path}]{escape(path.name)}",
        "guide_style": "bold bright_blue",
    }
    items = {key.split(";")[0] for key in uproot_object}
    insides = tuple(uproot_object[key] for key in sorted(items))
    return result, insides


@process_item.register
def _process_item_TTree(uproot_object: uproot.TTree) -> RetTuple:
    label = Text.assemble(
        "🌴 ",
        (f"{uproot_object.name} ", "bold"),
        f"({uproot_object.num_entries:g})",
    )

    result = {
        "label": label,
        "guide_style": "bold bright_green",
    }
    insides = tuple(v for v in uproot_object.values())
    return result, insides


@process_item.register
def _process_item_TBranch(uproot_object: uproot.TBranch) -> RetTuple:

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
    return result, ()


@process_item.register
def _process_item_TH(uproot_object: uproot.behaviors.TH1.Histogram) -> RetTuple:
    icon = "📊 " if uproot_object.kind == "COUNT" else "📈 "
    sizes = " × ".join(f"{len(ax)}" for ax in uproot_object.axes)

    label = Text.assemble(
        icon,
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.classname} ", "italic"),
        f"({sizes})",
    )
    result = {"label": label}
    return result, ()


def print_tree(entry: str) -> None:
    """
    Prints a tree given a specification string. Currently, that must be a
    single filename. Colons are not allowed currently in the filename.
    """

    f = uproot.open(entry)
    t = make_tree(f)
    rich.print(t)
