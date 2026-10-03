"""Minimal schema-valid full-trip fixture for the mechanized-gate CLIs.

One deterministic single-base 2-day trip. Every artifact passes the D1
validator; the itinerary passes run_gate; the exports pass run_export_gate /
run_html_gate. Shared by test_gate_cli / test_export_gate CLI tests /
test_next_stage / test_e2e_mechanized_pipeline.
"""
import datetime
import os
import pathlib

import yaml

SLUG = "2026-08-testtrip"

# The corpus the corpus guards measure: four real consumer trips, de-identified and
# shipped with the plugin under tests/corpus/ (slugs trip-a..trip-d, members 成員N,
# hotels and home endpoints replaced, YAML comments dropped), so the guards run
# everywhere, CI included. TRIPWORK_CORPUS points them at another corpus.
CORPUS = pathlib.Path(os.environ.get(
    "TRIPWORK_CORPUS", str(pathlib.Path(__file__).resolve().parent / "corpus")))
# The four trips whose artifacts pass validate_artifact. Adding a trip here is a
# deliberate act, not automatic.
CORPUS_TRIPS = ("trip-a", "trip-b", "trip-c", "trip-d")


def corpus_dir(trip):
    """Where one corpus trip's artifacts are, measured as the trip stands: its root
    while any artifact is still there (pre-v1.0 or half-migrated), data/ once
    migrated. The ONE place corpus guards resolve a trip; never CORPUS / trip."""
    from scripts.paths import data_dir, is_legacy_layout
    d = CORPUS / trip
    return d if is_legacy_layout(d) or not data_dir(d).is_dir() else data_dir(d)


def load_trip(trip):
    """Every artifact of one corpus trip, as the gate CLI would load them
    (absent optional artifacts become None, exactly like scripts/gate.py's
    `opt()`)."""
    d = corpus_dir(trip)

    def opt(name):
        p = d / name
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.is_file() else None

    return {"pois": opt("verified-pois.yaml"), "itinerary": opt("itinerary.yaml"),
            "accommodations": opt("accommodations.yaml"),
            "calendar": opt("calendar.yaml"), "advisory": opt("advisory.yaml"),
            "legs": opt("legs.yaml"), "routing": opt("routing.yaml"),
            "cost": opt("cost.yaml"), "brief": opt("trip-brief.yaml") or {}}

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

# HTML_DELIVERABLE is rendered by the real reader at the end of this module (v1.0 P4).


def write_artifact(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
                    encoding="utf-8")
    return path


# v1.0 P1: every fixture passes the reader-data checks. must_do is [] in these
# fixtures, so headline refs are waived (scripts/brief_names.py) and may stay [].
HEADLINE_CANDIDATES = [
    {"text": "五稜郭看完先吃午餐", "device": "contrast", "refs": []},
    {"text": "為了午餐走遍五稜郭", "device": "exaggerate", "refs": []},
    {"text": "五稜郭看我們吃午餐", "device": "pov", "refs": []},
    {"text": "五稜郭吃午餐", "device": "swap", "riff_on": "午餐吃五稜郭", "refs": []},
    {"text": "五稜郭的午餐好吃", "device": "pun", "riff_on": "五稜郭的午餐很好吃", "refs": []},
    {"text": "五稜郭的午餐很有料", "device": "double_meaning", "riff_on": "很有料", "refs": []},
]


def brief_name_fields():
    import copy
    return {"short_name": "測試", "headline": {"text": HEADLINE_CANDIDATES[0]["text"]},
            "headline_candidates": copy.deepcopy(HEADLINE_CANDIDATES)}


def move_row(**kw):
    """A complete estimated move row. The taxi default (5 km / 15 min) clears
    rederive_moves for poi-1 <-> hotel-1 (~3.7 km straight): 5 >= 0.95 x 3.7 and
    15 >= the drive floor. Check it with scripts/distance.py if coordinates change."""
    row = {"slot": "move", "text": "移動", "mode": "taxi", "mins": 15, "km": 5,
           "basis": "estimated", "estimate_method": "直線距離乘 1.4 估算"}
    row.update(kw)
    return row


def _complete_source_records(sources):
    for s in sources or []:
        s.setdefault("site", "測試網站")
        s.setdefault("note", "測試說明")
        if not str(s.get("lang") or "").lower().startswith("zh"):
            s.setdefault("site_local", "test site")


