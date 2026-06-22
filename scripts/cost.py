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


def pass_break_even(individual_fares, pass_price):
    """Compare buying a pass vs paying each covered leg fare individually.

    individual_fares: list of numbers (the fares of the legs the pass would cover).
    Returns {"individual_total", "pass_price", "use_pass", "saving"} where
    use_pass is True only when the pass is strictly cheaper, and saving is the
    absolute difference between the two options.
    """
    individual_total = sum(individual_fares)
    use_pass = pass_price < individual_total
    saving = abs(individual_total - pass_price)
    return {"individual_total": individual_total, "pass_price": pass_price,
            "use_pass": use_pass, "saving": saving}


def over_budget(total, budget_amount):
    """True if the estimated total exceeds the budget (strict)."""
    return total > budget_amount
