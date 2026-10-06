"""Print a trip's verified places as a Markdown table (v2.1.0 §10).

    python <plugin>/scripts/tripwork.py table <slug> [欄位… | 吃的 | 景點] [--out FILE]
    python <plugin>/scripts/tripwork.py table <slug> --page       # the survey's list page

Reads data/verified-pois.yaml and the brief (and data/calendar.yaml when there is one);
never the itinerary, so a survey's list and a planned trip print the same way. Fields are
named in Chinese, in the order given; a preset name stands for its list of fields and
also picks the rows (吃的: places to eat; 景點: places to visit). Rows are the verified
places, best rated first.
"""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py table <slug>")

import argparse
import datetime
import pathlib
import sys

import yaml

from scripts.paths import artifact_path
from scripts.render.gmaps_links import maps_url
from scripts.render.markdown import md_escape
from scripts.trip_calendar import WEEKDAYS, holiday_on, poi_closed_on
from scripts.verify import official_source_url, site_key

# category -> group. A literal because a category is free text (no shipped table to
# call): every category the corpus and the consumer workspace carry is listed, and
# tests/test_survey_table.py fails when a new one appears unlisted. Unlisted -> 其他.
_EAT = ("restaurant", "food", "cafe", "cafe_restaurant", "view_restaurant", "dessert", "breakfast",
        "drink", "bakery", "bbq", "chicken", "seafood")
_STAY = ("lodging", "hotel", "minsu", "resort", "villa_whole_house", "farm_stay")
_OTHER = ("sight", "trail", "attraction_trail", "onsen", "hotspring", "hot_spring", "beach",
          "fishing_village", "grassland", "cycling", "oldstreet", "museum", "nature", "market",
          "factory_tour", "rainy_backup", "cultural-village", "temple", "shrine", "zoo", "experience",
          "activity", "theme_park", "observation", "tower", "historic-walk", "mural-street",
          "shopping", "shopping-street", "shop", "department-store", "cosmetics-shop", "visit",
          "must_do", "alternative", "service_area", "parking", "transport", "logistics",
          "pharmacy", "supermarket")
CATEGORY_GROUP = {**{c: "吃的" for c in _EAT}, **{c: "住的" for c in _STAY}, **{c: "其他" for c in _OTHER}}
# not a place to visit, though grouped 其他: kept out of the 景點 preset
_ERRANDS = ("service_area", "parking", "transport", "logistics", "pharmacy", "supermarket")

_WEEKDAY_ZH = "一二三四五六日"
_STATUS = {"OPERATIONAL": "營業中", "CLOSED_TEMPORARILY": "暫停營業", "CLOSED_PERMANENTLY": "已歇業"}
FEW_REVIEWS = 30                     # warning ①: fewer reviews than this


def hours_text(hours):
    """'11:00–21:00（最後點餐 20:30）'; without an opening time only the closing half."""
    h = hours if isinstance(hours, dict) else {}
    if h.get("no_fixed_close"):
        return "全天開放"
    opening, close = h.get("open"), h.get("close")
    if not close:
        return f"{opening} 起" if opening else ""
    out = f"{opening}–{close}" if opening else f"～{close}"
    last = [f"最後點餐 {h['last_order']}"] if h.get("last_order") else []
    last += [f"最後入場 {h['last_entry']}"] if h.get("last_entry") else []
    return out + (f"（{'、'.join(last)}）" if last else "")


def _day(iso):
    d = datetime.date.fromisoformat(iso)
    return f"{d.month}/{d.day}（{_WEEKDAY_ZH[d.weekday()]}）"


def closed_text(poi, dates, calendar):
    """With dates: the days the place is closed. Without: its closing days as recorded.
    A public-holiday closure with no calendar.yaml (a survey runs no calendar-check) says so."""
    raw = [str(x).strip().lower() for x in poi.get("closed_days") or []]
    if not raw:
        return ""
    if not dates:
        names = [f"週{_WEEKDAY_ZH[WEEKDAYS.index(x)]}" if x in WEEKDAYS else
                 "國定假日" if x == "public_holiday" else x for x in raw]
        return "、".join(names) + "公休"
    out = []
    for d in dates:
        closed, _ = poi_closed_on(poi, d, calendar)
        if closed:
            h = holiday_on(d, calendar)
            label = h.get("name_display") or h.get("name_local") if h else None
            out.append(_day(d) + "公休" + (f"（{label}）" if label and "public_holiday" in raw
                                         and WEEKDAYS[datetime.date.fromisoformat(d).weekday()] not in raw else ""))
    if "public_holiday" in raw and calendar is None:
        out.append("國定假日公休（這幾天是否假日未查）")
    return "、".join(out)


def _rating(p):
    r = p.get("rating")
    return r if isinstance(r, dict) else {}


def _warning(p):
    r = _rating(p)
    out = ["評論少"] if isinstance(r.get("count"), int) and r["count"] < FEW_REVIEWS else []
    if r.get("note"):
        out.append(str(r["note"]))
    return "；".join(out)


def _sources(p):
    seen, out = set(), []
    first = official_source_url(p)
    urls = ([first] if first else []) + [s.get("url") for s in p.get("sources") or [] if isinstance(s, dict)]
    for u in urls:
        k = site_key(u) if u else None
        if k and k not in seen:
            seen.add(k)
            out.append(f"[{k}]({u})")
    return " ".join(out[:3])


