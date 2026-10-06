"""Tag the region of Chinese sources from their URL (v2.1.0 §1), run by `tripwork.py migrate`.

A source recorded as `lang: zh` no longer counts as a local-language source for a
Chinese destination: the language must carry its region (zh-TW, zh-HK, ...). This
pass gives it one where the URL proves it -- a .tw/.cn/.hk/.sg/.my domain, a zh-tw
style path or host, a tw. subdomain -- and leaves it `zh` otherwise: an unknown
source is never taken for Taiwan. Local, no network, no agent; the YAML is edited
in place at each value, so comments and layout survive.
"""
import pathlib
import re
from typing import NamedTuple
from urllib.parse import urlsplit

import yaml

from scripts.geocode import TW_COUNTRY_NAMES
from scripts.paths import is_legacy_layout

_REGIONS = ("TW", "CN", "HK", "SG", "MY")
_TAGGED = re.compile(r"zh-(tw|cn|hk)(?![a-z])")
_BARE_ZH = ("zh", "zh-hant", "zh-hans")

# (file, path from the document root to each list of sources)
_SOURCE_LISTS = (("candidates.yaml", ("candidates", "*", "sources")),
                 ("verified-pois.yaml", ("pois", "*", "sources")),
                 ("accommodations.yaml", ("stops", "*", "candidates", "*", "sources")))


class LangEdit(NamedTuple):
    path: pathlib.Path
    line: int
    col: int
    old: str
    new: str
    file: str
    start: int
    end: int


def region_from_url(url):
    """'TW' / 'CN' / 'HK' / 'SG' / 'MY' when the URL's host or path proves the region,
    else None. Case-insensitive, `_` read as `-`; the query and fragment are not read."""
    if not isinstance(url, str) or "://" not in url:
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = parts.path.lower().replace("_", "-")
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld.upper() in _REGIONS:
        return tld.upper()
    m = _TAGGED.search(host.replace("_", "-")) or _TAGGED.search(path)
    if m:
        return m.group(1).upper()
    if host.startswith("tw."):
        return "TW"
    return None


def country_lang_region(country):
    """The Chinese region a brief's country names, from the Taiwan names and a two-letter
    code only -- never geocode.country_code, which may go online."""
    if not isinstance(country, str) or not country.strip():
        return None
    c = country.strip().casefold()
    code = TW_COUNTRY_NAMES.get(c) or (c if re.fullmatch(r"[a-z]{2}", c) else None)
    return code.upper() if code and code.upper() in _REGIONS else None


def _is_bare_zh(value):
    return isinstance(value, str) and value.strip().lower().replace("_", "-") in _BARE_ZH


def _get(node, key):
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            if isinstance(k, yaml.ScalarNode) and k.value == key:
                return v
    return None


def _walk(node, path):
    """Every node at `path` ('*' = each item of a sequence)."""
    if not path:
        yield node
        return
    head, rest = path[0], path[1:]
    if head == "*":
        if isinstance(node, yaml.SequenceNode):
            for item in node.value:
                yield from _walk(item, rest)
    else:
        child = _get(node, head)
        if child is not None:
            yield from _walk(child, rest)


def _edit(path, name, text, node, new):
    raw = text[node.start_mark.index:node.end_mark.index]
    return LangEdit(path, node.start_mark.line + 1, node.start_mark.column + 1, node.value, new, name,
                    node.start_mark.index, node.end_mark.index) if node.value in raw else None


def plan_lang(trip_dir):
    """([LangEdit], [note]) for one trip, either layout. Empty when nothing is left to tag."""
    t = pathlib.Path(trip_dir)
    base = t if is_legacy_layout(t) else t / "data"
    edits, notes = [], []
    for name, path in _SOURCE_LISTS:
        f = base / name
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8")
        root = yaml.compose(text)
        skipped = 0
        for sources in _walk(root, path):
            if not isinstance(sources, yaml.SequenceNode):
                skipped += 1
                continue
            for s in sources.value:
                if not isinstance(s, yaml.MappingNode):
                    skipped += 1
                    continue
                lang, url = _get(s, "lang"), _get(s, "url")
                if not isinstance(lang, yaml.ScalarNode) or not _is_bare_zh(lang.value):
                    continue
                region = region_from_url(url.value if isinstance(url, yaml.ScalarNode) else None)
                if region:
                    e = _edit(f, name, text, lang, f"zh-{region}")
                    if e:
                        edits.append(e)
        if skipped:
            notes.append(f"{name}: {skipped} sources entries are not a list of sources — skipped")
    brief = base / "trip-brief.yaml"
    if brief.is_file():
        text = brief.read_text(encoding="utf-8")
        dest = _get(yaml.compose(text), "destination")
        lang = _get(dest, "local_lang")
        if isinstance(lang, yaml.ScalarNode) and _is_bare_zh(lang.value):
            country = _get(dest, "country")
            region = country_lang_region(country.value if isinstance(country, yaml.ScalarNode) else None)
            e = _edit(brief, "trip-brief.yaml", text, lang, f"zh-{region}") if region else None
            if e:
                edits.append(e)
            else:
                notes.append("trip-brief.yaml: local_lang is zh — write its region by hand "
                             "(zh-TW / zh-HK / zh-CN / zh-SG / zh-MY)")
    return edits, notes


def apply_lang(edits):
    """Write the edits, each at its own value; a file is rewritten once, back to front."""
    by_file = {}
    for e in edits:
        by_file.setdefault(e.path, []).append(e)
    for path, es in by_file.items():
        text = path.read_text(encoding="utf-8")
        for e in sorted(es, key=lambda e: e.start, reverse=True):
            raw = text[e.start:e.end]
            text = text[:e.start] + raw.replace(e.old, e.new, 1) + text[e.end:]
        path.write_text(text, encoding="utf-8")
