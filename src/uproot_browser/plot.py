"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

__lazy_modules__ = {
    "awkward",
    "hist",
    "math",
    "numpy",
    "operator",
    "textwrap",
    "uproot.interpretation",
    "uproot.interpretation.jagged",
    "uproot.interpretation.numerical",
    "uproot.interpretation.objects",
    "uproot.model",
    "uproot_browser.exceptions",
}

import functools
import math
import operator
import textwrap
from typing import TYPE_CHECKING, Any, cast

import awkward as ak
import hist
import numpy as np
import uproot
import uproot.behaviors.TH1
import uproot.interpretation.jagged
import uproot.interpretation.numerical
import uproot.interpretation.objects
import uproot.model
import uproot.models.RNTuple

from uproot_browser.exceptions import EmptyTreeError

if TYPE_CHECKING:
    from uproot_browser.plotext_compat import PlotextFigure


def make_hist_title(item: Any, histogram: hist.Hist[Any]) -> str:
    # counts() equals values() for plain storage, but gives the entry count for
    # Mean storage (TProfile) and the effective entries for Weight storage.
    inner_sum = float(np.sum(histogram.counts()))
    full_sum = float(np.sum(histogram.counts(flow=True)))

    if math.isclose(inner_sum, full_sum):
        return f"{item.name} -- Entries: {inner_sum:g}"

    return f"{item.name} -- Entries: {inner_sum:g} ({full_sum:g} with flow)"


@functools.singledispatch
def to_histogram(tree: Any, *, bins: int = 50) -> hist.Hist[Any]:  # noqa: ARG001
    """
    Build the histogram that :func:`plot` draws for this object.
    Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


# Simpler in Python 3.11+
@to_histogram.register(uproot.TBranch)
def branch_hist(
    tree: uproot.TBranch | uproot.models.RNTuple.RField, *, bins: int = 50
) -> hist.Hist[Any]:
    """
    Build a histogram from a branch/field. Branches holding TH1 objects are
    summed; numeric arrays are flattened, filtered to finite values, and filled.
    """
    # RField has no `interpretation`; it is always read as an array.
    interpretation = getattr(tree, "interpretation", None)
    if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
        arr = tree.array(library="np")
        if len(arr) == 0:
            msg = f"Branch {tree.name} is empty."
            raise EmptyTreeError(msg)
        if not isinstance(arr[0], uproot.behaviors.TH1.Histogram):
            msg = f"Branch {tree.name} ({tree.typename}) contains objects that cannot be plotted"
            raise TypeError(msg)
        histogram: hist.Hist[Any] = functools.reduce(
            operator.add, (h.to_hist() for h in arr)
        )
        return histogram
    array = tree.array()
    values = ak.ravel(array)
    # pylint: disable-next=unsubscriptable-object  # ak.ravel return is opaque to pylint
    finite = values[np.isfinite(values)]
    if len(finite) < 1:
        msg = f"Branch {tree.name} is empty."
        raise EmptyTreeError(msg)
    filled: hist.Hist[Any] = hist.numpy.histogram(
        finite, bins=bins, histogram=hist.Hist
    )
    return filled


def field_hist(tree: uproot.models.RNTuple.RField, *, bins: int = 50) -> hist.Hist[Any]:
    """
    Build a histogram from an RNTuple field. Only numeric values can be filled.
    """
    if not _field_plottable(tree):
        msg = f"Field {tree.name} ({tree.typename}) contains values that cannot be plotted"
        raise TypeError(msg)
    filled: hist.Hist[Any] = branch_hist(tree, bins=bins)
    return filled


to_histogram.register(uproot.models.RNTuple.RField)(field_hist)  # type: ignore[no-untyped-call]


# Explicit type: inferring it evaluates the hist.Hist[Any] annotation at
# runtime, which the minimum hist version cannot subscript.
@to_histogram.register(uproot.behaviors.TH1.Histogram)
def _hist_to_histogram(
    tree: uproot.behaviors.TH1.Histogram,
    *,
    bins: int = 50,  # noqa: ARG001
) -> hist.Hist[Any]:
    # to_hist() is already a hist.Hist; uproot's untyped stub loses that for mypy.
    return cast("hist.Hist[Any]", tree.to_hist())


def apply_expr(histogram: hist.Hist[Any], expr: str) -> hist.Hist[Any]:
    """Evaluate the slice expression with the histogram bound to ``h``."""
    if expr:
        # pylint: disable-next=eval-used
        histogram = eval(expr, {"h": histogram})
    return histogram


def _bin_ticks(axis: Any, count: int = 5) -> tuple[list[int], list[str]]:
    positions = np.unique(
        np.linspace(0, len(axis) - 1, min(count, len(axis))).round().astype(int)
    )
    return positions.tolist(), [f"{axis.centers[i]:g}" for i in positions]


def _draw_hist_2d(fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any]) -> None:
    xaxis, yaxis = histogram.axes
    values = histogram.values().astype(float)
    # heatmap rows draw top-to-bottom; flip so y increases upward
    fig.draw(fig.heatmap(values.T[::-1].tolist(), map="viridis", fill=True))
    fig.ruler("x").ticks(*_bin_ticks(xaxis))
    fig.ruler("y").ticks(*_bin_ticks(yaxis))
    fig.label(xaxis.name, axis="x")
    fig.label(yaxis.name, axis="y")
    fig.title(make_hist_title(tree, histogram))


def _collapses_in_float32(lower: float, upper: float) -> bool:
    """Is the range too narrow to survive plotext's internal float32 rescale?"""
    with np.errstate(over="ignore"):
        low32, high32 = np.float32(lower), np.float32(upper)
    return bool(low32 == high32 or not np.isfinite(low32) or not np.isfinite(high32))


