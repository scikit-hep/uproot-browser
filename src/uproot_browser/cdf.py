"""
CDF (NASA Common Data Format) support through cdflib and xarray.

Importing this module registers the xarray Dataset/DataArray types with the
tree and plot dispatchers. It needs the [cdf] extra, so import it only when
a CDF file is opened (see :mod:`uproot_browser.files`).
"""

from __future__ import annotations

__lazy_modules__ = {
    "cdflib",
    "cdflib.xarray",
    "logging",
    "numpy",
    "pathlib",
    "rich",
    "rich.style",
    "rich.text",
    "textwrap",
    "typing",
    "xarray",
}

import logging
import textwrap
from pathlib import Path
from typing import Any, Literal

import cdflib.xarray
import numpy as np
import xarray as xr  # noqa: TC002 (singledispatch reads annotations)
from rich.style import Style
from rich.text import Text

import uproot_browser.plot
import uproot_browser.tree
from uproot_browser.tree import MetaDict

__all__ = ("open_cdf", "open_cdf_source")


def __dir__() -> tuple[str, ...]:
    return __all__


# cdf_to_xarray keyword arguments; also written into the Dump & Quit source
_READ_OPTIONS = {"to_datetime": True, "fillval_to_nan": True}


def open_cdf(path: str) -> xr.Dataset:
    """Read a CDF file into an xarray Dataset, remembering its source path."""
    logger = logging.getLogger("cdflib")
    level = logger.level
    # cdflib logs every ISTP compliance deviation, which would land on the terminal
    logger.setLevel(logging.ERROR)
    try:
        dataset: xr.Dataset = cdflib.xarray.cdf_to_xarray(path, **_READ_OPTIONS)
    finally:
        logger.setLevel(level)
    dataset.encoding["source"] = str(Path(path).resolve())
    return dataset


def open_cdf_source(path: str) -> str:
    options = ", ".join(f"{k}={v!r}" for k, v in _READ_OPTIONS.items())
    return f"import cdflib.xarray\nuproot_file = cdflib.xarray.cdf_to_xarray({path!r}, {options})"


# Tree


@uproot_browser.tree.is_dir.register
def _(item: xr.Dataset) -> Literal[True]:  # noqa: ARG001
    return True


@uproot_browser.tree.get_children.register
def _(item: xr.Dataset) -> set[str]:
    return {str(key) for key in item.variables}


@uproot_browser.tree.source_path.register
def _(item: xr.Dataset) -> str:
    return str(item.encoding.get("source", ""))


@uproot_browser.tree.lookup.register
def _(item: xr.Dataset, key: str) -> Any:
    return item[key.strip("/")]


@uproot_browser.tree.process_item.register
def _(item: xr.Dataset) -> MetaDict:
    path = Path(uproot_browser.tree.source_path(item))
    label_text = Text(path.name, style=Style(link=f"file://{path}"))
    return MetaDict(
        label_icon="📁 ", label_text=label_text, guide_style="bold bright_blue"
    )


@uproot_browser.tree.process_item.register
def _(item: xr.DataArray) -> MetaDict:
    icon = "📏 " if item.name in item.coords else "🔢 "
    sizes = ", ".join(f"{dim}: {size}" for dim, size in item.sizes.items())
    label_text = Text.assemble(
        (f"{item.name} ", "bold"),
        (f"{item.dtype} ", "italic"),
        f"({sizes})",
    )
    return MetaDict(label_icon=icon, label_text=label_text)


# Plot


def _numeric(item: xr.DataArray) -> bool:
    return item.dtype.kind in "biuf"


@uproot_browser.plot.plottable.register
@uproot_browser.plot.array_plottable.register
def _(item: xr.DataArray) -> bool:
    return _numeric(item)


# cdf_to_xarray turns float fill values into NaN, but leaves integer ones
_FILL_TO_NAN = 'np.where({var}.values.ravel() == {var}.attrs.get("FILLVAL"), np.nan, {var}.values.ravel())'


@uproot_browser.plot.read_array.register
def _(item: xr.DataArray) -> Any:
    values = np.asarray(item.values).ravel()
    return np.where(values == item.attrs.get("FILLVAL"), np.nan, values)


@uproot_browser.plot.array_source.register
def _(item: xr.DataArray, var: str) -> str:  # noqa: ARG001
    return _FILL_TO_NAN.format(var=var)


@uproot_browser.plot.to_histogram.register
def _(item: xr.DataArray, *, bins: int = 50) -> Any:
    if not _numeric(item):
        msg = f"Variable {item.name} ({item.dtype}) contains values that cannot be plotted"
        raise TypeError(msg)
    return uproot_browser.plot.fill_finite(
        uproot_browser.plot.read_array(item),
        bins=bins,
        empty_msg=f"Variable {item.name} has no finite values.",
    )


@uproot_browser.plot.dump.register
def _(item: xr.DataArray, *, width: int = 100) -> str:  # noqa: ARG001
    return textwrap.dedent(f"""\
        import hist
        import numpy as np
        values = {_FILL_TO_NAN.format(var="item")}
        finite = values[np.isfinite(values)]
        h = hist.numpy.histogram(finite, bins={width}, histogram=hist.Hist)""")
