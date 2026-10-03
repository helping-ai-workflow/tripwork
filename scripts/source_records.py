"""Source-record completeness (spec §4.2) and lodging area labels (§4.6).

by_id MUST come from scripts/gate.py::poi_pool -- never a hand-built map. The
verified-pois / chosen-lodging fold decides which record an id resolves to, and
v0.33.0's C1 shipped because a guard rebuilt that fold differently.
A verified-pois id is a POI (fixed by source-verify); anything else in the pool
is a chosen lodging candidate (fixed by accommodation-research).
"""


def _is_zh(lang):
    return isinstance(lang, str) and lang.lower().startswith("zh")


def source_record_failures(by_id, poi_ids, referenced):
    out = []
    for pid in sorted(referenced):
        rec = by_id.get(pid)
        if rec is None:
            continue            # "unknown POI" is run_gate's own failure
        prefix = ("POI source record incomplete: " if pid in poi_ids
                  else "lodging source record incomplete: ")
        for n, s in enumerate(rec.get("sources") or []):
            if not isinstance(s, dict):
                out.append(f"{prefix}{pid!r} sources[{n}] is not a record")
                continue
            lacks = [k for k in ("site", "note")
                     if not (isinstance(s.get(k), str) and s[k].strip())]
            if not _is_zh(s.get("lang")) and not (isinstance(s.get("site_local"), str)
                                                  and s["site_local"].strip()):
                lacks.append("site_local")
            if lacks:
                out.append(f"{prefix}{pid!r} sources[{n}] lacks {', '.join(lacks)}")
    return out


def area_label_failures(accommodations):
    out = []
    for i, stop in enumerate((accommodations or {}).get("stops") or []):
        label = stop.get("area_label")
        if not (isinstance(label, str) and 2 <= len(label.strip()) <= 4):
            # the stop's ordinal, never its district: a district is trip-authored
            # text and must not reach a routed message (v1.0 P1 final review, I3)
            out.append(f"lodging area label missing: stops[{i}] needs a 2–4 character "
                       f"area_label")
    return out