def upgrade_to_v1(pois, itinerary, accommodations=None):
    """Bring a pre-v1.0 hand-built gate fixture up to the v1.0 reader-data rules
    WITHOUT changing what the calling test is about: complete every source
    record, label every stop, wrap each day into a chain whose moves are
    estimated from the endpoints' real coordinates (via the shipped
    scripts/rederive.py::_move_segments -- never a re-implementation of the
    endpoint walk), theme each day on its first stop, and structure free-text
    checklist items. Rows the test wrote (including leg_index moves) are kept.
    Mutates in place; returns (pois, itinerary)."""
    from scripts.distance import haversine_km, min_plausible_mins
    from scripts.gate import poi_pool
    from scripts.rederive import _move_segments, _point
    for p in pois:
        _complete_source_records(p.get("sources"))
    for stop in (accommodations or {}).get("stops") or []:
        district = stop.get("district") or ""
        stop.setdefault("area_label", district[:4] if len(district) >= 2 else "住宿")
        for c in stop.get("candidates") or []:
            _complete_source_records(c.get("sources"))
    by = poi_pool(pois, accommodations)
    for i, d in enumerate(itinerary.get("days") or []):
        chained = []
        for r in d.get("rows") or []:
            if r.get("slot") != "move" and (not chained or chained[-1].get("slot") != "move"):
                chained.append({"slot": "move", "text": "移動"})
            chained.append(r)
        if not chained or chained[-1].get("slot") != "move":
            chained.append({"slot": "move", "text": "移動"})
        d["rows"] = chained
        nodes = [r.get("poi_id") for r in chained if r.get("slot") != "move" and r.get("poi_id")]
        d.setdefault("theme", f"測試第{i + 1}天")
        d.setdefault("theme_refs", nodes[:1])
    from tests.title_fixture import add_titles          # v1.1 topic 7: six candidates a day
    add_titles(itinerary)
    for _date, _j, run, frm, to in _move_segments(itinerary):
        if any(r.get("leg_index") is not None for r in run) or all(r.get("mode") for r in run):
            continue
        pa, pb = _point(by, frm), _point(by, to)
        straight = haversine_km(pa[0], pa[1], pb[0], pb[1]) if pa and pb else 1.0
        for r in run:
            r.setdefault("mode", "none")
        if not (pa and pb and straight <= 0.3):
            run[0].update(mode="taxi", km=round(straight * 1.4 + 0.5, 1),
                          mins=int(min_plausible_mins(straight, "drive")) + 10,
                          basis="estimated", estimate_method="直線距離乘 1.4 估算")
    itinerary["checklist"] = [c if isinstance(c, dict) else {"kind": "出發前確認", "task": c}
                              for c in itinerary.get("checklist") or []]
    return pois, itinerary


WALK_IN = {"mode": "walk", "mins": 10, "km": 0.5}
CHECKLIST = [{"kind": "打包", "task": "battery: spare lithium batteries carry-on only"}]


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
        **brief_name_fields(),
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
    # geocode_source + resolved_name + business_status (TW-070, v0.34.0): so
    # rederive_pois re-derives poi-1 to the SAME 'verified' it's recorded as --
    # mirrors the geocode_source/resolved_name pair accommodations() already
    # carries for I2 (rederive_lodging). Without them the record is a genuine
    # verdicts_rule_current gap (correct behaviour for the real corpus, wrong
    # for this "everything passes" fixture). business_status.as_of is computed
    # at CALL time, never a literal: OPERATING_MAX_AGE_DAYS is 90, so a fixed
    # date would silently turn this fixture stale 90 days after it was written
    # (the same trap Task 2's two hardcoded-as_of tests hit and had to be
    # de-fused for).
    return {"pois": [{
        "id": "poi-1", "name_local": "五稜郭", "name_display": "五稜郭",
        "category": "sight", "district": "函館",
        "sources": [
            {"url": "https://official.example/goryokaku", "lang": "ja", "official": True,
             "site": "五稜郭官方網站", "site_local": "五稜郭公式サイト", "note": "開放時間與票價"},
            {"url": "https://guide.example/goryokaku", "lang": "zh",
             "site": "旅遊指南", "note": "交通方式"},
        ],
        "verify_status": "verified",
        "geocode": {"lat": 41.796, "lng": 140.757, "geocode_source": "nominatim"},
        "resolved_name": "五稜郭",
        "business_status": {"status": "OPERATIONAL",
                            "source_url": "https://official.example/goryokaku",
                            "as_of": datetime.date.today().isoformat()},
        # v0.33.0 (R4): both rows below schedule poi-1 at 12:00 with slot "meal",
        # so last_order is what closing_status actually reads; last_entry is also
        # given so the fixture stays valid if a row's slot ever changes to visit.
        "hours": {"close": "22:00", "last_order": "21:30", "last_entry": "21:30",
                  "typical_visit_mins": 60, "as_of": "2026-07-06"},
    }]}


