"""Day-chain structure checks for the v1.0 reader (spec §4.1 / §4.4 / §4.8).

Every message starts with a fixed prefix that is ALSO the routing marker in
scripts/orchestration.py::_ROUTES and the class marker in tests/corpus_measure.py.
Messages interpolate only dates, row ordinals and POI ids -- never trip-authored
free text (theme, mode, row text): _ROUTES matches by substring, so free text
inside a message would let the itinerary pick where its own failure is routed.

Endpoints are positional, never string-matched: a move run connects the node
before it (or last night's lodging) to the node after it (or tonight's lodging).
The corpus shows from/to strings never equal the rows they connect
(scripts/gate.py::_home_legs_rendered_failures).
"""

from scripts.day_titles import THEME_MAX, candidate_failures, picked  # noqa: E402  (v1.1 topic 7)

ALT_KINDS = ("備案", "選項")
MOVE_MODES = ("walk", "rail", "bus", "taxi", "drive", "ferry", "flight", "ropeway", "none")
BASES = ("sourced", "estimated")
LEGACY_ALT_MARK = "▸"


def is_move(row):
    return row.get("slot") == "move"


def _number(v):
    """A non-negative number. bool is an int subclass and is not one; a string
    "5" is not one either -- the gate CLI does not schema-validate, so a
    hand-edited value reaches this code verbatim and must FAIL, not pass."""
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v >= 0


def node_poi_ids(day):
    return {r.get("poi_id") for r in day.get("rows") or []
            if not is_move(r) and isinstance(r.get("poi_id"), str) and r.get("poi_id")}


def chain_failures(itinerary):
    out = []
    for d in itinerary.get("days") or []:
        date = d.get("date", "?")
        rows = d.get("rows") or []
        if not rows:
            out.append(f"day chain broken: {date} has no rows")
            continue
        if not is_move(rows[0]):
            out.append(f"day chain broken: {date} row 0 is not a move "
                       f"(a day starts from last night's lodging or the arrival point)")
        last = len(rows) - 1
        if last > 0 and not is_move(rows[last]):      # a 1-row day was reported once above
            out.append(f"day chain broken: {date} row {last} is not a move "
                       f"(a day ends at tonight's lodging or the departure point)")
        for j in range(1, len(rows)):
            if not is_move(rows[j - 1]) and not is_move(rows[j]):
                out.append(f"day chain broken: {date} rows {j - 1} and {j} are adjacent "
                           f"stops with no move between them")
        for j, r in enumerate(rows):
            if not is_move(r) and not r.get("poi_id"):
                out.append(f"chain node without poi: {date} row {j} has no poi_id")
    return out


def move_record_failures(itinerary):
    out = []
    for d in itinerary.get("days") or []:
        date = d.get("date", "?")
        for j, r in enumerate(d.get("rows") or []):
            if not is_move(r) or r.get("leg_index") is not None:
                continue            # a leg_index row takes its fields from legs.yaml
            mode = r.get("mode")
            if mode is None:
                out.append(f"move record incomplete: {date} row {j} has no mode")
                continue
            if mode not in MOVE_MODES:
                out.append(f"move record incomplete: {date} row {j} has an unknown mode")
                continue
            if mode == "none":
                continue
            missing = [k for k in ("mins", "km") if not _number(r.get(k))]
            basis = r.get("basis")
            if basis not in BASES:
                missing.append("basis")
            if basis == "sourced" and not r.get("source_url"):
                missing.append("source_url")
            if basis == "estimated" and not r.get("estimate_method"):
                missing.append("estimate_method")
            if missing:
                out.append(f"move record incomplete: {date} row {j} lacks {', '.join(missing)}")
    return out


def legacy_failures(itinerary):
    out = []
    if itinerary.get("contingency"):
        out.append("legacy contingency: trip-level contingency is retired — convert each "
                   "entry into days[].alternatives on the stops it affects")
    for d in itinerary.get("days") or []:
        date = d.get("date", "?")
        for j, r in enumerate(d.get("rows") or []):
            text = r.get("text")
            if isinstance(text, str) and text.lstrip().startswith(LEGACY_ALT_MARK):
                out.append(f"legacy alternative row: {date} row {j} is an inline ▸ "
                           f"alternative — move it to days[].alternatives")
    return out


def alternative_failures(itinerary):
    """Structure only. Whether the fallback place is verified + geocoded is checked
    by run_gate's referenced-POI loop, which _referenced_ids feeds with every
    alternative's poi_id -- one check, not two copies of it."""
    out = []
    for d in itinerary.get("days") or []:
        date = d.get("date", "?")
        nodes = node_poi_ids(d)
        for k, a in enumerate(d.get("alternatives") or []):
            where = f"alternative invalid: {date} #{k}"
            if not isinstance(a, dict):
                out.append(f"{where} is not a record")
                continue
            if a.get("kind") not in ALT_KINDS:
                out.append(f"{where} kind must be 備案 or 選項")
            if not isinstance(a.get("applies_to"), str) or a["applies_to"] not in nodes:
                out.append(f"{where} applies_to is not a stop on that day")
            for key in ("trigger", "fallback"):
                v = a.get(key)
                if not (isinstance(v, str) and v.strip()):
                    out.append(f"{where} lacks {key}")
            if not (isinstance(a.get("poi_id"), str) and a["poi_id"]):
                out.append(f"{where} has no poi_id (fallback places must be verified)")
    return out


def theme_failures(itinerary):
    """The picked theme (v1.0) plus its six candidates (v1.1 topic 7, scripts/day_titles.py)."""
    out, seen = [], {}
    for d in itinerary.get("days") or []:
        date = d.get("date", "?")
        if d.get("theme_candidates") is None:
            out.append(f"day theme invalid: {date} has no theme_candidates (6 for the user to pick from)")
        theme = d.get("theme")
        if not (isinstance(theme, str) and theme.strip()):
            out.append(f"day theme invalid: {date} has no theme")
            continue
        theme = theme.strip()
        if len(theme) > THEME_MAX:
            out.append(f"day theme invalid: {date} theme is {len(theme)} chars (max {THEME_MAX})")
        if theme in seen:
            out.append(f"day theme invalid: {date} repeats the theme of {seen[theme]}")
        else:
            seen[theme] = date
        own = bool(d.get("theme_user_written"))        # the user's own words: no candidate, refs optional
        if not own and d.get("theme_candidates") is not None and picked(d) is None:
            out.append(f"day theme invalid: {date} theme is not one of its candidates "
                       f"(or set theme_user_written)")
        refs = d.get("theme_refs")
        if refs is not None and not isinstance(refs, list):
            out.append(f"day theme invalid: {date} theme_refs is not a list")
        elif not refs:
            if own:
                continue
            out.append(f"day theme invalid: {date} has no theme_refs")
        else:
            nodes = node_poi_ids(d)
            bad = [r for r in refs if not isinstance(r, str) or r not in nodes]
            if bad:
                # a count, never the refs themselves: a ref that is not a stop is
                # free text, and free text in a routed message hijacks _ROUTES
                # (v1.0 P1 final review, I3)
                out.append(f"day theme invalid: {date} theme_refs has {len(bad)} "
                           f"entries that are not stops on that day")
    return out + candidate_failures(itinerary)


def alternative_line(alt):
    """One-line text the interim md/html renderers print (full UI lands in P4)."""
    return f"{alt.get('kind', '')}（{alt.get('trigger', '')}）：{alt.get('fallback', '')}"
