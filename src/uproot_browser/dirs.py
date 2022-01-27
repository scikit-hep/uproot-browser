from __future__ import annotations

from typing import Any, Iterable


def filename(select: str) -> str:
    return select.split(":")[0]


def selections(select: str) -> tuple[str, ...]:
    return tuple(select.split(":")[1:])


def apply_selection(tree: Any, select: Iterable[str]) -> Iterable[Any]:
    for s in select:
        tree = tree[s]
        yield tree
