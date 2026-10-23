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
    "get_children",
    "is_dir",
    "lookup",
    "make_tree",
    "open_path",
    "open_source",
    "print_tree",
    "process_item",
    "source_path",
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
    error: Exception | None = dataclasses.field(default=None, init=False, repr=False)
    """The exception of a failed open; the file then has no keys."""
    _file: Any = dataclasses.field(default=None, init=False, repr=False)

    @property
    def file_path(self) -> str:
        return str(self.path)

    @property
    def is_open(self) -> bool:
        return self._file is not None

    @property
    def file(self) -> Any:
        if self._file is None:
            try:
                self._file = uproot.open(self.path)
            except Exception as err:
                self.error = err
                raise
        return self._file

    def keys(self, **_: object) -> Iterable[str]:
        try:
            return self.file.keys(recursive=False)  # type: ignore[no-any-return]
        except Exception:  # noqa: BLE001
            return []

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
    def file_path(self) -> str:
        return str(self.path)

    def keys(self, **_: object) -> list[str]:
        return self._listing

    @functools.cached_property
    def _listing(self) -> list[str]:
        return sorted(
            p.name
            for p in self.path.iterdir()
            if not p.name.startswith(".")
            and (
                (p.is_file() and p.suffix == ".root")
                or (p.is_dir() and any(p.rglob("*.root")))
            )
        )

    def _resolve(self, key: str) -> tuple[Any, str]:
        """The child named by the first part of a key, and the rest of the key."""
        name, _, rest = key.strip("/").partition("/")
        if name not in self._files:
            child = self.path / name
            self._files[name] = (
                LocalDirectory(child) if child.is_dir() else LocalFile(child)
            )
        return self._files[name], rest

    def __getitem__(self, key: str) -> Any:
        child, rest = self._resolve(key)
        return child[rest] if rest else child

    def locate(self, key: str) -> tuple[LocalFile, str]:
        """Split a key into the LocalFile and the key inside that file."""
        child, rest = self._resolve(key)
        if isinstance(child, LocalDirectory):
            return child.locate(rest)
        return child, rest

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
        if char != ":":
            continue
        path = Path(spec[:i])
        # Skip a Windows drive, like "C:"
        if path.drive != spec[: i + 1] and path.exists():
            return spec[:i], spec[i + 1 :]
    return spec, ""


def _is_cdf(name: str) -> bool:
    return "://" not in name and Path(name).suffix.lower() == ".cdf"


def _cdf_module() -> Any:
    try:
        import uproot_browser.cdf  # noqa: PLC0415
    except ModuleNotFoundError as err:
        msg = "Install the [cdf] extra (cdflib and xarray) to open CDF files"
        raise ModuleNotFoundError(msg) from err
    return uproot_browser.cdf


def open_path(spec: str) -> Any:
    """
    Like uproot.open, but a local directory opens as a LocalDirectory and a
    CDF file as an xarray Dataset (with the [cdf] extra). A ``path:key`` spec
    selects a key inside it.
    """
    name, key = split_spec(spec)
    if Path(name).is_dir():
        directory = LocalDirectory(Path(name))
        return directory[key] if key else directory
    if _is_cdf(name):
        dataset = _cdf_module().open_cdf(name)
        return dataset[key] if key else dataset
    return uproot.open(spec)


def open_source(spec: str) -> str:
    """Python source that opens ``spec`` as ``uproot_file``, like :func:`open_path`."""
    name, _ = split_spec(spec)
    if Path(name).is_dir():
        return f"import uproot_browser.tree\nuproot_file = uproot_browser.tree.open_path({spec!r})"
    if _is_cdf(name):
        source: str = _cdf_module().open_cdf_source(name)
        return source
    return f"import uproot\nuproot_file = uproot.open({spec!r})"


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


@functools.singledispatch
def get_children(item: Any) -> set[str]:
    """The keys of the direct children of a container; specialize per format."""
    keys: SupportsRecursiveKeys = item
    return {key.partition(";")[0] for key in keys.keys(recursive=False)}


@functools.singledispatch
def lookup(item: Any, key: str) -> Any:
    """Get the child at ``key`` (a tree path); specialize per format."""
    return item[key]


@functools.singledispatch
def source_path(item: Any) -> str:
    """The path of the file a top-level object was read from."""
    return str(item.file_path)


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

        children = []
        for key in sorted(get_children(self.item)):
            try:
                item = lookup(self.item, key)
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

    # Children first: a file of a directory opens here, and that can fail
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

    if not uproot_object.path:
        # The top of the tree: the file
        return _path_meta(path, "📁 ")

    # A TDirectory in the file
    link_text = f"file://{path}:/{'/'.join(uproot_object.path)}"
    return MetaDict(
        label_icon="📁 ",
        label_text=Text(uproot_object.path[-1], style=Style(link=link_text)),
        guide_style="bold bright_blue",
    )


def _path_meta(path: Path, icon: str) -> MetaDict:
    """Meta for a local file or directory: its name, linked to the path."""
    return MetaDict(
        label_icon=icon,
        label_text=Text(path.name, style=Style(link=f"file://{path.resolve()}")),
        guide_style="bold bright_blue",
    )


@process_item.register
def _process_item_local_file(uproot_object: LocalFile) -> MetaDict:
    """Label a file of a directory without opening it."""
    if uproot_object.error is not None:
        return _failed_meta(uproot_object.path.name, "TFile", uproot_object.error)
    return _path_meta(uproot_object.path, "📁 ")


@process_item.register
def _process_item_local_directory(uproot_object: LocalDirectory) -> MetaDict:
    return _path_meta(uproot_object.path, "🗂️ ")


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
    return _failed_meta(
        uproot_object.name, uproot_object.classname, uproot_object.exception
    )


def _failed_meta(name: str, classname: str, exception: Exception) -> MetaDict:
    label_text = Text.assemble(
        (f"{name} ", "bold"),
        (f"{classname} ", "italic"),
        (f"({exception.__class__.__name__})", "red"),
    )
    return MetaDict(label_icon="‼️ ", label_text=label_text)


# pylint: disable-next=redefined-outer-name
def print_tree(entry: str, *, console: Console = console) -> None:
    """
    Prints a tree given a specification string: a filename or a directory.
    """

    with open_path(entry) as upfile:
        tree = make_tree(UprootEntry("/", upfile))
    console.print(tree)
