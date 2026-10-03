"""v1.1 topic 7 (spec §7.3): the reply line from the title picker (or typed by hand)
is parsed and written back into itinerary.yaml / trip-brief.yaml."""
import copy

import pytest
import yaml

from scripts import title_picks as tp
from scripts.day_titles import candidate_failures, display_order
from scripts.day_chain import theme_failures
from tests.title_fixture import six


def _itin(n=3):
    days = []
    for i in range(n):
        d = {"date": f"2026-10-{13 + i}", "rows": [{"poi_id": "a"}], "theme_candidates": six(i)}
        d["theme"], d["theme_refs"] = d["theme_candidates"][0]["text"], ["a"]
        days.append(d)
    return {"days": days}


def _brief():
    from tests.mech_fixtures import HEADLINE_CANDIDATES
    return {"headline": {"text": HEADLINE_CANDIDATES[0]["text"]},
            "headline_candidates": copy.deepcopy(HEADLINE_CANDIDATES)}


@pytest.mark.parametrize("line,want", [
    ('tripwork 標題 H=2 D1=3 D2="自己寫的" D5=+', {"H": 2, "days": {1: 3, 2: "自己寫的", 5: "+"}}),
    ("D1=2 D2=3", {"H": None, "days": {1: 2, 2: 3}}),
    ("ｔｒｉｐｗｏｒｋ　標題　Ｄ１＝２　ｄ２＝３", {"H": None, "days": {1: 2, 2: 3}}),
    ("tripwork 標題  D1 = 2 ,D3=＋", {"H": None, "days": {1: 2, 3: "+"}}),
    ("D1=「海邊的風」 H=“北海道蟹到底”", {"H": "北海道蟹到底", "days": {1: "海邊的風"}}),
    ("H=+", {"H": "+", "days": {}}),
])
def test_parse_the_reply(line, want):
    assert tp.parse(line) == want


@pytest.mark.parametrize("line", ["", "好", "D1", "D1=", "D0=2", "D1=0", "D1=2 D1=3", "X1=2", 'D1="沒關引號'])
def test_garbage_is_an_error(line):
    with pytest.raises(tp.PickError):
        tp.parse(line)


def test_a_pick_writes_the_candidate_in_display_order():
    itin, brief = _itin(), _brief()
    tp.apply(itin, brief, tp.parse("D1=3 D2=6"))
    for day, n in ((itin["days"][0], 3), (itin["days"][1], 6)):
        c = day["theme_candidates"][display_order(day["theme_candidates"])[n - 1]]
        assert day["theme"] == c["text"] and day["theme_refs"] == c["refs"]
        assert "theme_user_written" not in day
    assert theme_failures(itin) == []


def test_own_words_are_marked_and_checked_for_length():
    itin, brief = _itin(), _brief()
    tp.apply(itin, brief, tp.parse('D2="海邊的風" H="北海道蟹到底"'))
    assert itin["days"][1]["theme"] == "海邊的風" and itin["days"][1]["theme_user_written"] is True
    assert brief["headline"] == {"text": "北海道蟹到底", "user_written": True}
    assert theme_failures(itin) == []
    with pytest.raises(tp.PickError, match="13"):
        tp.apply(_itin(), _brief(), tp.parse('D1="這是一句自己寫但太長的標題啦"'))


def test_a_headline_pick_uses_the_stored_order():
    brief = _brief()
    tp.apply(_itin(), brief, tp.parse("H=4"))
    assert brief["headline"] == {"text": brief["headline_candidates"][3]["text"]}


def test_plus_asks_for_more_and_writes_nothing_for_that_day():
    itin, brief = _itin(), _brief()
    before = copy.deepcopy(itin["days"][2])
    more = tp.apply(itin, brief, tp.parse("D1=2 D3=+ H=+"))
    assert more == {"days": [3], "headline": True}
    assert itin["days"][2] == before


@pytest.mark.parametrize("line,needle", [("D4=2", "D4"), ("D1=7", "D1"), ("H=7", "H")])
def test_out_of_range_writes_nothing(line, needle):
    itin, brief = _itin(), _brief()
    snap = copy.deepcopy((itin, brief))
    with pytest.raises(tp.PickError, match=needle):
        tp.apply(itin, brief, tp.parse("D2=2 " + line))
    assert (itin, brief) == snap


