from __future__ import annotations

import functools
import io
import math
import re
import shutil
import sys
from typing import TYPE_CHECKING

import hist
import numpy as np
import pytest
import rich.console
import uproot
from skhep_testdata import data_path

import uproot_browser.plot
import uproot_browser.plotext_compat
import uproot_browser.tree
import uproot_browser.tui.plot
from uproot_browser.axis import AxisLimits
from uproot_browser.exceptions import ExpressionError
from uproot_browser.tree import UprootEntry, print_tree, process_item

if TYPE_CHECKING:
    import pathlib

ANSI = re.compile(r"\x1b\[[0-9;]*m")

OUT1 = """\
📁 uproot-Event.root
┣━━ ❓ <unnamed> TProcessID
┣━━ 🌴 T (1000)
┃   ┗━━ 🌿 event Event
┃       ┣━━ 🌿 TObject (group of fUniqueID:uint32_t, fBits:uint32_t)
┃       ┃   ┣━━ 🍁 fBits uint32_t
┃       ┃   ┗━━ 🍁 fUniqueID uint32_t
┃       ┣━━ 🍁 fClosestDistance unknown[]
┃       ┣━━ 🍁 fEventName char*
┃       ┣━━ 🌿 fEvtHdr EventHeader
┃       ┃   ┣━━ 🍁 fEvtHdr.fDate int32_t
┃       ┃   ┣━━ 🍁 fEvtHdr.fEvtNum int32_t
┃       ┃   ┗━━ 🍁 fEvtHdr.fRun int32_t
┃       ┣━━ 🍁 fFlag uint32_t
┃       ┣━━ 🍁 fH TH1F
┃       ┣━━ 🍁 fHighPt TRefArray*
┃       ┣━━ 🍁 fIsValid bool
┃       ┣━━ 🍁 fLastTrack TRef
┃       ┣━━ 🍁 fMatrix[4][4] float[4][4]
┃       ┣━━ 🍁 fMeasures[10] int32_t[10]
┃       ┣━━ 🍁 fMuons TRefArray*
┃       ┣━━ 🍁 fNseg int32_t
┃       ┣━━ 🍁 fNtrack int32_t
┃       ┣━━ 🍁 fNvertex uint32_t
┃       ┣━━ 🍁 fTemperature float
┃       ┣━━ 🌿 fTracks TClonesArray*
┃       ┃   ┣━━ 🍃 fTracks.fBits uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fBx Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fBy Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fCharge Double32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fMass2 Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fMeanCharge float[]
┃       ┃   ┣━━ 🍃 fTracks.fNpoint int32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fNsp uint32_t[]
┃       ┃   ┣━━ 🍁 fTracks.fPointValue unknown[][]
┃       ┃   ┣━━ 🍃 fTracks.fPx float[]
┃       ┃   ┣━━ 🍃 fTracks.fPy float[]
┃       ┃   ┣━━ 🍃 fTracks.fPz float[]
┃       ┃   ┣━━ 🍃 fTracks.fRandom float[]
┃       ┃   ┣━━ 🍃 fTracks.fTArray[3] float[][3]
┃       ┃   ┣━━ 🍁 fTracks.fTriggerBits.fAllBits uint8_t[][]
┃       ┃   ┣━━ 🍃 fTracks.fTriggerBits.fBits uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fTriggerBits.fNbits uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fTriggerBits.fNbytes uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fTriggerBits.fUniqueID uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fUniqueID uint32_t[]
┃       ┃   ┣━━ 🍃 fTracks.fValid int16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fVertex[3] Double32_t[][3]
┃       ┃   ┣━━ 🍃 fTracks.fXfirst Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fXlast Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fYfirst Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fYlast Float16_t[]
┃       ┃   ┣━━ 🍃 fTracks.fZfirst Float16_t[]
┃       ┃   ┗━━ 🍃 fTracks.fZlast Float16_t[]
┃       ┣━━ 🌿 fTriggerBits TBits
┃       ┃   ┣━━ 🌿 fTriggerBits.TObject (group of fTriggerBits.fUniqueID:uint32_t, fTriggerBits.fBits:uint32_t)
┃       ┃   ┃   ┣━━ 🍁 fTriggerBits.fBits uint32_t
┃       ┃   ┃   ┗━━ 🍁 fTriggerBits.fUniqueID uint32_t
┃       ┃   ┣━━ 🍃 fTriggerBits.fAllBits uint8_t[]
┃       ┃   ┣━━ 🍁 fTriggerBits.fNbits uint32_t
┃       ┃   ┗━━ 🍁 fTriggerBits.fNbytes uint32_t
┃       ┣━━ 🍁 fType[20] int8_t[20]
┃       ┗━━ 🍁 fWebHistogram TRef
┣━━ 📊 hstat TH1F (100)
┗━━ 📊 htime TH1F (10)
"""


