from __future__ import annotations

__lazy_modules__ = {
    "importlib.metadata",
    "textual.app",
    "textual.widgets",
    "uproot_browser",
}

import importlib.metadata
import re

import textual.app
import textual.containers
import textual.widgets

from uproot_browser import __version__

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def dependencies(name: str = "uproot-browser") -> dict[str, str]:
    """
    The installed dependencies of ``name`` and their versions, by name. This
    has the installed extras of ``name``, but not the extras of its
    dependencies.
    """
    found: dict[str, str] = {}
    todo = [(name, True)]
    while todo:
        current, with_extras = todo.pop()
        for req in importlib.metadata.requires(current) or []:
            if not with_extras and "extra" in req.partition(";")[2]:
                continue
            match = _NAME.match(req)
            if match is None:
                continue
            dep = _normalize(match.group())
            if dep in found:
                continue
            try:
                found[dep] = importlib.metadata.version(dep)
            except importlib.metadata.PackageNotFoundError:
                continue
            todo.append((dep, False))
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
