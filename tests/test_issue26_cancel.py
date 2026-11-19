"""#26: a booking given up after the plan changed is kept for the refund, matched to
no row, listed to cancel, and noticed once past its deadline. Placeholder bookings."""
import datetime

from scripts import reservation
from scripts.render.markdown import render_markdown_page

ITIN = {"days": [{"date": "2030-01-13", "label": "D5", "rows": []}]}


def _res(**kw):
    return {"reservations": [dict({"date": "2030-01-13", "from": "示意駅", "to": "サンプル駅",
                                   "status": "cancel", "ref": "AB123456",
                                   "details": [{"label": "座位", "value": "4號車 5A"}]}, **kw)]}


def test_a_booking_to_cancel_needs_no_row():
    pairs, failures = reservation.match(ITIN, None, _res())
    assert pairs == [] and failures == []
    pairs, failures = reservation.match(ITIN, None, _res(status="booked"))
    assert failures and failures[0].startswith("reservation has no row")      # unchanged for booked


def test_the_list_and_the_late_notice():
    res = _res(cancel_by="2030-01-12 09:30", cancel_by_source="https://rail.example/refund")
    assert reservation.to_cancel(res)[0]["ref"] == "AB123456"
    assert reservation.cancel_notices(res, today=datetime.date(2030, 1, 11)) == []
    assert len(reservation.cancel_notices(res, today=datetime.date(2030, 1, 13))) == 1
    assert reservation.to_cancel(_res(status="cancelled")) == []


def test_the_markdown_lists_it_with_the_masked_number():
    md = render_markdown_page(ITIN, {}, reservations=_res(cancel_by="2030-01-12", cancel_how="到窗口退"))
    sect = md.split("## 要取消的訂位", 1)[1]
    assert "示意駅→サンプル駅" in sect and "2030-01-12 前取消" in sect and "到窗口退" in sect
    assert "AB123456" not in md and "4號車 5A" in sect
