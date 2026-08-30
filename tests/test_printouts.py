from __future__ import annotations

import functools
import re
import sys

import hist
import pytest
import rich.console
import uproot
from skhep_testdata import data_path

import uproot_browser.plot
import uproot_browser.plotext_compat
import uproot_browser.tree
import uproot_browser.tui.plot
from uproot_browser.tree import print_tree

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


@pytest.mark.parametrize(
    ("filename", "selection", "expr"),
    [
        ("uproot-Event.root", "hstat", ""),
        ("uproot-Event.root", "hstat", "h[50:]"),
        ("uproot-Event.root", "T/event/fNtrack", ""),
        ("uproot-Event.root", "T/event/fH", "h[::2j]"),
        ("uproot-hepdata-example.root", "hpxpy", ""),
        ("ntpl001_staff_rntuple_v1-0-0-0.root", "Staff/Age", "h[::2j]"),
    ],
)
def test_dump_is_runnable(filename: str, selection: str, expr: str) -> None:
    """The "Dump & Quit" source rebuilds the plotted histogram as ``h``."""
    uproot_file = uproot.open(data_path(filename))
    # Navigate key-by-key, like the tree browser does (RNTuple fields are not
    # reachable via a recursive "a/b" lookup on the minimum uproot).
    item = functools.reduce(
        lambda obj, key: obj[key], selection.split("/"), uproot_file
    )

    code = uproot_browser.tui.plot.make_dump(item, 105, 30, expr=expr)

    namespace: dict[str, object] = {"item": item}
    exec(code, namespace)

    assert isinstance(namespace["h"], hist.Hist)


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
