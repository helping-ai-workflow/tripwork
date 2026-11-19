"""A made-up Kamakura day trip on the README demo (public landmarks, 示意 shops): its
hotel is in Asakusa, ~49 km away; three street shops share one approximate point; two
shops are inside one 示意 building. Shared by the #38 map tests."""
import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "docs" / "images" / "readme"))
import demo_trip as D                                                     # noqa: E402
from tests import mech_fixtures as M                                     # noqa: E402
from tests.reader_fixture import _closing, _mv, _stop                    # noqa: E402

H = {"close": "18:00", "last_entry": "17:30", "typical_visit_mins": 40, "as_of": "2026-04-01"}
F = {"close": "19:00", "last_order": "18:30", "typical_visit_mins": 20, "as_of": "2026-04-01"}


def pois():
    P = [D.poi("hachimangu", "鶴岡八幡宮", "鶴岡八幡宮", "sight", 35.3259, 139.5566, H, "鎌倉"),
         D.poi("komachi", "小町通り", "小町通", "sight", 35.3204, 139.5527, H, "鎌倉"),
         D.poi("k-shop1", "示意せんべい", "示意仙貝", "food", 35.3204, 139.5527, F, "鎌倉"),
         D.poi("k-shop2", "示意だんご", "示意糰子", "food", 35.3204, 139.5527, F, "鎌倉"),
         D.poi("k-shop3", "示意プリン", "示意布丁", "food", 35.3204, 139.5527, F, "鎌倉"),
         D.poi("hasedera", "長谷寺", "長谷寺", "sight", 35.3125, 139.5332, H, "長谷"),
         D.poi("daibutsu", "鎌倉大仏（高徳院）", "鎌倉大佛", "sight", 35.3167, 139.5357, H, "長谷"),
         D.poi("store", "示意百貨 鎌倉", "示意百貨", "sight", 35.3190, 139.5505, H, "鎌倉"),
         D.poi("s-a", "示意菓子 鎌倉店", "示意菓子", "food", 35.3190, 139.5505, F, "鎌倉"),
         D.poi("s-b", "示意茶舗 鎌倉店", "示意茶舖", "food", 35.3190, 139.5505, F, "鎌倉")]
    for p in P:
        if p["id"].startswith("k-shop"):
            p["geocode"]["geocode_source"] = "cluster_fallback"
        if p["id"] in ("s-a", "s-b"):
            p["inside"] = "store"
            p["geocode"]["parent"] = "store"
    return P


def day():
    rows = [_mv("rail", 50, 60, basis="sourced", text="JR 橫須賀線到鎌倉", source_url="https://rail.example/y"),
            _stop("visit", "09:30", "hachimangu", "參拜"), _mv("walk", 0.7, 10),
            _stop("visit", "10:30", "komachi", "逛小町通"), _mv("walk", 0.05, 1),
            _stop("meal", "10:50", "k-shop1", "仙貝"), _mv("walk", 0.05, 1),
            _stop("meal", "11:10", "k-shop2", "糰子"), _mv("walk", 0.05, 1),
            _stop("meal", "11:30", "k-shop3", "布丁"), _mv("walk", 0.4, 6),
            _stop("meal", "12:00", "s-a", "伴手禮"), _mv("walk", 0.05, 1),
            _stop("meal", "12:20", "s-b", "抹茶"),
            _mv("rail", 2.5, 10, basis="sourced", text="江之電到長谷", source_url="https://rail.example/e"),
            _stop("visit", "13:30", "daibutsu", "大佛"), _mv("walk", 0.6, 10),
            _stop("visit", "14:30", "hasedera", "長谷寺"),
            _mv("rail", 52, 70, basis="sourced", text="回淺草", source_url="https://rail.example/b")]
    return {"date": "2026-05-14", "lodging": "demo-hotel", "theme": "鎌倉一日遊", "theme_refs": ["hachimangu"],
            "theme_candidates": D.six(["鎌倉一日遊"] * 6, "hachimangu"), "rows": rows}


def build(root, fetch):
    """(day-maps doc, reader html) for the trip with the Kamakura day as D3."""
    from scripts.day_maps import build as maps
    from scripts.paths import artifact_path
    itin = D.itinerary()
    itin["days"][2]["date"] = "2026-05-15"
    d, allp = day(), D.POIS + pois()
    _closing(d["rows"], {p["id"]: p for p in allp + [D.HOTEL]})
    itin["days"].insert(2, d)
    b = D.brief()
    b["dates"]["end"] = "2026-05-15"
    res = copy.deepcopy(D.RESERVATIONS)
    for r in res["reservations"]:
        if r["date"] == "2026-05-14":
            r["date"] = "2026-05-15"
    t, w = M.build_full_trip(root, slug="2026-05-tokyo-demo")
    for name, doc in (("trip-brief.yaml", b), ("verified-pois.yaml", {"pois": allp}), ("accommodations.yaml", D.ACC),
                      ("legs.yaml", D.LEGS), ("reservations.yaml", res), ("itinerary.yaml", itin)):
        M.write_artifact(artifact_path(t, name), doc)
    doc = maps(t, w, fetch=fetch)
    from scripts.render.reader import render_reader
    html = render_reader(itin, {p["id"]: p for p in allp + [D.HOTEL]}, brief=b, accommodations=D.ACC,
                         advisory=D.R.ADVISORY, legs=D.LEGS, maps=doc, reservations=res)
    return doc, html
