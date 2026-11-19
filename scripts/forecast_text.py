"""How a day's forecast reads (#31), for every renderer. Pure: no network."""


def forecast_day(forecast, date):
    for d in ((forecast or {}).get("days") or []) if isinstance(forecast, dict) else []:
        if isinstance(d, dict) and str(d.get("date")) == str(date):
            return d
    return None


def _when(fetched_at):
    s = str(fetched_at or "")
    return f"{int(s[5:7])}/{int(s[8:10])} {s[11:16]}" if len(s) >= 16 and s[4] == "-" else s


def forecast_line(forecast, date, who=True):
    """'-2～3°C・多雲時有雪・降水 70%（11/19 11:00 查，日本氣象廳）；有雪，注意防滑', '尚無預報'
    for a day of a fetched forecast it does not reach, '' when nothing was fetched."""
    if not isinstance(forecast, dict) or not forecast.get("days"):
        return ""
    d = forecast_day(forecast, date)
    if d is None:
        return "尚無預報"
    temp = ""
    if isinstance(d.get("tmin"), (int, float)) and isinstance(d.get("tmax"), (int, float)):
        temp = f"{d['tmin']:g}～{d['tmax']:g}°C"
    parts = [x for x in (temp, d.get("weather"), f"降水 {d['pop']}%" if isinstance(d.get("pop"), int) else "") if x]
    who = "模型預報" if d.get("kind") == "model" else (d.get("source") or "") if who else ""
    line = "・".join(parts) + f"（{_when(forecast.get('fetched_at'))} 查" + (f"，{who}" if who else "") + "）"
    tips = [t for flag, t in (("snow", "有雪，注意防滑"), ("rain", "有雨，帶雨具")) if d.get(flag)]
    return line + (f"；{'；'.join(tips)}" if tips else "")
