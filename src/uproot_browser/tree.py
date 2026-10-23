"""
Display tools for TTrees.
"""

from __future__ import annotations

__lazy_modules__ = {"pathlib", "rich", "rich.style", "rich.text", "rich.tree"}

import dataclasses
import functools
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, TypedDict

import uproot
import uproot.reading
from rich.console import Console
from rich.style import Style
from rich.text import Text
from rich.tree import Tree

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

console = Console()

__all__ = (
    "FailedEntry",
    "LocalDirectory",
    "LocalFile",
    "MetaDict",
    "UprootEntry",
    "console",
    "make_tree",
    "open_path",
    "print_tree",
    "process_item",
    "split_spec",
)


class SupportsRecursiveKeys(Protocol):
    def keys(self, *, recursive: bool = True) -> Iterable[str]: ...


def __dir__() -> tuple[str, ...]:
    return __all__


class MetaDictRequired(TypedDict, total=True):
    label_text: Text
    label_icon: str


class MetaDict(MetaDictRequired, total=False):
    guide_style: str


@dataclasses.dataclass(frozen=True, slots=True)
class FailedEntry:
    """A key whose object could not be read (e.g. unsupported RooFit classes)."""

    name: str
    classname: str
    exception: Exception


@dataclasses.dataclass
class LocalFile:
    """A ROOT file in a LocalDirectory, opened on first access to its contents."""

    path: Path
    _file: Any = dataclasses.field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def is_open(self) -> bool:
        return self._file is not None

    @property
    def file(self) -> Any:
        if self._file is None:
            self._file = uproot.open(self.path)
        return self._file

    def keys(self, *, recursive: bool = False) -> Iterable[str]:
        return self.file.keys(recursive=recursive)  # type: ignore[no-any-return]

    def __getitem__(self, key: str) -> Any:
        return self.file[key]

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


@dataclasses.dataclass
class LocalDirectory:
    """
    A filesystem directory. Its keys are the ROOT files and the subdirectories
    that contain ROOT files; a key may continue into the file, like uproot.
    """

    path: Path
    _files: dict[str, Any] = dataclasses.field(
        default_factory=dict, init=False, repr=False
    )

    @property
    def name(self) -> str:
        return self.path.name

    def keys(self, *, recursive: bool = False) -> list[str]:  # noqa: ARG002
        return self._keys

    @functools.cached_property
    def _keys(self) -> list[str]:
        return sorted(
            p.name
            for p in self.path.iterdir()
            if not p.name.startswith(".")
            and (
                (p.is_file() and p.suffix == ".root")
                or (p.is_dir() and any(p.rglob("*.root")))
            )
        )

    def _child(self, name: str) -> Any:
        if name not in self._files:
            child = self.path / name
            self._files[name] = (
                LocalDirectory(child) if child.is_dir() else LocalFile(child)
            )
        return self._files[name]

    def __getitem__(self, key: str) -> Any:
        name, _, rest = key.strip("/").partition("/")
        child = self._child(name)
        return child[rest] if rest else child

    def locate(self, key: str) -> tuple[Any, str]:
        """Split a key into the opened ROOT file and the key inside that file."""
        name, _, rest = key.strip("/").partition("/")
        child = self._child(name)
        if isinstance(child, LocalDirectory):
            return child.locate(rest)
        return child.file, rest

    def close(self) -> None:
        for child in self._files.values():
            child.close()
        self._files.clear()

    def __enter__(self) -> LocalDirectory:  # noqa: PYI034
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def split_spec(spec: str) -> tuple[str, str]:
    """
    Split ``path:key`` at the first colon that ends an existing local path,
    since keys can contain colons. Returns ``(spec, "")`` if there is none.
    """
    if "://" in spec or Path(spec).exists():
        return spec, ""
    for i, char in enumerate(spec):
        path = Path(spec[:i])
        # Skip a Windows drive, like "C:"
        if char == ":" and path.drive != spec[: i + 1] and path.exists():
            return spec[:i], spec[i + 1 :]
    return spec, ""


def open_path(spec: str) -> Any:
    """
    Like uproot.open, but a local directory opens as a LocalDirectory. A
    ``directory:key`` spec selects a key inside it.
    """
    name, key = split_spec(spec)
    if Path(name).is_dir():
        directory = LocalDirectory(Path(name))
        return directory[key] if key else directory
    return uproot.open(spec)


@functools.singledispatch
def is_dir(item: Any) -> bool:  # noqa: ARG001
    return False


@is_dir.register(LocalDirectory)
@is_dir.register(LocalFile)
@is_dir.register(uproot.reading.ReadOnlyDirectory)
def _(item: Any) -> Literal[True]:  # noqa: ARG001
    return True


@is_dir.register(uproot.behaviors.TBranch.HasBranches)
@is_dir.register(uproot.behaviors.RNTuple.HasFields)
def _(
    item: uproot.behaviors.TBranch.HasBranches | uproot.behaviors.RNTuple.HasFields,
) -> bool:
    return len(item) > 0


