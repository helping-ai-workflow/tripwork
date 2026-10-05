"""v2.0.0 spec §5 (D7/D9/Q1/Q2, round-2 #12/#21/#24/#25): what counts as an independent
source and as an operating signal.

- one site per registrable domain (Public Suffix List eTLD+1), so `www.`, a port,
  `user@`, a trailing dot, case and sub-domains of one site are one source; PSL
  private-section platforms (blogspot) keep one site per author, platforms the PSL
  does not list (pixnet) are one site;
- a search engine's results page is never a source, nor an operating signal.

Every rule is exercised through the three shipped paths that judge a record --
verify_poi (source-verify), rederive_lodging and rederive_pois (the gate's
re-derivation) -- never through a helper alone.
"""
import gzip
import pathlib

import pytest

from tests.test_rederive import _accom, _lodging_cand, _poi_rec, _sourced_business_status

ROOT = pathlib.Path(__file__).resolve().parents[1]
AS_OF = "2026-08-05"                                       # _poi_rec's era


def _bs(url="https://a.example.tw/p", **over):
    b = {"status": "OPERATIONAL", "source_url": url, "as_of": AS_OF}
    b.update(over)
    return b


def _accepted(path, sources, bs=None):
    """True when the path accepts a record carrying `sources` as verified."""
    from scripts.rederive import rederive_lodging, rederive_pois
    from scripts.verify import verify_poi
    bs = bs or _bs(sources[0]["url"])
    if path == "verify_poi":
        rec = _poi_rec(sources=sources, business_status=bs)
        _, status, _ = verify_poi(rec, True, True, resolved_name=rec["resolved_name"], today=AS_OF)
        return status == "verified"
    if path == "rederive_pois":
        out = rederive_pois([_poi_rec(sources=sources, business_status=bs)])
        return not out.mismatches and not out.superseded
    cand = _lodging_cand(sources=sources, business_status={**bs, "as_of": _sourced_business_status()["as_of"]},
                         resolved_name="日月潭旅店",
                         geocode={"lat": 23.86, "lng": 120.91, "geocode_source": "nominatim"})
    out = rederive_lodging(_accom(cand))
    return not out.mismatches and not out.superseded


PATHS = ["verify_poi", "rederive_lodging", "rederive_pois"]


def _src(url, lang="zh"):
    return {"url": url, "lang": lang}


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("a,b", [
    ("https://www.example.com/a", "https://example.com/b"),
    ("https://example.com:443/a", "https://example.com/b"),
    ("https://user@example.com/a", "https://example.com/b"),
    ("https://example.com./a", "https://example.com/b"),
    ("https://WWW.EXAMPLE.COM/a", "https://example.com/b"),
    ("https://zh.wikipedia.org/wiki/A", "https://en.wikipedia.org/wiki/A"),
    ("https://a.pixnet.net/blog/1", "https://b.pixnet.net/blog/2"),
    ("https://shop.example.co.jp/a", "https://www.example.co.jp/b"),
], ids=["www", "port", "userinfo", "trailing-dot", "case", "wiki-langs", "pixnet", "co.jp"])
def test_one_site_is_one_source(path, a, b):
    assert not _accepted(path, [_src(a), _src(b)])


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("a,b", [
    ("https://x.blogspot.com/p", "https://y.blogspot.com/q"),        # PSL private section
    ("https://a.example.co.jp/p", "https://b.example2.co.jp/q"),     # two companies under co.jp
    ("https://192.0.2.1/p", "https://192.0.2.2/q"),
], ids=["blogspot-authors", "two-co.jp-companies", "two-ips"])
def test_distinct_sites_are_two_sources(path, a, b):
    assert _accepted(path, [_src(a), _src(b)])


def test_reason_names_the_shared_site():
    from scripts.verify import classify_candidate
    status, note = classify_candidate({"sources": [_src("https://a.pixnet.net/1"), _src("https://b.pixnet.net/2")]},
                                      True, True)
    assert status == "unverified"
    assert "distinct sites" in note and "pixnet.net" in note and "add one from another site" in note


