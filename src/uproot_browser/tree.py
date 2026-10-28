"""
Display tools for the tree of a file.
"""

from __future__ import annotations

__lazy_modules__ = {"rich", "rich.tree", "uproot_browser.backends"}

from typing import TYPE_CHECKING

from rich.console import Console
from rich.tree import Tree

from uproot_browser.backends import open_path

if TYPE_CHECKING:
    from uproot_browser.nodes import Node

console = Console()

__all__ = ("console", "make_tree", "print_tree")


def __dir__() -> tuple[str, ...]:
    return __all__


def make_tree(node: Node, *, tree: Tree | None = None) -> Tree:
    """
    Given a node, build a rich.tree.Tree output.
    """

    # Children first: a file of a directory opens here, and that can fail
    children = node.children
    tree = Tree(**node.tree_args()) if tree is None else tree.add(**node.tree_args())

    for child in children:
        make_tree(child, tree=tree)

    return tree


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string: a filename or a directory.
    """

    with open_path(entry) as root:
        tree = make_tree(root)
    console.print(tree)