def test_a_partial_reply_leaves_the_other_days():
    itin = _itin()
    tp.apply(itin, _brief(), tp.parse("D2=2"))
    assert itin["days"][0]["theme"] == itin["days"][0]["theme_candidates"][0]["text"]


def test_the_cli_writes_both_artifacts(tmp_path):
    from scripts.paths import artifact_path
    trip = tmp_path / "trip"
    artifact_path(trip, "itinerary.yaml").parent.mkdir(parents=True)
    artifact_path(trip, "itinerary.yaml").write_text(yaml.safe_dump(_itin(), allow_unicode=True), encoding="utf-8")
    artifact_path(trip, "trip-brief.yaml").write_text(yaml.safe_dump(_brief(), allow_unicode=True), encoding="utf-8")
    assert tp.main([str(trip), "tripwork 標題 H=2 D1=3 D3=+"]) == 0
    itin = yaml.safe_load(artifact_path(trip, "itinerary.yaml").read_text(encoding="utf-8"))
    brief = yaml.safe_load(artifact_path(trip, "trip-brief.yaml").read_text(encoding="utf-8"))
    assert brief["headline"]["text"] == brief["headline_candidates"][1]["text"]
    c0 = itin["days"][0]["theme_candidates"]
    assert itin["days"][0]["theme"] == c0[display_order(c0)[2]]["text"]
    assert candidate_failures(itin) == []
    assert tp.main([str(trip), "胡言亂語"]) == 2


# ---- final review fixes ----------------------------------------------------

def test_own_words_that_fail_the_ai_tone_scan_are_refused_at_reply_time():
    itin, brief = _itin(), _brief()
    snap = copy.deepcopy((itin, brief))
    with pytest.raises(tp.PickError, match="D1"):
        tp.apply(itin, brief, tp.parse('D1="海風——燈火"'))
    with pytest.raises(tp.PickError, match="H"):
        tp.apply(itin, brief, tp.parse('H="北海道——蟹"'))
    assert (itin, brief) == snap


def test_two_days_may_not_end_up_with_the_same_title():
    itin, brief = _itin(), _brief()
    snap = copy.deepcopy((itin, brief))
    with pytest.raises(tp.PickError, match="D2"):
        tp.apply(itin, brief, tp.parse('D1="海邊的風" D2="海邊的風"'))
    same = itin["days"][1]["theme"]
    with pytest.raises(tp.PickError, match="D1"):
        tp.apply(itin, brief, tp.parse(f'D1="{same}"'))                  # D2 already has it
    assert (itin, brief) == snap


def test_a_picked_day_is_marked_and_plus_leaves_the_mark():
    itin, brief = _itin(), _brief()
    tp.apply(itin, brief, tp.parse('D1=2 D2="海邊的風" D3=+'))
    assert itin["days"][0]["theme_picked"] is True and itin["days"][1]["theme_picked"] is True
    assert "theme_picked" not in itin["days"][2]
    assert theme_failures(itin) == []


def test_the_cli_leaves_an_unchanged_file_alone(tmp_path):
    from scripts.paths import artifact_path
    trip = tmp_path / "trip"
    artifact_path(trip, "itinerary.yaml").parent.mkdir(parents=True)
    ip, bp = artifact_path(trip, "itinerary.yaml"), artifact_path(trip, "trip-brief.yaml")
    ip.write_text(yaml.safe_dump(_itin(), allow_unicode=True), encoding="utf-8")
    bp.write_text("# the user's note\n" + yaml.safe_dump(_brief(), allow_unicode=True), encoding="utf-8")
    before = bp.read_text(encoding="utf-8")
    assert tp.main([str(trip), "D1=2"]) == 0
    assert bp.read_text(encoding="utf-8") == before                     # no H: the brief is not rewritten
    i_before = ip.read_text(encoding="utf-8")
    assert tp.main([str(trip), "H=2"]) == 0
    assert ip.read_text(encoding="utf-8") == i_before                   # no day: the itinerary is not rewritten


def test_plus_on_a_picked_day_opens_it_again():
    itin, brief = _itin(), _brief()
    tp.apply(itin, brief, tp.parse("D3=2"))
    tp.apply(itin, brief, tp.parse("D3=+"))
    assert "theme_picked" not in itin["days"][2]