FIELDS = {
    "名稱": lambda p, c: md_escape(p.get("name_display") or p.get("name_local") or ""),
    "類別": lambda p, c: md_escape(p.get("category") or ""),
    "區": lambda p, c: md_escape(p.get("district") or ""),
    "地址": lambda p, c: md_escape(p.get("address_local") or ""),
    "營業時間": lambda p, c: hours_text(p.get("hours")),
    "公休日": lambda p, c: closed_text(p, c["dates"], c["calendar"]),
    "訂位": lambda p, c: "要訂位" if (p.get("booking") or {}).get("required") else "",
    "簡介": lambda p, c: md_escape(p.get("intro") or ""),
    "評分": lambda p, c: (f"{_rating(p)['score']}（{md_escape(_rating(p).get('platform') or '')}）"
                        if _rating(p).get("score") is not None else ""),
    "評論數": lambda p, c: str(_rating(p)["count"]) if _rating(p).get("count") is not None else "",
    "評分警訊": lambda p, c: md_escape(_warning(p)),
    "營業狀態": lambda p, c: _STATUS.get(((p.get("business_status") or {}) if isinstance(
        p.get("business_status"), dict) else {}).get("status"), ""),
    "地圖連結": lambda p, c: f"[地圖]({maps_url(p)})",
    "來源": lambda p, c: _sources(p),
}
PRESETS = {
    "吃的": ["名稱", "區", "營業時間", "公休日", "訂位", "評分", "評論數", "評分警訊", "地圖連結"],
    "景點": ["名稱", "類別", "區", "營業時間", "公休日", "簡介", "地圖連結"],
}


def _in_preset(p, preset):
    group = CATEGORY_GROUP.get(str(p.get("category") or ""), "其他")
    if preset == "吃的":
        return group == "吃的"
    if preset == "景點":
        return group == "其他" and p.get("category") not in _ERRANDS
    return True


def rows_for(pois, preset):
    """The verified places a table lists, best rated first, then by name."""
    rows = [p for p in pois if isinstance(p, dict) and p.get("verify_status") == "verified"
            and _in_preset(p, preset)]
    return sorted(rows, key=lambda p: (-(_rating(p).get("score") or -1),
                                       p.get("name_display") or p.get("name_local") or ""))


def _dates(brief):
    d = (brief or {}).get("dates") or {}
    try:
        start, end = datetime.date.fromisoformat(str(d["start"])), datetime.date.fromisoformat(str(d["end"]))
    except (KeyError, TypeError, ValueError):
        return None
    return [(start + datetime.timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def render_table(pois, fields, brief, calendar=None):
    """Markdown table of `pois` (already chosen and ordered) with `fields`."""
    ctx = {"dates": _dates(brief), "calendar": calendar}
    lines = ["| " + " | ".join(fields) + " |", "|" + "---|" * len(fields)]
    for p in pois:
        lines.append("| " + " | ".join(FIELDS[f](p, ctx) for f in fields) + " |")
    return "\n".join(lines)


def _load(trip, name):
    p = artifact_path(trip, name)
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}) if p.is_file() else None


def _page(trip):
    """Write the survey's list page; refuse (2) when the brief cannot name it or the page
    fails the shipped HTML safety check."""
    from scripts.brief_names import is_survey, name_failures
    from scripts.export_gate import html_safety_failures
    from scripts.paths import deliverable_paths
    from scripts.render.reader.assets import FontPackageMissing
    from scripts.render.survey_page import render
    brief = _load(trip, "trip-brief.yaml") or {}
    if not is_survey(brief):              # a trip's html deliverable is its reader: never replace it
        print("--page is the survey's list page (mode: survey); this trip's page is its reader "
              "-- use `tripwork.py export`", file=sys.stderr)
        return 2
    pois = (_load(trip, "verified-pois.yaml") or {}).get("pois")
    bad = name_failures(brief)
    if bad or not isinstance(pois, list):
        print("\n".join(bad) or "no verified-pois — run verify first", file=sys.stderr)
        return 2
    try:
        html = render(pois, brief, _load(trip, "calendar.yaml"))
    except FontPackageMissing as exc:
        print(exc, file=sys.stderr)
        return 2
    unsafe = html_safety_failures(html)
    if unsafe:
        print("\n".join(unsafe), file=sys.stderr)
        return 2
    out = deliverable_paths(trip, brief)["html"]
    out.write_text(html, encoding="utf-8")
    print(f"list page: {out}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trip_dir")
    ap.add_argument("fields", nargs="*", help="欄位名稱，或 吃的 / 景點")
    ap.add_argument("--out", default=None, help="also write the table to this file")
    ap.add_argument("--page", action="store_true",
                    help="write the list page (trips/<slug>/<short_name> 清單.html) instead of a table")
    args = ap.parse_args(argv)
    if args.page:
        return _page(pathlib.Path(args.trip_dir))
    preset = next((f for f in args.fields if f in PRESETS), None)
    fields = []
    for f in args.fields:
        fields += PRESETS[f] if f in PRESETS else [f]
    unknown = [f for f in fields if f not in FIELDS]
    if unknown:
        print(f"沒有這個欄位：{'、'.join(unknown)}。可用：{'、'.join(FIELDS)}；或 {'、'.join(PRESETS)}",
              file=sys.stderr)
        return 2
    trip = pathlib.Path(args.trip_dir)
    pois = (_load(trip, "verified-pois.yaml") or {}).get("pois")
    if not isinstance(pois, list):
        print(f"{artifact_path(trip, 'verified-pois.yaml')} has no pois — run verify first", file=sys.stderr)
        return 2
    table = render_table(rows_for(pois, preset), fields or PRESETS["景點"], _load(trip, "trip-brief.yaml") or {},
                         _load(trip, "calendar.yaml"))
    print(table)
    if args.out:
        pathlib.Path(args.out).write_text(table + "\n", encoding="utf-8")
    return 0
