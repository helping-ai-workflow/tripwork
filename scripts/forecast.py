"""Day-by-day weather forecast for the week before departure (#31).

    python <plugin>/scripts/tripwork.py forecast <slug> [--jma DATE=OFFICE/POINT ...]

Writes trips/<slug>/data/forecast.yaml. Official first: a day given `--jma` reads the
Japan Meteorological Agency's weekly forecast for that office (area code, e.g. 016000)
and temperature point (e.g. 札幌); `--jma all=OFFICE/POINT` covers every day. Any other
trip day inside the window gets a model forecast (Open-Meteo) at that night's lodging,
marked `kind: model`. Only the next FORECAST_DAYS days are written -- a day beyond that
has no entry and the reader says 尚無預報. Exit 0 ok / 1 fetch failed / 2 bad input."""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py forecast <slug>")

import datetime
import json
import pathlib
import sys
import urllib.parse
import urllib.request

import yaml

# #31 (user's pick, 2026-11-18): an official weekly forecast reaches 7 days; days past
# that are left unforecast rather than filled from a model whose error is too large.
FORECAST_DAYS = 7
JMA_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/{office}.json"
JMA_PAGE = "https://www.jma.go.jp/bosai/forecast/#area_type=offices&area_code={office}"
MODEL_URL = "https://api.open-meteo.com/v1/forecast"
TZ = datetime.timezone(datetime.timedelta(hours=9))

# JMA weather codes, in Chinese (the common ones; others fall back to the first digit)
JMA_CODES = {
    "100": "晴", "101": "晴時多雲", "102": "晴短暫雨", "103": "晴時有雨", "104": "晴短暫雪",
    "105": "晴時有雪", "110": "晴後多雲", "111": "晴後多雲", "112": "晴後有雨", "113": "晴後有雨",
    "114": "晴後有雨", "115": "晴後有雪", "116": "晴後有雪", "117": "晴後有雪",
    "200": "多雲", "201": "多雲時晴", "202": "多雲短暫雨", "203": "多雲時有雨", "204": "多雲短暫雪",
    "205": "多雲時有雪", "206": "多雲短暫雨或雪", "207": "多雲時有雨或雪", "208": "多雲短暫雷雨",
    "209": "霧", "210": "多雲後晴", "211": "多雲後晴", "212": "多雲後有雨", "213": "多雲後有雨",
    "214": "多雲後有雨", "215": "多雲後有雪", "216": "多雲後有雪", "217": "多雲後有雪",
    "218": "多雲後雨或雪", "260": "多雲短暫雪或雨", "270": "多雲時有雪或雨",
    "300": "雨", "301": "雨時晴", "302": "雨時停", "303": "雨時有雪", "311": "雨後晴",
    "313": "雨後多雲", "314": "雨後時有雪",
    "400": "雪", "401": "雪時晴", "402": "雪時停", "403": "雪時有雨", "411": "雪後晴",
    "413": "雪後多雲", "414": "雪後雨",
}
_FIRST = {"1": "晴", "2": "多雲", "3": "雨", "4": "雪"}
# WMO weather codes (the model's)
WMO = {0: "晴", 1: "晴時多雲", 2: "多雲", 3: "陰", 45: "霧", 48: "霧", 51: "毛毛雨", 53: "毛毛雨",
       55: "毛毛雨", 61: "小雨", 63: "雨", 65: "大雨", 66: "凍雨", 67: "凍雨", 71: "小雪", 73: "雪",
       75: "大雪", 77: "雪", 80: "陣雨", 81: "陣雨", 82: "大陣雨", 85: "陣雪", 86: "陣雪",
       95: "雷雨", 96: "雷雨", 99: "雷雨"}


class ForecastError(RuntimeError):
    pass


def _get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:          # noqa: S310 (https only)
        return json.loads(r.read().decode("utf-8"))


def jma_weather(code):
    code = str(code or "")
    return JMA_CODES.get(code) or _FIRST.get(code[:1], "")


def _flags(text):
    return {"snow": "雪" in text, "rain": "雨" in text}


def _num(v):
    try:
        return float(v) if v not in ("", None) else None
    except (TypeError, ValueError):
        return None