@pytest.mark.xfail(
    sys.platform.startswith("win"),
    reason="Unicode is different on Windows, for some reason?",
)
def test_tree(capsys: pytest.CaptureFixture[str]) -> None:
    filename = data_path("uproot-Event.root")
    console = rich.console.Console(width=120)

    print_tree(filename, console=console)
    out, err = capsys.readouterr()

    assert not err
    assert out == OUT1


OUT2 = """\
📁 ntpl001_staff_rntuple_v1-0-0-0.root
┗━━ 🌳 Staff (3354)
    ┣━━ 🍁 Age std::int32_t
    ┣━━ 🍁 Category std::int32_t
    ┣━━ 🍁 Children std::int32_t
    ┣━━ 🍁 Cost std::int32_t
    ┣━━ 🍁 Division std::string
    ┣━━ 🍁 Flag std::uint32_t
    ┣━━ 🍁 Grade std::int32_t
    ┣━━ 🍁 Hrweek std::int32_t
    ┣━━ 🍁 Nation std::string
    ┣━━ 🍁 Service std::int32_t
    ┗━━ 🍁 Step std::int32_t
"""


@pytest.mark.xfail(
    sys.platform.startswith("win"),
    reason="Unicode is different on Windows, for some reason?",
)
def test_tree_rntuple(capsys: pytest.CaptureFixture[str]) -> None:
    filename = data_path("ntpl001_staff_rntuple_v1-0-0-0.root")
    console = rich.console.Console(width=120)

    print_tree(filename, console=console)
    out, err = capsys.readouterr()
    assert not err
    assert out == OUT2


