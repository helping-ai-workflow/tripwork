"""v1.0 P1 — trip-brief 的 short_name / day_label / KUSO headline（spec §4.5、§5.2）。"""
import copy

from scripts.brief_names import (deliverable_stem, headline_failures, must_do_names,
                                 name_failures, riff_overlap_ok, trip_length_label)

BRIEF = {
    "dates": {"start": "2026-10-12", "end": "2026-10-19"},
    "short_name": "北海道",
    "must_do": ["函館", "螃蟹季海鮮", "溫泉住宿"],
    "headline": {"text": "北海道泡螃蟹吃溫泉"},
    "headline_candidates": [
        {"text": "北海道泡螃蟹吃溫泉", "device": "swap", "riff_on": "泡溫泉吃螃蟹",
         "refs": ["螃蟹季海鮮", "溫泉住宿"]},
        {"text": "蟹蟹北海道", "device": "pun", "riff_on": "謝謝北海道", "refs": ["螃蟹季海鮮"]},
        {"text": "熊在看我們吃螃蟹", "device": "pov", "refs": ["螃蟹季海鮮"]},
        {"text": "泡完溫泉，螃蟹才是主角", "device": "contrast", "refs": ["螃蟹季海鮮", "溫泉住宿"]},
        {"text": "八天吃空半個海", "device": "exaggerate", "refs": ["螃蟹季海鮮"]},
        {"text": "函館的夜景很下飯", "device": "double_meaning", "riff_on": "很下飯", "refs": ["函館"]},
    ],
}
H = "trip-brief headline invalid: "
N = "trip-brief name invalid: "


def _b(**over):
    b = copy.deepcopy(BRIEF)
    b.update(over)
    return b


def test_length_label_for_a_multi_day_trip():
    assert trip_length_label(BRIEF) == "8天7夜"


def test_length_label_for_a_same_day_trip():
    b = _b(dates={"start": "2026-05-20", "end": "2026-05-20"})
    assert trip_length_label(b) == "一日遊"
    assert trip_length_label(dict(b, day_label="展覽晚餐")) == "展覽晚餐"


def test_deliverable_stem():
    assert deliverable_stem(BRIEF) == "2026-10-12 北海道 8天7夜"


def test_a_good_brief_has_no_name_failures():
    assert name_failures(BRIEF) == []


def test_the_spec_example_that_is_exactly_22_chars_passes():
    b = _b(short_name="海邊露營烤肉", dates={"start": "2026-05-02", "end": "2026-05-03"})
    assert len(deliverable_stem(b)) == 22 and name_failures(b) == []


def test_a_stem_over_22_chars_fails():
    b = _b(short_name="海邊露營烤肉派對", dates={"start": "2026-05-02", "end": "2026-05-03"})
    assert name_failures(b) == [N + "deliverable name is 24 chars (max 22)"]


def test_short_name_is_required():
    b = _b()
    b.pop("short_name")
    assert name_failures(b) == [N + "short_name missing"]


def test_short_name_length_and_charset():
    assert name_failures(_b(short_name="北")) == [N + "short_name is 1 chars (2–8)"]
    assert name_failures(_b(short_name="北海道/函館")) == [
        N + "short_name has characters a filename cannot carry"]


def test_day_label_only_on_a_same_day_trip():
    assert name_failures(_b(day_label="展覽晚餐")) == [N + "day_label is only for a same-day trip"]


def test_day_label_length():
    b = _b(dates={"start": "2026-05-20", "end": "2026-05-20"}, day_label="展")
    assert name_failures(b) == [N + "day_label must be 2–6 filename-safe characters"]


def test_malformed_dates_are_a_failure_not_an_exception():
    assert name_failures(_b(dates={"start": "2026-13-40", "end": "2026-10-19"})) == [
        N + "dates are not valid ISO dates"]


def test_must_do_names_accepts_the_dict_shape():
    b = _b(must_do=[{"name": "Lake Tekapo 星空 + 湖", "notes": "x"}, "峽灣郵輪"])
    assert must_do_names(b) == ["Lake Tekapo 星空 + 湖", "峽灣郵輪"]


