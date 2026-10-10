"""v2.1.0 §9 (D10): home is drawn on the first and last day's map -- one map with the
first / last stop when its leg is short, a small map of its own when far."""
import json
import pathlib

import jsonschema
import pytest

from scripts import day_maps
from scripts.paths import artifact_path
from scripts.render.reader import maps as M
from scripts.render.reader.page import _context
from scripts.rederive import MAX_HOP_MINS
from tests.mech_fixtures import write_artifact

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOME = {"name": "示意超商", "lat": 24.9983, "lng": 121.5810, "geocode_source": "nominatim"}
BACK = {"name": "示意公園", "lat": 25.0330, "lng": 121.5654, "geocode_source": "nominatim"}


def _p(pid, lat, lng, cat="sight"):
    return {"id": pid, "name_local": pid, "name_display": pid, "category": cat, "verify_status": "verified",
            "geocode": {"lat": lat, "lng": lng, "geocode_source": "nominatim"}}


POIS = {"a1": _p("a1", 24.83, 121.77), "a2": _p("a2", 24.84, 121.78), "h": _p("h", 24.82, 121.77, "lodging")}


def _home_mv(li):
    return {"slot": "move", "text": "移動", "leg_index": li}


def _trip(first=50, last=75, rows1=None, rows2=None, legs=None, brief=None, days=2):
    legs = legs if legs is not None else [
        {"from": "家", "to": "礁溪", "mode": "drive", "kind": "home", "duration_mins": first},
        {"from": "礁溪", "to": "家", "mode": "drive", "kind": "home", "duration_mins": last}]
    d1 = {"date": "2030-01-07", "rows": rows1 if rows1 is not None else
          [_home_mv(0), {"slot": "visit", "time": "10:00", "poi_id": "a1"}], "lodging": "h"}
    d2 = {"date": "2030-01-08", "rows": rows2 if rows2 is not None else
          [{"slot": "visit", "time": "10:00", "poi_id": "a2"}, _home_mv(1)]}
    if days == 1:
        d1 = {"date": "2030-01-07", "rows": [_home_mv(0), {"slot": "visit", "time": "10:00", "poi_id": "a1"},
                                             _home_mv(1)]}
    b = brief if brief is not None else {"home_origin": "家", "home_return": "家",
                                         "home_origin_point": HOME, "home_return_point": BACK}
    itin = {"days": [d1] if days == 1 else [d1, d2]}
    return _context(itin, POIS, b, {"stops": []}, None, {"legs": legs})


def _keys(ctx, i):
    return [(s, p["key"]) for s, p in M.day_points(ctx, i, ctx.days[i - 1])]


def test_day1_starts_at_home_last_day_ends_at_home():
    ctx = _trip()
    assert _keys(ctx, 1)[0] == (0, "home-start")
    assert _keys(ctx, 2)[-1][1] == "home-end"
    first = M.day_points(ctx, 1, ctx.days[0])[0][1]
    assert first["poi"]["id"] == "home-origin" and first["kind"] == "home"
    assert first["poi"]["geocode"] == {"lat": HOME["lat"], "lng": HOME["lng"], "geocode_source": "nominatim"}


def test_only_origin_point_draws_start_only():
    ctx = _trip(brief={"home_origin_point": HOME})
    assert _keys(ctx, 1)[0][1] == "home-start"
    assert "home-end" not in [k for _, k in _keys(ctx, 2)]


def test_string_only_home_draws_nothing():
    ctx = _trip(brief={"home_origin": "家", "home_return": "家"})
    assert not any(k.startswith("home") for _, k in _keys(ctx, 1) + _keys(ctx, 2))


def test_home_leg_within_max_hop_joins_first_segment():
    ctx = _trip(first=MAX_HOP_MINS)                                   # <=, like classify_hop
    assert {s for s, _ in _keys(ctx, 1)} == {0}


def test_home_leg_over_max_hop_is_own_segment():
    ctx = _trip(last=MAX_HOP_MINS + 1)
    pts = M.day_points(ctx, 2, ctx.days[1])
    segs = M._segments(pts)
    assert [p["key"] for p in segs[-1]] == ["home-end"]               # kept, a map of its own


