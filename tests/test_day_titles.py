"""v1.1 topic 7 (spec §7.1): six day-title candidates per day, shape x twist, quotas,
Taiwan-reading rhyme, trip-wide repeats; the user's pick, notices only."""
import copy

import pytest

from scripts import day_titles as dt
from scripts.day_chain import theme_failures

D = "2026-10-13"
# a valid day: lengths 7/7, 8/9, 10/14; skeletons two x2, whole x2, question, three;
# scene A C D F; twist A C D E F
SIX = [
    {"text": "早市的蟹，山頂的夜", "shape": "couplet", "twist": "rhyme", "refs": ["mkt", "yama"]},
    {"text": "蟹看我，我看蟹", "shape": "chiasmus", "refs": ["mkt"]},
    {"text": "剝完蟹再上山看燈", "shape": "sentence", "twist": "turn", "refs": ["mkt", "yama"]},
    {"text": "山頂的燈替整座港口守夜", "shape": "sentence", "twist": "pov", "refs": ["yama"]},
    {"text": "夜景會等我嗎？", "shape": "question", "twist": "pov", "refs": ["yama"]},
    {"text": "晨的蟹、午的倉、夜的燈", "shape": "triple", "twist": "contrast", "refs": ["mkt", "soko", "yama"]},
]


def _day(date=D, cands=None, theme="早市的蟹，山頂的夜", **kw):
    d = {"date": date, "theme": theme, "theme_refs": ["mkt", "yama"],
         "theme_candidates": copy.deepcopy(SIX if cands is None else cands),
         "rows": [{"slot": "start", "poi_id": "hotel"}, {"mode": "walk", "mins": 5},
                  {"poi_id": "mkt"}, {"mode": "walk", "mins": 5}, {"poi_id": "soko"},
                  {"mode": "walk", "mins": 5}, {"poi_id": "yama"}, {"mode": "walk", "mins": 5},
                  {"slot": "end", "poi_id": "hotel"}]}
    d.update(kw)
    return d


def _with(k, **change):
    cands = copy.deepcopy(SIX)
    cands[k].update(change)
    for key, v in change.items():
        if v is None:
            cands[k].pop(key)
    return cands


def _f(*days):
    return dt.candidate_failures({"days": list(days)})


def test_a_valid_day_passes():
    assert _f(_day()) == []
    assert theme_failures({"days": [_day()]}) == []


@pytest.mark.parametrize("text,want", [
    ("早市的蟹，山頂的夜", ("ㄝ", 4)),          # ㄒㄧㄝˋ / ㄧㄝˋ
    ("啤酒一杯，烤羊一堆", ("ㄟ", 1)),          # ㄅㄟ / ㄉㄨㄟ
    ("湖上的燈，山頂的風", ("ㄥ", 1)),
    ("早市的蟹，山頂的燈", None),                # different groups
    ("看見了夜，吃到了蟹呀", ("ㄝ", 4)),        # trailing particles are skipped
    ("一碗丼，一座山", None),                    # 丼 is not in the dictionary
    ("吃一整天", None),                          # one segment: no two halves
])
def test_rhyme_on_taiwan_readings(text, want):
    assert dt.rhyme(text) == want


def test_same_rhyme_different_tone_is_not_a_rhyme():
    assert dt.rhyme("山上的雪，湖邊的街") is None                # ㄒㄩㄝˇ / ㄐㄧㄝ


@pytest.mark.parametrize("cands,needle", [
    (SIX[:5], "6 candidates"),
    (_with(0, text="早市的蟹，山頂的燈"), "candidate 0 is labelled rhyme"),
    (_with(3, text="山頂的燈替整座函館的港口守夜"), "candidate 3 is 14 chars (max 13)"),
    (_with(2, twist=None), "candidate 2 has no twist"),
    (_with(2, twist="meme"), "candidate 2 twist"),
    (_with(2, shape="four_char"), "candidate 2 shape"),
    (_with(4, text="夜景會等我們"), "candidate 4 is not a question"),
    (_with(1, text="蟹看我，我吃蟹"), "candidate 1 is not a chiasmus"),
    (_with(2, twist="pun"), "candidate 2 has no riff_on"),
    (_with(2, twist="pun", riff_on="今天天氣很好"), "candidate 2 does not rework its riff_on"),
    (_with(5, refs=["zzz"]), "candidate 5 refs"),
    (_with(5, refs=[]), "candidate 5 refs"),
    (_with(2, text="早市的蟹，山頂的夜"), "repeats"),
])
def test_each_candidate_rule_fails_its_violation(cands, needle):
    f = _f(_day(cands=cands))
    assert any(needle in m for m in f), f