def test_tree_with_unreadable_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keys that fail to deserialize show as failed entries, not a crash."""
    orig = uproot.reading.ReadOnlyDirectory.__getitem__

    def bad_getitem(self: uproot.reading.ReadOnlyDirectory, key: str) -> object:
        if key.split(";", maxsplit=1)[0] == "hstat":
            msg = "simulated deserialization failure"
            raise ValueError(msg)
        return orig(self, key)

    monkeypatch.setattr(uproot.reading.ReadOnlyDirectory, "__getitem__", bad_getitem)

    with uproot.open(data_path("uproot-Event.root")) as upfile:
        entry = uproot_browser.tree.UprootEntry("/", upfile)
        children = {c.path.rsplit("/", maxsplit=1)[-1]: c for c in entry.children}

        failed = children["hstat"].item
        assert isinstance(failed, uproot_browser.tree.FailedEntry)
        assert isinstance(failed.exception, ValueError)

        meta = children["hstat"].meta()
        assert meta["label_icon"] == "‼️ "
        assert "hstat" in meta["label_text"].plain
        assert "ValueError" in meta["label_text"].plain

        # a failed entry is a leaf and the whole tree still renders
        assert not children["hstat"].is_dir
        uproot_browser.tree.make_tree(entry)


def test_tree_nested_directory_label() -> None:
    """A nested TDirectory is labeled by its own name, not the root one (issue #282)."""
    with uproot.open(data_path("uproot-nesteddirs.root")) as upfile:
        entry = UprootEntry("/", upfile)
        (nested,) = (e for e in entry.walk() if e.path == "//one/two")

        label_text = nested.meta()["label_text"]
        assert label_text.plain == "two"
        assert label_text.style.link is not None
        assert label_text.style.link.endswith("one/two")


def test_tree_bracket_path_link(tmp_path: pathlib.Path) -> None:
    """A file path containing brackets does not corrupt the rendered link (issue #282)."""
    src = data_path("uproot-Event.root")
    dest_dir = tmp_path / "a[1]"
    dest_dir.mkdir()
    dest = dest_dir / "uproot-Event.root"
    shutil.copy(src, dest)

    with uproot.open(dest) as upfile:
        meta = process_item(upfile)
        assert meta["label_text"].plain == "uproot-Event.root"
        assert meta["label_text"].style.link is not None
        assert meta["label_text"].style.link.startswith("file://")


@pytest.mark.parametrize(
    ("filename", "selection", "expr"),
    [
        ("uproot-Event.root", "hstat", ""),
        ("uproot-Event.root", "hstat", "h[50:]"),
        ("uproot-Event.root", "hstat", "np.array([1., 2., 3.])"),
        ("uproot-Event.root", "hstat", "np.array([1., np.nan, np.inf, 2.])"),
        ("uproot-Event.root", "T/event/fNtrack", ""),
        ("uproot-Event.root", "T/event/fH", "h[::2j]"),
        ("uproot-hepdata-example.root", "hpxpy", ""),
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff/Age", "h[::2j]"),
        # Build a custom histogram from the containing tree's branch arrays.
        (
            "uproot-Event.root",
            "T/event/fNtrack",
            'hist.Hist.new.Reg(10, 0, 100).Double().fill(tree["fNtrack"].array())',
        ),
        # `tree` exposes the containing uproot tree, so a cut expression
        # still runs from the dumped source
        (
            "uproot-Event.root",
            "T/event/fNtrack",
            'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]',
        ),
        (
            "uproot-Event.root",
            "T/event/fNtrack",
            'tree.arrays("fTracks.fPx", cut="fTracks.fPy < 0")["fTracks.fPx"]',
        ),
        (
            "ntpl001_staff_rntuple_v1-0-0-0.root",
            "Staff/Age",
            'tree["Age"].array()[tree["Age"].array() > 20]',
        ),
        # library="np" gives an object array for a jagged branch
        (
            "uproot-Event.root",
            "T/event/fNtrack",
            'tree["fTracks.fPx"].array(library="np")',
        ),
        # an uproot histogram converts through to_hist()
        ("uproot-Event.root", "T/event/fNtrack", 'tree["fH"].array(library="np")[0]'),
    ],
)
def test_dump_is_runnable(filename: str, selection: str, expr: str) -> None:
    """The exported source rebuilds the plotted histogram without the browser package."""
    uproot_file = uproot.open(data_path(filename))
    # Navigate key-by-key, like the tree browser does (RNTuple fields are not
    # reachable via a recursive "a/b" lookup on the minimum uproot).
    item = functools.reduce(
        lambda obj, key: obj[key], selection.split("/"), uproot_file
    )

    code = uproot_browser.tui.plot.make_dump(item, 105, 30, expr=expr)
    assert "uproot_browser" not in code

    namespace: dict[str, object] = {"item": item}
    exec(code, namespace)

    actual = namespace["h"]
    assert isinstance(actual, hist.Hist)
    if expr:
        assert "t" not in namespace
        assert namespace.get("tree") is uproot_browser.plot.containing_tree(item)
    expected = uproot_browser.plot.apply_expr(
        uproot_browser.plot.to_histogram(item, bins=100), expr, item
    )
    np.testing.assert_array_equal(actual.values(flow=True), expected.values(flow=True))
    for actual_axis, expected_axis in zip(actual.axes, expected.axes, strict=True):
        np.testing.assert_array_equal(actual_axis.edges, expected_axis.edges)


def test_dump_with_limits_draws_once() -> None:
    """With limits, the dump draws ``h`` instead of re-evaluating the expression."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    expr = 'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]'
    limits = AxisLimits(x=(-1.0, 1.0), y=(None, None))

    code = uproot_browser.tui.plot.make_dump(item, 105, 30, expr=expr, limits=limits)

    assert code.count(expr) == 1
    assert "uproot_browser.plot.plot(" not in code
    namespace: dict[str, object] = {"item": item, "print": lambda *_: None}
    exec(code, namespace)
    assert isinstance(namespace["h"], hist.Hist)


@pytest.mark.parametrize(
    ("expr", "match"),
    [
        ("42", r"hist\.Hist"),
        ("np.array([np.nan])", "no finite values"),
    ],
)
def test_dump_expr_errors_match_tui(expr: str, match: str) -> None:
    """The dumped script fails the way the TUI did, not inside awkward."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)
    with pytest.raises(Exception, match=match):
        uproot_browser.plot.apply_expr(default, expr, item)

    code = uproot_browser.tui.plot.make_dump(item, 105, 30, expr=expr)
    with pytest.raises(Exception, match=match):
        exec(code, {"item": item})


def test_dump_without_tree_omits_tree() -> None:
    """A histogram in a directory has no containing tree to bind."""
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]
    code = uproot_browser.tui.plot.make_dump(item, 105, 30, expr="h[::2j]")
    assert "tree" not in code


