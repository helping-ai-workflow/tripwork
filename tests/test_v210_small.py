"""v2.1.0 §8 (D9) and §12: a lodging keeps its Google place id; small v2.0.0 leftovers."""
import json
import pathlib

import jsonschema

from scripts.gate import poi_pool
from scripts.render.gmaps_links import maps_url
from scripts.verify import classify_candidate
from tests.cli_helpers import run_main

ROOT = pathlib.Path(__file__).resolve().parent.parent
PID = "ChIJ0000000000000000000000"    # 27 chars, made up


def _accommodations():
    return {"stops": [{"district": "示意區", "nights": 1, "chosen": "h1", "candidates": [{
        "id": "h1", "name_local": "示意旅館", "name_display": "示意旅館", "gmaps_place_id": PID,
        "sources": [{"url": "https://h.example/", "lang": "zh-TW"}]}]}]}


def test_accommodations_schema_accepts_gmaps_place_id():
    schema = json.loads((ROOT / "schemas" / "accommodations.schema.json").read_text(encoding="utf-8"))
    cand = schema["properties"]["stops"]["items"]["properties"]["candidates"]["items"]
    assert "gmaps_place_id" in cand["properties"] and "gmaps" in cand["properties"]
    jsonschema.validate(PID, cand["properties"]["gmaps_place_id"])


def test_lodging_maps_link_carries_its_place_id():
    hotel = poi_pool([], _accommodations())["h1"]
    assert f"query_place_id={PID}" in maps_url(hotel)


def test_tripwork_call_prints_a_systemexit_message(capsys, monkeypatch):
    from scripts import tripwork

    class Stop:
        @staticmethod
        def main(argv):
            raise SystemExit("示意的停止訊息")
    monkeypatch.setattr(tripwork.importlib, "import_module", lambda name: Stop)
    assert tripwork._call("scripts.x", [], "next") == 1
    assert "示意的停止訊息" in capsys.readouterr().err


def test_run_main_prints_a_systemexit_message(monkeypatch):
    import sys
    import types
    mod = types.ModuleType("tw_stop_fixture")
    mod.main = lambda argv: (_ for _ in ()).throw(SystemExit("示意的停止訊息"))
    monkeypatch.setitem(sys.modules, "tw_stop_fixture", mod)
    r = run_main("tw_stop_fixture", [])
    assert r.returncode == 1 and "示意的停止訊息" in r.stderr


def _cand(urls):
    return {"sources": [{"url": u, "lang": "zh-TW"} for u in urls]}


def test_gate_1a_three_sources_on_one_site():
    _, note = classify_candidate(_cand(["https://a.example/1", "https://a.example/2", "https://a.example/3"]),
                                 True, True)
    assert "所有來源都在 a.example" in note


def test_gate_1a_two_sources_on_one_site_unchanged():
    _, note = classify_candidate(_cand(["https://a.example/1", "https://a.example/2"]), True, True)
    assert "both sources are on a.example" in note


def test_gate_1a_hostless_urls_are_not_counted():
    _, note = classify_candidate(_cand(["https://a.example/1", "tel:0212345678"]), True, True)
    assert note == "needs >=2 independent sources (distinct sites)"
