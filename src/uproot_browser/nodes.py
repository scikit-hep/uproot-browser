"""
The backend-neutral model of what the browser shows.

A backend (uproot, a local directory, ...) wraps each of its objects in one of
these node classes. Everything else (tree printing, plotting, the TUI and
Dump & Quit) talks to the nodes only. A new format implements the abstract
members of the classes it needs; see :mod:`uproot_browser.backends`.
"""

from __future__ import annotations

__lazy_modules__ = {
    "awkward",
    "hist",
    "numpy",
    "re",
    "rich",
    "rich.style",
    "rich.text",
    "textwrap",
    "uproot_browser.exceptions",
}

import dataclasses
import re
import textwrap
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Self, TypedDict

import awkward as ak
import hist
import numpy as np
from rich.style import Style
from rich.text import Text

from uproot_browser.exceptions import EmptyTreeError

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

__all__ = (
    "Column",
    "DataTree",
    "FailedNode",
    "Folder",
    "Histogram",
    "MetaDict",
    "Node",
    "Pair",
    "Plottable",
    "Root",
    "failed_meta",
    "fill_finite",
    "path_meta",
)


def __dir__() -> tuple[str, ...]:
    return __all__


class MetaDictRequired(TypedDict, total=True):
    label_text: Text
    label_icon: str


class MetaDict(MetaDictRequired, total=False):
    guide_style: str


_SEPARATORS = re.compile(r"[/:]")


@dataclasses.dataclass(eq=False)
class Node(ABC):
    """
    An entry in the browser tree: a backend object and its place in the tree.

    Nodes compare by identity. Subclasses add behavior, not fields, so a class
    can mix several concepts (a branch with sub-branches is a Column and a
    Folder).
    """

    item: Any
    """The raw backend object. Expressions and Dump & Quit work on this."""
    parent: Folder | None = None
    key: str = ""
    """The name of this node in its parent; empty for the top of the tree."""

    @property
    def path(self) -> str:
        return "/" if self.parent is None else f"{self.parent.path}/{self.key}"

    @property
    def name(self) -> str:
        """The display name, also used in plot titles."""
        return self.key

    @property
    def is_dir(self) -> bool:
        return False

    @property
    def children(self) -> list[Node]:
        return []

    @abstractmethod
    def meta(self) -> MetaDict:
        """The icon and label shown in the tree."""

    def tree_args(self) -> dict[str, Any]:
        meta = self.meta()
        d: dict[str, Text | str] = {
            "label": Text.assemble(meta["label_icon"], meta["label_text"])
        }
        if "guide_style" in meta:
            d["guide_style"] = meta["guide_style"]
        return d

    def walk(self) -> Iterator[Node]:
        """Yield every descendant depth-first (not including self)."""
        for child in self.children:
            yield child
            yield from child.walk()

    def resolve(self, path: str) -> Node:
        """
        The node at a ``/`` or ``:`` separated path below this one. A segment
        that fails to load gives a :class:`FailedNode`, so the selection can
        still be named in Dump & Quit.
        """
        node: Node = self
        for key in filter(None, _SEPARATORS.split(path)):
            if isinstance(node, FailedNode):
                return node
            if not isinstance(node, Folder):
                msg = f"{node.path!r} has no children, cannot look up {key!r}"
                raise KeyError(msg)
            folder = node
            try:
                node = folder.lookup(key)  # pylint: disable=no-member
            except Exception as err:  # noqa: BLE001
                classname = folder.classname_of(key)  # pylint: disable=no-member
                return FailedNode(None, folder, key, exception=err, classname=classname)
        return node

    @property
    def root(self) -> Root:
        """The nearest ancestor (or self) that opened a file."""
        node: Node = self
        while not isinstance(node, Root):
            if node.parent is None:
                msg = f"{self.path!r} was not opened from a file"
                raise LookupError(msg)
            node = node.parent
        return node

    @property
    def keys_below_root(self) -> list[str]:
        keys: list[str] = []
        node: Node = self
        while not isinstance(node, Root):
            if node.parent is None:
                msg = f"{self.path!r} was not opened from a file"
                raise LookupError(msg)
            keys.append(node.key)
            node = node.parent
        return keys[::-1]

    def bind_source(self, var: str = "item", file_var: str = "uproot_file") -> str:
        """Source that binds ``var`` to this object, given the open file in ``file_var``."""
        return f"{var} = {self.root.lookup_source(file_var, self.keys_below_root)}"

    def data_tree(self) -> DataTree | None:
        """The columnar dataset this node belongs to (itself, if it is one)."""
        node: Node | None = self
        while node is not None:
            if isinstance(node, DataTree):
                return node
            node = node.parent
        return None

    def data_tree_source(
        self, var: str = "item", file_var: str = "uproot_file"
    ) -> str | None:
        """Source for :meth:`data_tree` given this object in ``var``, or None."""
        tree = self.data_tree()
        if tree is None:
            return None
        if tree is self:
            return var
        return tree.root.lookup_source(file_var, tree.keys_below_root)

    def close(self) -> None:
        """Release what this node opened; the default holds nothing."""

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class Folder(Node):
    """A node with named children: a directory, a file, a TDirectory, a dataset."""

    @property
    def is_dir(self) -> bool:
        return True

    @property
    def is_loaded(self) -> bool:
        """False while listing the children would first open a file."""
        return True

    @abstractmethod
    def keys(self) -> list[str]:
        """The names of the direct children."""

    @abstractmethod
    def lookup(self, key: str) -> Node:
        """The child named ``key``, with this node as its parent."""

    def classname_of(self, key: str) -> str:  # noqa: ARG002
        """The type name of a child without loading it, for failed entries."""
        return ""

    @property
    def children(self) -> list[Node]:
        children: list[Node] = []
        for key in sorted(self.keys()):
            try:
                node = self.lookup(key)
            except Exception as err:  # noqa: BLE001
                node = FailedNode(
                    None, self, key, exception=err, classname=self.classname_of(key)
                )
            children.append(node)
        return children


