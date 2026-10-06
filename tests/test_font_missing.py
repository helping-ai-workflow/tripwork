"""v2.1.0 §7 (D8): the title list never needs the font package; the page does, and when
the package is missing it says so in one line (exit 2), with no traceback."""
import sys

import pytest
import yaml

from scripts import title_picker as tpk
from scripts.paths import artifact_path
from scripts.render.reader import assets
from tests.test_title_picker import _inputs


@pytest.fixture
def no_fonttools(monkeypatch):
    monkeypatch.setitem(sys.modules, "fontTools", None)
    monkeypatch.setitem(sys.modules, "fontTools.subset", None)
    monkeypatch.setitem(sys.modules, "fontTools.ttLib", None)
    assets.font_faces.cache_clear()
    yield
    assets.font_faces.cache_clear()


@pytest.fixture
def no_brotli(monkeypatch):
    from fontTools.ttLib import woff2         # binds brotli when imported; its flag is what save() reads
    monkeypatch.setattr(woff2, "haveBrotli", False)
    assets.font_faces.cache_clear()
    yield
    assets.font_faces.cache_clear()


MSG = "缺少字型套件：請執行 pip install fonttools brotli"


def test_font_faces_names_the_missing_package(no_fonttools):
    with pytest.raises(assets.FontPackageMissing, match=MSG):
        assets.font_faces("示意")


def test_font_faces_without_brotli(no_brotli):
    with pytest.raises(assets.FontPackageMissing, match=MSG):
        assets.font_faces("示意")


def _trip(tmp_path):
    itin, brief, acc = _inputs()
    trip = tmp_path / "trips" / "t"
    artifact_path(trip, "itinerary.yaml").parent.mkdir(parents=True)
    for name, doc in (("itinerary.yaml", itin), ("trip-brief.yaml", brief), ("accommodations.yaml", acc)):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return trip


def test_picker_prints_the_list_then_stops_on_missing_fonts(tmp_path, capsys, no_fonttools):
    trip = _trip(tmp_path)
    assert tpk.main([str(trip), "--work-dir", str(tmp_path / "work")]) == 2
    out, err = capsys.readouterr()
    assert "回覆格式" in out and MSG in err and "Traceback" not in err
    assert not (tmp_path / "work" / tpk.PAGE_NAME).exists()


def test_tripwork_picker_exits_2_without_traceback(tmp_path, capsys, monkeypatch, no_fonttools):
    from scripts import tripwork
    _trip(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert tripwork.main(["picker", "t"]) == 2
    out, err = capsys.readouterr()
    assert MSG in err and "Traceback" not in err


def test_tripwork_call_turns_the_error_into_exit_2(capsys, monkeypatch):
    from scripts import tripwork

    class Boom:
        @staticmethod
        def main(argv):
            raise assets.FontPackageMissing(MSG)
    monkeypatch.setattr(tripwork.importlib, "import_module", lambda name: Boom)
    assert tripwork._call("scripts.x", [], "export") == 2
    assert MSG in capsys.readouterr().err
