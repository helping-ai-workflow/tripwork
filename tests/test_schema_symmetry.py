"""Every artifact field re-derivation reads must be declared in that artifact's
schema.

TW-071 was not "we forgot a field". It was a gate demanding an input the schema
actively forbade (`additionalProperties: false` plus no `resolved_name`), so the
verdict was structurally un-re-derivable and no amount of agent diligence could
fix it. The same shape produced v0.33.0's C1 one artifact over, where
rederive_closing demanded `hours` on a lodging candidate whose schema forbids it.

This scan does NOT stand guard on a C1 recurrence, despite sharing its origin
story — rederive_closing is EXEMPT (see below), because its `by_id` reads can
resolve against either of two source schemas at runtime
(scripts/gate.py::poi_pool folds verified-pois and chosen accommodations
candidates into one pool) and a flat per-function AST walk cannot attribute a
given `.get()` call to the schema its receiver actually had. What covers a C1
recurrence is tests/test_rederive.py::test_a_timed_lodging_row_is_out_of_closing_scope
(:484) and ::test_a_lodging_row_is_skipped_even_when_it_records_a_closing_status
(:530), which pin the runtime scope cut that keeps it correct today, plus
::test_an_accommodations_candidate_cannot_legally_carry_hours (:550) — a direct
differential schema test that goes red the moment a future release adds
`hours` to schemas/accommodations.schema.json.

This scan enumerates the reads of every function it CAN attribute to a single
artifact schema and asserts each is declarable, so the next such pairing fails
here instead of in a consumer's re-gate.
"""
import ast
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]

# (rederive.py parameter name) -> (schema file, JSON pointer to the item object
# whose `properties` the reads must appear in)
ARTIFACT_ITEMS = {
    "legs": ("legs.schema.json", ("properties", "legs", "items")),
    "routing": ("routing.schema.json", ("properties", "hops", "items")),
    "cost": ("cost.schema.json", ("properties", "line_items", "items")),
    "accommodations": ("accommodations.schema.json",
                       ("properties", "stops", "items", "properties",
                        "candidates", "items")),
    "pois": ("verified-pois.schema.json", ("properties", "pois", "items")),
}


def _item_schema(fname, pointer):
    node = json.loads((ROOT / "schemas" / fname).read_text(encoding="utf-8"))
    for key in pointer:
        node = node[key]
    return node


def test_every_declared_artifact_item_is_reachable():
    """Guard, GREEN at HEAD: the pointers above must keep resolving. A schema
    restructure that moves an item object silently turns the scan below into a
    no-op, and a no-op guard is indistinguishable from a passing one."""
    for fname, pointer in ARTIFACT_ITEMS.values():
        item = _item_schema(fname, pointer)
        assert item.get("properties"), (fname, pointer)


