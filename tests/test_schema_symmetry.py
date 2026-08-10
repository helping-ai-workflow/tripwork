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


def test_no_rederive_read_is_forbidden_by_its_schema():
    """The load-bearing half: a field rederive.py reads off a record must be
    declarable on that record."""
    src = (ROOT / "scripts" / "rederive.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # collect `<name>.get("field")` string literals per enclosing function
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

    found_axes = {n for n in reads if n.startswith("rederive_")}
    unowned = found_axes - set(OWNER) - EXEMPT
    assert not unowned, (
        f"new re-derivation axis {sorted(unowned)} has no OWNER entry — add it "
        f"(or EXEMPT it with a reason) so its reads are schema-checked")

    for fn_name, artifact in OWNER.items():
        if fn_name not in reads:
            continue          # not written yet; found_axes above is the ratchet
        fname, pointer = ARTIFACT_ITEMS[artifact]
        declared = set(_item_schema(fname, pointer)["properties"])
        item = _item_schema(fname, pointer)
        if item.get("additionalProperties") is not False:
            continue  # the schema permits extras; nothing can be forbidden
        forbidden = {f for f in reads[fn_name] if f not in declared}
        # container-level and non-record keys are read off wrapper dicts, not
        # off the item; list them explicitly so the set stays honest.
        forbidden -= {"legs", "hops", "clusters", "line_items", "stops",
                      "candidates", "pois", "days", "rows", "by_category",
                      "district", "centroid", "lat", "lng", "status", "as_of",
                      "source_url", "close", "no_fixed_close", "last_order",
                      "last_entry", "typical_visit_mins", "closing_status",
                      "time", "slot", "poi_id", "geocode_source", "kind",
                      "duration_mins", "depart", "last_service",
                      "last_service_exempt", "mode", "mins", "flag",
                      "duration_source", "from", "to", "amount", "category",
                      "total", "currency", "official", "url", "lang"}
        assert not forbidden, (
            f"{fn_name} reads {sorted(forbidden)} off a {fname} record whose "
            f"schema is additionalProperties:false and does not declare them")
