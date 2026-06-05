"""E2E closure for v0.9.0 cost rollup (spec §7 / CLAUDE.md step-7 fixture).

A Japan trip: accommodation (per-night x nights) + rail fares + a JR Pass option, plus a
daily incidental allowance. The pass is cheaper than the covered fares -> use_pass; the
total over a set budget -> over_budget; a no-budget variant skips the comparison.
"""
import json, pathlib, jsonschema
from scripts.cost import sum_costs, incidental_total, pass_break_even, over_budget

ROOT = pathlib.Path(__file__).resolve().parent.parent

def test_pass_is_recommended_when_cheaper():
    covered_fares = [20000, 20000, 20000]          # 3 long shinkansen legs = 60000
    be = pass_break_even(covered_fares, 50000)     # 7-day pass cheaper
    assert be["use_pass"] is True
    assert be["saving"] == 10000

def test_full_rollup_total_and_over_budget():
    accommodation = 15000 * 4                       # 60000
    transport = 50000                               # use the pass price (cheaper)
    incidental = incidental_total(6000, 5)          # 30000
    items = [{"category": "accommodation", "amount": accommodation},
             {"category": "transport", "amount": transport},
             {"category": "incidental", "amount": incidental}]
    r = sum_costs(items)
    assert r["total"] == 140000
    assert over_budget(r["total"], 120000) is True   # 140000 > 120000
    assert over_budget(r["total"], 150000) is False

def test_cost_yaml_fixture_is_schema_valid():
    schema = json.load(open(ROOT / "schemas" / "cost.schema.json"))
    doc = {
        "currency": "JPY",
        "line_items": [
            {"category": "accommodation", "label": "4 nights", "amount": 60000},
            {"category": "transport", "label": "JR Pass 7d", "amount": 50000},
            {"category": "incidental", "label": "5 days @ 6000", "amount": 30000},
        ],
        "total": 140000,
        "budget": {"amount": 120000, "over": True, "delta": 20000},
        "pass_break_even": {"name": "JR Pass 7d", "pass_price": 50000,
                            "individual_total": 60000, "use_pass": True, "saving": 10000},
        "as_of": "2026-06-05", "estimate_note": "estimate; prices vary",
    }
    jsonschema.validate(doc, schema)  # must not raise

def test_no_budget_means_no_comparison():
    r = sum_costs([{"category": "accommodation", "amount": 60000}])
    assert r["total"] == 60000
