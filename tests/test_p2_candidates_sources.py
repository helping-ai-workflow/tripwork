"""v1.0 P2 — candidates carry site / site_local / note and the source-verify
driver copies them into verified-pois unchanged."""
import datetime
import pathlib
import subprocess
import sys

import yaml

from scripts.validate_artifact import validate_file
from scripts.paths import artifact_path, deliverable_paths, report_path, work_dir_for

ROOT = str(pathlib.Path(__file__).resolve().parents[1])


def test_driver_carries_site_fields_into_verified_pois(tmp_path):
    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir(); (trip / "data").mkdir()
    (artifact_path(trip, "trip-brief.yaml")).write_text(yaml.safe_dump(
        {"slug": "t", "destination": {"country": "JP", "city": "函館", "local_lang": "ja"},
         "dates": {"start": "2026-10-12", "end": "2026-10-13"}}, allow_unicode=True),
        encoding="utf-8")
    src = [{"url": "https://www.hakodate-asaichi.com/", "lang": "ja", "site": "函館朝市官網",
            "site_local": "函館朝市公式サイト", "note": "營業時間 6:00–14:00"},
           {"url": "https://guide.example/asaichi", "lang": "zh", "site": "旅遊指南",
            "note": "交通與推薦"}]
    (artifact_path(trip, "candidates.yaml")).write_text(yaml.safe_dump({"candidates": [
        {"id": "hak-asaichi", "name_local": "函館朝市", "name_display": "函館朝市", "category": "food",
         "claimed_district": "函館", "sources": src,
         "business_status": {"status": "OPERATIONAL", "source_url": src[0]["url"],
                             "as_of": datetime.date.today().isoformat()}}]},
        allow_unicode=True), encoding="utf-8")
    assert validate_file(str(artifact_path(trip, "candidates.yaml")))[0] == 0
    r = subprocess.run([sys.executable, "scripts/source_verify_run.py", str(trip),
                        "--work-dir", str(work), "--offline"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    out = yaml.safe_load((artifact_path(trip, "verified-pois.yaml")).read_text(encoding="utf-8"))
    got = out["pois"][0]["sources"]
    for want, have in zip(src, got):
        for k in ("site", "site_local", "note"):
            assert have.get(k) == want.get(k), (k, have)
    assert validate_file(str(artifact_path(trip, "verified-pois.yaml")))[0] == 0


def test_driver_carries_intro_and_booking_so_a_reverify_keeps_them(tmp_path):
    """P2 review I4: intro / booking.opens_at recorded on the candidate survive a
    source_verify_run re-run instead of being wiped by _build_poi."""
    trip, work = tmp_path / "trip", tmp_path / "work"
    trip.mkdir(); work.mkdir(); (trip / "data").mkdir()
    (artifact_path(trip, "trip-brief.yaml")).write_text(yaml.safe_dump(
        {"slug": "t", "destination": {"country": "JP", "city": "札幌", "local_lang": "ja"},
         "dates": {"start": "2026-10-12", "end": "2026-10-13"}}, allow_unicode=True),
        encoding="utf-8")
    booking = {"required": True, "opens_at": "2026-10-17 08:00",
               "opens_at_source": "https://www.sapporobeer.jp/brewery/s_museum/"}
    (artifact_path(trip, "candidates.yaml")).write_text(yaml.safe_dump({"candidates": [
        {"id": "beer", "name_local": "サッポロビール博物館", "name_display": "札幌啤酒博物館",
         "category": "sight", "claimed_district": "札幌",
         "intro": "日本唯一的啤酒博物館。", "intro_source": "https://www.sapporobeer.jp/",
         "booking": booking,
         "sources": [{"url": "https://www.sapporobeer.jp/", "lang": "ja"}],
         "business_status": {"status": "OPERATIONAL", "source_url": "https://www.sapporobeer.jp/",
                             "as_of": datetime.date.today().isoformat()}}]},
        allow_unicode=True), encoding="utf-8")
    assert validate_file(str(artifact_path(trip, "candidates.yaml")))[0] == 0
    r = subprocess.run([sys.executable, "scripts/source_verify_run.py", str(trip),
                        "--work-dir", str(work), "--offline"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    poi = yaml.safe_load((artifact_path(trip, "verified-pois.yaml")).read_text(encoding="utf-8"))["pois"][0]
    assert poi.get("intro") == "日本唯一的啤酒博物館。"
    assert poi.get("booking") == booking

