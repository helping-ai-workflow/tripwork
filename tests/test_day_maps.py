"""v1.0 P5 — the day-maps side-file: schema, and the generator with an injected
tile fetcher (no network in tests)."""
import copy
import io
import json

import pytest
import yaml

from scripts.validate_artifact import SCHEMAS, validate_file
from tests.reader_fixture import PNG


def _errors(doc):
    import jsonschema
    schema = json.loads((SCHEMAS / "day-maps.schema.json").read_text(encoding="utf-8"))
    return list(jsonschema.Draft7Validator(schema).iter_errors(doc))


GOOD = {"attribution": "© OpenStreetMap contributors",
        "days": {"2026-10-13": [{"image": {"data": PNG, "width": 10, "height": 8},
                                 "bbox": {"north": 1, "south": 0, "east": 1, "west": 0},
                                 "closeups": {}}]}}


def test_a_good_side_file_is_valid():
    assert _errors(GOOD) == []


@pytest.mark.parametrize("mutate", [
    lambda d: d["days"]["2026-10-13"][0]["image"].__setitem__("data", "https://x.example/t.png"),
    lambda d: d.pop("attribution"),
    lambda d: d["days"]["2026-10-13"][0]["bbox"].pop("west"),
    lambda d: d.__setitem__("attribution", "© Some Other Tiles"),   # the gate requires OSM's credit
])
def test_bad_side_files_are_rejected(mutate):
    doc = copy.deepcopy(GOOD)
    mutate(doc)
    assert _errors(doc)


def test_the_validator_knows_the_side_file():
    from scripts.paths import artifact_names
    assert "day-maps.yaml" in artifact_names()


def _tile():
    pytest.importorskip("PIL")      # the generator is the optional [maps] extra; CI installs it
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), (200, 210, 190)).save(buf, "PNG")
    return buf.getvalue()


def test_the_generator_writes_a_valid_side_file(tmp_path):
    from scripts.day_maps import USER_AGENT, build
    from scripts.paths import artifact_path
    from tests.mech_fixtures import build_full_trip
    t, w = build_full_trip(tmp_path)
    calls = []

    def fetch(z, x, y):
        calls.append((z, x, y))
        return _tile()

    doc = build(t, w, fetch=fetch)
    assert _errors(doc) == []
    assert doc["days"]["2026-08-01"][0]["poi_ids"]
    out = artifact_path(t, "day-maps.yaml")
    assert out.is_file() and validate_file(out)[0] == 0
    day = doc["days"]["2026-08-01"][0]
    assert day["image"]["width"] <= 1400 and day["image"]["data"].startswith("data:image/jpeg")
    close = day["closeups"]["poi-1"]["image"]
    assert (close["width"], close["height"]) == (640, 480)
    assert "@" not in USER_AGENT and "github.com/helping-ai-workflow/tripwork" in USER_AGENT
    n = len(calls)
    build(t, w, fetch=fetch)                    # second run: every tile from the cache
    assert len(calls) == n


def test_offline_uses_the_cache_and_never_writes_blank_maps(tmp_path):
    from scripts.day_maps import build
    from scripts.paths import artifact_path
    from tests.mech_fixtures import build_full_trip
    t, w = build_full_trip(tmp_path)
    with pytest.raises(LookupError):
        build(t, w, offline=True)                       # nothing cached yet
    assert not artifact_path(t, "day-maps.yaml").exists()
    build(t, w, fetch=lambda z, x, y: _tile())         # warm the cache
    assert build(t, w, offline=True)["days"]