def test_site_key_edge_cases():
    from scripts.verify import site_key
    assert site_key("https:///x") is None
    assert site_key("not a url") is None
    assert site_key("https://192.0.2.1/x") == "192.0.2.1"
    assert site_key("https://例え.jp/x") == site_key("https://xn--r8jz45g.jp/y")
    assert site_key("https://foo.github.io/x") != site_key("https://bar.github.io/x")


@pytest.mark.parametrize("path", PATHS)
def test_hostless_url_is_not_a_source(path):
    assert not _accepted(path, [_src("https:///x"), _src("https://b.example.com/q")],
                         bs=_bs("https://b.example.com/q"))


SEARCH_PAGES = [
    "https://tw.search.yahoo.com/search?p=x",
    "https://search.yahoo.co.jp/search?p=x",
    "https://m.search.naver.com/search.naver?query=x",
    "https://search.naver.com/search.naver?query=x",
    "https://cn.bing.com/search?q=x",
    "https://www.google.com/search?q=x",
    "https://www.google.co.jp/search?q=x",
    "https://www.google.com/maps/search/?api=1&query=x",
    "https://html.duckduckgo.com/html/?q=x",
    "https://lite.duckduckgo.com/lite/?q=x",
    "https://search.daum.net/search?q=x",
    "https://m.search.daum.net/search?q=x",
    "https://www.baidu.com/s?wd=x",
    "https://yandex.ru/search/?text=x",
]
NOT_SEARCH_PAGES = [
    "https://www.google.com/maps/place/x",
    "https://maps.google.com/?cid=123",
    "https://map.naver.com/p/entry/place/1",
    "https://places.googleapis.com/v1/places:searchText",
    "https://places.googleapis.com/v1/places/abc",
    "https://naver.me/abc",
    "https://www.yahoo.co.jp/",
    "https://baike.baidu.com/item/x",
    "https://www.bing.com/maps?q=x",
]


@pytest.mark.parametrize("url", SEARCH_PAGES)
def test_search_pages_are_recognised(url):
    from scripts.verify import is_search_results_page
    assert is_search_results_page(url)


@pytest.mark.parametrize("url", NOT_SEARCH_PAGES)
def test_other_pages_are_not_search_pages(url):
    from scripts.verify import is_search_results_page
    assert not is_search_results_page(url)


@pytest.mark.parametrize("path", PATHS)
def test_a_search_page_never_counts_as_a_source(path):
    srcs = [_src("https://a.example.tw/p"), _src("https://html.duckduckgo.com/html/?q=x")]
    assert not _accepted(path, srcs)


def test_search_page_reason():
    from scripts.verify import classify_candidate
    _, note = classify_candidate({"sources": [_src("https://a.example.tw/p"),
                                              _src("https://search.naver.com/search.naver?query=x")]}, True, True)
    assert "search results page is not a source" in note and "search.naver.com" in note


@pytest.mark.parametrize("path", PATHS)
def test_gate0_rejects_a_search_page_as_operating_evidence(path):
    srcs = [_src("https://a.example.tw/p"), _src("https://b.example.com/q")]
    assert not _accepted(path, srcs, bs=_bs("https://search.naver.com/search.naver?query=x"))


def test_gate0_search_page_reason_and_bucket():
    from scripts.rederive import rederive_pois
    from scripts.verify import operating_from_status
    op, why = operating_from_status(_bs("https://html.duckduckgo.com/html/?q=x"), today=AS_OF)
    assert op is None and "search results page" in why
    out = rederive_pois([_poi_rec(business_status=_bs("https://search.naver.com/search.naver?query=x"))])
    assert out.superseded and not out.mismatches


def test_places_api_is_still_operating_evidence():
    from scripts.verify import operating_from_status
    op, _ = operating_from_status(_bs("https://places.googleapis.com/v1/places:searchText"), today=AS_OF)
    assert op is True


def test_psl_snapshot_ships_and_stays_out_of_the_skills():
    gz = ROOT / "assets" / "psl" / "public_suffix_list.dat.gz"
    text = gzip.decompress(gz.read_bytes()).decode("utf-8")
    assert "Mozilla Public" in text and "MPL" in text and "// VERSION:" in text
    assert (ROOT / "assets" / "psl" / "README").is_file()
    for p in (ROOT / "skills").rglob("*.md"):
        assert "assets/psl" not in p.read_text(encoding="utf-8"), p
