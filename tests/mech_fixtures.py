"""Minimal schema-valid full-trip fixture for the mechanized-gate CLIs.

One deterministic single-base 2-day trip. Every artifact passes the D1
validator; the itinerary passes run_gate; the exports pass run_export_gate /
run_html_gate. Shared by test_gate_cli / test_export_gate CLI tests /
test_next_stage / test_e2e_mechanized_pipeline.
"""
import pathlib

import yaml

SLUG = "2026-08-testtrip"

MD_DELIVERABLE = """## 測試行程

### 2026-08-01
| 時間 | 內容 |
|---|---|
| 12:00 | [五稜郭](https://www.google.com/maps/search/?api=1&query=%E4%BA%94%E7%A8%9C%E9%83%AD) 午餐 |
| 21:00 | [駅前ホテル（車站前旅館）](https://hotel.example) 入住 |

### 2026-08-02
| 時間 | 內容 |
|---|---|
| 12:00 | [五稜郭](https://www.google.com/maps/search/?api=1&query=%E4%BA%94%E7%A8%9C%E9%83%AD) 午餐 |

## 行前清單
- battery: spare lithium batteries carry-on only
"""

HTML_DELIVERABLE = """<h1>測試行程</h1>
<div class="day-card"><a href="https://www.google.com/maps/search/?api=1&query=%E4%BA%94%E7%A8%9C%E9%83%AD">五稜郭</a></div>
<div class="day-card"><a href="https://hotel.example">駅前ホテル（車站前旅館）</a></div>
"""


def write_artifact(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


def trip_brief():
    return {
        "slug": SLUG,
        "destination": {"country": "JP", "city": "Hakodate", "local_lang": "ja"},
        "dates": {"start": "2026-08-01", "end": "2026-08-02"},
        "members": [{"name": "A"}],
        "base": {"name": "駅前ホテル", "district": "函館"},
        "must_do": [],
        "constraints": [],
        "preferences": {},
    }


def advisory():
    return {"items": [{
        "topic": "battery", "rule": "spare lithium batteries carry-on only",
        "effective_date": "2026-01-01", "risk": "restricted",
        "sources": [
            {"url": "https://gov.example/battery", "official": True},
            {"url": "https://airline.example/battery", "official": False},
        ],
    }]}


def candidates():
    return {"candidates": [{
        "id": "poi-1", "name_local": "五稜郭", "name_display": "五稜郭",
        "category": "sight",
        "sources": [{"url": "https://guide.example/goryokaku", "lang": "zh"}],
    }]}


def verified_pois():
    return {"pois": [{
        "id": "poi-1", "name_local": "五稜郭", "name_display": "五稜郭",
        "category": "sight", "district": "函館",
        "sources": [
            {"url": "https://official.example/goryokaku", "lang": "ja", "official": True},
            {"url": "https://guide.example/goryokaku", "lang": "zh"},
        ],
        "verify_status": "verified",
        "geocode": {"lat": 41.796, "lng": 140.757},
    }]}


def routing():
    return {"clusters": [{"district": "函館", "pois": ["poi-1"],
                          "centroid": {"lat": 41.79, "lng": 140.75}}],
            "hops": [], "warnings": []}


def accommodations():
    # Kana-named hotel + name_zh (v0.30.0): exercises the lodging gloss path —
    # the gate's kana_name_without_gloss check on the folded lodging POI is
    # satisfied by name_zh, mirroring verified-pois.
    return {"stops": [{
        "district": "函館", "nights": 1, "chosen": "hotel-1",
        "candidates": [{
            "id": "hotel-1", "name_local": "駅前ホテル",
            "name_display": "駅前ホテル", "name_zh": "車站前旅館",
            "facilities": [], "geocode": {"lat": 41.77, "lng": 140.73},
            "sources": [
                {"url": "https://hotel.example", "lang": "ja", "official": True},
                {"url": "https://guide.example/hotel", "lang": "zh"},
            ],
            "verify_status": "verified",
        }],
    }]}


def legs():
    return {"legs": []}


def calendar():
    return {"holidays": []}


def seasonal():
    return {"items": [], "daylight": []}


def transit():
    return {"peak_windows": [], "walks": []}


def cost():
    return {"currency": "JPY", "line_items": [], "total": 0,
            "as_of": "2026-07-06", "estimate_note": "estimate"}


def itinerary():
    return {
        "title": "測試行程",
        "checklist": ["battery: spare lithium batteries carry-on only"],
        "days": [
            {"date": "2026-08-01",
             "rows": [{"time": "12:00", "slot": "meal", "poi_id": "poi-1",
                       "text": "午餐"}],
             "lodging": "hotel-1"},
            {"date": "2026-08-02",
             "rows": [{"time": "12:00", "slot": "meal", "poi_id": "poi-1",
                       "text": "午餐"}]},
        ],
    }


def rederive_kwargs(**over):
    """The legs/routing/cost/trip_brief bundle run_gate needs so verdict
    re-derivation has something to re-derive. Every existing run_gate call site
    that asserts status == 'pass' must pass **rederive_kwargs().

    There is deliberately NO rederive=False switch: an off-switch would make a
    skipped check indistinguishable from a green one, which is the defect class
    the mechanism closes.
    """
    kw = {
        "legs": {"legs": []},
        "routing": {"clusters": [], "hops": [], "warnings": []},
        "cost": {"currency": "TWD", "as_of": "2026-08-07", "total": 0,
                 "line_items": []},
        "trip_brief": {"dates": {"start": "2026-08-29", "end": "2026-08-31"}},
    }
    kw.update(over)
    return kw


def build_full_trip(root, slug=SLUG):
    """Write the complete artifact set under root/trips/<slug> + work stamp."""
    t = root / "trips" / slug
    w = root / "work" / slug
    w.mkdir(parents=True, exist_ok=True)
    (root / "work" / ".preflight-completed").touch()
    write_artifact(t / "trip-brief.yaml", trip_brief())
    write_artifact(t / "advisory.yaml", advisory())
    write_artifact(t / "candidates.yaml", candidates())
    write_artifact(t / "verified-pois.yaml", verified_pois())
    write_artifact(t / "routing.yaml", routing())
    write_artifact(t / "accommodations.yaml", accommodations())
    write_artifact(t / "legs.yaml", legs())
    write_artifact(t / "calendar.yaml", calendar())
    write_artifact(t / "seasonal.yaml", seasonal())
    write_artifact(t / "transit.yaml", transit())
    write_artifact(t / "cost.yaml", cost())
    write_artifact(t / "itinerary.yaml", itinerary())
    (t / "exports").mkdir(exist_ok=True)
    (t / "exports" / f"{slug}-itinerary.md").write_text(MD_DELIVERABLE, encoding="utf-8")
    (t / "exports" / f"{slug}-itinerary.html").write_text(HTML_DELIVERABLE, encoding="utf-8")
    return t, w
