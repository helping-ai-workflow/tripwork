"""Structured pre-trip checklist (spec §4.7).

The gate checks STRUCTURE only. "An item must not restate a stop's facts" is
deliberately not mechanised (user decision 2026-09-30): matching free text
against stop facts is a false-positive machine -- rule_of_three went 21/21 FP.
That rule lives in itinerary-synthesis's writing guidance instead.
"""
import re

KINDS = ("預約", "出發前確認", "打包")
_ABS_DUE = re.compile(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2})?$")
P = "checklist item invalid: "


def checklist_failures(itinerary, by_id, referenced):
    items = itinerary.get("checklist") or []
    out = []
    for k, it in enumerate(items):
        if not isinstance(it, dict):
            out.append(P + f"item {k} is free text — record kind/task/due")
            continue
        if it.get("kind") not in KINDS:
            out.append(P + f"item {k} kind must be 預約, 出發前確認 or 打包")
        if not (isinstance(it.get("task"), str) and it["task"].strip()):
            out.append(P + f"item {k} has no task")
        if it.get("due_is_hard") and not _ABS_DUE.match(str(it.get("due") or "")):
            out.append(P + f"item {k} is a hard deadline but due is not an absolute date")
        links = it.get("links") or []
        if not isinstance(links, list) or not all(
                isinstance(l, dict) and l.get("label") and l.get("url") for l in links):
            out.append(P + f"item {k} has a link that is not a label + url record")
    booked = {it["due"] for it in items
              if isinstance(it, dict) and it.get("kind") == "預約" and it.get("due_is_hard")
              and isinstance(it.get("due"), str)}
    for pid in sorted(referenced):
        opens = ((by_id.get(pid) or {}).get("booking") or {}).get("opens_at")
        if opens and opens not in booked:
            out.append(f"booking not in checklist: POI {pid!r} opens reservations at a "
                       f"recorded time but no hard-dated 預約 item carries it")
    return out


def checklist_line(item):
    """The single line the interim md/html renderers print (P4 replaces the HTML)."""
    if isinstance(item, str):
        return item
    task = item.get("task", "")
    return f"{task}（{item['due']}）" if item.get("due") else task


def checklist_texts(item):
    """Every authored string of one item, for scripts/gate.py::_itinerary_text."""
    if isinstance(item, str):
        return [item]
    if not isinstance(item, dict):
        return []
    out = [item.get(k) for k in ("task", "detail", "origin")]
    out += [l.get("label") for l in item.get("links") or [] if isinstance(l, dict)]
    return [s for s in out if isinstance(s, str) and s]
