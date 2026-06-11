from scripts.cost import sum_costs, incidental_total, pass_break_even, over_budget

def test_sum_costs_by_category_and_total():
    items = [{"category": "accommodation", "amount": 100},
             {"category": "accommodation", "amount": 50},
             {"category": "transport", "amount": 30}]
    r = sum_costs(items)
    assert r["by_category"] == {"accommodation": 150, "transport": 30}
    assert r["total"] == 180

def test_sum_costs_empty():
    r = sum_costs([])
    assert r["by_category"] == {} and r["total"] == 0

def test_incidental_total():
    assert incidental_total(50, 10) == 500
    assert incidental_total(50, 0) == 0

def test_pass_break_even_pass_cheaper():
    r = pass_break_even([80, 80, 80], 200)
    assert r["individual_total"] == 240
    assert r["use_pass"] is True
    assert r["saving"] == 40

def test_pass_break_even_pass_dearer():
    r = pass_break_even([80, 80], 300)
    assert r["use_pass"] is False
    assert r["saving"] == 140

def test_pass_break_even_equal_is_not_worth():
    r = pass_break_even([120, 120], 240)
    assert r["use_pass"] is False
    assert r["saving"] == 0

def test_over_budget():
    assert over_budget(180, 150) is True
    assert over_budget(150, 150) is False
    assert over_budget(100, 150) is False


def test_sum_costs_raises_on_missing_amount():   # TW-014
    import pytest
    from scripts.cost import sum_costs
    with pytest.raises(ValueError):
        sum_costs([{"category": "transport", "label": "KTX", "amount": None}])
    with pytest.raises(ValueError):
        sum_costs([{"category": "food", "label": "lunch"}])   # no amount key