def get_children(item: SupportsRecursiveKeys) -> set[str]:
    return {key.partition(";")[0] for key in item.keys(recursive=False)}


@dataclasses.dataclass
class UprootEntry:
    path: str
    item: Any

    @property
    def is_dir(self) -> bool:
        return is_dir(self.item)

    def meta(self) -> MetaDict:
        return process_item(self.item)

    def tree_args(self) -> dict[str, Any]:
        meta = self.meta()
        d: dict[str, Text | str] = {
            "label": Text.assemble(meta["label_icon"], meta["label_text"])
        }
        if "guide_style" in meta:
            d["guide_style"] = meta["guide_style"]
        return d

    @property
    def children(self) -> list[UprootEntry]:
        if not self.is_dir:
            return []

        try:
            keys = get_children(self.item)
        except Exception as err:
            # A file of a directory opens here; show it as failed
            if not isinstance(self.item, LocalFile):
                raise
            self.item = FailedEntry(self.item.name, "TFile", err)
            return []

        children = []
        for key in sorted(keys):
            try:
                item = self.item[key]
            except Exception as err:  # noqa: BLE001
                classname_of = getattr(self.item, "classname_of", None)
                classname = classname_of(key) if classname_of else ""
                item = FailedEntry(key, classname, err)
            children.append(UprootEntry(f"{self.path}/{key}", item))
        return children

    def walk(self) -> Iterator[UprootEntry]:
        """Yield every descendant entry depth-first (not including self)."""
        for child in self.children:
            yield child
            yield from child.walk()


def make_tree(node: UprootEntry, *, tree: Tree | None = None) -> Tree:
    """
    Given an object, build a rich.tree.Tree output.
    """

    # Children first: a file that fails to open changes the label
    children = node.children
    tree = Tree(**node.tree_args()) if tree is None else tree.add(**node.tree_args())

    for child in children:
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
        path_name = uproot_object.path[-1]
        link_text = f"file://{path}:/{'/'.join(uproot_object.path)}"
    else:
        # path is the top of the tree: the file
        path_name = path.name
        link_text = f"file://{path}"

    label_text = Text(path_name, style=Style(link=link_text))

    return MetaDict(
        label_icon="📁 ",
        label_text=label_text,
        guide_style="bold bright_blue",
    )


@process_item.register
def _process_item_local_file(uproot_object: LocalFile) -> MetaDict:
    """Label a file of a directory without opening it."""
    path = uproot_object.path.resolve()
    return MetaDict(
        label_icon="📁 ",
        label_text=Text(path.name, style=Style(link=f"file://{path}")),
        guide_style="bold bright_blue",
    )


@process_item.register
def _process_item_local_directory(uproot_object: LocalDirectory) -> MetaDict:
    path = uproot_object.path.resolve()
    return MetaDict(
        label_icon="🗂️ ",
        label_text=Text(path.name, style=Style(link=f"file://{path}")),
        guide_style="bold bright_blue",
    )


def _tree_meta(uproot_object: Any, icon: str) -> MetaDict:
    """Meta for a tree-like object (TTree, RNTuple): name and entry count."""
    label_text = Text.assemble(
        (f"{uproot_object.name} ", "bold"),
        f"({uproot_object.num_entries:g})",
    )
    return MetaDict(
        label_icon=icon,
        label_text=label_text,
        guide_style="bold bright_green",
    )


def _branch_meta(uproot_object: Any, icon: str) -> MetaDict:
    """Meta for a branch-like object (TBranch, RField): name and typename."""
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
def _process_item_ttree(uproot_object: uproot.TTree) -> MetaDict:
    return _tree_meta(uproot_object, "🌴 ")


@process_item.register
def _process_item_rntuple(
    uproot_object: uproot.behaviors.RNTuple.RNTuple,
) -> MetaDict:
    return _tree_meta(uproot_object, "🌳 ")


@process_item.register
def _process_item_tbranch(uproot_object: uproot.TBranch) -> MetaDict:
    if uproot_object.branches:
        icon = "🌿 "
    elif isinstance(
        uproot_object.interpretation, uproot.interpretation.jagged.AsJagged
    ):
        icon = "🍃 "
    else:
        icon = "🍁 "
    return _branch_meta(uproot_object, icon)


@process_item.register
def _process_item_rbranch(uproot_object: uproot.models.RNTuple.RField) -> MetaDict:
    return _branch_meta(uproot_object, "🍁 ")


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


@process_item.register
def _process_item_failed(uproot_object: FailedEntry) -> MetaDict:
    """
    Given an unreadable object, return a rich.tree.Tree output.
    """
    label_text = Text.assemble(
        (f"{uproot_object.name} ", "bold"),
        (f"{uproot_object.classname} ", "italic"),
        (f"({uproot_object.exception.__class__.__name__})", "red"),
    )
    return MetaDict(label_icon="‼️ ", label_text=label_text)


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string: a filename or a directory.
    Colons are not allowed currently in the filename.
    """

    with open_path(entry) as upfile:
        tree = make_tree(UprootEntry("/", upfile))
    console.print(tree)
