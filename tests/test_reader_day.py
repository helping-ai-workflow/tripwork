"""v1.0 P4 — the mobile day page (spec §6.3 / §6.4)."""
from bs4 import BeautifulSoup

from scripts.render.reader import render_reader
from tests.reader_fixture import itinerary, poi_map, reader_kwargs


def _day(n, itin=None):
    html = render_reader(itin or itinerary(), poi_map(), **reader_kwargs())
    return BeautifulSoup(html, "html.parser").select_one(f'section.page.day[data-pg="d{n}"]')


def _stop(day, pid):
    return next(s for s in day.select(".stop") if s.get("data-poi") == pid)


def test_one_page_per_day():
    html = render_reader(itinerary(), poi_map(), **reader_kwargs())
    s = BeautifulSoup(html, "html.parser")
    assert [p["data-pg"] for p in s.select("section.page.day")] == ["d1", "d2", "d3"]


def test_the_header():
    d = _day(2)
    # v1.1 §3: the date line and the tip are retired; the title carries Day N
    assert d.select_one(".dh .dht").get_text() == "早市的蟹，山頂的夜"
    assert d.select_one(".dh .dstep .dn").get_text() == "Day 2"          # the user's check: a stepper on both widths
    assert d.select_one('label.back[for="pg-home"]')
    stamps = d.select(".mini label.stamp")
    assert [s["for"] for s in stamps] == ["pg-d1", "pg-d2", "pg-d3"]
    assert "cur" in stamps[1]["class"]


def test_the_chain_ends_are_anchors():
    d1, d2, d3 = _day(1), _day(2), _day(3)
    assert "從 函館空港 出發" in d1.select(".anchor")[0].get_text()
    assert "回到 函館示意飯店" in d1.select(".anchor")[-1].get_text()
    assert "從 函館示意飯店 出發" in d2.select(".anchor")[0].get_text()
    assert "前往 函館空港" in d3.select(".anchor")[-1].get_text()
    assert d2.select(".anchor")[0].select_one("a.navb")


def test_every_stop_is_an_anchor_target_and_starts_collapsed():
    """v1.1 §8.1: no radios -- a stop opens by an in-page jump to it (works in Quick Look)."""
    d = _day(2)
    stops = d.select(".stop")
    assert [s["data-poi"] for s in stops] == ["hak-asaichi", "hak-goryokaku", "hak-yama", "hak-hotel"]
    assert not d.select('input[name^="sel-"]')
    for s in stops:
        tid = s["id"]
        assert tid.startswith("t-d2-s")
        assert s.select_one(f'a.hd-open[href="#{tid}"]') and s.select_one(f'a.hd-close[href="#{tid}-x"]')
        assert s.select_one(f"span.tx#{tid}-x")                          # "closed, stay here"
        assert not s.select(".hd .cv")                                   # rows carry no ⌄
        assert s.select_one("a.navb")["href"].startswith("https://www.google.com/maps")


def test_time_and_expected_departure():
    head = _stop(_day(2), "hak-asaichi").select_one(".hd-open .t")
    assert head.select_one("b").get_text() == "08:00" and head.select_one("small").get_text() == "– 09:00"


def test_expanded_rows_in_order():
    d = _day(2)
    gor = _stop(d, "hak-goryokaku").select_one(".in")
    assert gor.select_one("figure.bp .bpi")["role"] == "img"                 # the photo (a CSS background since P7)
    assert [t.get_text() for t in gor.select("dl > dt")] == ["停留", "營業", "安排", "來源"]
    yama = _stop(d, "hak-yama").select_one(".in")
    assert [t.get_text() for t in yama.select("dl > dt")] == ["停留", "介紹", "營業", "安排", "來源"]
    assert "至 22:00（最後入場 21:30）" in yama.get_text()
    asaichi = _stop(d, "hak-asaichi").select_one(".in")
    assert "至 14:00（L.O. 13:30）" in asaichi.get_text()


def test_missing_facts_are_omitted_not_blank():
    gor = _stop(_day(2), "hak-goryokaku").select_one(".in")
    assert "介紹" not in [t.get_text() for t in gor.select("dt")]
    lodge = _stop(_day(2), "hak-hotel").select_one(".in")
    assert [t.get_text() for t in lodge.select("dl > dt")][0] == "日文"
    assert not lodge.select("figure")


def test_legs_carry_their_mode():
    legs = _day(2).select(".leg")
    modes = [next(c for c in l.select_one("svg")["class"] if c.startswith("m-")) if l.select_one("svg")
             else None for l in legs]
    assert modes == ["m-walk", "m-taxi", "m-bus", "m-taxi", None]
    texts = [l.get_text(" ", strip=True) for l in legs]
    # v1.1 (user): a capsule is mode + minutes + distance; no 估 marker, no note
    from scripts.render.reader.text import move_summary
    assert texts[0] == BeautifulSoup(move_summary("步行", 12, 0.9), "html.parser").get_text(" ", strip=True)
    assert texts[2].startswith("巴士 30 分")
    assert not [t for t in texts if "估" in t]
    assert "zero" in legs[4]["class"] and "同一個地方，不用移動" in texts[4]


def test_gaps_are_flagged_and_tight_moves_are_red():
    gaps = [g.get_text() for g in _day(2).select(".gap")]
    assert gaps == ["空檔 40 分", "空檔 5 小時", "空檔 50 分"]
    itin = itinerary()
    itin["days"][1]["rows"][3]["time"] = "09:00"
    assert _day(2, itin).select(".tight")


