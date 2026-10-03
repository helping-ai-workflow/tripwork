"""Trip-cost aggregation — pure, currency-agnostic. The cost-rollup skill converts
all amounts to one primary currency before calling these functions. Mirrors the
pure-function style of legs.py / facilities.py.
"""

def sum_costs(line_items):
    """Sum same-currency line items.

    line_items: [{"category": str, "amount": number}, ...].
    Returns {"by_category": {category: subtotal}, "total": grand_total}.
    """
    by_category = {}
    for item in line_items:
        cat = item.get("category", "other")
        amount = item.get("amount")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError(
                f"line item '{item.get('label') or cat}' has no numeric 'amount' "
                "(record unknown costs as an explicit estimate or exclude with an "
                "estimate_note — never silently zero them)")
        by_category[cat] = by_category.get(cat, 0) + amount
    return {"by_category": by_category, "total": sum(by_category.values())}


def lodging_line_amount(cost, nights, rooms=1):
    """Total cost of one stop's lodging, multiplying the per-room `amount` by rooms
    (and by nights when the basis is per_night). (P6)

    `cost` is an accommodations cost dict ``{amount, basis}`` whose `amount` is the
    price PER ROOM. basis ``per_night`` -> amount × nights × rooms; basis ``total``
    -> amount × rooms (a per-room total for the whole stay). `rooms` defaults to 1.
    cost-rollup builds the lodging line item with this before handing it to sum_costs.
    """
    amount = cost.get("amount")
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError(
            "lodging cost has no numeric 'amount' (record an explicit estimate; "
            "never silently zero a room cost)")
    rooms = rooms or 1
    if cost.get("basis", "per_night") == "per_night":
        return amount * nights * rooms
    return amount * rooms  # basis == "total": per-room total for the whole stay


def incidental_total(daily_amount, days):
    """The user-supplied daily incidental allowance times the number of days."""
    return daily_amount * days


def pass_break_even(individual_fares, pass_price, travellers=1):
    """Compare buying a pass vs paying each covered leg fare individually.

    individual_fares: list of numbers (the per-person fares of the legs the pass covers).
    pass_price: the per-person pass price. travellers: head count (default 1) — both
    sides scale by it so the returned `individual_total` / `pass_price` / `saving` are
    GROUP totals (what cost-rollup adds to the trip total). The `use_pass` decision is
    head-count-invariant (both sides scale equally) but the magnitudes are not — a
    multi-traveller trip was previously under-counted by the head count. (F2, P6-twin)

    Returns {"individual_total", "pass_price", "use_pass", "saving"} where use_pass is
    True only when the pass is strictly cheaper, and saving is the absolute difference.
    """
    travellers = travellers or 1
    individual_total = sum(individual_fares) * travellers
    group_pass_price = pass_price * travellers
    use_pass = group_pass_price < individual_total
    saving = abs(individual_total - group_pass_price)
    return {"individual_total": individual_total, "pass_price": group_pass_price,
            "use_pass": use_pass, "saving": saving}


def over_budget(total, budget_amount):
    """True if the estimated total exceeds the budget (strict)."""
    return total > budget_amount