def _draw_hist_1d(fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any]) -> None:
    axis = histogram.axes[0]
    values = histogram.values().astype(float)
    if _collapses_in_float32(axis.edges[0], axis.edges[-1]):
        # Positions rescale to NaN in float32; draw against bin indices instead
        # and put the real values in the tick labels.
        fig.draw(fig.bar(np.arange(len(axis)).tolist(), values))
        fig.ruler("x").ticks(*_bin_ticks(axis))
    else:
        fig.draw(fig.bar(axis.centers, values))
        fig.ruler("x").ticks(np.linspace(axis.edges[0], axis.edges[-1], 5))
    fig.ruler("y").lim(lower=0)
    fig.label(axis.name, axis="x")
    fig.title(make_hist_title(tree, histogram))


def _draw_hist(fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any]) -> None:
    match len(histogram.axes):
        case 1:
            _draw_hist_1d(fig, tree, histogram)
        case 2:
            _draw_hist_2d(fig, tree, histogram)
        case ndim:
            msg = f"Histograms with {ndim} dimensions are not plottable; reduce to 1 or 2 first"
            raise RuntimeError(msg)


def plot(tree: Any, *, fig: PlotextFigure, width: int = 100, expr: str = "") -> None:
    """
    Plot ``tree`` into the given plotext figure.
    Support new types by registering a :func:`to_histogram` overload.
    """
    histogram = to_histogram(tree, bins=width)
    _draw_hist(fig, tree, apply_expr(histogram, expr))


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


def _branch_plottable(branch: uproot.TBranch) -> bool:
    interpretation = branch.interpretation
    if isinstance(interpretation, uproot.interpretation.jagged.AsJagged):
        interpretation = interpretation.content
    match interpretation:
        case uproot.interpretation.objects.AsObjects(model=model):
            return _model_is_histogram(model)
        # AsStridedObjects is a Numerical, but yields records np.isfinite rejects
        case uproot.interpretation.objects.AsStridedObjects():
            return False
        case uproot.interpretation.numerical.Numerical():
            return True
        case _:
            return False


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


def plottable(item: Any) -> bool:
    """
    True if :func:`plot` has an implementation for this object that can
    succeed. Some failures (like an empty branch) are only found by reading
    the data, so this is a necessary but not sufficient check.
    """
    if isinstance(item, uproot.behaviors.TH1.Histogram):
        return len(item.axes) <= 2
    if isinstance(item, uproot.TBranch):
        return _branch_plottable(item)
    if isinstance(item, uproot.models.RNTuple.RField):
        return _field_plottable(item)
    return to_histogram.dispatch(type(item)) is not to_histogram.dispatch(object)


@functools.singledispatch
def dump(tree: Any, *, width: int = 100) -> str:  # noqa: ARG001
    """
    Return standalone Python source that rebuilds the plotted histogram as ``h``
    from an object bound to ``item``. Mirrors :func:`plot` for the "Dump & Quit"
    output. Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


# Simpler in Python 3.11+
@dump.register(uproot.TBranch)
def dump_branch(
    tree: uproot.TBranch | uproot.models.RNTuple.RField,
    *,
    width: int = 100,
) -> str:
    """
    Source for rebuilding a single tree branch as a histogram.
    """
    # RField has no `interpretation`; it is always read as an array.
    interpretation = getattr(tree, "interpretation", None)
    if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
        return textwrap.dedent("""\
            import functools
            import operator
            arr = item.array(library="np")
            h = functools.reduce(operator.add, [x.to_hist() for x in arr])""")
    return textwrap.dedent(f"""\
        import awkward as ak
        import hist
        import numpy as np
        array = item.array()
        values = ak.ravel(array)
        finite = values[np.isfinite(values)]
        h = hist.numpy.histogram(finite, bins={width}, histogram=hist.Hist)""")


dump.register(uproot.models.RNTuple.RField)(dump_branch)  # type: ignore[no-untyped-call]


@dump.register
def dump_hist(
    tree: uproot.behaviors.TH1.Histogram,  # noqa: ARG001
    *,
    width: int = 100,  # noqa: ARG001
) -> str:
    """
    Source for rebuilding a 1-D histogram.
    """
    return "h = item.to_hist()"