class Root(Node):
    """
    A node that opened a resource (a file). Dump & Quit starts from its
    :meth:`open_source`, and :meth:`close` releases it.
    """

    @abstractmethod
    def open_source(self, var: str) -> str:
        """Standalone source that binds ``var`` to this object (imports included)."""

    def lookup_source(self, file_var: str, keys: Sequence[str]) -> str:
        """Source for the object at ``keys`` below this root, bound to ``file_var``."""
        if not keys:
            return file_var
        return f'{file_var}["{"/".join(keys)}"]'

    @abstractmethod
    def close(self) -> None: ...


class DataTree(Folder):
    """A columnar dataset (TTree, RNTuple): columns sharing one entry count."""

    @property
    @abstractmethod
    def num_entries(self) -> int: ...


class Plottable(Node):
    """A node :func:`uproot_browser.plot.plot` can draw."""

    @property
    def plottable(self) -> bool:
        """
        Can plotting succeed? Some failures (like an empty branch) are only
        found by reading the data, so this is a necessary but not sufficient check.
        """
        return True

    @property
    def ndim(self) -> int:
        """The dimensions of the plotted histogram, without reading data."""
        return 1

    @abstractmethod
    def to_histogram(self, *, bins: int = 50) -> hist.Hist[Any]:
        """Build the histogram to draw."""

    @abstractmethod
    def dump_hist(self, *, width: int = 100) -> str:
        """Standalone source that rebuilds :meth:`to_histogram` as ``h`` from ``item``."""

    def title_source(self, var: str = "item") -> str:
        """An f-string source for the plot title (the flow count is omitted)."""
        return f'f"{{{var}.name}} -- Entries: {{np.sum(h.counts()):g}}"'


class Histogram(Plottable):  # pylint: disable=abstract-method
    """A stored histogram, any object with ``axes`` and ``to_hist()``."""

    @property
    def ndim(self) -> int:
        return len(self.item.axes)

    @property
    def plottable(self) -> bool:
        return self.ndim <= 2

    def to_histogram(self, *, bins: int = 50) -> hist.Hist[Any]:  # noqa: ARG002
        histogram: hist.Hist[Any] = self.item.to_hist()
        return histogram

    def dump_hist(self, *, width: int = 100) -> str:  # noqa: ARG002
        return "h = item.to_hist()"


class Column(Plottable):
    """A leaf that reads as an array: a branch, a field, a variable."""

    @property
    @abstractmethod
    def numeric(self) -> bool:
        """Does :meth:`read` give numbers (so it can be one axis of a 2D plot)?"""

    @property
    @abstractmethod
    def entry_count(self) -> int: ...

    @property
    @abstractmethod
    def typename(self) -> str: ...

    @abstractmethod
    def read(self) -> Any:
        """The values, as a numpy or awkward array."""

    @abstractmethod
    def read_source(self, var: str) -> str:
        """Source for :meth:`read` applied to the object bound to ``var``."""

    @property
    def plottable(self) -> bool:
        return self.numeric

    def to_histogram(self, *, bins: int = 50) -> hist.Hist[Any]:
        if not self.numeric:
            msg = f"{self.name} ({self.typename}) contains values that cannot be plotted"
            raise TypeError(msg)
        return fill_finite(self.read(), bins=bins, empty_msg=f"{self.name} is empty.")

    def dump_hist(self, *, width: int = 100) -> str:
        return textwrap.dedent(f"""\
            import awkward as ak
            import hist
            import numpy as np
            array = {self.read_source("item")}
            values = ak.ravel(array)
            finite = values[np.isfinite(values)]
            h = hist.numpy.histogram(finite, bins={width}, histogram=hist.Hist)""")


