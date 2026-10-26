"""
The uproot backend: ROOT files, with TDirectories, TTrees, RNTuples, branches,
fields and histograms. It also opens any spec no other backend claims.
"""

from __future__ import annotations

__lazy_modules__ = {
    "numpy",
    "operator",
    "pathlib",
    "rich",
    "rich.style",
    "rich.text",
    "textwrap",
    "uproot._util",
    "uproot.behaviors",
    "uproot.behaviors.TBranch",
    "uproot.interpretation",
    "uproot.interpretation.jagged",
    "uproot.interpretation.numerical",
    "uproot.interpretation.objects",
    "uproot_browser.exceptions",
}

import dataclasses
import functools
import operator
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
import uproot
import uproot._util
import uproot.behaviors.RNTuple
import uproot.behaviors.TBranch
import uproot.behaviors.TH1
import uproot.interpretation.jagged
import uproot.interpretation.numerical
import uproot.interpretation.objects
import uproot.model
import uproot.models.RNTuple
import uproot.reading
from rich.style import Style
from rich.text import Text

from uproot_browser.backends import as_node, split_spec
from uproot_browser.exceptions import EmptyTreeError
from uproot_browser.nodes import (
    Column,
    DataTree,
    Folder,
    Histogram,
    MetaDict,
    Node,
    Root,
    path_meta,
)

if TYPE_CHECKING:
    import hist

__all__ = (
    "UprootBranch",
    "UprootDirectory",
    "UprootField",
    "UprootFile",
    "UprootHistogram",
    "UprootObject",
    "UprootRNTuple",
    "UprootTTree",
    "matches",
    "open_spec",
    "wrap",
)


def __dir__() -> tuple[str, ...]:
    return __all__


def matches(spec: str) -> bool:
    name, _ = split_spec(spec)
    return "://" in name or Path(name).suffix.lower() == ".root"