def test_make_hist_title_counts_profile_entries() -> None:
    """A TProfile title counts entries, not the sum of per-bin means (issue #282)."""
    item = uproot.open(data_path("uproot-hepdata-example.root"))["hprof"]
    h = uproot_browser.plot.to_histogram(item)

    inner_sum = float(np.sum(h.counts()))
    full_sum = float(np.sum(h.counts(flow=True)))
    title = uproot_browser.plot.make_hist_title(item, h)

    assert f"Entries: {inner_sum:g}" in title
    assert f"{full_sum:g} with flow" in title


def test_make_hist_title_th1_unchanged() -> None:
    """An ordinary TH1 title still sums bin values, unaffected by the TProfile fix."""
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]
    h = uproot_browser.plot.to_histogram(item)

    inner_sum = float(np.sum(h.values()))
    full_sum = float(np.sum(h.values(flow=True)))
    title = uproot_browser.plot.make_hist_title(item, h)

    assert f"Entries: {inner_sum:g}" in title
    assert "with flow" not in title
    assert math.isclose(inner_sum, full_sum)


def test_plot_1d_draws_bars() -> None:
    """A TH1 renders actual bars, not an empty frame (plotext 6 regression)."""
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]

    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(80, 25)
    uproot_browser.plot.plot(item, fig=fig)
    out = str(fig.build())

    assert "hstat" in out
    assert "█" in out


def test_plot_narrow_range_branch() -> None:
    """A branch whose range is tiny next to its magnitude still plots (float32 rescale)."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/TObject/fBits"]

    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(80, 25)
    uproot_browser.plot.plot(item, fig=fig, width=50)
    out = str(fig.build())

    assert "fBits" in out
    assert "\u2588" in out


@pytest.mark.skipif(
    not uproot_browser.plotext_compat.PLOTEXT_6, reason="heatmaps require plotext 6"
)
def test_plot_2d() -> None:
    """A TH2 renders as a heatmap with both axes labeled (issue #175)."""
    item = uproot.open(data_path("uproot-hepdata-example.root"))["hpxpy"]

    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(80, 25)
    uproot_browser.plot.plot(item, fig=fig)
    out = str(fig.build())

    assert "hpxpy" in out
    assert "xaxis" in out
    assert "yaxis" in out
    assert "█" in out


def _render(item: object, limits: AxisLimits, size: tuple[int, int]) -> str:
    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(*size)
    uproot_browser.plot.plot(item, fig=fig, limits=limits)
    return ANSI.sub("", str(fig.build()))


def test_y_range_clips_tall_bars() -> None:
    """A bar above the typed Y maximum is clipped at the limit, not hidden."""
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]
    peak = float(np.max(item.values()))

    out = _render(item, AxisLimits(y=(None, peak / 2)), (60, 12))
    rows = [line.split("┤", 1) for line in out.splitlines() if "┤" in line]

    assert rows
    assert float(rows[0][0]) == peak / 2  # a tick sits at the limit
    assert "█" in rows[0][1]  # the clipped peak still reaches the top
    assert "0┤" in out


@pytest.mark.skipif(
    not uproot_browser.plotext_compat.PLOTEXT_6, reason="heatmaps need plotext 6"
)
def test_2d_ranges_are_in_data_units() -> None:
    """Typed limits window the heatmap's bin-index axes in data units."""
    item = uproot.open(data_path("uproot-hepdata-example.root"))["hpxpy"]

    full = _render(item, AxisLimits(), (80, 20))
    zoomed = _render(item, AxisLimits(x=(-1, 1), y=(-1, 1)), (80, 20))

    assert "-3.9" in full
    assert "-3.9" not in zoomed
    assert "█" in zoomed
    labels = [float(x) for x in re.findall(r"-?\d+\.\d+", zoomed.rsplit("┘", 1)[1])]
    assert labels
    assert all(-1 <= x <= 1 for x in labels)


