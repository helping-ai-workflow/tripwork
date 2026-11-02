"""行前清單 and reservations: a booked place's 預約 line hides, a todo derives one, and the
approximate-coordinate disclosures fold into one line."""
from scripts import reservation as R
from scripts.render.centroid import merged_line, merged_note
from scripts.text_hygiene import ai_tone_failures, jargon_failures, kana_gloss_failures
from tests import reservation_fixture as F

SKY = {"kind": "預約", "task": "晴空塔線上預約時段票", "due": "2026-05-05", "due_is_hard": True, "poi_id": "skytree"}


def _visible(checklist, res=None, poi_map=None):
    itin = F.itinerary()
    itin["checklist"] = checklist
    return R.visible_checklist(itin, F.legs(), res or F.reservations(), poi_map or F.poi_map())


def _tasks(items):
    return [i["task"] for i in items]


def test_booked_place_hides_its_line():
    assert "晴空塔線上預約時段票" not in _tasks(_visible([SKY]))


def test_booked_leg_hides_its_seat_reminder():
    seat = {"kind": "預約", "task": "去程劃位", "leg_index": 0}
    assert "去程劃位" not in _tasks(_visible([seat]))


def test_old_line_without_poi_id_stays_visible():
    """A line that does not say what it is for is never hidden by a matching due date (the
    review found a seat reminder opening the same minute as a booked restaurant). The skill
    gives the line its poi_id when the booking is recorded."""
    pm = F.poi_map()
    pm["skytree"]["booking"] = {"required": True, "opens_at": "2026-05-05"}
    old = {k: v for k, v in SKY.items() if k != "poi_id"}
    assert "晴空塔線上預約時段票" in _tasks(_visible([old], poi_map=pm))


def test_todo_derives_one_line():
    items = _visible([])
    assert {"kind": "預約", "task": "訂上野示意洋食 13:00，3 位", "origin": "D2・5/13"} in items


def test_todo_with_a_written_line_is_not_doubled():
    mine = {"kind": "預約", "task": "訂洋食", "poi_id": "yoshoku"}
    tasks = _tasks(_visible([mine]))
    assert tasks.count("訂洋食") == 1 and not any(t.startswith("訂上野示意洋食") for t in tasks)


def test_unbooked_lines_and_strings_stay():
    sky = dict(SKY)
    res = F.reservations()
    next(r for r in res["reservations"] if r.get("poi_id") == "skytree")["status"] = "todo"
    items = _visible([sky, "帶護照"], res=res)
    assert "晴空塔線上預約時段票" in _tasks(items)
    assert {"kind": "出發前確認", "task": "帶護照"} in items


def test_no_reservations_keeps_the_checklist():
    itin = F.itinerary()
    itin["checklist"] = [SKY]
    assert R.visible_checklist(itin, F.legs(), None, F.poi_map()) == [SKY]


def _approx(pm, *ids):
    for pid in ids:
        pm[pid]["geocode"]["geocode_source"] = "cluster_fallback"
    return pm


def test_merged_note_is_one_item():
    pm = _approx(F.poi_map(), "kappo", "izakaya", "yoshoku")
    note = merged_note(F.itinerary(), pm)
    assert note["kind"] == "出發前確認"
    assert note["task"] == "3 個地點的地圖只標到區域中心"
    assert note["detail"].startswith("浅草サンプル居酒屋（淺草示意居酒屋）、上野サンプル洋食（上野示意洋食）、押上サンプル割烹（押上示意割烹）：")
    assert "距離與步行時間請出發前自行確認" in note["detail"]
    assert merged_line(F.itinerary(), pm).startswith("3 個地點的地圖只標到區域中心：浅草サンプル居酒屋")


def test_merged_note_none_without_approximate_places():
    assert merged_note(F.itinerary(), F.poi_map()) is None
    assert merged_line(F.itinerary(), F.poi_map()) is None


def test_generated_sentences_pass_the_text_checks():
    pm = _approx(F.poi_map(), "kappo")
    texts = _tasks(_visible([])) + [merged_note(F.itinerary(), pm)["task"], merged_line(F.itinerary(), pm)]
    joined = "\n".join(texts)
    assert ai_tone_failures(joined) == []
    assert jargon_failures(joined, list(pm.values())) == []
    assert kana_gloss_failures(joined) == []
