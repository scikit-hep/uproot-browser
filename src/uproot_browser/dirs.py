"""
This holds common functions for accessing a file, ROOT directories, and trees
split by colons.
"""
from __future__ import annotations

from typing import Any, Iterable


def filename(select: str) -> str:
    """
    Return the filename portion of a colon-separated selection.
    """
    return select.split(":")[0]


def selections(select: str) -> tuple[str, ...]:
    """
    Return the directory/tree portion of a colon-separated selection.
    """
    return tuple(select.split(":")[1:])


def apply_selection(tree: Any, selection: Iterable[str]) -> Iterable[Any]:
    """
    Apply a colon-separated selection to an uproot tree. Slashes are handled by uproot.
    """
    for sel in selection:
        tree = tree[sel]
        yield tree