def routing():
    return {"clusters": [{"district": "函館", "pois": ["poi-1"],
                          "centroid": {"lat": 41.79, "lng": 140.75}}],
            "hops": [], "warnings": []}


def accommodations():
    # Kana-named hotel + name_zh (v0.30.0): exercises the lodging gloss path —
    # the gate's kana_name_without_gloss check on the folded lodging POI is
    # satisfied by name_zh, mirroring verified-pois.
    # geocode_source + resolved_name (I2, v0.33.0) + business_status (Task 6,
    # v0.34.0): so run_gate's rederive_lodging re-derives this candidate to the
    # SAME 'verified' it's recorded as -- without them the record is a genuine
    # verdicts_rederivable / verdicts_rule_current gap (correct behaviour for
    # the real corpus, wrong for this "everything passes" fixture).
    # business_status.as_of is computed at CALL time, never a literal, the same
    # reason verified_pois() above computes its own: a fixed date would
    # silently turn this fixture stale 90 days after it was written.
    return {"stops": [{
        "district": "函館", "nights": 1, "chosen": "hotel-1", "area_label": "函館",
        "candidates": [{
            "id": "hotel-1", "name_local": "駅前ホテル",
            "name_display": "駅前ホテル", "name_zh": "車站前旅館",
            "facilities": [],
            "geocode": {"lat": 41.77, "lng": 140.73, "geocode_source": "nominatim"},
            "resolved_name": "駅前ホテル",
            "business_status": {"status": "OPERATIONAL",
                                "source_url": "https://hotel.example",
                                "as_of": datetime.date.today().isoformat()},
            "sources": [
                {"url": "https://hotel.example", "lang": "ja", "official": True,
                 "site": "車站前旅館官網", "site_local": "駅前ホテル公式", "note": "房型與入住時間"},
                {"url": "https://guide.example/hotel", "lang": "zh",
                 "site": "旅遊指南", "note": "位置"},
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
    from tests.title_fixture import add_titles          # v1.1 topic 7
    return add_titles({
        "title": "測試行程",
        "checklist": [dict(c) for c in CHECKLIST],
        "days": [
            {"date": "2026-08-01", "theme": "先吃五稜郭午餐", "theme_refs": ["poi-1"],
             "rows": [move_row(text="抵達後前往", **WALK_IN),
                      {"time": "12:00", "slot": "meal", "poi_id": "poi-1",
                       "text": "午餐", "closing_status": "ok"},
                      move_row(text="回旅館")],
             "lodging": "hotel-1"},
            {"date": "2026-08-02", "theme": "再吃一次五稜郭", "theme_refs": ["poi-1"],
             "rows": [move_row(text="出發"),
                      {"time": "12:00", "slot": "meal", "poi_id": "poi-1",
                       "text": "午餐", "closing_status": "ok"},
                      move_row(text="前往機場", **WALK_IN)]},
        ],
    })


def rederive_kwargs(**over):
    """The legs/routing/cost/trip_brief/accommodations bundle run_gate needs so
    verdict re-derivation has something to re-derive. Every existing run_gate
    call site that asserts status == 'pass' must pass **rederive_kwargs().

    accommodations defaults to {"stops": []} (I2, v0.33.0): rederive_lodging
    treats an ABSENT accommodations.yaml as a verdicts_rederivable failure, same
    as legs/routing/cost -- a call site that wants a real lodging fixture must
    override it explicitly, e.g. **rederive_kwargs(accommodations=MY_ACCOM),
    never a bare accommodations=MY_ACCOM alongside **rederive_kwargs() (that
    collides: run_gate() got multiple values for keyword argument
    'accommodations').

    v1.0 P1: run_gate checks short_name/headline on any trip_brief it is given,
    so the brief here carries complete names (brief_name_fields()).

    There is deliberately NO rederive=False switch: an off-switch would make a
    skipped check indistinguishable from a green one, which is the defect class
    the mechanism closes.
    """
    kw = {
        "legs": {"legs": []},
        "routing": {"clusters": [], "hops": [], "warnings": []},
        "cost": {"currency": "TWD", "as_of": "2026-08-07", "total": 0,
                 "line_items": []},
        "trip_brief": {"dates": {"start": "2026-08-29", "end": "2026-08-31"}, **brief_name_fields()},
        "accommodations": {"stops": []},
    }
    kw.update(over)
    return kw


def build_gate_inputs():
    """(pois, itin) pair that PASSES run_gate(advisory={"items": []},
    **rederive_kwargs()) as-is, so a caller can mutate `itin` in place (e.g.
    inject an em-dash into a row's text) and attribute any resulting failure
    to that one mutation.

    Deliberately a single day (not itinerary()'s two-day shape): a single day
    is its own last day, so the always-on `_day_has_lodging` floor over
    `days[:-1]` never fires and no `lodging` field is needed -- itinerary()'s
    day 1 `lodging: "hotel-1"` is REFERENCED (scripts/gate.py::_referenced_ids)
    but hotel-1 resolves only via a chosen accommodations candidate, which
    rederive_kwargs()'s default `accommodations={"stops": []}` does not carry,
    so pairing itinerary() with rederive_kwargs() bare fails on "day
    references unknown POI 'hotel-1'" independent of any AI-tone content.
    Confirmed empirically before this fixture was added.
    """
    from tests.title_fixture import add_titles          # v1.1 topic 7
    return verified_pois()["pois"], add_titles({
        "title": "測試行程",
        "checklist": [dict(c) for c in CHECKLIST],
        "days": [
            {"date": "2026-08-01", "theme": "五稜郭吃午餐", "theme_refs": ["poi-1"],
             "rows": [move_row(text="出發", **WALK_IN),
                      {"time": "12:00", "slot": "meal", "poi_id": "poi-1",
                       "text": "午餐", "closing_status": "ok"},
                      move_row(text="離開", **WALK_IN)]},
        ],
    })


def build_full_trip(root, slug=SLUG):
    """Write the complete v1.0 artifact set under root/trips/<slug> + work stamp.
    Every path comes from scripts/paths.py (data/ for artifacts, the brief's
    deliverable stem for the md/html), never a re-joined string."""
    from scripts.paths import artifact_path, deliverable_paths
    t = root / "trips" / slug
    w = root / "work" / slug
    w.mkdir(parents=True, exist_ok=True)
    (root / "work" / ".preflight-completed").touch()
    for name, doc in (("trip-brief.yaml", trip_brief()), ("advisory.yaml", advisory()),
                      ("candidates.yaml", candidates()), ("verified-pois.yaml", verified_pois()),
                      ("routing.yaml", routing()), ("accommodations.yaml", accommodations()),
                      ("legs.yaml", legs()), ("calendar.yaml", calendar()),
                      ("seasonal.yaml", seasonal()), ("transit.yaml", transit()),
                      ("cost.yaml", cost()), ("itinerary.yaml", itinerary())):
        write_artifact(artifact_path(t, name), doc)
    paths = deliverable_paths(t, trip_brief())
    paths["md"].write_text(MD_DELIVERABLE, encoding="utf-8")
    paths["html"].write_text(HTML_DELIVERABLE, encoding="utf-8")
    return t, w


def html_deliverable():
    """The HTML deliverable for this fixture trip, rendered by the shipped reader
    exactly as export-artifact renders it (never a hand-written stand-in)."""
    from scripts.gate import poi_pool
    from scripts.render.html_page import render_html_page
    poi_map = poi_pool(verified_pois()["pois"], accommodations())
    return render_html_page(itinerary(), poi_map, brief=trip_brief(), accommodations=accommodations(),
                            advisory=advisory(), legs=legs())


HTML_DELIVERABLE = html_deliverable()