def test_brief_max_hop_overrides_default():
    ctx = _trip(first=50, brief={"home_origin_point": HOME, "routing": {"max_hop_mins": 30}})
    assert [p["key"] for p in M._segments(M.day_points(ctx, 1, ctx.days[0]))[0]] == ["home-start"]


def test_multi_home_legs_decided_by_leg_touching_home():
    legs = [{"from": "家", "to": "車站", "mode": "rail", "kind": "home", "duration_mins": 90},
            {"from": "車站", "to": "礁溪", "mode": "taxi", "kind": "home", "duration_mins": 15},
            {"from": "礁溪", "to": "家", "mode": "drive", "kind": "home", "duration_mins": 40}]
    ctx = _trip(legs=legs, rows1=[_home_mv(0), _home_mv(1), {"slot": "visit", "time": "10:00", "poi_id": "a1"}],
                rows2=[{"slot": "visit", "time": "10:00", "poi_id": "a2"}, _home_mv(2)])
    segs = M._segments(M.day_points(ctx, 1, ctx.days[0]))
    assert [p["key"] for p in segs[0]] == ["home-start"]              # the 90-minute rail leg decides


def test_home_leg_without_duration_is_far():
    legs = [{"from": "家", "to": "礁溪", "mode": "flight", "kind": "home"},
            {"from": "礁溪", "to": "家", "mode": "drive", "kind": "home", "duration_mins": 40}]
    ctx = _trip(legs=legs)
    assert [p["key"] for p in M._segments(M.day_points(ctx, 1, ctx.days[0]))[0]] == ["home-start"]


def test_home_point_without_home_leg_joins_segment():
    ctx = _trip(legs=[], rows1=[{"slot": "visit", "time": "10:00", "poi_id": "a1"}])
    assert {s for s, _ in _keys(ctx, 1)} == {0}


def test_same_origin_and_return_day_trip_merges():
    ctx = _trip(days=1, first=30, last=30, brief={"home_origin_point": HOME, "home_return_point": dict(HOME)})
    pts = M.day_points(ctx, 1, ctx.days[0])
    assert pts[0][1]["poi"] is pts[-1][1]["poi"]


def test_other_lone_segments_still_dropped():
    pts = [(0, {"key": "start", "kind": "lodging", "poi": POIS["h"]}),
           (1, {"key": "s1", "kind": "visit", "poi": POIS["a1"]}), (1, {"key": "s2", "kind": "visit", "poi": POIS["a2"]})]
    assert [[p["key"] for p in s] for s in M._segments(pts)] == [["s1", "s2"]]


def _trip_dir(tmp_path, home_lat=HOME["lat"]):
    t = tmp_path / "trips" / "t"
    write_artifact(artifact_path(t, "trip-brief.yaml"),
                   {"home_origin_point": {**HOME, "lat": home_lat}, "home_return_point": BACK})
    write_artifact(artifact_path(t, "verified-pois.yaml"), {"pois": list(POIS.values())})
    write_artifact(artifact_path(t, "itinerary.yaml"),
                   {"days": [{"date": "2030-01-07", "lodging": "h",
                              "rows": [_home_mv(0), {"slot": "visit", "time": "10:00", "poi_id": "a1"}]},
                             {"date": "2030-01-08", "rows": [{"slot": "visit", "time": "10:00", "poi_id": "a2"},
                                                             _home_mv(1)]}]})
    write_artifact(artifact_path(t, "legs.yaml"), {"legs": [
        {"from": "家", "to": "礁溪", "mode": "drive", "kind": "home", "duration_mins": 50},
        {"from": "礁溪", "to": "家", "mode": "drive", "kind": "home", "duration_mins": 75}]})
    return t


def _png():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (200, 200, 200)).save(buf, "PNG")
    return buf.getvalue()


def test_day_maps_home_segment_uses_tiles_and_closeup(tmp_path):
    t = _trip_dir(tmp_path)
    tile = _png()
    doc = day_maps.build(t, tmp_path / "work" / "t", fetch=lambda z, x, y: tile)
    d1, d2 = doc["days"]["2030-01-07"], doc["days"]["2030-01-08"]
    assert "home-origin" in d1[0]["poi_ids"] and "home-origin" in d1[0]["closeups"]
    assert d2[-1]["poi_ids"] == ["home-return"] and "home-return" in d2[-1]["closeups"]
    ctx = _context(*_ctx_inputs(t), maps=doc)
    card = M.map_card(ctx, 1, ctx.days[0])
    assert 'class="mimg' in card and 'data-poi="home-origin"' in card      # tiles drawn (images sit in the page css)


