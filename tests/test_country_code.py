"""v2.1.0 §2 (D4): Taiwan's names map to `tw` without a lookup; a country no lookup can
name stops verify instead of silently searching the whole world."""
import datetime

import pytest
import requests
import yaml

from scripts import geocode as G
from scripts import source_verify_run as svr
from scripts.geocode_cache import cache_key
from scripts.paths import artifact_path


@pytest.mark.parametrize("name", ["台灣", "臺灣", "Taiwan", "taiwan ", "中華民國", "ROC"])
def test_taiwan_names_map_without_network(name):
    assert G.country_code(name) == "tw"          # conftest fails any unmocked Nominatim request


def test_cached_miss_does_not_override_table():
    cache = {}
    from scripts.geocode_cache import cache_put
    cache_put(cache, cache_key("台灣", "@country", None), None)
    assert G.country_code("台灣", cache=cache) == "tw"


def test_offline_never_connects():
    assert G.country_code("日本", offline=True) is None


def test_network_error_propagates(monkeypatch):
    def boom(*a, **kw):
        raise requests.exceptions.ConnectionError("down")
    monkeypatch.setattr(G, "geocode_country", boom)
    with pytest.raises(requests.exceptions.ConnectionError):
        G.country_code("日本")


def _trip(tmp_path, country):
    t = tmp_path / "trips" / "t"
    for name, doc in (("trip-brief.yaml", {"destination": {"country": country, "city": "示意市",
                                                            "local_lang": "zh-TW"}}),
                      ("candidates.yaml", {"candidates": [{
                          "id": "a", "name_local": "示意食堂", "name_display": "示意食堂",
                          "claimed_district": "示意區",
                          "business_status": {"status": "OPERATIONAL", "source_url": "https://a.example/",
                                              "as_of": datetime.date.today().isoformat()},
                          "sources": [{"url": "https://a.example/", "lang": "zh-TW"},
                                      {"url": "https://b.example/", "lang": "zh-TW"}]}]})):
        p = artifact_path(t, name)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return t


def test_unknown_country_stops_verify(tmp_path, monkeypatch, capsys):
    t = _trip(tmp_path, "亞特蘭提斯")
    monkeypatch.setattr(G, "geocode_country", lambda *a, **kw: None)
    called = []
    monkeypatch.setattr(svr, "resolve_place", lambda *a, **kw: called.append(a) or (None, None))
    code = svr.main([str(t), "--work-dir", str(tmp_path / "work" / "t")])
    assert code == 2
    err = capsys.readouterr().err
    assert "請在 trip-brief 把 destination.country 寫成兩碼國碼，例如 JP" in err
    assert called == []


def test_offline_verify_does_not_stop_on_country(tmp_path):
    t = _trip(tmp_path, "亞特蘭提斯")
    assert svr.main([str(t), "--work-dir", str(tmp_path / "work" / "t"), "--offline"]) in (0, 1)
