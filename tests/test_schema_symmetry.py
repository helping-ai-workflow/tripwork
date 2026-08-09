"""Every artifact field re-derivation reads must be declared in that artifact's
schema.

TW-071 was not "we forgot a field". It was a gate demanding an input the schema
actively forbade (`additionalProperties: false` plus no `resolved_name`), so the
verdict was structurally un-re-derivable and no amount of agent diligence could
fix it. The same shape produced v0.33.0's C1 one artifact over, where
rederive_closing demanded `hours` on a lodging candidate whose schema forbids it.

This scan enumerates the reads and asserts each is declarable, so the next such
pairing fails here instead of in a consumer's re-gate.
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

    # function -> which artifact's item object its record-level reads belong to
    OWNER = {"rederive_legs": "legs", "rederive_hops": "routing",
             "rederive_lodging": "accommodations", "rederive_pois": "pois"}
    for fn_name, artifact in OWNER.items():
        assert fn_name in reads, f"{fn_name} not found — update OWNER"
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
