"""
Compatibility layer supporting both plotext 5.2.8+ (module-level API) and
plotext 6+ (figure-object API).

The rest of the codebase draws only through the small ``PlotextFigure``
protocol; ``make_figure`` picks the implementation for the installed plotext.
"""

# The plotext 5 branch uses names that don't exist in the installed plotext 6
# pylint: disable=no-member,no-name-in-module

from __future__ import annotations

import importlib.metadata
from typing import Any, Protocol

import plotext as plt

__all__ = ["PLOTEXT_6", "PlotextFigure", "add_theme", "make_figure"]

# plotext 6 introduced the module-level master figure object
PLOTEXT_6 = hasattr(plt, "figure")


def __dir__() -> list[str]:
    return __all__


class PlotextFigure(Protocol):
    """The subset of plotting operations used by uproot-browser."""

    def clear(self) -> None: ...
    def theme(self, name: str) -> None: ...
    def plot_size(self, width: int, height: int) -> None: ...
    def bar(self, x: Any, y: Any) -> None: ...
    def heatmap(self, data: list[list[float]]) -> None: ...
    def ylim(self, lower: float | None = None, upper: float | None = None) -> None: ...
    def xticks(self, positions: Any, labels: list[str] | None = None) -> None: ...
    def yticks(self, positions: Any, labels: list[str] | None = None) -> None: ...
    def xlabel(self, label: str) -> None: ...
    def ylabel(self, label: str) -> None: ...
    def title(self, label: str) -> None: ...
    def build(self) -> str: ...
    def show(self) -> None: ...


class _Figure6:
    """Wraps the plotext 6 figure-object API."""

    def __init__(self) -> None:
        self._fig = plt.figure

    def clear(self) -> None:
        self._fig.clear()

    def theme(self, name: str) -> None:
        self._fig.theme(name)

    def plot_size(self, width: int, height: int) -> None:
        self._fig.plot_size(width, height)

    def bar(self, x: Any, y: Any) -> None:
        self._fig.draw(self._fig.bar(x, y))

    def heatmap(self, data: list[list[float]]) -> None:
        self._fig.draw(self._fig.heatmap(data, map="viridis", fill=True))

    def ylim(self, lower: float | None = None, upper: float | None = None) -> None:
        self._fig.ruler("y").lim(lower=lower, upper=upper)

    def xticks(self, positions: Any, labels: list[str] | None = None) -> None:
        self._fig.ruler("x").ticks(positions, labels)

    def yticks(self, positions: Any, labels: list[str] | None = None) -> None:
        self._fig.ruler("y").ticks(positions, labels)

    def xlabel(self, label: str) -> None:
        self._fig.label(label, axis="x")

    def ylabel(self, label: str) -> None:
        self._fig.label(label, axis="y")

    def title(self, label: str) -> None:
        self._fig.title(label)

    def build(self) -> str:
        return str(self._fig.build())

    def show(self) -> None:
        self._fig.show()


class _Figure5:
    """Wraps the plotext 5 module-level API."""

    def clear(self) -> None:
        plt.clf()

    def theme(self, name: str) -> None:
        plt.theme(name)

    def plot_size(self, width: int, height: int) -> None:
        plt.plotsize(width, height)

    def bar(self, x: Any, y: Any) -> None:
        plt.bar(x, y)

    def heatmap(self, data: list[list[float]]) -> None:  # noqa: ARG002
        version = importlib.metadata.version("plotext")
        msg = f"2D histograms require plotext 6 or newer (you have plotext {version})"
        raise RuntimeError(msg)

    def ylim(self, lower: float | None = None, upper: float | None = None) -> None:
        plt.ylim(lower, upper)

    def xticks(self, positions: Any, labels: list[str] | None = None) -> None:
        plt.xticks(positions, labels)

    def yticks(self, positions: Any, labels: list[str] | None = None) -> None:
        plt.yticks(positions, labels)

    def xlabel(self, label: str) -> None:
        plt.xlabel(label)

    def ylabel(self, label: str) -> None:
        plt.ylabel(label)

    def title(self, label: str) -> None:
        plt.title(label)

    def build(self) -> str:
        return str(plt.build())

    def show(self) -> None:
        plt.show()


def make_figure() -> PlotextFigure:
    """The figure for the installed plotext version (a shared global in both)."""
    return _Figure6() if PLOTEXT_6 else _Figure5()


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
        from plotext import _dict

        # [canvas, axes, ticks color, ticks style, color sequence]
        sequence = list(_dict.themes["default"][4])
        _dict.themes[name] = [canvas, canvas, text[0], "default", sequence]
