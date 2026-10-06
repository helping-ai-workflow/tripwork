"""v2.1.0 §1: Chinese sources get a region from their URL, once, locally (scripts/migrate_lang.py)."""
import pytest
import yaml

from scripts.migrate_lang import apply_lang, country_lang_region, plan_lang, region_from_url


@pytest.mark.parametrize("url,want", [
    ("https://www.example.com.tw/a", "TW"), ("https://shop.example.cn/", "CN"),
    ("https://x.example.hk/", "HK"), ("https://x.example.sg/", "SG"), ("https://x.example.my/", "MY"),
    ("https://example.com/zh-tw/menu", "TW"), ("https://example.com/ZH_TW/", "TW"),
    ("https://example.com/zh-cn/", "CN"), ("https://example.com/zh-hk/", "HK"),
    ("https://tw.example.com/", "TW"),
    ("https://example.com/?lang=zh-tw", None),        # the query is not read
    ("https://example.com/#zh-tw", None),             # nor the fragment
    ("https://example.com/", None), ("not a url", None), ("", None), (None, None)])
def test_region_from_url(url, want):
    assert region_from_url(url) == want


@pytest.mark.parametrize("country,want", [("台灣", "TW"), ("臺灣", "TW"), ("Taiwan", "TW"), (" taiwan", "TW"),
                                          ("中華民國", "TW"), ("ROC", "TW"), ("tw", "TW"), ("HK", "HK"),
                                          ("JP", None), ("日本", None), (None, None)])
def test_country_lang_region_never_connects(country, want):
    assert country_lang_region(country) == want


def _src(url, lang="zh"):
    return {"url": url, "lang": lang}


def _write_trip(root, country="台灣", local_lang="zh", legacy=False):
    base = root if legacy else root / "data"
    base.mkdir(parents=True, exist_ok=True)
    (base / "trip-brief.yaml").write_text(
        yaml.safe_dump({"slug": root.name, "destination": {"country": country, "city": "示意市",
                                                            "local_lang": local_lang}},
                       allow_unicode=True), encoding="utf-8")
    (base / "candidates.yaml").write_text(yaml.safe_dump({"candidates": [
        {"id": "a", "sources": [_src("https://a.example.com.tw/x"), _src("https://example.com/")]}]},
        allow_unicode=True), encoding="utf-8")
    (base / "verified-pois.yaml").write_text(yaml.safe_dump({"pois": [
        {"id": "a", "sources": [_src("https://a.example.com.tw/x"), _src("https://tw.example.org/")]}]},
        allow_unicode=True), encoding="utf-8")
    (base / "accommodations.yaml").write_text(yaml.safe_dump({"stops": [{"candidates": [
        {"id": "h", "sources": [_src("https://h.example.com/zh-tw/"), _src("https://h.example.jp/", "ja")]}]}]},
        allow_unicode=True), encoding="utf-8")
    return root


def _counts(edits):
    out = {}
    for e in edits:
        out[e.file] = out.get(e.file, 0) + 1
    return out


@pytest.mark.parametrize("legacy", [False, True])
def test_plan_lang_reads_root_and_data_layouts(tmp_path, legacy):
    edits, _ = plan_lang(_write_trip(tmp_path / "t", legacy=legacy))
    assert _counts(edits) == {"trip-brief.yaml": 1, "candidates.yaml": 1,
                              "verified-pois.yaml": 2, "accommodations.yaml": 1}


def test_plan_lang_skips_int_sources_with_note(tmp_path):
    t = _write_trip(tmp_path / "t")
    (t / "data" / "verified-pois.yaml").write_text("pois:\n- id: a\n  sources: 25\n- id: b\n  sources: [x]\n",
                                                  encoding="utf-8")
    edits, notes = plan_lang(t)
    assert "verified-pois.yaml" not in _counts(edits)
    assert any("verified-pois.yaml" in n for n in notes)


def test_plan_lang_brief_zh_by_country(tmp_path):
    edits, _ = plan_lang(_write_trip(tmp_path / "tw"))
    assert [(e.old, e.new) for e in edits if e.file == "trip-brief.yaml"] == [("zh", "zh-TW")]
    edits, notes = plan_lang(_write_trip(tmp_path / "jp", country="日本"))
    assert not [e for e in edits if e.file == "trip-brief.yaml"]
    assert any("local_lang" in n for n in notes)


def test_plan_lang_unknown_region_stays_zh(tmp_path):
    t = _write_trip(tmp_path / "t")
    apply_lang(plan_lang(t)[0])
    cands = yaml.safe_load((t / "data" / "candidates.yaml").read_text(encoding="utf-8"))["candidates"]
    assert [s["lang"] for s in cands[0]["sources"]] == ["zh-TW", "zh"]


def test_apply_preserves_comments_and_is_idempotent(tmp_path):
    t = tmp_path / "t" / "data"
    t.mkdir(parents=True)
    (t / "trip-brief.yaml").write_text("destination:\n  country: 台灣  # 國家\n  local_lang: zh\n", encoding="utf-8")
    text = ("# 蒐集結果\ncandidates:\n- id: a   # 第一家\n  sources:\n"
            "  - url: https://a.example.com.tw/x\n    lang: 'zh'   # 中文\n"
            "  - {url: 'https://b.example.cn/', lang: zh}\n")
    (t / "candidates.yaml").write_text(text, encoding="utf-8")
    edits, _ = plan_lang(tmp_path / "t")
    apply_lang(edits)
    got = (t / "candidates.yaml").read_text(encoding="utf-8")
    assert got == text.replace("lang: 'zh'", "lang: 'zh-TW'").replace("lang: zh}", "lang: zh-CN}")
    assert "# 國家" in (t / "trip-brief.yaml").read_text(encoding="utf-8")
    assert plan_lang(tmp_path / "t")[0] == []