def open_spec(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """Open a file; a ``path:key`` spec gives the node at ``key`` inside it."""
    name, obj_path = split_spec(spec)
    if not obj_path and "://" in spec:
        name, remote_path = uproot._util.file_object_path_split(spec)  # noqa: SLF001  # pylint: disable=protected-access
        obj_path = remote_path or ""
    root = UprootFile(uproot.open(name), parent, key, spec=name)
    return root.resolve(obj_path) if obj_path else root


def _name(item: Any) -> str:
    return str(getattr(item, "name", "<unnamed>"))


class _UprootNode(Node):  # pylint: disable=abstract-method
    """A node named after its uproot object."""

    @property
    def name(self) -> str:
        return _name(self.item)


class UprootObject(_UprootNode):
    """Any object the browser has no special support for."""

    def meta(self) -> MetaDict:
        classname = getattr(self.item, "classname", self.item.__class__.__name__)
        label_text = Text.assemble((f"{self.name} ", "bold"), (classname, "italic"))
        return MetaDict(label_icon="❓ ", label_text=label_text)


class _UprootFolder(Folder):  # pylint: disable=abstract-method
    """Children come from ``keys(recursive=False)`` and ``item[key]``."""

    def keys(self) -> list[str]:
        return list({key.partition(";")[0] for key in self.item.keys(recursive=False)})

    def lookup(self, key: str) -> Node:
        return wrap(self.item[key], parent=self, key=key)

    def classname_of(self, key: str) -> str:
        classname_of = getattr(self.item, "classname_of", None)
        return str(classname_of(key)) if classname_of else ""


class UprootDirectory(_UprootFolder):
    """A TDirectory, or the top of a file."""

    @property
    def name(self) -> str:
        return str(self.item.path[-1]) if self.item.path else _name(self.item)

    def meta(self) -> MetaDict:
        path = Path(self.item.file_path)
        if not self.item.path:
            # The top of the tree: the file
            return path_meta(path, "📁 ")

        # A TDirectory in the file
        link_text = f"file://{path}:/{'/'.join(self.item.path)}"
        return MetaDict(
            label_icon="📁 ",
            label_text=Text(self.item.path[-1], style=Style(link=link_text)),
            guide_style="bold bright_blue",
        )


@dataclasses.dataclass(eq=False)
class UprootFile(Root, UprootDirectory):
    """The directory a file was opened as."""

    spec: str = dataclasses.field(kw_only=True)
    """The path passed to ``uproot.open``."""

    def open_source(self, var: str) -> str:
        return f'import uproot\n{var} = uproot.open("{self.spec}")'

    def close(self) -> None:
        self.item.close()


class _UprootContainer(_UprootFolder, _UprootNode):  # pylint: disable=abstract-method
    """A tree, branch or field: a folder only when it has sub-items."""

    @property
    def is_dir(self) -> bool:
        return len(self.item) > 0


class _UprootTreeLike(_UprootContainer, DataTree):
    icon: ClassVar[str]

    @property
    def num_entries(self) -> int:
        return int(self.item.num_entries)

    def meta(self) -> MetaDict:
        label_text = Text.assemble(
            (f"{self.name} ", "bold"), f"({self.item.num_entries:g})"
        )
        return MetaDict(
            label_icon=self.icon, label_text=label_text, guide_style="bold bright_green"
        )


class UprootTTree(_UprootTreeLike):
    icon = "🌴 "


class UprootRNTuple(_UprootTreeLike):
    icon = "🌳 "


class _UprootColumn(Column, _UprootContainer):  # pylint: disable=abstract-method
    """A branch or field; it may have sub-branches or sub-fields."""

    @property
    def icon(self) -> str:
        return "🍁 "

    @property
    def entry_count(self) -> int:
        return int(self.item.num_entries)

    @property
    def typename(self) -> str:
        return str(self.item.typename)

    def read(self) -> Any:
        return self.item.array()

    def read_source(self, var: str) -> str:
        return f"{var}.array()"

    def meta(self) -> MetaDict:
        label_text = Text.assemble(
            (f"{self.name} ", "bold"), (f"{self.typename}", "italic")
        )
        return MetaDict(
            label_icon=self.icon, label_text=label_text, guide_style="bold bright_green"
        )


class UprootBranch(_UprootColumn):
    """
    A TBranch. Branches holding TH1 objects plot as their sum; numeric arrays
    are flattened, filtered to finite values, and filled.
    """

    @property
    def icon(self) -> str:
        if self.item.branches:
            return "🌿 "
        if isinstance(self.item.interpretation, uproot.interpretation.jagged.AsJagged):
            return "🍃 "
        return "🍁 "

    @property
    def numeric(self) -> bool:
        return _branch_numeric(self.item)

    @property
    def plottable(self) -> bool:
        interpretation = _leaf_interpretation(self.item)
        if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
            return _model_is_histogram(interpretation.model)
        return self.numeric

    @property
    def _holds_objects(self) -> bool:
        return isinstance(
            self.item.interpretation, uproot.interpretation.objects.AsObjects
        )

    def data_tree(self) -> DataTree | None:
        return super().data_tree() or UprootTTree(self.item.tree)

    def data_tree_source(
        self,
        var: str = "item",
        file_var: str = "uproot_file",  # noqa: ARG002
    ) -> str | None:
        return f"{var}.tree"

    def to_histogram(self, *, bins: int = 50) -> hist.Hist[Any]:
        if self._holds_objects:
            arr = self.item.array(library="np")
            if len(arr) == 0:
                msg = f"Branch {self.name} is empty."
                raise EmptyTreeError(msg)
            if not isinstance(arr[0], uproot.behaviors.TH1.Histogram):
                msg = f"Branch {self.name} ({self.typename}) contains objects that cannot be plotted"
                raise TypeError(msg)
            histogram: hist.Hist[Any] = functools.reduce(
                operator.add, (h.to_hist() for h in arr)
            )
            return histogram
        return super().to_histogram(bins=bins)

    def dump_hist(self, *, width: int = 100) -> str:
        if self._holds_objects:
            return textwrap.dedent("""\
                import functools
                import operator
                arr = item.array(library="np")
                h = functools.reduce(operator.add, [x.to_hist() for x in arr])""")
        return super().dump_hist(width=width)


class UprootField(_UprootColumn):
    """An RNTuple field. Only numeric values can be filled."""

    @property
    def numeric(self) -> bool:
        return _field_plottable(self.item)

    def data_tree(self) -> DataTree | None:
        return super().data_tree() or UprootRNTuple(self.item.ntuple)

    def data_tree_source(
        self,
        var: str = "item",
        file_var: str = "uproot_file",  # noqa: ARG002
    ) -> str | None:
        return f"{var}.ntuple"


class UprootHistogram(Histogram, _UprootNode):
    def meta(self) -> MetaDict:
        icon = "📊 " if self.item.kind == "COUNT" else "📈 "
        sizes = " × ".join(f"{len(ax)}" for ax in self.item.axes)
        label_text = Text.assemble(
            (f"{self.name} ", "bold"),
            (f"{self.item.classname} ", "italic"),
            f"({sizes})",
        )
        return MetaDict(label_icon=icon, label_text=label_text)


def _model_is_histogram(model: Any) -> bool:
    if not isinstance(model, type):
        return False
    if issubclass(model, uproot.behaviors.TH1.Histogram):
        return True
    if issubclass(model, uproot.model.DispatchByVersion):
        versions: dict[int, type] = getattr(model, "known_versions", {})
        return any(
            issubclass(v, uproot.behaviors.TH1.Histogram) for v in versions.values()
        )
    return False


def _leaf_interpretation(branch: uproot.TBranch) -> Any:
    interpretation = branch.interpretation
    if isinstance(interpretation, uproot.interpretation.jagged.AsJagged):
        return interpretation.content
    return interpretation


def _branch_numeric(branch: uproot.TBranch) -> bool:
    interpretation = _leaf_interpretation(branch)
    # AsStridedObjects is a Numerical, but yields records np.isfinite rejects
    return isinstance(
        interpretation, uproot.interpretation.numerical.Numerical
    ) and not isinstance(interpretation, uproot.interpretation.objects.AsStridedObjects)


_TEXT_ARRAYS = frozenset({"string", "bytestring"})


def _unwrap_lists(form: Any) -> Any:
    """The content inside any number of lists, or None if the lists hold text."""
    while form.is_list:
        if form.parameter("__array__") in _TEXT_ARRAYS:
            return None
        form = form.content
    return form


def _field_leaf_form(field: uproot.models.RNTuple.RField) -> Any:
    """The form of the values that ``field.array()`` gives, or None."""
    akform = field.to_akform()
    # uproot 5.7+ gives (form, path); older versions give only the form, whose
    # single top-level field names the path.
    form, path = akform if isinstance(akform, tuple) else (akform, None)
    for name in form.fields if path is None else path:
        form = _unwrap_lists(form)
        if form is None or not form.is_record or name not in form.fields:
            return None
        form = form.content(name)
    return _unwrap_lists(form)


def _field_plottable(field: uproot.models.RNTuple.RField) -> bool:
    leaf = _field_leaf_form(field)
    if leaf is None or not leaf.is_numpy or leaf.parameter("__array__") is not None:
        return False
    # bool, integer and float values can go into a histogram; text, records,
    # unions and datetimes cannot.
    return np.dtype(leaf.primitive).kind in "biuf"


@functools.singledispatch
def wrap(item: Any, *, parent: Folder | None = None, key: str = "") -> Node:
    """The node for an uproot object; the object's type picks the class."""
    return UprootObject(item, parent, key)


def _register(cls: type, node_cls: type[Node]) -> None:
    def make(item: Any, *, parent: Folder | None = None, key: str = "") -> Node:
        return node_cls(item, parent, key)

    wrap.register(cls, make)
    as_node.register(cls, make)


_register(uproot.model.Model, UprootObject)
_register(uproot.reading.ReadOnlyDirectory, UprootDirectory)
_register(uproot.TTree, UprootTTree)
_register(uproot.behaviors.RNTuple.RNTuple, UprootRNTuple)
_register(uproot.TBranch, UprootBranch)
_register(uproot.models.RNTuple.RField, UprootField)
_register(uproot.behaviors.TH1.Histogram, UprootHistogram)