def test_riff_overlap():
    assert riff_overlap_ok("北海道泡螃蟹吃溫泉", "泡溫泉吃螃蟹")
    assert riff_overlap_ok("蟹蟹北海道", "謝謝北海道")
    assert not riff_overlap_ok("泡溫泉吃螃蟹", "泡溫泉吃螃蟹")
    assert not riff_overlap_ok("北海道泡螃蟹吃溫泉", "今天天氣很好")


def test_a_good_headline_set_passes():
    assert headline_failures(BRIEF) == []


def test_headline_is_required():
    assert headline_failures(_b(headline={})) == [H + "headline missing"]


def test_the_chosen_headline_must_be_a_candidate_or_user_written():
    assert headline_failures(_b(headline={"text": "別的標題"})) == [
        H + "chosen headline is neither a candidate nor marked user_written"]
    assert headline_failures(_b(headline={"text": "別的標題", "user_written": True})) == []


def test_six_candidates():
    b = _b()
    b["headline_candidates"] = b["headline_candidates"][:3]
    assert H + "3 candidates recorded (6 required)" in headline_failures(b)


def test_the_first_six_use_each_device_once():
    b = _b()
    b["headline_candidates"][2]["device"] = "swap"
    b["headline_candidates"][2]["riff_on"] = "我們看熊吃螃蟹"
    assert H + "the first 6 candidates must use each of the six devices once" in headline_failures(b)


def test_a_later_batch_of_three_may_repeat_devices():
    b = _b()
    b["headline_candidates"] += [{"text": "熊看我們泡湯", "device": "pov", "refs": ["溫泉住宿"]},
                                 {"text": "螃蟹排隊等我們", "device": "pov", "refs": ["螃蟹季海鮮"]},
                                 {"text": "胃比行李先滿", "device": "exaggerate", "refs": ["螃蟹季海鮮"]}]
    assert headline_failures(b) == []


def test_meme_is_retired_and_double_meaning_needs_its_riff():
    b = _b()
    b["headline_candidates"][5]["device"] = "meme"
    assert H + "a candidate's device is not one of the six" in headline_failures(b)
    b = _b()
    b["headline_candidates"][5].pop("riff_on")
    assert headline_failures(b) == [H + "candidate 5 has no riff_on"]


def test_an_unknown_device_fails():
    b = _b()
    b["headline_candidates"][2]["device"] = "rhyme"
    assert H + "a candidate's device is not one of the six" in headline_failures(b)


def test_riff_devices_need_a_riff_on_that_they_rework():
    b = _b()
    b["headline_candidates"][0].pop("riff_on")
    assert headline_failures(b) == [H + "candidate 0 has no riff_on"]
    b["headline_candidates"][0]["riff_on"] = "今天天氣很好"
    assert headline_failures(b) == [H + "candidate 0 does not rework its riff_on"]


def test_refs_must_name_must_do_entries():
    b = _b()
    b["headline_candidates"][2]["refs"] = ["看熊"]
    assert headline_failures(b) == [H + "candidate 2 refs must name must_do entries"]


def test_refs_are_waived_when_there_is_no_must_do():
    b = _b(must_do=[])
    for c in b["headline_candidates"]:
        c["refs"] = []
    assert headline_failures(b) == []


def test_a_candidate_over_14_visible_chars_fails():
    b = _b()
    b["headline_candidates"][2]["text"] = "熊在看我們吃螃蟹還有溫泉跟夜景一起來"
    assert H + "candidate 2 is 18 chars (max 14)" in headline_failures(b)


def test_an_ai_toned_candidate_fails_without_hijacking_the_ai_tone_route():
    b = _b()
    b["headline_candidates"][2]["text"] = "熊在看——我們吃螃蟹"
    f = headline_failures(b)
    assert H + "candidate 2 fails the AI tone scan" in f
    assert not any("AI-tone " in x for x in f)
