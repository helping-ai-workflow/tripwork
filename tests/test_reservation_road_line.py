"""reservation.road_line: what a day's move row shows of its booking -- the one rule the
reader's 移動列 and the md day table share (status word, then the first two details)."""
from scripts.reservation import road_line


def _d(*pairs):
    return [{"label": k, "value": v} for k, v in pairs]


def test_booked_two_values_no_ref():
    res = {"status": "booked", "ref": "K7Q2PX",
           "details": _d(("座位", "32A・32B・32C"), ("行李", "每人託運 23 kg"), ("備註", "x"))}
    assert road_line(res) == ("已訂", ["32A・32B・32C", "每人託運 23 kg"])


def test_todo_label():
    assert road_line({"status": "todo", "details": _d(("怎麼訂", "官網"))}) == ("還要訂", ["官網"])


def test_booked_without_details():
    assert road_line({"status": "booked", "ref": "M3R8TZ"}) == ("已訂", [])


def test_one_detail():
    assert road_line({"status": "booked", "details": _d(("座位", "41A"))}) == ("已訂", ["41A"])


def test_none_with_details_has_no_label():
    assert road_line({"status": "none", "details": _d(("付款", "刷 IC 卡，不用買票"))}) == (None, ["刷 IC 卡，不用買票"])


def test_none_without_details_and_self_are_none():
    assert road_line({"status": "none"}) is None
    assert road_line({"status": "self", "details": _d(("備註", "x"))}) is None


def test_non_dict_detail_skipped_and_value_is_text():
    assert road_line({"status": "booked", "details": ["oops", {"label": "車廂", "value": 4}]}) == ("已訂", ["4"])
