from __future__ import annotations

__lazy_modules__ = {
    "importlib.metadata",
    "packaging.requirements",
    "packaging.utils",
    "textual.app",
    "textual.widgets",
    "uproot_browser",
}

import importlib.metadata
from typing import TYPE_CHECKING

import packaging.requirements
import packaging.utils
import textual.app
import textual.containers
import textual.widgets

from uproot_browser import __version__

if TYPE_CHECKING:
    from collections.abc import Iterable


def dependencies(
    name: str = "uproot-browser", extras: Iterable[str] | None = None
) -> dict[str, str]:
    """
    The installed dependencies of ``name`` and their versions, by name.
    ``extras`` are the extras of ``name`` to follow, all of them by default.
    The extras of each requirement are followed, and markers are evaluated
    for this environment.
    """
    if extras is None:
        extras = importlib.metadata.metadata(name).get_all("Provides-Extra") or []
    todo = [(name, extra) for extra in ("", *extras)]
    seen = set(todo)
    found: dict[str, str] = {}
    while todo:
        current, extra = todo.pop()
        for text in importlib.metadata.requires(current) or []:
            req = packaging.requirements.Requirement(text)
            if req.marker is not None and not req.marker.evaluate({"extra": extra}):
                continue
            dep = packaging.utils.canonicalize_name(req.name)
            try:
                found[dep] = importlib.metadata.version(dep)
            except importlib.metadata.PackageNotFoundError:
                continue
            for visit in ((dep, dep_extra) for dep_extra in ("", *req.extras)):
                if visit not in seen:
                    seen.add(visit)
                    todo.append(visit)
    return found


class Info(textual.containers.Container):
    def compose(self) -> textual.app.ComposeResult:
        with textual.widgets.Collapsible(title="uproot-browser", collapsed=False):
            yield textual.widgets.Static(f"Version: [green]{__version__}[/green]")
        with textual.widgets.Collapsible(title="Dependencies", collapsed=False):
            yield textual.widgets.Static(
                "\n".join(
                    f"{dep} == [green]{version}[/green]"
                    for dep, version in sorted(dependencies().items())
                ),
                id="dependencies",
            )
