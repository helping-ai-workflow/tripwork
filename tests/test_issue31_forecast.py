"""#31: the week-before forecast. JMA documents and the model's answer are small made-up
stand-ins in their real shapes; nothing is fetched."""
import datetime

import yaml

from scripts import forecast as F
from scripts.forecast_text import forecast_line
from scripts.paths import artifact_path
from scripts.render.markdown import render_markdown_page
from scripts.validate_artifact import validate_file

JMA = [{"timeSeries": [{"timeDefines": ["2030-01-02T11:00:00+09:00"], "areas": [{"area": {"name": "示意地方"},
                                                                              "weatherCodes": ["100"]}]}]},
       {"timeSeries": [
           {"timeDefines": [f"2030-01-0{k}T00:00:00+09:00" for k in (3, 4, 5)],
            "areas": [{"area": {"name": "示意地方"}, "weatherCodes": ["205", "100", "300"], "pops": ["", "10", "80"]}]},
           {"timeDefines": [f"2030-01-0{k}T00:00:00+09:00" for k in (3, 4, 5)],
            "areas": [{"area": {"name": "示意"}, "tempsMin": ["", "-3", "1"], "tempsMax": ["", "2", "6"]}]}]}]
MODEL = {"daily": {"time": ["2030-01-06"], "weather_code": [73], "temperature_2m_min": [-4.4],
                   "temperature_2m_max": [0.6], "precipitation_probability_max": [90], "snowfall_sum": [3.2]}}


def _trip(tmp_path, dates):
    t = tmp_path / "trip"
    (t / "data").mkdir(parents=True)
    days = [{"date": d, "rows": [], "lodging": "hotel"} for d in dates]
    pois = [{"id": "hotel", "district": "示意區", "geocode": {"lat": 43.0, "lng": 141.0}}]
    for n, doc in (("itinerary.yaml", {"days": days}), ("verified-pois.yaml", {"pois": pois})):
        artifact_path(t, n).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    return t


def _fetch(url):
    return JMA if "jma.go.jp" in url else MODEL


def test_official_days_then_a_marked_model_day_and_nothing_past_seven(tmp_path):
    t = _trip(tmp_path, ["2030-01-04", "2030-01-05", "2030-01-06", "2030-01-10"])
    doc = F.build(t, {"all": "000000/示意"}, fetch=_fetch, today=datetime.date(2030, 1, 3),
                  now=datetime.datetime(2030, 1, 3, 11, 0, tzinfo=F.TZ))
    by = {d["date"]: d for d in doc["days"]}
    assert by["2030-01-04"]["kind"] == "official" and by["2030-01-04"]["tmin"] == -3
    assert by["2030-01-05"]["rain"] and by["2030-01-05"]["pop"] == 80
    assert by["2030-01-06"]["kind"] == "model" and by["2030-01-06"]["snow"]      # JMA had no 01-06
    assert "2030-01-10" not in by                                               # past the window
    assert F.FORECAST_DAYS == 7
    assert validate_file(str(artifact_path(t, "forecast.yaml")))[0] == 0


def test_jma_codes_read_in_chinese_with_their_flags():
    assert F.jma_weather("205") == "多雲時有雪" and F.jma_weather("999") == ""
    assert F.jma_weather("150") == "晴"


def test_the_line_says_when_and_who_and_reminds():
    fc = {"fetched_at": "2030-01-03T11:00+09:00", "days": [
        {"date": "2030-01-04", "tmin": -3, "tmax": 2, "weather": "多雲時有雪", "pop": 70, "snow": True,
         "kind": "official", "source": "日本氣象廳 週間天氣預報", "source_url": "https://x.example"}]}
    line = forecast_line(fc, "2030-01-04")
    assert line.startswith("-3～2°C・多雲時有雪・降水 70%（1/3 11:00 查，日本氣象廳") and "注意防滑" in line
    assert forecast_line(fc, "2030-01-09") == "尚無預報"
    assert forecast_line(None, "2030-01-04") == ""
    fc["days"][0]["kind"] = "model"
    assert "模型預報" in forecast_line(fc, "2030-01-04")


def test_the_markdown_day_carries_the_line():
    fc = {"fetched_at": "2030-01-03T11:00+09:00", "days": [
        {"date": "2030-01-04", "weather": "晴", "kind": "official", "source": "示意", "source_url": "https://x.example"}]}
    md = render_markdown_page({"days": [{"date": "2030-01-04", "label": "D1", "rows": []}]}, {}, forecast=fc)
    assert "**天氣**：晴（1/3 11:00 查，示意）" in md
