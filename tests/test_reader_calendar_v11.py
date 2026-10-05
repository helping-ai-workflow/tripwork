"""v1.1 §6.2 — one calendar card per trip; the 1st of a month reads M/1."""
import datetime as dt

from bs4 import BeautifulSoup

from scripts.render.reader import month_calendar

D = dt.date


def _card(dates):
    areas = [("函館", "r1")] * len(dates)
    return BeautifulSoup(month_calendar.months(dates, areas), "html.parser")


def test_title_single_cross_month_and_year():
    assert month_calendar.month_title([D(2026, 11, 9), D(2026, 11, 16)]) == "2026 年 11 月"
    assert month_calendar.month_title([D(2026, 10, 30), D(2026, 11, 2)]) == "2026 年 10～11 月"
    assert month_calendar.month_title([D(2026, 12, 30), D(2027, 1, 2)]) == "2026 年 12 月～2027 年 1 月"


def test_a_single_month_trip_draws_the_whole_month_in_one_card():
    s = _card([D(2026, 11, 9), D(2026, 11, 10)])
    assert len(s.select(".month")) == 1 and s.select_one(".month h3").get_text() == "2026 年 11 月"
    cells = s.select(".g > :not(.wd)")
    assert len(cells) == 35                                        # Nov 2026 spans 5 weeks (11/1 is a Sunday)
    assert cells[0].get_text() == "1"                              # a whole-month grid keeps its own 1st plain


def test_a_cross_month_trip_is_one_card_of_continuous_weeks_padded_to_five():
    s = _card([D(2026, 10, 30), D(2026, 10, 31), D(2026, 11, 1), D(2026, 11, 2)])
    assert len(s.select(".month")) == 1 and s.select_one(".month h3").get_text() == "2026 年 10～11 月"
    cells = s.select(".g > :not(.wd)")
    assert len(cells) == 35                                        # 2 trip weeks + 1 before + 2 after
    assert cells[0].get_text() == "18" and cells[-1].get_text() == "21"
    first = s.select_one('label.stamp[for="pg-d3"]')
    assert first.select_one("b").get_text() == "11/1" and "m1" in first["class"]


def test_a_trip_across_years():
    s = _card([D(2026, 12, 30), D(2026, 12, 31), D(2027, 1, 1)])
    assert s.select_one(".month h3").get_text() == "2026 年 12 月～2027 年 1 月"
    assert s.select_one('label.stamp[for="pg-d3"] b').get_text() == "1/1"


def test_the_mini_calendar_uses_the_same_first_of_month_label():
    dates = [D(2026, 10, 31), D(2026, 11, 1)]
    mini = BeautifulSoup(month_calendar.mini(dates, [("函館", "r1")] * 2, 2), "html.parser")
    assert mini.select_one('label.stamp[for="pg-d2"] b').get_text() == "11/1"


def test_an_off_cell_on_the_first_reads_m1():
    s = _card([D(2026, 10, 31), D(2026, 11, 2)])                  # crosses months; 11/1 itself is not a trip day
    assert "11/1" in [c.get_text() for c in s.select(".g .off")]


def test_a_broken_first_date_cannot_conjure_years_of_grey_weeks():
    """Review I3: a typo'd year must not draw every week in between (as big_calendar and
    mini already refuse): a run with more than two empty weeks keeps only the trip weeks."""
    dates = [D(2020, 11, 9), D(2026, 11, 10), D(2026, 11, 11)]
    cells = _card(dates).select(".g > :not(.wd)")
    assert len(cells) <= 5 * 7, len(cells)
    assert [c["for"] for c in _card(dates).select("label.stamp")] == ["pg-d1", "pg-d2", "pg-d3"]


def test_a_trip_with_a_short_gap_keeps_its_weeks_continuous():
    dates = [D(2026, 10, 30), D(2026, 11, 13)]                      # one empty week between
    cells = _card(dates).select(".g > :not(.wd)")
    assert len(cells) == 35 and cells[0].get_text() == "18"         # the v1.1 continuous run, padded to five


def test_no_days_draw_no_card():
    assert month_calendar.months([], []) == "" and month_calendar.month_title([]) == ""