def jma_days(doc, office, point):
    """{date: day record} from a JMA forecast document's weekly block (and today's)."""
    out = {}
    for blk in doc if isinstance(doc, list) else []:
        series = blk.get("timeSeries") or []
        if len(series) < 2:
            continue
        weather, temps = series[0], series[1]
        area = (weather.get("areas") or [{}])[0]
        spot = next((a for a in temps.get("areas") or [] if (a.get("area") or {}).get("name") == point), None)
        if "tempsMax" not in (spot or {}) and "pops" not in area:
            continue                                   # not the weekly block
        for k, t in enumerate(weather.get("timeDefines") or []):
            day = str(t)[:10]
            text = jma_weather((area.get("weatherCodes") or [""] * (k + 1))[k])
            rec = {"date": day, "place": f"{(area.get('area') or {}).get('name', '')}／{point}".strip("／"),
                   "weather": text, "kind": "official", "source": "日本氣象廳 週間天氣預報",
                   "source_url": JMA_PAGE.format(office=office), **_flags(text)}
            pop = _num((area.get("pops") or [""] * (k + 1))[k])
            if pop is not None:
                rec["pop"] = int(pop)
            for key, src in (("tmin", "tempsMin"), ("tmax", "tempsMax")):
                v = _num(((spot or {}).get(src) or [""] * (k + 1))[k])
                if v is not None:
                    rec[key] = v
            out[day] = rec
    return out


def model_day(doc, day, place):
    d = (doc or {}).get("daily") or {}
    dates = d.get("time") or []
    if day not in dates:
        return None
    k = dates.index(day)
    pick = lambda name: (d.get(name) or [None] * (k + 1))[k]
    text = WMO.get(pick("weather_code"), "")
    rec = {"date": day, "place": place, "kind": "model", "source": "Open-Meteo（模型預報）",
           "source_url": MODEL_URL, **_flags(text)}
    if text:
        rec["weather"] = text
    if (pick("snowfall_sum") or 0) > 0:
        rec["snow"] = True
    for key, name in (("tmin", "temperature_2m_min"), ("tmax", "temperature_2m_max")):
        if _num(pick(name)) is not None:
            rec[key] = round(float(pick(name)))
    pop = _num(pick("precipitation_probability_max"))
    if pop is not None:
        rec["pop"] = int(pop)
    return rec


def build(trip_dir, jma=None, *, fetch=None, today=None, now=None):
    """Write data/forecast.yaml; returns the document. `jma` = {date or 'all': 'OFFICE/POINT'}."""
    from scripts.gate import poi_pool
    from scripts.paths import artifact_path
    fetch = fetch or _get_json
    today = today or datetime.datetime.now(TZ).date()
    t = pathlib.Path(trip_dir)
    load = lambda n: (yaml.safe_load(artifact_path(t, n).read_text(encoding="utf-8")) or {}) \
        if artifact_path(t, n).is_file() else {}
    itin = load("itinerary.yaml")
    pool = poi_pool(load("verified-pois.yaml").get("pois") or [], load("accommodations.yaml") or {"stops": []})
    window = {(today + datetime.timedelta(days=k)).isoformat() for k in range(FORECAST_DAYS)}
    days = [d for d in itin.get("days") or [] if str(d.get("date")) in window]
    jma = jma or {}
    offices, out = {}, []
    for d in days:
        date = str(d["date"])
        spec = jma.get(date) or jma.get("all")
        rec = None
        if spec:
            office, _, point = spec.partition("/")
            if office not in offices:
                offices[office] = fetch(JMA_URL.format(office=office))
            rec = jma_days(offices[office], office, point).get(date)
        if rec is None:
            p = pool.get(d.get("lodging")) or {}
            geo = p.get("geocode") or {}
            if geo.get("lat") is not None:
                q = {"latitude": geo["lat"], "longitude": geo["lng"], "timezone": "auto",
                     "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                              "precipitation_probability_max,snowfall_sum", "forecast_days": FORECAST_DAYS}
                rec = model_day(fetch(MODEL_URL + "?" + urllib.parse.urlencode(q)), date,
                                p.get("district") or p.get("name_display") or "")
        if rec is not None:
            out.append(rec)
    doc = {"fetched_at": (now or datetime.datetime.now(TZ)).isoformat(timespec="minutes"), "days": out}
    dest = artifact_path(t, "forecast.yaml")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return doc


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("trip_dir")
    ap.add_argument("--jma", action="append", default=[], metavar="DATE=OFFICE/POINT",
                    help="the JMA office and temperature point for a day (DATE or all)")
    args = ap.parse_args(argv)
    jma = {}
    for item in args.jma:
        key, sep, spec = item.partition("=")
        if not sep or "/" not in spec:
            print(f"--jma wants DATE=OFFICE/POINT, e.g. all=016000/札幌 (got {item!r})", file=sys.stderr)
            return 2
        jma[key] = spec
    if not pathlib.Path(args.trip_dir).is_dir():
        print(f"no trip folder: {args.trip_dir}", file=sys.stderr)
        return 2
    try:
        doc = build(args.trip_dir, jma)
    except OSError as exc:
        print(f"forecast could not be fetched ({exc.__class__.__name__}); try again later", file=sys.stderr)
        return 1
    print(f"forecast: {len(doc['days'])} day(s) written "
          f"({sum(d['kind'] == 'official' for d in doc['days'])} official)")
    return 0