def test_the_quotas():
    no_scene = _with(0, text="早市的蟹，山頂的夜吧")              # ends 吧
    no_scene[2]["text"] = "剝完蟹再上山一下"
    assert any("scene" in m for m in _f(_day(cands=no_scene, theme=no_scene[0]["text"])))
    few_twists = copy.deepcopy(SIX)                                  # only A and F keep a twist
    for k, text in ((2, "剝完一隻蟹再看燈"), (3, "山頂的燈替一整座港守夜"), (4, "夜景等一個我嗎？")):
        few_twists[k].pop("twist")
        few_twists[k].update(text=text, shape="number")
    assert any("twist" in m for m in _f(_day(cands=few_twists)))
    three_whole = _with(5, text="晨的蟹午的倉夜的燈港口", shape="sentence")
    assert any("skeleton" in m for m in _f(_day(cands=three_whole)))
    sizes = _with(1, text="蟹看我呀，我看蟹呀")                     # short -> mid: 1/3/2
    assert any("lengths" in m for m in _f(_day(cands=sizes)))


def test_extra_candidates_skip_the_quotas_but_not_the_rules():
    more = SIX + [{"text": "纜車上去，嘴巴張開", "shape": "couplet", "twist": "exaggerate", "refs": ["yama"]},
                  {"text": "倉庫裡的燈", "shape": "sentence", "twist": "pov", "refs": ["soko"]},
                  {"text": "港口的夜被我打包回家", "shape": "sentence", "twist": "exaggerate", "refs": ["yama"]}]
    assert _f(_day(cands=more)) == []
    more[7]["refs"] = ["ghost"]
    assert any("candidate 7 refs" in m for m in _f(_day(cands=more)))


def test_no_candidates_routes_back_to_synthesis():
    d = _day()
    d.pop("theme_candidates")
    f = theme_failures({"days": [d]})
    assert f == [f"day theme invalid: {D} has no theme_candidates (6 for the user to pick from)"]


def test_the_chosen_theme_is_a_candidate_or_user_written():
    f = theme_failures({"days": [_day(theme="隨便寫的")]})
    assert any("is not one of its candidates" in m for m in f)
    assert theme_failures({"days": [_day(theme="隨便寫的", theme_user_written=True, theme_refs=[])]}) == []
    long = theme_failures({"days": [_day(theme="這是一句自己寫但太長的標題啦", theme_user_written=True)]})
    assert any("max 13" in m for m in long)


def _trip(n, edit=None):
    days = []
    for k in range(n):
        cands = copy.deepcopy(SIX)
        if edit:
            edit(k, cands)
        days.append(_day(date=f"2026-10-{13 + k}", cands=cands, theme=cands[0]["text"]))
    return days


def test_a_keyword_in_three_days_fails():
    f = _f(*_trip(3))
    assert any("keyword 蟹 appears in the candidates of 3 days (max 2)" in m for m in f), f
    assert not any("keyword" in m for m in _f(*_trip(2)))


def test_a_signature_shape_in_three_days_fails():
    f = _f(*_trip(3))
    assert any("shape chiasmus is used on 3 days (max 2)" in m for m in f), f


def test_onomatopoeia_may_not_repeat_its_first_character():
    def ono(k, cands):
        cands[1].update(text=("咕嚕咕嚕，冬天" if k == 0 else "咕嘟咕嘟，夜裡"), shape="onomatopoeia")
    f = _f(*_trip(2, ono))
    assert any("onomatopoeia" in m for m in f), f


def test_display_order_is_short_to_long_and_extras_stay_after():
    order = dt.display_order(SIX + [{"text": "一"}, {"text": "一二三四五六七八九十"}, {"text": "一二"}])
    assert [len(SIX[k]["text"]) for k in order[:6]] == sorted(len(c["text"]) for c in SIX)
    assert order[6:] == [6, 8, 7]


