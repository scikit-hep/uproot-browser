"""
The CDF backend: NASA Common Data Format files, read with cdflib into an
xarray Dataset (the [cdf] extra). Each variable is a column.
"""

from __future__ import annotations

__lazy_modules__ = {
    "logging",
    "numpy",
    "pathlib",
    "rich.text",
    "uproot_browser.backends",
}

import dataclasses
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
from rich.text import Text

from uproot_browser.backends import select_key, split_spec
from uproot_browser.nodes import Column, Folder, MetaDict, Node, Root, path_meta

if TYPE_CHECKING:
    import xarray as xr

__all__ = ("CdfFile", "CdfVariable", "matches", "open_spec")


def __dir__() -> tuple[str, ...]:
    return __all__


# cdf_to_xarray keyword arguments; also written into the Dump & Quit source
_READ_OPTIONS = {"to_datetime": True, "fillval_to_nan": True}


def matches(spec: str) -> bool:
    """A local ``.cdf`` file."""
    name, _ = split_spec(spec)
    return (
        "://" not in name
        and Path(name).suffix.lower() == ".cdf"
        and not Path(name).is_dir()
    )


def open_spec(spec: str, *, parent: Folder | None = None, key: str = "") -> Node:
    """Open a file; a ``path:variable`` spec gives that variable."""
    import cdflib.xarray  # noqa: PLC0415

    name, var = split_spec(spec)
    logger = logging.getLogger("cdflib")
    level = logger.level
    # cdflib logs every ISTP compliance deviation, which would land on the terminal
    logger.setLevel(logging.ERROR)
    try:
        dataset = cdflib.xarray.cdf_to_xarray(name, **_READ_OPTIONS)
    finally:
        logger.setLevel(level)
    return select_key(CdfFile(dataset, parent, key, spec=name), var)


@dataclasses.dataclass(eq=False)
class CdfFile(Root, Folder):
    """The Dataset a file was read into."""

    spec: str = dataclasses.field(kw_only=True)

    @property
    def name(self) -> str:
        return Path(self.spec).name

    def keys(self) -> list[str]:
        return [str(key) for key in self.item.variables]

    def lookup(self, key: str) -> Node:
        return CdfVariable(self.item[key], self, key)

    def meta(self) -> MetaDict:
        return path_meta(self.spec, "📁 ")

    def open_source(self, var: str) -> str:
        options = ", ".join(f"{k}={v!r}" for k, v in _READ_OPTIONS.items())
        return f"import cdflib.xarray\n{var} = cdflib.xarray.cdf_to_xarray({self.spec!r}, {options})"

    def close(self) -> None:
        self.item.close()


class CdfVariable(Column):
    """
    A variable (a DataArray). cdf_to_xarray turns float fill values into NaN;
    integer ``FILLVAL`` entries become NaN when read.
    """

    item: xr.DataArray

    @property
    def name(self) -> str:
        return str(self.item.name)

    @property
    def numeric(self) -> bool:
        return self.item.dtype.kind in "biuf"

    @property
    def entry_count(self) -> int:
        return int(self.item.shape[0]) if self.item.ndim else 1

    @property
    def typename(self) -> str:
        return str(self.item.dtype)

    def read(self) -> Any:
        values = self.item.values
        return np.where(values == self.item.attrs.get("FILLVAL"), np.nan, values)

    def read_source(self, var: str) -> str:
        return f'np.where({var}.values == {var}.attrs.get("FILLVAL"), np.nan, {var}.values)'

    def meta(self) -> MetaDict:
        icon = "📏 " if self.item.name in self.item.coords else "🔢 "
        sizes = ", ".join(f"{dim}: {size}" for dim, size in self.item.sizes.items())
        label_text = Text.assemble(
            (f"{self.name} ", "bold"), (f"{self.typename} ", "italic"), f"({sizes})"
        )
        return MetaDict(label_icon=icon, label_text=label_text)