def test_tiles_are_pasted_where_the_bbox_says(tmp_path):
    """A coloured tile per (x, y): the pixel under a projected point must carry the
    colour of the tile _world puts that point in -- a swapped paste shows up here."""
    pytest.importorskip("PIL")
    import base64
    from PIL import Image
    from scripts.day_maps import _world, build
    from scripts.render.reader.maps import project
    from tests.mech_fixtures import build_full_trip
    t, w = build_full_trip(tmp_path)

    def colour(z, x, y):
        return ((x * 67) % 256, (y * 131) % 256, (z * 29) % 256)

    def fetch(z, x, y):
        buf = io.BytesIO()
        Image.new("RGB", (256, 256), colour(z, x, y)).save(buf, "PNG")
        return buf.getvalue()

    doc = build(t, w, fetch=fetch)
    from scripts.gate import poi_pool
    from scripts.paths import artifact_path

    def load(name):
        return yaml.safe_load(artifact_path(t, name).read_text(encoding="utf-8"))
    pois = poi_pool(load("verified-pois.yaml")["pois"], load("accommodations.yaml"))
    checked = 0
    for entries in doc["days"].values():
        for e in entries:
            for pid, close in e["closeups"].items():
                g = pois[pid]["geocode"]
                img = Image.open(io.BytesIO(base64.b64decode(close["image"]["data"].split(",", 1)[1])))
                x, y = project(g["lat"], g["lng"], close["bbox"], img.width, img.height)
                wx, wy = _world(g["lat"], g["lng"], 16)
                want = colour(16, int(wx // 256), int(wy // 256))
                got = img.getpixel((int(x), int(y)))
                assert all(abs(a - b) <= 12 for a, b in zip(got, want)), (pid, got, want)   # JPEG q70
                checked += 1
    assert checked >= 2


def test_overviews_are_43_and_hold_every_point(tmp_path):
    """v1.1 §9: the phone's map frame is full-width 4:3; an overview at any other ratio
    would be cropped and could lose an edge pin."""
    from scripts.day_maps import build
    from scripts.render.reader.maps import COVER_TOLERANCE
    from tests.mech_fixtures import build_full_trip
    t, w = build_full_trip(tmp_path)
    doc = build(t, w, fetch=lambda z, x, y: _tile())
    assert doc["days"]
    for entries in doc["days"].values():
        for e in entries:
            iw, ih = e["image"]["width"], e["image"]["height"]
            assert abs((iw / ih) / (4 / 3) - 1) <= COVER_TOLERANCE / 3, (iw, ih)
            assert iw >= 480 and ih >= 360
    # review I4: "hold every point" -- every stop the reader pins on a mapped segment is
    # in one of the day's images, inside that image's bbox (the same helpers build() maps from)
    import yaml
    from scripts.gate import poi_pool
    from scripts.paths import artifact_path
    from scripts.render.reader.maps import _geo, _segments, day_points
    from scripts.render.reader.page import _context
    load = lambda n: yaml.safe_load(artifact_path(t, n).read_text(encoding="utf-8")) or {}
    acc = load("accommodations.yaml") or {"stops": []}
    ctx = _context(load("itinerary.yaml"), poi_pool(load("verified-pois.yaml")["pois"], acc),
                   load("trip-brief.yaml"), acc, None, load("legs.yaml") or {"legs": []})
    checked = 0
    for i, day in enumerate(ctx.days, start=1):
        entries = doc["days"].get(str(day.get("date"))) or []
        for pt in (pt for seg in _segments(day_points(ctx, i, day)) for pt in seg):
            pid = pt["poi"].get("id")
            holders = [e for e in entries if pid in e["poi_ids"]]
            assert holders, (day.get("date"), pid)
            lat, lng = _geo(pt["poi"])
            for e in holders:
                b = e["bbox"]
                assert b["west"] < lng < b["east"] and b["south"] < lat < b["north"], (pid, b)
                checked += 1
    assert checked >= 2


def test_a_stop_alone_in_its_segment_still_gets_a_close_up(tmp_path):
    """trip-e D3 / D4: the hotel, then a long train first thing -- the hotel is a
    segment of one, which builds no entry, so its 出發 view was a blank schematic. Every
    mapped stop must have a close-up somewhere in the side-file."""
    from scripts.day_maps import build
    from scripts.gate import poi_pool
    from scripts.paths import artifact_path
    from scripts.render.reader.maps import _geo, day_points
    from scripts.render.reader.page import _context
    from tests.mech_fixtures import build_full_trip, write_artifact
    t, w = build_full_trip(tmp_path)
    load = lambda n: yaml.safe_load(artifact_path(t, n).read_text(encoding="utf-8")) or {}
    itin = load("itinerary.yaml")
    # hotel-1 is reached by a long leg (D1's last move) and left by one (D2's first), so
    # it is a segment of one on BOTH days -- no entry anywhere carries its close-up
    itin["days"][0]["rows"][2] = {"slot": "move", "text": "特急", "leg_index": 0}
    itin["days"][1]["rows"][0] = {"slot": "move", "text": "特急", "leg_index": 0}
    write_artifact(artifact_path(t, "itinerary.yaml"), itin)
    write_artifact(artifact_path(t, "legs.yaml"), {"legs": [{"from": "a", "to": "b", "mode": "rail",
                                                             "duration_mins": 90, "status": "ok", "sources": []}]})
    doc = build(t, w, fetch=lambda z, x, y: _tile())
    acc = load("accommodations.yaml") or {"stops": []}
    ctx = _context(load("itinerary.yaml"), poi_pool(load("verified-pois.yaml")["pois"], acc),
                   load("trip-brief.yaml"), acc, None, load("legs.yaml"))
    have = set(doc.get("closeups") or {})
    for entries in doc["days"].values():
        for e in entries:
            have |= set(e["closeups"])
    want = {pt["poi"]["id"] for i, d in enumerate(ctx.days, 1) for _, pt in day_points(ctx, i, d) if _geo(pt["poi"])}
    assert "hotel-1" in want and want <= have, want - have
    assert validate_file(str(artifact_path(t, "day-maps.yaml")))[0] == 0
