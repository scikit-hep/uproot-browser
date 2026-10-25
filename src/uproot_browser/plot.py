"""
Display tools for making plots via plotext.
"""

from __future__ import annotations

__lazy_modules__ = {
    "ast",
    "awkward",
    "boost_histogram",
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

import ast
import dataclasses
import functools
import math
import operator
import textwrap
from typing import TYPE_CHECKING, Any, cast

import awkward as ak
import boost_histogram as bh
import hist
import numpy as np
import uproot
import uproot.behaviors.RNTuple
import uproot.behaviors.TBranch
import uproot.behaviors.TH1
import uproot.interpretation.jagged
import uproot.interpretation.numerical
import uproot.interpretation.objects
import uproot.model
import uproot.models.RNTuple

from uproot_browser.axis import NO_LIMITS, AxisLimits, AxisRange
from uproot_browser.exceptions import EmptyTreeError, ExpressionError
from uproot_browser.plotext_compat import PLOTEXT_6

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
    return fill_finite(
        tree.array(), bins=bins, empty_msg=f"Branch {tree.name} is empty."
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


@dataclasses.dataclass(frozen=True, slots=True)
class BranchPair:
    """Two branches/fields filled together into a 2D histogram (x, y)."""

    x: Any
    y: Any

    @property
    def name(self) -> str:
        return f"{self.y.name} vs {self.x.name}"


@functools.singledispatch
def read_array(item: Any) -> Any:
    """Read the values of an array-like item (branch, field, variable)."""
    return item.array()


@functools.singledispatch
def array_source(item: Any, var: str) -> str:  # noqa: ARG001
    """Source for :func:`read_array` applied to the object bound to ``var``."""
    return f"{var}.array()"


def entry_count(item: Any) -> int:
    """The number of entries of an array-like item, without reading it."""
    count = getattr(item, "num_entries", None)
    return len(item) if count is None else int(count)


def typename(item: Any) -> str:
    """The type of an array-like item: a C++ typename or a numpy dtype."""
    return str(getattr(item, "typename", None) or item.dtype)


@to_histogram.register(BranchPair)
def _pair_hist(pair: BranchPair, *, bins: int = 50) -> hist.Hist[Any]:
    for item in (pair.x, pair.y):
        if not array_plottable(item):
            msg = f"{item.name} ({typename(item)}) does not hold numbers for a 2D plot"
            raise TypeError(msg)
    x_entries, y_entries = entry_count(pair.x), entry_count(pair.y)
    if x_entries != y_entries:
        msg = (
            f"{pair.x.name} has {x_entries} entries, but {pair.y.name} has {y_entries}"
        )
        raise ValueError(msg)
    # A per-entry value broadcasts against a per-item (jagged) value
    x_array, y_array = ak.broadcast_arrays(read_array(pair.x), read_array(pair.y))
    x = np.asarray(ak.ravel(x_array), dtype=float)
    y = np.asarray(ak.ravel(y_array), dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if not np.any(finite):
        msg = f"{pair.name} has no finite values."
        raise EmptyTreeError(msg)
    filled: hist.Hist[Any] = hist.numpy.histogram2d(
        x[finite], y[finite], bins=bins, histogram=hist.Hist
    )
    filled.axes[0].label = pair.x.name
    filled.axes[1].label = pair.y.name
    return filled


@functools.singledispatch
def containing_tree(item: Any) -> Any:  # noqa: ARG001
    """The TTree/RNTuple that ``item`` lives in (itself, if it is one), else None."""
    return None


@containing_tree.register(uproot.behaviors.TBranch.HasBranches)
def _branch_tree(item: uproot.behaviors.TBranch.HasBranches) -> Any:
    return item.tree


@containing_tree.register(uproot.behaviors.RNTuple.HasFields)
def _field_tree(item: uproot.behaviors.RNTuple.HasFields) -> Any:
    return item.ntuple


@containing_tree.register(BranchPair)
def _pair_tree(item: BranchPair) -> Any:
    return containing_tree(item.x)


@functools.singledispatch
def containing_tree_source(item: Any) -> str | None:  # noqa: ARG001
    """Source for :func:`containing_tree` applied to ``item``, or None."""
    return None


@containing_tree_source.register(uproot.behaviors.TBranch.HasBranches)
def _branch_tree_source(item: uproot.behaviors.TBranch.HasBranches) -> str:  # noqa: ARG001
    return "item.tree"


@containing_tree_source.register(uproot.behaviors.RNTuple.HasFields)
def _field_tree_source(item: uproot.behaviors.RNTuple.HasFields) -> str:  # noqa: ARG001
    return "item.ntuple"


@containing_tree_source.register(BranchPair)
def _pair_tree_source(item: BranchPair) -> str | None:
    source = containing_tree_source(item.x)
    return None if source is None else f"x_{source}"


@dataclasses.dataclass(slots=True)
class ExprCache:
    """One-slot cache of an expression's raw result, keyed on the expression.

    Plot items share one by reference across copies, so a redraw (resize,
    theme, limits) does not read the tree again. The single attribute keeps a
    write atomic for concurrent render workers.
    """

    entry: tuple[str, Any] | None = None


def _uses_h(expr: str) -> bool:
    """Does the expression read ``h``, which changes with the bin count?"""
    return any(
        isinstance(node, ast.Name) and node.id == "h"
        for node in ast.walk(ast.parse(expr, mode="eval"))
    )


def evaluate_expr(expr: str, namespace: dict[str, Any]) -> Any:
    # pylint: disable-next=eval-used
    return eval(expr, namespace)


def apply_expr(
    histogram: hist.Hist[Any], expr: str, item: Any, *, cache: ExprCache | None = None
) -> hist.Hist[Any]:
    """
    Evaluate with ``h`` as the histogram and ``tree`` as the containing
    TTree/RNTuple (only when there is one), using uproot's normal API, e.g.
    ``tree["fPx"].array()[tree["fPy"].array() < 0]``. An array result is
    histogrammed with the bin count of ``h``.

    With a ``cache``, the result of an expression that does not use ``h`` is
    kept and only rebinned on later calls.

    Any failure is raised as :class:`ExpressionError` from the original error.
    """
    if not expr:
        return histogram
    try:
        if cache is not None and cache.entry is not None and cache.entry[0] == expr:
            result = cache.entry[1]
        else:
            namespace = {"h": histogram, "ak": ak, "hist": hist, "np": np}
            tree = containing_tree(item)
            if tree is not None:
                namespace["tree"] = tree
            result = evaluate_expr(expr, namespace)
            if cache is not None and not _uses_h(expr):
                cache.entry = (expr, result)
        return _result_to_histogram(result, bins=len(histogram.axes[0]))
    except Exception as err:
        raise ExpressionError(str(err)) from err


def _result_to_histogram(result: Any, *, bins: int) -> hist.Hist[Any]:
    """Coerce an expression result into a hist.Hist. Mirrored in :func:`dump_expr`."""
    if hasattr(result, "to_hist"):
        result = result.to_hist()
    if isinstance(result, hist.Hist):
        return result
    if isinstance(result, bh.Histogram):
        return hist.Hist(result)
    if isinstance(result, (ak.Array, np.ndarray)):
        return fill_finite(
            result,
            bins=bins,
            empty_msg="Expression produced no finite values.",
        )
    msg = (
        "Expression must produce a hist.Hist or an awkward/numpy array, "
        f"got {type(result).__name__}."
    )
    raise RuntimeError(msg)


def dump_expr(item: Any, expr: str) -> str:
    """Self-contained source that applies ``expr`` to ``h`` like :func:`apply_expr`."""
    tree_source = containing_tree_source(item)
    tree_line = "" if tree_source is None else f"tree = {tree_source}\n\n"
    imports = textwrap.dedent("""\
        import awkward as ak
        import boost_histogram as bh
        import hist
        import numpy as np

        """)
    body = textwrap.dedent(f"""\
        result = {expr}
        if hasattr(result, "to_hist"):
            result = result.to_hist()
        if isinstance(result, bh.Histogram) and not isinstance(result, hist.Hist):
            result = hist.Hist(result)
        if isinstance(result, (ak.Array, np.ndarray)):
            if isinstance(result, np.ndarray) and result.dtype == object:
                flat = np.concatenate([np.ravel(x) for x in result]) if len(result) else result
                result = ak.from_iter(result) if flat.dtype == object else flat
            values = ak.ravel(result)
            finite = values[np.isfinite(values)]
            if len(finite) < 1:
                msg = "Expression produced no finite values."
                raise ValueError(msg)
            result = hist.numpy.histogram(finite, bins=len(h.axes[0]), histogram=hist.Hist)
        if not isinstance(result, hist.Hist):
            msg = f"Expression must produce a hist.Hist or an awkward/numpy array, got {{type(result).__name__}}."
            raise TypeError(msg)
        h = result""")
    return imports + tree_line + body


def _bin_ticks(
    axis: Any, visible: AxisRange = (None, None), count: int = 5
) -> tuple[list[int], list[str]]:
    """Tick positions (bin indices) and labels spread over the visible index range."""
    lower, upper = visible
    first = 0 if lower is None else max(0, math.ceil(lower))
    last = len(axis) - 1 if upper is None else min(len(axis) - 1, math.floor(upper))
    positions = np.unique(
        np.linspace(first, last, min(count, last - first + 1)).round().astype(int)
    )
    return positions.tolist(), [f"{axis.centers[i]:g}" for i in positions]


def _index_range(axis: Any, lim: AxisRange) -> AxisRange:
    """Map a data-unit range onto bin-index coordinates (bar i spans i±0.5)."""
    positions = np.arange(len(axis) + 1) - 0.5
    return tuple(  # type: ignore[return-value]
        None if v is None else float(np.interp(v, axis.edges, positions)) for v in lim
    )


def _set_lim(fig: PlotextFigure, axis: str, lim: AxisRange) -> None:
    # lim(None, None) would undo an earlier default, so only set typed limits
    if lim != (None, None):
        fig.ruler(axis).lim(*lim)


def _draw_hist_2d(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    xaxis, yaxis = histogram.axes
    values = histogram.values().astype(float)
    # heatmap rows draw top-to-bottom; flip so y increases upward
    fig.draw(fig.heatmap(values.T[::-1].tolist(), map="viridis", fill=True))
    # The heatmap draws against bin indices, so limits must be mapped too
    xlim, ylim = _index_range(xaxis, limits.x), _index_range(yaxis, limits.y)
    fig.ruler("x").ticks(*_bin_ticks(xaxis, xlim))
    fig.ruler("y").ticks(*_bin_ticks(yaxis, ylim))
    _set_lim(fig, "x", xlim)
    _set_lim(fig, "y", ylim)
    fig.label(xaxis.label, axis="x")
    fig.label(yaxis.label, axis="y")
    fig.title(make_hist_title(tree, histogram))


def _collapses_in_float32(lower: float, upper: float) -> bool:
    """Is the range too narrow to survive plotext's internal float32 rescale?"""
    with np.errstate(over="ignore"):
        low32, high32 = np.float32(lower), np.float32(upper)
    return bool(low32 == high32 or not np.isfinite(low32) or not np.isfinite(high32))


def _draw_hist_1d(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    axis = histogram.axes[0]
    values = histogram.values().astype(float)
    if _collapses_in_float32(axis.edges[0], axis.edges[-1]):
        # Positions rescale to NaN in float32; draw against bin indices instead
        # and put the real values in the tick labels.
        fig.draw(fig.bar(np.arange(len(axis)).tolist(), values))
        xlim = _index_range(axis, limits.x)
        fig.ruler("x").ticks(*_bin_ticks(axis, xlim))
        _set_lim(fig, "x", xlim)
    else:
        fig.draw(fig.bar(axis.centers, values))
        fig.ruler("x").ticks(np.linspace(axis.edges[0], axis.edges[-1], 5))
        _set_lim(fig, "x", limits.x)
    lower, upper = limits.y
    fig.ruler("y").lim(0 if lower is None else lower, upper)
    fig.label(axis.label, axis="x")
    fig.title(make_hist_title(tree, histogram))


def draw_hist(
    fig: PlotextFigure, tree: Any, histogram: hist.Hist[Any], *, limits: AxisLimits
) -> None:
    """Draw an already-built histogram into the figure, titled for ``tree``."""
    match len(histogram.axes):
        case 1:
            _draw_hist_1d(fig, tree, histogram, limits=limits)
        case 2:
            _draw_hist_2d(fig, tree, histogram, limits=limits)
        case ndim:
            msg = f"Histograms with {ndim} dimensions are not plottable; reduce to 1 or 2 first"
            raise RuntimeError(msg)


def plot(
    tree: Any,
    *,
    fig: PlotextFigure,
    width: int = 100,
    expr: str = "",
    limits: AxisLimits = NO_LIMITS,
    cache: ExprCache | None = None,
) -> None:
    """
    Plot ``tree`` into the given plotext figure.
    Support new types by registering a :func:`to_histogram` overload.
    """
    histogram = to_histogram(tree, bins=width)
    draw_hist(fig, tree, apply_expr(histogram, expr, tree, cache=cache), limits=limits)


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


def _branch_plottable(branch: uproot.TBranch) -> bool:
    interpretation = _leaf_interpretation(branch)
    if isinstance(interpretation, uproot.interpretation.objects.AsObjects):
        return _model_is_histogram(interpretation.model)
    return _branch_numeric(branch)


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
def array_plottable(item: Any) -> bool:  # noqa: ARG001
    """Does ``item`` read as a numeric array (not histogram objects)?"""
    return False


@array_plottable.register(uproot.models.RNTuple.RField)
def _field_array_plottable(item: uproot.models.RNTuple.RField) -> bool:
    return _field_plottable(item)


@array_plottable.register(uproot.TBranch)
def _branch_array_plottable(item: uproot.TBranch) -> bool:
    return _branch_numeric(item)


@functools.singledispatch
def plottable(item: Any) -> bool:
    """
    True if :func:`plot` has an implementation for this object that can
    succeed. Some failures (like an empty branch) are only found by reading
    the data, so this is a necessary but not sufficient check.
    """
    return to_histogram.dispatch(type(item)) is not to_histogram.dispatch(object)


@plottable.register(uproot.behaviors.TH1.Histogram)
def _hist_plottable(item: uproot.behaviors.TH1.Histogram) -> bool:
    return len(item.axes) <= 2


plottable.register(uproot.TBranch)(_branch_plottable)  # type: ignore[no-untyped-call]
plottable.register(uproot.models.RNTuple.RField)(_field_plottable)  # type: ignore[no-untyped-call]


@plottable.register(BranchPair)
def _pair_plottable(item: BranchPair) -> bool:
    return array_plottable(item.x) and array_plottable(item.y)


@functools.singledispatch
def dump(tree: Any, *, width: int = 100) -> str:  # noqa: ARG001
    """
    Return standalone Python source that rebuilds the plotted histogram as ``h``
    from an object bound to ``item``. Mirrors :func:`plot` for the "Dump & Quit"
    output. Implement this for each type of plottable.
    """
    msg = f"This object ({type(tree)}) is not plottable yet"
    raise RuntimeError(msg)


@dump.register(uproot.TBranch | uproot.models.RNTuple.RField)
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


@dump.register
def dump_pair(tree: BranchPair, *, width: int = 100) -> str:
    """
    Source for rebuilding a 2D histogram from branches bound to ``x_item`` and
    ``y_item``.
    """
    x_source, y_source = array_source(tree.x, "x_item"), array_source(tree.y, "y_item")
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


def _dump_ndim(item: Any) -> int:
    """The dimensions of the histogram :func:`dump` builds, without reading data."""
    if isinstance(item, BranchPair):
        return 2
    if isinstance(item, uproot.behaviors.TH1.Histogram):
        return len(item.axes)
    return 1


def _dump_title(item: Any) -> str:
    """Source for the plot title; the flow count of :func:`make_hist_title` is omitted."""
    name = (
        "{y_item.name} vs {x_item.name}"
        if isinstance(item, BranchPair)
        else "{item.name}"
    )
    return f'f"{name} -- Entries: {{np.sum(h.counts()):g}}"'


def _lim_args(lim: AxisRange) -> str:
    return ", ".join("None" if v is None else repr(float(v)) for v in lim)


def dump_plotext(item: Any, *, limits: AxisLimits = NO_LIMITS) -> str:
    """Source that draws ``h`` with plotext like :func:`draw_hist` (ticks omitted)."""
    xlabel = "h.axes[0].label"
    if _dump_ndim(item) == 2 or PLOTEXT_6:
        lines = [
            "import numpy as np",
            "import plotext as plt",
            "",
            "fig = plt.figure",
        ]
        if _dump_ndim(item) == 2:
            # Heatmap rows draw top-to-bottom; flip so y increases upward
            lines += [
                "values = h.values().T[::-1].tolist()",
                'fig.draw(fig.heatmap(values, map="viridis", fill=True))',
                f'fig.label({xlabel}, axis="x")',
                'fig.label(h.axes[1].label, axis="y")',
            ]
        else:
            lines.append("fig.draw(fig.bar(h.axes[0].centers, h.values()))")
            if limits.x != (None, None):
                lines.append(f'fig.ruler("x").lim({_lim_args(limits.x)})')
            lower, upper = limits.y
            lines += [
                f'fig.ruler("y").lim({_lim_args((0 if lower is None else lower, upper))})',
                f'fig.label({xlabel}, axis="x")',
            ]
        lines += [f"fig.title({_dump_title(item)})", "print(fig.build())"]
        return "\n".join(lines)

    lines = [
        "import numpy as np",
        "import plotext as plt",
        "",
        "plt.bar(h.axes[0].centers, h.values())",
    ]
    if limits.x != (None, None):
        lines.append(f"plt.xlim({_lim_args(limits.x)})")
    lower, upper = limits.y
    lines += [
        f"plt.ylim({_lim_args((0 if lower is None else lower, upper))})",
        f"plt.xlabel({xlabel})",
        f"plt.title({_dump_title(item)})",
        "plt.show()",
    ]
    return "\n".join(lines)


def dump_mpl(item: Any, *, limits: AxisLimits = NO_LIMITS) -> str:
    """Source that draws ``h`` with matplotlib like :mod:`uproot_browser.plot_mpl`."""
    lines = [
        "import matplotlib.pyplot as plt",
        "import numpy as np",
        "",
        "h.plot()",
        f"plt.title({_dump_title(item)})",
    ]
    if limits.x != (None, None):
        lines.append(f"plt.xlim({_lim_args(limits.x)})")
    if limits.y != (None, None):
        lines.append(f"plt.ylim({_lim_args(limits.y)})")
    lines.append("plt.show()")
    return "\n".join(lines)
