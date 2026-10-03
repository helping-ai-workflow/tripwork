"""v1.1 topic 7 (spec §7.3): the title picker page and its plain-text twin."""
import re

import yaml
from bs4 import BeautifulSoup

from scripts import title_picker as tpk
from scripts.day_titles import display_order
from tests import reader_fixture as R
from tests.mech_fixtures import brief_name_fields


def _inputs():
    itin = R.itinerary()
    brief = dict(R.brief(), **brief_name_fields())
    return itin, brief, R.reader_kwargs()["accommodations"]


def test_each_day_lists_its_candidates_short_to_long_numbered_like_the_text():
    itin, brief, acc = _inputs()
    soup = BeautifulSoup(tpk.page(itin, brief, acc), "html.parser")
    text = tpk.text_list(itin, brief, acc)
    cols = soup.select(".col")
    assert len(cols) == len(itin["days"])
    for i, (col, d) in enumerate(zip(cols, itin["days"]), start=1):
        cands = d["theme_candidates"]
        want = [cands[k]["text"] for k in display_order(cands)]
        got = [r["data-t"] for r in col.select("input[type=radio]")]
        assert got == want
        assert [r["value"] for r in col.select("input[type=radio]")] == [str(n) for n in range(1, len(want) + 1)]
        block = text.split(f"D{i} ")[1].split("\nD")[0]
        assert re.findall(r"^  (\d+)\. ([^（\n]+)", block, re.M) == [(str(n), t) for n, t in enumerate(want, start=1)]


def test_a_rhyming_line_carries_its_zhuyin_tag():
    itin, brief, acc = _inputs()
    soup = BeautifulSoup(tpk.page(itin, brief, acc), "html.parser")
    tags = {r["data-t"]: r.find_next("em", class_="rm") for r in soup.select(".col")[0].select("input[type=radio]")}
    line = next(t for t in tags if "，" in t and "山頂的風" in t)          # 湖上的燈，山頂的風
    assert soup.select(".col")[0].find("input", attrs={"data-t": line}).parent.select_one(".rm").get_text() == "ㄥ韻"
    assert "（ㄥ韻）" in tpk.text_list(itin, brief, acc)


def test_the_headline_starts_on_the_briefs_pick():
    itin, brief, acc = _inputs()
    soup = BeautifulSoup(tpk.page(itin, brief, acc), "html.parser")
    checked = soup.select("input[name=h][checked]")
    assert [c["data-t"] for c in checked] == [brief["headline"]["text"]]
    assert len(soup.select("input[name=h]")) == 6
    # each day starts on its current title (the user's check); the fixture's are own words
    assert [c.select_one(".own")["value"] for c in soup.select(".col")] == [d["theme"] for d in itin["days"]]


def test_the_page_is_offline_and_says_what_to_do_without_scripts():
    html = tpk.page(*_inputs())
    assert not re.search(r"(src|href)=\"https?://", html)
    soup = BeautifulSoup(html, "html.parser")
    assert "D1=3" in soup.select_one("noscript").get_text()


def test_the_cli_writes_the_page_into_work_and_prints_the_list(tmp_path, capsys):
    from scripts.paths import artifact_path
    itin, brief, acc = _inputs()
    trip = tmp_path / "trip"
    artifact_path(trip, "itinerary.yaml").parent.mkdir(parents=True)
    for name, doc in (("itinerary.yaml", itin), ("trip-brief.yaml", brief), ("accommodations.yaml", acc)):
        artifact_path(trip, name).write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
    work = tmp_path / "work"
    assert tpk.main([str(trip), "--work-dir", str(work)]) == 0
    assert (work / "挑標題.html").exists()
    out = capsys.readouterr().out
    assert "D1 " in out and "回覆格式" in out


def test_a_regenerated_picker_shows_each_days_current_title():
    """After 再給我 3 個 the page is written again: every day starts on its current title
    (picked lines checked, own words in their box), the asked day included."""
    from scripts import title_picks as tp
    itin, brief, acc = _inputs()
    tp.apply(itin, brief, tp.parse('D1=2 D2="海邊的風" D3=+'))
    soup = BeautifulSoup(tpk.page(itin, brief, acc), "html.parser")
    c1, c2, c3 = soup.select(".col")
    assert [r["value"] for r in c1.select("input[type=radio][checked]")] == ["2"]
    assert c2.select_one(".own")["value"] == "海邊的風" and not c2.select("input[checked]")
    assert c3.select_one(".own")["value"] == itin["days"][2]["theme"]          # the fixture's own words
def test_the_current_titles_start_marked():
    """The user's check: the page did not show which line each day has now. A day whose
    theme is one of its lines starts on it; own words start in their box."""
    itin, brief, acc = _inputs()
    itin["days"][0]["theme"] = itin["days"][0]["theme_candidates"][3]["text"]
    itin["days"][0].pop("theme_user_written", None)
    itin["days"][1].update(theme="海邊的風", theme_user_written=True)
    soup = BeautifulSoup(tpk.page(itin, brief, acc), "html.parser")
    c1, c2 = soup.select(".col")[:2]
    assert [r["data-t"] for r in c1.select("input[type=radio][checked]")] == [itin["days"][0]["theme"]]
    assert c2.select_one(".own")["value"] == "海邊的風"