def _rederive_reads():
    """AST-walk scripts/rederive.py once; return {fn_name: set(string-literal
    field names passed to a `.get(...)` call inside that function)}. Shared by
    both tests below so there is exactly one definition of "what does this
    function read" — never two copies that can drift apart."""
    src = (ROOT / "scripts" / "rederive.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    reads = {}
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        got = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                got.add(node.args[0].value)
        reads[fn.name] = got
    return reads


# function -> which artifact's item object its record-level reads belong to.
# DISCOVERED, not hard-coded forward: every rederive_* function that exists
# must be either owned or explicitly exempt, so a new axis is enrolled the
# moment it is written and cannot be forgotten. Hard-coding a name that a
# later task creates would instead leave this suite red for every task in
# between — which is how the first draft of this plan was wrong.
OWNER = {"rederive_legs": "legs", "rederive_hops": "routing",
         "rederive_lodging": "accommodations", "rederive_pois": "pois"}
# Two DIFFERENT reasons, not one shared one — state each, never exempt by
# silence:
#
# rederive_cost reads cost.get("line_items"/"total"/"by_category") off the
# WRAPPER cost.yaml document itself, never off a single line_items record —
# there is no item schema for a document-level read to be checked against.
#
# rederive_closing's `by_id[pid].get("hours")` CAN resolve against a real
# item schema — but which one is a runtime fact this static walk cannot
# see. scripts/gate.py::poi_pool folds verified-pois records together with
# each stop's chosen accommodations candidate into one `by_id` (P4), so a
# given `.get()` call may run against either source schema depending on
# the record. The scope cut that keeps today's reads correct
# (`if row.get("slot") == "lodging": continue`, scripts/rederive.py:285)
# is a runtime branch a flat per-function AST walk has no control-flow
# awareness to observe, so enrolling this function would hard-fail on
# correct code. This is NOT "no schema to check" the way rederive_cost is
# — it is "AST cannot attribute the read to the right schema". What
# actually guards this boundary (the C1 shape cited in the module
# docstring above) is tests/test_rederive.py's three closing-scope tests,
# not this scan.
EXEMPT = {"rederive_cost", "rederive_closing"}

# container-level and non-record keys, read off a WRAPPER dict (or a
# sub-object of a record) rather than off the item record itself. This list
# exists for exactly one purpose: absorb reads that structurally CANNOT be
# item-level fields. Keep record-level fields OUT of it, full stop — a
# record field belongs in the schema, not here.
#
# TW-076: this list had accumulated 45 names. 12 of them were genuine
# record fields (depart, duration_mins, from, last_service,
# last_service_exempt, mode, status, to, duration_source, flag, mins,
# source_url) shadowing 15 (function, field) combinations across two axes,
# leaving rederive_legs (9 reads) and rederive_hops (11 reads) with ZERO
# fields under guard — the exact TW-071 deadlock shape, invisible. Every
# survivor below is annotated with the wrapper or sub-object it is read
# off; if you cannot point at one, it does not belong here.
ALLOWLIST = {
    "legs",             # legs.yaml document wrapper — rederive_legs(legs, ...)
    "hops",             # routing.yaml document wrapper — rederive_hops(routing, ...)
    "clusters",         # routing.yaml document wrapper
    "stops",            # accommodations.yaml document wrapper
    "candidates",       # stop object wrapper — stop["candidates"], not a
                         # candidate item itself
    "district",         # cluster object (routing.yaml) / stop object
                         # (accommodations.yaml) — not a hop item or a
                         # candidate item
    "centroid",         # cluster object (routing.yaml)
    # Not container-level, but still not item-level: read off a SUB-OBJECT
    # of the record, never off the record itself.
    "geocode_source",   # candidate.geocode sub-object
    "as_of",            # record.business_status sub-object
}


def _effective_coverage():
    """{fn_name: sorted(fields the schema-symmetry guard can actually catch)}
    for every OWNER axis that exists today. A field lands here iff
    rederive.py reads it off the record AND the allowlist doesn't absorb
    it — i.e. iff removing that field from the schema would turn
    `forbidden` non-empty in test_no_rederive_read_is_forbidden_by_its_schema.
    An axis whose set here is empty has a guard that can never fire, no
    matter what a future edit does to that artifact's schema."""
    reads = _rederive_reads()
    coverage = {}
    for fn_name, artifact in OWNER.items():
        if fn_name not in reads:
            continue          # not written yet
        fname, pointer = ARTIFACT_ITEMS[artifact]
        item = _item_schema(fname, pointer)
        if item.get("additionalProperties") is not False:
            coverage[fn_name] = []  # schema permits extras; nothing checkable
            continue
        coverage[fn_name] = sorted(reads[fn_name] - ALLOWLIST)
    return coverage


def test_no_rederive_read_is_forbidden_by_its_schema():
    """The load-bearing half: a field rederive.py reads off a record must be
    declarable on that record."""
    reads = _rederive_reads()

    found_axes = {n for n in reads if n.startswith("rederive_")}
    unowned = found_axes - set(OWNER) - EXEMPT
    assert not unowned, (
        f"new re-derivation axis {sorted(unowned)} has no OWNER entry — add it "
        f"(or EXEMPT it with a reason) so its reads are schema-checked")

    covered = _effective_coverage()
    for fn_name, checked_fields in covered.items():
        artifact = OWNER[fn_name]
        fname, pointer = ARTIFACT_ITEMS[artifact]
        declared = set(_item_schema(fname, pointer)["properties"])
        forbidden = [f for f in checked_fields if f not in declared]
        assert not forbidden, (
            f"{fn_name} reads {sorted(forbidden)} off a {fname} record whose "
            f"schema is additionalProperties:false and does not declare them")


def test_the_allowlist_does_not_blind_an_entire_axis():
    """TW-076：allowlist 的用途是排除讀在 wrapper dict 上的 container-level key，
    不是排除 record 欄位。它曾經含有 15 個貨真價實的 record 欄位，使 rederive_legs 與
    rederive_hops 兩條軸的受檢欄位為 0 —— 把 TW-071 一模一樣的 deadlock 注射到 legs 軸，
    整套測試全綠。

    這條 guard 直接斷言每條 OWNER 軸至少有一個欄位真的被檢查，所以一個把整條軸減光的
    allowlist 不可能再悄悄成立。"""
    covered = _effective_coverage()
    empty = sorted(fn for fn, fields in covered.items() if not fields)
    assert not empty, (
        f"allowlist 把 {empty} 的每一個 read 都減掉了 —— 這些軸的 schema 檢查是空轉的")