def _ctx_inputs(t):
    import yaml
    load = lambda n: yaml.safe_load(artifact_path(t, n).read_text(encoding="utf-8"))
    return (load("itinerary.yaml"), POIS, load("trip-brief.yaml"), {"stops": []}, None, load("legs.yaml"))


def test_moving_home_marks_segment_stale(tmp_path):
    t = _trip_dir(tmp_path)
    tile = _png()
    doc = day_maps.build(t, tmp_path / "work" / "t", fetch=lambda z, x, y: tile)
    moved = _trip_dir(tmp_path / "moved", home_lat=24.70)                 # home now outside the old image
    ctx = _context(*_ctx_inputs(moved), maps=doc)
    seg = M.map_card(ctx, 1, ctx.days[0]).split('class="mv mv-d1-all"')[1].split('class="mv ')[0]
    assert 'class="mimg' not in seg                                        # the schematic instead


def test_poi_id_cannot_be_home_id():
    s = json.loads((ROOT / "schemas" / "verified-pois.schema.json").read_text(encoding="utf-8"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate("home-origin", s["properties"]["pois"]["items"]["properties"]["id"])


def test_brief_schema_takes_home_points():
    s = json.loads((ROOT / "schemas" / "trip-brief.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(HOME, s["properties"]["home_origin_point"])
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"name": "x"}, s["properties"]["home_return_point"])


def test_schema_home_ids_are_the_maps_ids():
    s = json.loads((ROOT / "schemas" / "verified-pois.schema.json").read_text(encoding="utf-8"))
    assert tuple(s["properties"]["pois"]["items"]["properties"]["id"]["not"]["enum"]) == M.HOME_IDS


def test_home_chips_land_in_the_list():
    """Found by the v2.1.0 consumer-copy closure: home's chips linked to an anchor the
    day list did not have, and the export gate failed the page. Every map link lands."""
    import re
    from scripts.export_gate import html_safety_failures
    from scripts.render.reader import render_reader
    ctx = _trip()
    html = render_reader({"days": ctx.days}, POIS, brief=ctx.brief, legs=ctx.legs)
    assert not [f for f in html_safety_failures(html) if "missing target" in f]
    ids = set(re.findall(r'\sid="([^"]+)"', html))
    assert {"t-d1-home-start", "t-d2-home-end"} <= ids


def test_a_last_day_ending_at_a_hotel_still_lands_home():
    import re
    from scripts.render.reader import render_reader
    ctx = _trip()
    days = [dict(ctx.days[0]), dict(ctx.days[1], lodging="h")]
    html = render_reader({"days": days}, POIS, brief=ctx.brief, legs=ctx.legs)
    ids = set(re.findall(r'\sid="([^"]+)"', html))
    assert {"t-d2-end", "t-d2-home-end"} <= ids


def test_only_the_leg_touching_home_decides_a_flight_still_splits():
    """Final review: rail 40 min to the airport (near) then a 185-minute flight -- home must
    not share the destination's map; only the leg touching home may join it to anything."""
    legs = [{"from": "家", "to": "機場", "mode": "rail", "kind": "home", "duration_mins": 40},
            {"from": "機場", "to": "目的地", "mode": "flight", "kind": "home", "duration_mins": 185},
            {"from": "目的地", "to": "機場", "mode": "flight", "kind": "home", "duration_mins": 185},
            {"from": "機場", "to": "家", "mode": "rail", "kind": "home", "duration_mins": 40}]
    ctx = _trip(legs=legs, rows1=[_home_mv(0), _home_mv(1), {"slot": "visit", "time": "10:00", "poi_id": "a1"}],
                rows2=[{"slot": "visit", "time": "10:00", "poi_id": "a2"}, _home_mv(2), _home_mv(3)])
    d1 = M._segments(M.day_points(ctx, 1, ctx.days[0]))
    d2 = M._segments(M.day_points(ctx, 2, ctx.days[1]))
    assert [p["key"] for p in d1[0]] == ["home-start"]
    assert [p["key"] for p in d2[-1]] == ["home-end"]
