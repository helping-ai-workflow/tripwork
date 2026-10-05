"""v2.0.0 spec §4: README's cloud network allowlist and the plain-language source rules."""
import pathlib
import re
from urllib.parse import urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text(encoding="utf-8")


def _allowlist():
    m = re.search(r"<!-- cloud-allowlist -->(.*?)<!-- /cloud-allowlist -->", README, re.S)
    assert m, "README needs the <!-- cloud-allowlist --> block"
    return {ln.split("#")[0].strip() for ln in m.group(1).splitlines()
            if ln.strip() and not ln.strip().startswith("```") and "." in ln.split("#")[0]}


def test_cloud_allowlist_matches_the_scripts():
    from scripts import day_maps, geocode, photo_adapter
    hosts = {urlsplit(u).hostname for u in (geocode.NOMINATIM_URL, day_maps.TILE_URL, photo_adapter.WIKIDATA_API,
                                            photo_adapter.COMMONS_API, photo_adapter.OPENVERSE_API)}
    # Literal because these two have no constant to call: Commons returns the image
    # host in its API response, and wrangler talks to Cloudflare's API internally.
    hosts |= {"upload.wikimedia.org", "api.cloudflare.com"}
    assert _allowlist() == hosts


def test_readme_source_rules():
    # Literal phrases: the rules exist only in README prose (guard rule (b)).
    for phrase in ("搜尋引擎的結果頁", "同一個部落格平台", "營業狀態查不到"):
        assert phrase in README, phrase


def test_readme_uses_the_single_entry():
    assert "tripwork.py export" in README and "tripwork.py migrate" in README
