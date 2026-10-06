"""Disclose district-centroid coordinates in the deliverable.

A POI or lodging whose `geocode.geocode_source` is `cluster_fallback` is verified to
EXIST (Gate 0's sourced business_status), but its map pin is the district centroid,
not the venue. Anything distance- or walk-time-sensitive needs a manual check, and the
reader has to be told which places those are. The renderers emit that from the data so
it cannot be forgotten: source-verify's instruction to "tell the user" was never
followed in the consumer corpus (verified cluster_fallback POIs and chosen lodgings,
zero disclosures in the deliverables).
"""

CENTROID_SOURCE = "cluster_fallback"
# v1.3.0: a point from the venue's sourced address (its 丁目 or town) is approximate too
APPROX_SOURCES = (CENTROID_SOURCE, "nominatim_address", "nominatim_road", "village_centroid")


def _label(poi):
    """name_display（name_zh）— the same label the day rows use, so a kana name keeps
    its gloss. Never the poi id: that would leak an internal token."""
    base = poi.get("name_display") or poi.get("name_local") or ""
    zh = poi.get("name_zh")
    return f"{base}（{zh}）" if zh and zh != base else base


def centroid_items(itin, poi_map):
    """Every scheduled POI (a row's poi_id) and every night's lodging (day.lodging)
    whose coordinate is a centroid, once each, in first-use order. Unscheduled POIs
    and ids that do not resolve in poi_map are not the reader's concern."""
    seen, out = set(), []
    for day in itin.get("days", []):
        ids = [row.get("poi_id") for row in day.get("rows", [])] + [day.get("lodging")]
        for pid in ids:
            poi = poi_map.get(pid) if pid else None
            if not poi or pid in seen or not _label(poi):
                continue
            if (poi.get("geocode") or {}).get("geocode_source") in APPROX_SOURCES:
                seen.add(pid)
                out.append(poi)
    return out


def centroid_note(poi):
    """Plain text (unescaped) disclosure line for one place located only approximately."""
    # v2.1.0: the two Taiwanese stand-ins say which point they are (the user's pick A1)
    where = {"nominatim_address": "它地址所在街區的中心點", "nominatim_road": "它地址那條路上的一點",
             "village_centroid": "它所在村里的中心點"}.get((poi.get("geocode") or {}).get("geocode_source"),
                                                    "所在區域的中心點")
    return (f"{_label(poi)}：地圖座標是{where}，不是它本身的位置"
            f"——距離與步行時間請出發前自行確認")
