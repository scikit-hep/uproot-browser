"""
Display tools for the tree of a file.
"""

from __future__ import annotations

__lazy_modules__ = {
    "rich",
    "rich.tree",
    "typing",
    "uproot_browser.backends",
    "uproot_browser.nodes",
}

from typing import Any

from rich.console import Console
from rich.tree import Tree

from uproot_browser.backends import as_node, open_path, split_spec
from uproot_browser.nodes import FailedNode, MetaDict, Node

console = Console()

__all__ = (
    "FailedNode",
    "MetaDict",
    "Node",
    "console",
    "make_tree",
    "open_path",
    "print_tree",
    "process_item",
    "split_spec",
)


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


def process_item(item: Any) -> MetaDict:
    """The icon and label of a raw object or a node."""
    return as_node(item).meta()


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string: a filename or a directory.
    """

    with open_path(entry) as root:
        tree = make_tree(root)
    console.print(tree)