def test_pick_notices():
    days = _trip(2)
    days[0]["theme"], days[1]["theme"] = SIX[0]["text"], SIX[1]["text"]     # both two-part
    n = dt.pick_notices({"days": days})
    assert any("2026-10-13 and 2026-10-14 both have the two-part skeleton" in m for m in n), n
    days[1]["theme"] = SIX[2]["text"]
    assert not any("skeleton" in m for m in dt.pick_notices({"days": days}))
    trip = _trip(3)
    for d in trip:
        d["theme"] = SIX[3]["text"]                                         # pov on 3 of 3 days
    assert any("twist pov is picked on 3 days" in m for m in dt.pick_notices({"days": trip}))


def test_the_gate_reports_pick_notices_and_still_passes():
    from scripts.gate import run_gate
    from tests import mech_fixtures as M
    kw = M.rederive_kwargs(accommodations=M.accommodations())
    kw["advisory"] = M.advisory()
    itin = M.itinerary()
    a, b = itin["days"]
    for d, k in ((a, 1), (b, 5)):                          # two-part, two-part
        c = d["theme_candidates"][k]
        d.update(theme=c["text"], theme_refs=c["refs"])
        d.pop("theme_user_written")
    rep = run_gate(M.verified_pois()["pois"], itin, **kw)
    assert rep["status"] == "pass", rep["failures"]
    assert f"day titles: {a['date']} and {b['date']} both have the two-part skeleton" in (rep.get("notices") or [])


def test_the_references_examples_pass_the_shipped_checks():
    """skills/itinerary-synthesis/references/day-titles.md teaches by example; each shape
    example must be that shape and each rhyme example must (or must not) rhyme by the
    same code the gate runs."""
    import pathlib
    import re
    ref = (pathlib.Path(__file__).resolve().parents[1] / "skills" / "itinerary-synthesis"
           / "references" / "day-titles.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| `(\w+)` \| [^|]+ \| ([^|]+) \|$", ref, re.M)
    shapes = {s: ex.strip() for s, ex in rows if s in dt.SHAPES}
    assert set(shapes) == set(dt.SHAPES)
    for s, ex in shapes.items():
        assert dt._shape_ok(s, ex), (s, ex)
        assert len(ex) <= dt.THEME_MAX
    assert dt.rhyme("早市的蟹，山頂的夜") and "蟹 ㄒㄧㄝˋ／夜 ㄧㄝˋ 押韻" in ref
    assert dt.rhyme("啤酒一杯，烤羊一堆") and "杯 ㄅㄟ／堆 ㄉㄨㄟ 押韻" in ref
    assert dt.rhyme("山上的雪，湖邊的街") is None and "雪 ㄒㄩㄝˇ／街 ㄐㄧㄝ 同韻不同調" in ref
    for w in dt.BAD_END:
        assert w in ref


def test_a_keyword_counts_inside_longer_words():
    """螃蟹 is 蟹: the trip-wide cap may not be dodged by writing the longer word."""
    def crab(k, cands):
        if k == 0:
            for c in cands:
                c["text"] = c["text"].replace("蟹", "螃蟹") if len(c["text"].replace("蟹", "螃蟹")) <= 13 else c["text"]
    f = _f(*_trip(3, crab))
    assert any("keyword 蟹 appears in the candidates of 3 days (max 2)" in m for m in f), f


# ---- final review fixes ----------------------------------------------------

def test_a_candidate_is_scanned_for_ai_tone_without_quoting_it():
    f = _f(_day(cands=_with(1, text="蟹看我——我看蟹", shape="sentence", twist="pov")))
    hit = [m for m in f if "candidate 1 fails the AI tone scan" in m]
    assert hit and "——" not in hit[0]


def test_the_same_line_on_two_days_fails_before_the_user_can_pick_it_twice():
    f = _f(_day(date="2026-10-13"), _day(date="2026-10-14"))
    assert any("2026-10-14 candidate 0 repeats a candidate of 2026-10-13" in m for m in f), f


def test_a_polyphone_needs_more_than_one_record_to_be_read():
    from scripts import zhuyin
    assert zhuyin.reading("七人成行", 3) is None            # one cross-word record (排成行列) is not enough
    assert dt.rhyme("七人成行，湯屋滿堂") is None