def test_the_alternative_hangs_under_its_stop():
    d = _day(2)
    yama = _stop(d, "hak-yama")
    alt = yama.find_next_sibling()
    assert alt.name == "details" and "altrow" in alt["class"] and "k備案" in alt["class"]
    assert not alt.has_attr("open") and alt.select_one("summary .cv")
    assert "纜車停駛" in alt.select_one("summary").get_text()
    assert "改上五稜郭塔看夜景" in alt.get_text() and alt.select_one("a.navb")


def test_the_source_list():
    s = _stop(_day(2), "hak-goryokaku")
    ver = s.select_one("div.ver")
    assert ver["id"] == s["id"] + "-src"
    assert ver.select_one(f'a.vopen[href="#{ver["id"]}"] .cv') and ver.select_one(f'a.vclose[href="#{s["id"]}"]')
    assert ver.select_one(".vopen .nms").get_text() == "五稜郭公園官網、旅遊指南"
    first, second = ver.select("ul.vlist li")
    assert first.select_one(".otag").get_text() == "官方" and first.select_one(".lg").get_text() == "日文"
    assert "五稜郭公園公式" in first.get_text()
    assert first.select_one(".su").get_text() == "https://official.example/hak-goryokaku"
    assert first.select_one(".sd").get_text() == "營業時間與票價"
    assert second.select_one(".lg").get_text() == "中文" and not second.select(".otag")


def test_an_unknown_language_code_is_escaped_and_never_crashes():
    """P4 review I3: lang_label returned an unknown code verbatim, unescaped."""
    from tests.reader_fixture import brief as make_brief
    kw = reader_kwargs()
    kw["brief"]["destination"]["local_lang"] = "<img src=x onerror=alert(1)>"
    pm = poi_map()
    pm["hak-goryokaku"]["sources"][0]["lang"] = 5
    html = render_reader(itinerary(), pm, **kw)
    assert "<img src=x" not in html.lower()


def test_fractional_minutes_do_not_crash_a_tight_transfer():
    """P4 review I4: hhmm() formatted with :02d and raised on a float."""
    itin = itinerary()
    itin["days"][1]["rows"][2]["mins"] = 20.5
    itin["days"][1]["rows"][3]["time"] = "09:00"
    assert _day(2, itin).select(".tight")


def test_no_gap_is_claimed_when_the_previous_stay_is_unknown():
    """P4 review (re-graded): without typical_visit_mins the gap swallowed the visit."""
    pm = poi_map()
    pm["hak-goryokaku"]["hours"].pop("typical_visit_mins")
    html = render_reader(itinerary(), pm, **reader_kwargs())
    d = BeautifulSoup(html, "html.parser").select_one('section.page.day[data-pg="d2"]')
    assert [g.get_text() for g in d.select(".gap")] == ["空檔 40 分", "空檔 50 分"]


def test_a_photo_shown_on_several_days_is_embedded_once():
    # real corpus (trip-e, v1.0 P7): 34 photos, 24 distinct -- 1.3 MB of repeats
    from scripts.render.reader import render_reader
    from tests.reader_fixture import MEDIA, itinerary, poi_map, reader_kwargs
    itin = itinerary()
    goryokaku = next(r for r in itin["days"][1]["rows"] if r.get("poi_id") == "hak-goryokaku")
    itin["days"][2]["rows"][2:2] = [dict(goryokaku, time="10:00"), itin["days"][2]["rows"][2]]
    html = render_reader(itin, poi_map(), **reader_kwargs())
    data = MEDIA["hak-goryokaku"]["photo"]["data"]
    soup = BeautifulSoup(html, "html.parser")
    assert len(soup.select('.stop[data-poi="hak-goryokaku"] figure.bp .bpi')) == 2
    assert html.count(data) == 1


def test_the_day_header_row_is_back_monthrange_and_a_slot():
    d = _day(2)
    row = d.select_one(".pcal .ymrow")
    kids = row.find_all(recursive=False)
    assert [k.name for k in kids] == ["label", "b", "span"]
    assert kids[0]["for"] == "pg-home" and kids[1].get_text() == "2026 年 10 月"


def test_the_title_carries_day_n_and_no_date_line_or_tip_remains():
    d = _day(2)
    dh = d.select_one(".pcal h2.dh")
    # the phone's Day chip became the 「‹ Day 2 ›」 stepper (the user's check, pick S1)
    assert dh.select_one(".dht").get_text() == "早市的蟹，山頂的夜" and dh.select_one(".dstep .dn").get_text() == "Day 2"
    assert not d.select(".dt") and not d.select(".tip")
    # the list card holds the chain plus, since v1.1 topic 6 (pick D2), the desktop's copy of
    # the title at its top (hidden on the phone, theme.py)
    assert [h["class"] for h in d.select(".plist .dh")] == [["dh", "dh-list"]]


def test_a_photo_opens_fullscreen_through_its_own_checkbox():
    import re
    html = render_reader(itinerary(), poi_map(), **reader_kwargs())
    s = BeautifulSoup(html, "html.parser")
    figs = s.select("figure.bp")
    assert figs
    for f in figs:
        cb, lab = f.select_one("input.pz"), f.select_one("label.bpz")
        assert cb["type"] == "checkbox" and lab["for"] == cb["id"] and lab.select_one(".bpi")
    ids = re.findall(r'\sid="([^"]+)"', html)
    assert len(ids) == len(set(ids))