class Pair(Plottable):
    """Two columns filled together into a 2D histogram (x, y)."""

    def __init__(self, x: Column, y: Column) -> None:
        super().__init__((x.item, y.item))
        self.x = x
        self.y = y

    @property
    def name(self) -> str:
        return f"{self.y.name} vs {self.x.name}"

    @property
    def ndim(self) -> int:
        return 2

    @property
    def plottable(self) -> bool:
        return self.x.numeric and self.y.numeric

    def meta(self) -> MetaDict:
        return MetaDict(label_icon="📊 ", label_text=Text(self.name, style="bold"))

    def data_tree(self) -> DataTree | None:
        return self.x.data_tree()

    def data_tree_source(
        self, var: str = "item", file_var: str = "uproot_file"
    ) -> str | None:
        return self.x.data_tree_source(f"x_{var}", file_var)

    def to_histogram(self, *, bins: int = 50) -> hist.Hist[Any]:
        for column in (self.x, self.y):
            if not column.numeric:
                msg = f"{column.name} ({column.typename}) does not hold numbers for a 2D plot"
                raise TypeError(msg)
        x_entries, y_entries = self.x.entry_count, self.y.entry_count
        if x_entries != y_entries:
            msg = f"{self.x.name} has {x_entries} entries, but {self.y.name} has {y_entries}"
            raise ValueError(msg)
        # A per-entry value broadcasts against a per-item (jagged) value
        x_array, y_array = ak.broadcast_arrays(self.x.read(), self.y.read())
        x = np.asarray(ak.ravel(x_array), dtype=float)
        y = np.asarray(ak.ravel(y_array), dtype=float)
        finite = np.isfinite(x) & np.isfinite(y)
        if not np.any(finite):
            msg = f"{self.name} has no finite values."
            raise EmptyTreeError(msg)
        filled: hist.Hist[Any] = hist.numpy.histogram2d(
            x[finite], y[finite], bins=bins, histogram=hist.Hist
        )
        filled.axes[0].label = self.x.name
        filled.axes[1].label = self.y.name
        return filled

    def dump_hist(self, *, width: int = 100) -> str:
        """Source using the columns bound to ``x_item`` and ``y_item``."""
        x_source = self.x.read_source("x_item")
        y_source = self.y.read_source("y_item")
        return textwrap.dedent(f"""\
            import awkward as ak
            import hist
            import numpy as np
            x, y = ak.broadcast_arrays({x_source}, {y_source})
            x = np.asarray(ak.ravel(x), dtype=float)
            y = np.asarray(ak.ravel(y), dtype=float)
            finite = np.isfinite(x) & np.isfinite(y)
            h = hist.numpy.histogram2d(x[finite], y[finite], bins={width}, histogram=hist.Hist)
            h.axes[0].label = x_item.name
            h.axes[1].label = y_item.name""")

    def title_source(self, var: str = "item") -> str:
        return f'f"{{y_{var}.name}} vs {{x_{var}.name}} -- Entries: {{np.sum(h.counts()):g}}"'


@dataclasses.dataclass(eq=False)
class FailedNode(Node):
    """A key whose object could not be read (e.g. unsupported RooFit classes)."""

    exception: Exception = dataclasses.field(kw_only=True)
    classname: str = dataclasses.field(default="", kw_only=True)

    def meta(self) -> MetaDict:
        return failed_meta(self.name, self.classname, self.exception)


def failed_meta(name: str, classname: str, exception: Exception) -> MetaDict:
    """Meta for an entry that failed to load: name, type, and the error class."""
    label_text = Text.assemble(
        (f"{name} ", "bold"),
        (f"{classname} ", "italic") if classname else "",
        (f"({exception.__class__.__name__})", "red"),
    )
    return MetaDict(label_icon="‼️ ", label_text=label_text)


def path_meta(path: Path, icon: str) -> MetaDict:
    """Meta for a local file or directory: its name, linked to the path."""
    return MetaDict(
        label_icon=icon,
        label_text=Text(path.name, style=Style(link=f"file://{path.resolve()}")),
        guide_style="bold bright_blue",
    )


def _flatten_object_array(array: Any) -> Any:
    """Flatten the object array uproot gives for a jagged branch with library="np".

    Concatenating the inner arrays is much faster than ``ak.from_iter``, which
    stays as the fallback for deeper nesting.
    """
    flat = np.concatenate([np.ravel(x) for x in array]) if len(array) else array
    return ak.from_iter(array) if flat.dtype == object else flat


def fill_finite(array: Any, *, bins: int, empty_msg: str) -> hist.Hist[Any]:
    """Flatten ``array``, drop non-finite values, and fill a regular histogram."""
    if isinstance(array, np.ndarray) and array.dtype == object:
        array = _flatten_object_array(array)
    values = ak.ravel(array)
    # pylint: disable-next=unsubscriptable-object  # ak.ravel return is opaque to pylint
    finite = values[np.isfinite(values)]
    if len(finite) < 1:
        raise EmptyTreeError(empty_msg)
    filled: hist.Hist[Any] = hist.numpy.histogram(
        finite, bins=bins, histogram=hist.Hist
    )
    return filled