@pytest.mark.skipif(
    uproot_browser.plotext_compat.PLOTEXT_6, reason="plotext 6 supports heatmaps"
)
def test_plot_2d_errors_on_plotext_5() -> None:
    """On plotext 5, a TH2 gives a clear upgrade message instead of a crash."""
    item = uproot.open(data_path("uproot-hepdata-example.root"))["hpxpy"]

    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(80, 25)
    with pytest.raises(RuntimeError, match="require plotext 6"):
        uproot_browser.plot.plot(item, fig=fig)


def test_custom_theme_keeps_signal_colors() -> None:
    """Signals on a custom theme keep their palette colors.

    plotext 6's ``add_theme`` without a ``sequence`` makes every signal
    colorless, so they all render in the theme's text color.
    """
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]

    uproot_browser.plotext_compat.add_theme(
        "test_signal_colors", canvas=(20, 20, 20), text=((255, 166, 43), (20, 20, 20))
    )
    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.theme("test_signal_colors")
    fig.plot_size(80, 25)
    uproot_browser.plot.plot(item, fig=fig)
    out = str(fig.build())

    foregrounds = set(re.findall(r"38;(?:5;\d+|2;\d+;\d+;\d+)", out))
    # the signal color plus the text color
    assert len(foregrounds) >= 2


def test_plot_3d_errors() -> None:
    """3+ dimensional histograms give a clear error, not a plotext internal one."""
    item = uproot.open(data_path("uproot-hepdata-example.root"))["hpxpy"]
    # the expr namespace only holds ``h``, so reach hist.Hist through it
    expr = "h.__class__.new.Reg(4, 0, 4).Reg(3, 0, 3).Reg(2, 0, 2).Double()"

    fig = uproot_browser.plotext_compat.make_figure()
    fig.clear()
    fig.plot_size(80, 25)
    with pytest.raises(RuntimeError, match="3 dimensions"):
        uproot_browser.plot.plot(item, fig=fig, expr=expr)


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("hstat", True),  # TH1F
        ("ProcessID0", False),  # TProcessID
        ("T/event/fNtrack", True),  # numeric
        ("T/event/fTracks/fTracks.fPx", True),  # jagged numeric
        ("T/event/fH", True),  # AsObjects(Model_TH1F)
        ("T/event/fLastTrack", False),  # AsStridedObjects(Model_TRef)
        ("T/event/fEventName", False),  # strings
        ("T/event/fTriggerBits", False),  # non-histogram objects
    ],
)
def test_plottable(selection: str, expected: bool) -> None:  # noqa: FBT001
    """Plottability is decided from the interpretation, without reading data."""
    with uproot.open(data_path("uproot-Event.root")) as upfile:
        assert uproot_browser.plot.plottable(upfile[selection]) is expected


@pytest.mark.parametrize(
    ("filename", "selection", "expected"),
    [
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff/Age", True),  # numeric
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff/Division", False),  # strings
        # jagged numeric
        ("test_1jag_int_float_rntuple_v1-0-0-0.root", "ntuple/one_v_integers", True),
    ],
)
def test_plottable_rfield(filename: str, selection: str, expected: bool) -> None:  # noqa: FBT001
    """Plottability of an RNTuple field comes from its form, not from the data."""
    with uproot.open(data_path(filename)) as upfile:
        item = functools.reduce(lambda obj, key: obj[key], selection.split("/"), upfile)
        assert uproot_browser.plot.plottable(item) is expected


def test_to_histogram_rejects_string_field() -> None:
    """A string field gives a clear error, not a numpy one."""
    with uproot.open(data_path("ntpl001_staff_rntuple_v1-0-0-0.root")) as upfile:
        item = upfile["Staff"]["Division"]
        with pytest.raises(TypeError, match="Division"):
            uproot_browser.plot.to_histogram(item)


def test_apply_expr_binds_tree() -> None:
    """The containing tree supplies arrays for custom histogram binning."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)

    result = uproot_browser.plot.apply_expr(
        default,
        'hist.Hist.new.Reg(7, 0, 1000).Double().fill(tree["fNtrack"].array())',
        item,
    )

    assert result.axes[0].size == 7
    assert result.sum() > 0


@pytest.mark.parametrize(
    "expr",
    [
        'tree["fTracks.fPx"].array()[tree["fTracks.fPy"].array() < 0]',
        'tree.arrays("fTracks.fPx", cut="fTracks.fPy < 0")["fTracks.fPx"]',
    ],
)
def test_apply_expr_cut_ttree(expr: str) -> None:
    """Plain uproot array access supports jagged cuts from the containing tree."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)

    result = uproot_browser.plot.apply_expr(default, expr, item)
    uncut = uproot_browser.plot.apply_expr(default, 'tree["fTracks.fPx"].array()', item)

    assert isinstance(result, hist.Hist)
    assert result.axes[0].size == default.axes[0].size
    assert 0 < result.sum() < uncut.sum()


