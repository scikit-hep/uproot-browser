"""
Compatibility layer supporting both plotext 5.2.8+ (module-level API) and
plotext 6+ (figure-object API).

The rest of the codebase draws only through the ``PlotextFigure`` protocol,
which is the subset of the native plotext 6 figure API that uproot-browser
uses. On plotext 6, ``make_figure`` returns the native figure directly; on
plotext 5, it returns an adaptor over the module-level functions.
"""

# The plotext 5 branch uses names that don't exist in the installed plotext 6
# pylint: disable=no-member,no-name-in-module

from __future__ import annotations

import importlib.metadata
from typing import Any, Protocol, cast

import plotext as plt

__all__ = ["PLOTEXT_6", "PlotextFigure", "add_theme", "make_figure"]

# plotext 6 introduced the module-level master figure object
PLOTEXT_6 = hasattr(plt, "figure")


def __dir__() -> list[str]:
    return __all__


class PlotextRuler(Protocol):
    """One axis of a figure (the plotext 6 ``ruler`` object)."""

    def ticks(self, positions: Any = None, labels: list[str] | None = None) -> Any: ...
    def lim(self, lower: float | None = None, upper: float | None = None) -> Any: ...


class PlotextFigure(Protocol):
    """The subset of the plotext 6 figure API used by uproot-browser."""

    def clear(self) -> Any: ...
    def theme(self, name: str) -> Any: ...
    def plot_size(self, width: int, height: int) -> Any: ...
    def bar(self, x: Any, y: Any) -> Any: ...
    def heatmap(self, data: Any, *, map: str = "gray", fill: bool = False) -> Any: ...  # noqa: A002
    def ruler(self, axis: str) -> PlotextRuler: ...
    def label(self, label: str, axis: str) -> Any: ...
    def title(self, label: str) -> Any: ...
    def build(self) -> Any: ...
    def show(self) -> Any: ...


class _Ruler5:
    """Maps the plotext 6 ruler methods onto the plotext 5 axis functions."""

    def __init__(self, axis: str) -> None:
        self._axis = axis

    def ticks(self, positions: Any = None, labels: list[str] | None = None) -> None:
        if self._axis == "x":
            plt.xticks(positions, labels)
        else:
            plt.yticks(positions, labels)

    def lim(self, lower: float | None = None, upper: float | None = None) -> None:
        if self._axis == "x":
            plt.xlim(lower, upper)
        else:
            plt.ylim(lower, upper)


class _Figure5:
    """Presents the plotext 5 module-level API with the figure-object shape."""

    def clear(self) -> None:
        plt.clf()

    def theme(self, name: str) -> None:
        plt.theme(name)

    def plot_size(self, width: int, height: int) -> None:
        plt.plotsize(width, height)

    def bar(self, x: Any, y: Any) -> None:
        plt.bar(x, y)

    def heatmap(self, data: Any, *, map: str = "gray", fill: bool = False) -> None:  # noqa: A002, ARG002
        version = importlib.metadata.version("plotext")
        msg = f"2D histograms require plotext 6 or newer (you have plotext {version})"
        raise RuntimeError(msg)

    def ruler(self, axis: str) -> PlotextRuler:
        return _Ruler5(axis)

    def label(self, label: str, axis: str) -> None:
        if axis == "x":
            plt.xlabel(label)
        else:
            plt.ylabel(label)

    def title(self, label: str) -> None:
        plt.title(label)

    def build(self) -> str:
        return str(plt.build())

    def show(self) -> None:
        plt.show()


def make_figure() -> PlotextFigure:
    """The figure for the installed plotext version (a shared global in both)."""
    if PLOTEXT_6:
        return cast("PlotextFigure", plt.figure)
    return _Figure5()


def add_theme(
    name: str,
    *,
    canvas: tuple[int, int, int],
    text: tuple[tuple[int, int, int], tuple[int, int, int]],
) -> None:
    """Register a plotext theme with a canvas color and (fg, bg) text colors."""
    if PLOTEXT_6:
        plt.add_theme(name, canvas=canvas, text=text)
    else:
        from plotext import _dict  # noqa: PLC0415  # only importable on plotext 5

        # [canvas, axes, ticks color, ticks style, color sequence]
        sequence = list(_dict.themes["default"][4])
        _dict.themes[name] = [canvas, canvas, text[0], "default", sequence]
