from __future__ import annotations

import sys

import hist
import pytest
import rich.console
import uproot
from skhep_testdata import data_path

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


@pytest.mark.parametrize(
    ("selection", "expr"),
    [
        ("hstat", ""),
        ("hstat", "h[50:]"),
        ("T/event/fNtrack", ""),
        ("T/event/fH", "h[::2j]"),
    ],
)
def test_dump_is_runnable(selection: str, expr: str) -> None:
    """The "Dump & Quit" source rebuilds the plotted histogram as ``h``."""
    uproot_file = uproot.open(data_path("uproot-Event.root"))
    item = uproot_file[selection]

    code = uproot_browser.tui.plot.dump(item, 105, 30, expr=expr)

    namespace: dict[str, object] = {"item": item}
    exec(code, namespace)

    assert isinstance(namespace["h"], hist.Hist)