def test_apply_expr_cut_rntuple() -> None:
    """Cuts work on RNTuple files too, not just TTree files."""
    item = uproot.open(data_path("ntpl001_staff_rntuple_v1-0-0-0.root"))["Staff"]["Age"]
    default = uproot_browser.plot.to_histogram(item)

    result = uproot_browser.plot.apply_expr(
        default, 'tree["Age"].array()[tree["Age"].array() > 30]', item
    )

    assert isinstance(result, hist.Hist)
    assert 0 < result.sum() <= default.sum()


def test_apply_expr_rejects_non_data() -> None:
    """An expression returning neither a histogram nor an array gives an error."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)

    with pytest.raises(ExpressionError, match=r"hist\.Hist") as excinfo:
        uproot_browser.plot.apply_expr(default, "42", item)
    assert isinstance(excinfo.value.__cause__, RuntimeError)


@pytest.mark.parametrize(
    ("filename", "tree_name", "selection"),
    [
        ("uproot-Event.root", "T", "fTracks"),
        ("uproot-Event.root", "T", None),
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff", "Age"),
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff", None),
    ],
)
def test_expression_objects_use_uproot_api(
    filename: str, tree_name: str, selection: str | None
) -> None:
    """Expressions receive the containing tree and retain sub-branch lookup."""
    with uproot.open(data_path(filename)) as upfile:
        tree = upfile[tree_name]
        item = tree if selection is None else tree[selection]
        default = hist.Hist.new.Reg(4, 0, 4).Double()
        expression = f"h if id(tree) == {id(tree)} else None"
        assert uproot_browser.plot.apply_expr(default, expression, item) is default
        assert uproot_browser.plot.containing_tree(tree) is tree
        if selection == "fTracks":
            result = uproot_browser.plot.apply_expr(
                default, 'tree["fTracks"]["fTracks.fPx"].array()', item
            )
            assert result.sum() > 0


def test_apply_expr_does_not_bind_selected_object_alias() -> None:
    with uproot.open(data_path("uproot-Event.root")) as upfile:
        item = upfile["T/event/fNtrack"]
        default = uproot_browser.plot.to_histogram(item)
        with pytest.raises(ExpressionError, match="'t'") as excinfo:
            uproot_browser.plot.apply_expr(default, "t", item)
        assert isinstance(excinfo.value.__cause__, NameError)


def test_apply_expr_object_array() -> None:
    """A numpy object array (jagged branch read with library="np") is flattened."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)

    result = uproot_browser.plot.apply_expr(
        default, 'tree["fTracks.fPx"].array(library="np")', item
    )
    direct = uproot_browser.plot.apply_expr(
        default, 'tree["fTracks.fPx"].array()', item
    )

    np.testing.assert_array_equal(result.values(flow=True), direct.values(flow=True))


def test_apply_expr_nested_object_array() -> None:
    """A doubly jagged object array falls back to awkward."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)
    expr = "np.array([np.array([np.array([1.0, 2.0]), np.array([3.0])], dtype=object), np.array([4.0])], dtype=object)"

    result = uproot_browser.plot.apply_expr(default, expr, item)
    assert result.sum() == 4


@pytest.mark.parametrize(
    "expr",
    [
        'tree["fH"].array(library="np")[0]',
        "__import__('boost_histogram').Histogram(h)",
    ],
)
def test_apply_expr_converts_to_hist(expr: str) -> None:
    """Objects that convert to hist.Hist are accepted, not rejected."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)

    result = uproot_browser.plot.apply_expr(default, expr, item)

    assert isinstance(result, hist.Hist)
    assert result.sum() > 0


