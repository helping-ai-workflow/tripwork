"""TW-059 cross-stage closure: one fixture walked through verify -> gate ->
render -> export-gate, proving the stages compose (not just pass in isolation)."""
from scripts.verify import classify_candidate
from scripts.gate import run_gate
from scripts.render.markdown import render_day_table
from scripts.export_gate import run_export_gate

def _src(dom, lang="ko", official=False):
    return {"url": f"https://{dom}.example", "lang": lang, "official": official}

def test_cross_stage_verify_gate_render_export():
    # 1) verify: two independent sources, geocoded, in region -> verified
    cand = {"id": "odari", "sources": [_src("official", official=True), _src("guide", "en")]}
    status, _ = classify_candidate(cand, geocoded=True, in_claimed_region=True, local_lang="ko")
    assert status == "verified"
    poi = {"id": "odari", "name_local": "오다리집", "name_display": "Odari",
           "verify_status": "verified", "geocode": {"lat": 37.56, "lng": 126.98},
           "booking": {"required": True},
           "sources": [_src("official", official=True), _src("guide", "en")]}
    # 2) gate: itinerary referencing only the verified POI passes
    itin = {"title": "t", "checklist": [],
            "days": [{"date": "2026-06-12", "label": "D1",
                      "rows": [{"time": "12:00", "slot": "meal", "poi_id": "odari", "text": "lunch"}]}]}
    g = run_gate([poi], itin, advisory={"items": []})
    assert g["status"] == "pass", g["failures"]
    # 3) render the day from the canonical itinerary + poi map
    md = "### D1\n\n| 時段 | 行程 |\n|---|---|\n" + \
         "".join(render_day_table(d, {"odari": poi}).split("\n", 2)[2] for d in itin["days"])
    # 4) export-gate on the rendered deliverable passes (official link present, content ok)
    eg = run_export_gate(md, [poi], min_days=1)
    assert eg["status"] == "pass", eg["failures"]
