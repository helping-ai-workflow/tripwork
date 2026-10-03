"""Tests for scripts/media_merge.py — render-time overlay of the photo side-file.

The side-file (verified-pois-media.yaml) is merged onto poi_map at export and is
NEVER written back into canonical verified-pois.yaml (source-verify wholesale-
rewrites that file every run, so any inline media would be clobbered).
"""
import pathlib

from scripts.media_merge import apply_media, load_media

FIX = pathlib.Path(__file__).resolve().parent / "fixtures"

_ENTRY = {
    "photo": {"data": "data:image/jpeg;base64,/9j/AAAA", "width": 640, "height": 480},
    "photo_attribution": {"author": "A", "license": "CC-BY", "source_url": "https://a.example"},
    "photo_source": "wikimedia",
}

def _media_doc():
    return {"media": {"p1": dict(_ENTRY)}}

def test_apply_media_overlays_onto_matching_id():
    poi_map = {"p1": {"id": "p1", "name_display": "X"}}
    out = apply_media(poi_map, _media_doc())
    assert out["p1"]["photo"] == _ENTRY["photo"]
    assert out["p1"]["photo_attribution"] == _ENTRY["photo_attribution"]
    assert out["p1"]["photo_source"] == "wikimedia"
    assert out["p1"]["name_display"] == "X"   # original poi fields preserved

def test_apply_media_ignores_non_matching_id():
    poi_map = {"p2": {"id": "p2"}}
    out = apply_media(poi_map, _media_doc())   # media keyed p1
    assert "photo" not in out["p2"]

def test_apply_media_poi_without_entry_unchanged():
    poi_map = {"p1": {"id": "p1"}, "p2": {"id": "p2"}}
    out = apply_media(poi_map, _media_doc())
    assert "photo" in out["p1"]
    assert "photo" not in out["p2"]

def test_apply_media_does_not_mutate_canonical_poi_map():
    poi = {"id": "p1"}
    poi_map = {"p1": poi}
    apply_media(poi_map, _media_doc())
    assert "photo" not in poi               # canonical object untouched
    assert "photo" not in poi_map["p1"]

def test_apply_media_returns_copies_even_when_empty():
    poi_map = {"p1": {"id": "p1"}}
    out = apply_media(poi_map, {})
    assert out == {"p1": {"id": "p1"}}
    assert out["p1"] is not poi_map["p1"]    # a copy, never the same object

def test_apply_media_none_doc_safe():
    out = apply_media({"p1": {"id": "p1"}}, None)
    assert out["p1"]["id"] == "p1"

def test_apply_media_only_overlays_known_media_keys():
    doc = {"media": {"p1": {**_ENTRY, "rogue": "x"}}}
    out = apply_media({"p1": {"id": "p1"}}, doc)
    assert "rogue" not in out["p1"]

def test_load_media_absent_returns_empty(tmp_path):
    assert load_media(tmp_path / "nope.yaml") == {}

def test_load_media_reads_sidefile():
    doc = load_media(FIX / "verified-pois-media.sample.yaml")
    assert "media" in doc
    assert "poi-onsen-01" in doc["media"]

def test_load_media_non_dict_yaml_returns_empty(tmp_path):   # step-8: graceful-absent contract
    p = tmp_path / "bad.yaml"
    p.write_text("- a\n- b\n", encoding="utf-8")   # valid YAML, but a list not a dict
    assert load_media(p) == {}

def test_load_media_directory_returns_empty(tmp_path):   # step-8: OSError degrades to {}
    assert load_media(tmp_path) == {}

def test_apply_media_non_dict_entry_ignored():   # step-8: robustness on malformed entry
    out = apply_media({"p1": {"id": "p1"}}, {"media": {"p1": ["photo"]}})
    assert "photo" not in out["p1"]
    assert out["p1"]["id"] == "p1"

def test_load_media_then_apply_end_to_end():
    doc = load_media(FIX / "verified-pois-media.sample.yaml")
    poi_map = {"poi-onsen-01": {"id": "poi-onsen-01", "name_display": "登別温泉"}}
    out = apply_media(poi_map, doc)
    assert out["poi-onsen-01"]["photo_source"] == "wikimedia"
    assert "photo" in out["poi-onsen-01"]