def test_apply_expr_no_tree_outside_tree() -> None:
    """A histogram in a directory does not bind ``tree`` at all."""
    item = uproot.open(data_path("uproot-Event.root"))["hstat"]
    default = uproot_browser.plot.to_histogram(item)

    with pytest.raises(ExpressionError, match="tree") as excinfo:
        uproot_browser.plot.apply_expr(default, 'tree["fNtrack"].array()', item)
    assert isinstance(excinfo.value.__cause__, NameError)


def test_expr_cache_reuses_tree_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """An expression that does not use ``h`` is evaluated once per cache."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    default = uproot_browser.plot.to_histogram(item)
    cache = uproot_browser.plot.ExprCache()
    expr = 'tree["fTracks.fPx"].array()'

    first = uproot_browser.plot.apply_expr(default, expr, item, cache=cache)
    monkeypatch.setattr(uproot_browser.plot, "evaluate_expr", _fail_eval)
    second = uproot_browser.plot.apply_expr(default, expr, item, cache=cache)
    np.testing.assert_array_equal(first.values(), second.values())

    # a different bin count rebins the cached array
    rebinned = uproot_browser.plot.apply_expr(
        uproot_browser.plot.to_histogram(item, bins=7), expr, item, cache=cache
    )
    assert rebinned.axes[0].size == 7

    # a different expression is a miss
    with pytest.raises(ExpressionError, match="evaluated"):
        uproot_browser.plot.apply_expr(default, "h", item, cache=cache)


def test_expr_cache_skips_h_expressions() -> None:
    """An expression using ``h`` depends on the bin count, so it is not cached."""
    item = uproot.open(data_path("uproot-Event.root"))["T/event/fNtrack"]
    cache = uproot_browser.plot.ExprCache()
    wide = uproot_browser.plot.to_histogram(item, bins=100)
    narrow = uproot_browser.plot.to_histogram(item, bins=10)

    uproot_browser.plot.apply_expr(wide, "h[::2j]", item, cache=cache)
    result = uproot_browser.plot.apply_expr(narrow, "h[::2j]", item, cache=cache)

    assert result.axes[0].size == 5
    assert cache.entry is None


def _fail_eval(*_args: object, **_kwargs: object) -> None:
    msg = "expression was evaluated"
    raise AssertionError(msg)


def _pair(upfile: uproot.ReadOnlyDirectory, x: str, y: str) -> object:
    return uproot_browser.plot.BranchPair(upfile[x], upfile[y])


def test_pair_histogram_broadcasts_per_entry_values() -> None:
    """A per-entry branch pairs with each value of a jagged branch."""
    with uproot.open(data_path("uproot-Event.root")) as upfile:
        pair = _pair(upfile, "T/event/fNtrack", "T/event/fTracks/fTracks.fPx")
        histogram = uproot_browser.plot.to_histogram(pair, bins=20)
        ntrack = upfile["T/event/fNtrack"].array()

    assert [ax.label for ax in histogram.axes] == ["fNtrack", "fTracks.fPx"]
    assert histogram.sum(flow=True) == np.sum(ntrack)
    assert uproot_browser.plot.plottable(pair)


@pytest.mark.parametrize(
    ("x", "y"),
    [
        ("T/event/fNtrack", "T/event/fH"),  # histogram objects
        ("T/event/fEventName", "T/event/fNtrack"),  # strings
    ],
)
def test_pair_needs_numbers(x: str, y: str) -> None:
    with uproot.open(data_path("uproot-Event.root")) as upfile:
        pair = _pair(upfile, x, y)
        assert not uproot_browser.plot.plottable(pair)
        with pytest.raises(TypeError, match="2D plot"):
            uproot_browser.plot.to_histogram(pair)


def test_pair_needs_same_entries() -> None:
    with (
        uproot.open(data_path("uproot-Event.root")) as event,
        uproot.open(data_path("uproot-HZZ.root")) as hzz,
    ):
        pair = uproot_browser.plot.BranchPair(
            event["T/event/fNtrack"], hzz["events/NJet"]
        )
        with pytest.raises(ValueError, match="1000 entries, but NJet has 2421"):
            uproot_browser.plot.to_histogram(pair)


@pytest.mark.skipif(
    not uproot_browser.plotext_compat.PLOTEXT_6, reason="heatmaps require plotext 6"
)
def test_plot_pair() -> None:
    with uproot.open(data_path("uproot-Event.root")) as upfile:
        pair = _pair(
            upfile, "T/event/fTracks/fTracks.fPx", "T/event/fTracks/fTracks.fPy"
        )
        out = _render(pair, AxisLimits(), (80, 25))

    assert "fTracks.fPy vs fTracks.fPx" in out
    assert "█" in out


@pytest.mark.parametrize("expr", ["", "h[::2j, :]"])
def test_dump_pair_is_runnable(expr: str) -> None:
    upfile = uproot.open(data_path("uproot-Event.root"))
    pair = _pair(upfile, "T/event/fTracks/fTracks.fPx", "T/event/fTracks/fTracks.fPy")

    code = uproot_browser.tui.plot.make_dump(pair, 105, 30, expr=expr)
    assert "uproot_browser" not in code

    namespace: dict[str, object] = {"x_item": pair.x, "y_item": pair.y}
    exec(code, namespace)

    expected = uproot_browser.plot.apply_expr(
        uproot_browser.plot.to_histogram(pair, bins=100), expr, pair
    )
    actual = namespace["h"]
    assert isinstance(actual, hist.Hist)
    np.testing.assert_array_equal(actual.values(flow=True), expected.values(flow=True))
    assert [ax.label for ax in actual.axes] == [ax.label for ax in expected.axes]


def make_root_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory with a ROOT file, a nested one, and entries to skip."""
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "a.root")
    (tmp_path / "sub").mkdir()
    shutil.copy(data_path("uproot-hepdata-example.root"), tmp_path / "sub" / "b.root")
    (tmp_path / "empty").mkdir()
    (tmp_path / "notes.txt").write_text("not ROOT")
    (tmp_path / ".hidden.root").write_text("")
    return tmp_path


