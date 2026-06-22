"""Acceptance tests for the v0.23.0 matrix follow-ups (twins of the v0.22.0 9 defects).

F1 (P7-twin): export-gate `retryable` — a data defect (missing attribution / no official
              source) that re-rendering cannot fix is non-retryable, so the orchestrator
              halts and asks instead of looping export-artifact forever.
F2 (P6-twin): pass_break_even head-count scaling.
(F3 is a source-verify SKILL contract change — capture gmaps_place_id during the P1 Google
 business_status check — no code behaviour, so no unit test.)

RED-first: new params/keys exercised so each reports its own RED.
"""
from scripts.export_gate import run_export_gate, run_html_gate
from scripts.cost import pass_break_even


# ============================ F1 — retryable flag ============================
class TestF1Retryable:
    CLEAN = "### D1\n\nplain text without prices\n"

    def _photo_noattr(self):
        return {"id": "p1", "name_local": "X", "name_display": "X",
                "photo": {"data": "data:image/png;base64,iVB"}}  # no photo_attribution

    def _bookable_noofficial(self):
        return {"id": "b1", "name_local": "X", "name_display": "X",
                "verify_status": "verified", "booking": {"required": True},
                "sources": [{"url": "https://aggregator.example", "lang": "zh"}]}  # no official

    def test_clean_pass_is_retryable_true(self):
        r = run_export_gate(self.CLEAN, [])
        assert r["status"] == "pass"
        assert r["retryable"] is True  # nothing blocking

    def test_naked_dollar_is_retryable(self):
        r = run_export_gate(self.CLEAN + "\nprice $5 today\n", [])
        assert r["status"] == "fail"
        assert r["retryable"] is True   # re-render can escape the $

    def test_missing_attribution_is_non_retryable(self):
        r = run_export_gate(self.CLEAN, [self._photo_noattr()])
        assert r["status"] == "fail"
        assert r["retryable"] is False  # re-render can't add attribution -> halt+ask

    def test_bookable_missing_official_is_non_retryable(self):
        md = self.CLEAN + "\n| 10:00 | X | foo |\n"   # POI name in a table row
        r = run_export_gate(md, [self._bookable_noofficial()])
        assert r["status"] == "fail"
        assert any("official source link" in f for f in r["failures"])
        assert r["retryable"] is False

    def test_mixed_defects_stay_retryable_until_render_fixed(self):
        r = run_export_gate(self.CLEAN + "\nprice $5\n", [self._photo_noattr()])
        assert r["status"] == "fail"
        assert r["retryable"] is True   # a render fix is still available this round

    def test_html_attribution_failure_non_retryable(self):
        r = run_html_gate('<div class="day-card"></div>', [self._photo_noattr()], min_days=1)
        assert r["status"] == "fail"
        assert r["retryable"] is False

    def test_html_render_defect_retryable(self):
        # raw <script> is a render defect
        r = run_html_gate('<div class="day-card"></div><script>x</script>', [], min_days=1)
        assert r["status"] == "fail"
        assert r["retryable"] is True


# ============================ F2 — pass head-count ============================
class TestF2PassHeadcount:
    def test_pass_break_even_scales_by_travellers(self):
        r = pass_break_even([1000, 1000], 1500, travellers=4)
        assert r["individual_total"] == 8000   # 2000 per person × 4
        assert r["pass_price"] == 6000         # 1500 per person × 4
        assert r["use_pass"] is True
        assert r["saving"] == 2000

    def test_decision_unchanged_by_headcount(self):
        # pass cheaper per person -> use_pass True regardless of group size
        assert pass_break_even([1000, 1000], 1500, travellers=1)["use_pass"] is True
        assert pass_break_even([1000, 1000], 1500, travellers=9)["use_pass"] is True

    def test_default_one_traveller_backcompat(self):
        r = pass_break_even([1000, 1000], 1500)
        assert r["individual_total"] == 2000 and r["pass_price"] == 1500


# ============================ e2e closure (F1 + F2) ==========================
class TestE2EFollowups:
    def test_render_defect_loops_then_data_defect_halts(self):
        # ONE deliverable with both a render defect (naked $) and a data defect (photo
        # without attribution). First pass: a render fix is available -> retryable True
        # (orchestrator re-renders). After the $ is escaped, only the data defect remains
        # -> retryable False (orchestrator halts and asks the user, no infinite loop).
        photo_noattr = {"id": "p1", "name_local": "X", "name_display": "X",
                        "photo": {"data": "data:image/png;base64,iVB"}}
        r1 = run_export_gate("### D1\n\nprice $5 today\n", [photo_noattr])
        assert r1["status"] == "fail" and r1["retryable"] is True

        r2 = run_export_gate("### D1\n\nprice \\$5 today\n", [photo_noattr])  # $ escaped
        assert r2["status"] == "fail" and r2["retryable"] is False
        assert any("missing attribution" in f for f in r2["failures"])

    def test_group_pass_cost_scales_into_rollup(self):
        from scripts.cost import sum_costs
        pb = pass_break_even([2000, 2000], 3000, travellers=4)  # 4000 vs 3000 per person
        assert pb["use_pass"] is True
        assert pb["pass_price"] == 12000   # group: 3000 × 4
        total = sum_costs([{"category": "transport", "amount": pb["pass_price"]}])["total"]
        assert total == 12000
