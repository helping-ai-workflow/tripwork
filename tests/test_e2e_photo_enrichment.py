"""End-to-end photo-enrichment closure (8-step pre-ship gate, step 7).

ONE fixture exercising EVERY photo defect together, along the real export path the
agent follows: photo_adapter -> side-file -> media_merge -> render -> gate.

Part A (happy path): adapter (mocked net) produces a clean CC photo, written to a
side-file, loaded, merged onto a photo-less canonical poi_map, rendered to HTML +
markdown, and both gates PASS — proving PR1 (schema-valid merged shape),
PR2 (&query_place_id deep-link), PR3 (img + escaped caption + pure-CSS lightbox),
PR5 (adapter), PR6 (canonical untouched) interoperate.

Part B (defect gating): the export gate REJECTS a photo with no attribution, a
photo_source=google (non-distributable), and an unsafe <img src> — proving PR4's
three guards fire on the merged/rendered deliverable.
"""
import json
import pathlib

import jsonschema

from scripts.photo_adapter import build_media, write_media_sidefile
from scripts.media_merge import load_media, apply_media
from scripts.render.html_page import render_html_page
from scripts.render.markdown import render_day_table
from scripts.export_gate import run_html_gate, run_export_gate

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"


class _Resp:
    def __init__(self, *, json_data=None, content=b"", content_type="application/json"):
        self._json = json_data
        self.content = content
        self.headers = {"Content-Type": content_type}

    def json(self):
        return self._json

    def raise_for_status(self):
        pass


_OV_RESULT = {
    "url": "https://ov.example/full.jpg", "thumbnail": "https://ov.example/thumb.jpg",
    "license": "by-sa", "creator": "Commons User <b>bold</b>",   # author carries markup
    "foreign_landing_url": "https://openverse.org/i/landmark",
}
_IMG_FULL = _Resp(content=b"\xff\xd8\xff FULL", content_type="image/jpeg")
_IMG_THUMB = _Resp(content=b"\xff\xd8\xff THUMB", content_type="image/jpeg")

# Canonical POI: verified, geocoded, 2 sources, has a place_id (PR2), NO photo.
PP = {
    "id": "pp", "name_local": "登別温泉", "name_display": "登別温泉", "name_zh": "登別溫泉",
    "category": "landmark", "district": "Noboribetsu",
    "geocode": {"lat": 42.49, "lng": 141.15},
    "gmaps_place_id": "ChIJ_landmark",
    "sources": [{"url": "https://a.example", "lang": "ja"},
                {"url": "https://b.example", "lang": "zh"}],
    "verify_status": "verified",
}

ITIN = {
    "title": "溫泉行 & 美食",
    "days": [{"date": "2026-11-01", "label": "D1", "lodging": "pp", "rows": [
        {"time": "10:00", "slot": "visit", "poi_id": "pp", "text": "泡湯 & 散步"},
    ]}],
}


def test_e2e_happy_path_adapter_to_gate(mocker, tmp_path):
    mocker.patch("scripts.photo_adapter.requests.get",
                 side_effect=[_Resp(json_data={"results": [_OV_RESULT]}), _IMG_FULL, _IMG_THUMB])

    # PR5: adapter -> media doc; PR1: it validates against the side-file schema.
    doc = build_media([PP], "wiki", sources=("openverse",))
    assert "pp" in doc["media"]
    media_schema = json.load(open(SCHEMAS / "verified-pois-media.schema.json"))
    jsonschema.validate(doc, media_schema)

    # write + reload the side-file
    side = tmp_path / "verified-pois-media.yaml"
    write_media_sidefile(side, doc)
    loaded = load_media(side)

    # PR6: overlay onto a photo-less canonical poi_map; canonical stays untouched.
    poi_map = {"pp": dict(PP)}
    merged = apply_media(poi_map, loaded)
    assert "photo" not in poi_map["pp"]                      # PR6: canonical clobber-free
    assert "photo" in merged["pp"]

    # PR1: the merged render-time shape validates against the canonical schema
    # (photo present => photo_attribution required, satisfied).
    canon = json.load(open(SCHEMAS / "verified-pois.schema.json"))
    jsonschema.validate({"pois": [merged["pp"]]}, canon)

    # render HTML + markdown from the merged poi_map
    html = render_html_page(ITIN, merged)
    md = render_day_table(ITIN["days"][0], merged)

    # P9 (RESTORED): place_id rode through to the rendered maps URL as the Maps URLs
    # API &query_place_id refinement (& escaped to &amp; in the href attr); the dead
    # 0.23.0 maps/place/?q=place_id form must not reappear.
    assert "&amp;query_place_id=ChIJ_landmark" in html
    assert "maps/place/?q=place_id" not in html
    # PR3: photo img + escaped caption + pure-CSS lightbox, no script
    assert "<img" in html and 'type="checkbox"' in html
    assert "data:image/jpeg;base64," in html
    assert "CC-BY-SA" in html
    assert "Commons User &lt;b&gt;bold&lt;/b&gt;" in html    # author markup escaped
    assert "<b>bold</b>" not in html
    assert "<script" not in html.lower()

    # PR4: both gates PASS on the clean, attributed, distributable deliverable
    pois = list(merged.values())
    hg = run_html_gate(html, pois=pois, min_days=1)
    assert hg["status"] == "pass", hg["failures"]
    eg = run_export_gate(md, pois)
    assert eg["status"] == "pass", eg["failures"]


def test_e2e_gate_rejects_missing_attribution():
    bad = {"id": "x", "photo": {"data": "data:image/png;base64,iVBOR"}}   # no attribution
    html = render_html_page(ITIN, {"pp": dict(PP)})
    r = run_html_gate(html, pois=[bad], min_days=1)
    assert r["status"] == "fail"
    assert any("missing attribution" in f for f in r["failures"])
    rm = run_export_gate(render_day_table(ITIN["days"][0], {"pp": dict(PP)}), [bad])
    assert rm["status"] == "fail"


def test_e2e_google_photo_is_terminal_nondistributable():
    # P7 (MIGRATED): a google photo is NOT a fail — it is a clean terminal
    # non-distributable deliverable (status pass, distributable False) so the
    # orchestrator does not re-export-loop on the personal variant.
    google = {"id": "g", "photo": {"url": "https://x/y.jpg"},
              "photo_attribution": {"author": "A", "license": "x", "source_url": "https://a.example"},
              "photo_source": "google"}
    html = render_html_page(ITIN, {"pp": dict(PP)})
    r = run_html_gate(html, pois=[google], min_days=1)
    assert r["status"] == "pass", r["failures"]
    assert r["distributable"] is False
    rm = run_export_gate(render_day_table(ITIN["days"][0], {"pp": dict(PP)}), [google])
    assert rm["status"] == "pass", rm["failures"]
    assert rm["distributable"] is False


def test_e2e_gate_rejects_unsafe_img_src():
    html = render_html_page(ITIN, {"pp": dict(PP)}) + '<img src="http://evil.example/x.jpg">'
    r = run_html_gate(html, pois=[], min_days=1)
    assert r["status"] == "fail"
    assert any("unsafe <img src>" in f for f in r["failures"])