def test_local_directory_tree(tmp_path: pathlib.Path) -> None:
    root = make_root_dir(tmp_path)
    with uproot_browser.tree.open_path(str(root)) as directory:
        assert isinstance(directory, uproot_browser.tree.LocalDirectory)
        assert directory.keys() == ["a.root", "sub"]
        paths = {e.path for e in UprootEntry("/", directory).walk()}
        assert {"//a.root/hpx", "//sub/b.root/hpx"} <= paths

        upfile, key = directory.locate("//sub/b.root/hpx")
        assert upfile.file_path == str(root / "sub" / "b.root")
        assert key == "hpx"
        assert directory["//sub/b.root/hpx"].name == "hpx"

    console = rich.console.Console(width=80, file=io.StringIO(), record=True)
    print_tree(str(root), console=console)
    out = console.export_text()
    assert "a.root" in out
    assert "b.root" in out
    assert "notes.txt" not in out
    assert "empty" not in out


def test_local_directory_selection(tmp_path: pathlib.Path) -> None:
    root = make_root_dir(tmp_path)
    item = uproot_browser.tree.open_path(f"{root}:sub/b.root/hpx")
    assert item.name == "hpx"


def test_local_directory_unreadable_file(tmp_path: pathlib.Path) -> None:
    """A file that fails to open shows as failed; the other files still list."""
    root = make_root_dir(tmp_path)
    (root / "bad.root").write_text("not ROOT")
    with uproot_browser.tree.open_path(str(root)) as directory:
        entries = {e.path: e for e in UprootEntry("/", directory).walk()}
        assert isinstance(entries["//bad.root"].item, uproot_browser.tree.FailedEntry)
        assert "//sub/b.root/hpx" in entries

    console = rich.console.Console(width=80, file=io.StringIO(), record=True)
    print_tree(str(root), console=console)
    out = console.export_text()
    assert "bad.root" in out
    assert "b.root" in out


@pytest.mark.parametrize(
    ("spec", "expected"),
    [
        ("{f}", ("{f}", "")),
        ("{f}:hpx", ("{f}", "hpx")),
        ("{f}:h:a", ("{f}", "h:a")),
        ("{d}:sub/b.root/h:a", ("{d}", "sub/b.root/h:a")),
        ("missing.root:h:a", ("missing.root:h:a", "")),
    ],
)
def test_split_spec(
    tmp_path: pathlib.Path, spec: str, expected: tuple[str, str]
) -> None:
    root = make_root_dir(tmp_path)
    fmt = {"f": root / "a.root", "d": root}
    assert uproot_browser.tree.split_spec(spec.format(**fmt)) == tuple(
        e.format(**fmt) for e in expected
    )
