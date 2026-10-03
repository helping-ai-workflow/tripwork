"""v1.1 topic 7 (spec §7.4): Taiwan readings from 教育部《國語小字典》, shipped unmodified."""
import hashlib
import pathlib
import re

import pytest

from scripts import zhuyin

DICT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "dict" / "moe-mini"


def test_the_shipped_files_are_the_ministrys_unmodified():
    rows = re.findall(r"^\| (\S+) \| ([0-9a-f]{64}) \|$", (DICT / "SOURCE.md").read_text(encoding="utf-8"), re.M)
    assert {n for n, _ in rows} == {"dict_mini_2019_20260929.xlsx", "minidict_10312.pdf"}
    for name, digest in rows:
        assert hashlib.sha256((DICT / name).read_bytes()).hexdigest() == digest, name
    assert zhuyin.XLSX.name == "dict_mini_2019_20260929.xlsx"


@pytest.mark.parametrize("text,i,want", [
    ("星期", 1, "ㄑㄧˊ"), ("危", 0, "ㄨㄟˊ"), ("頭髮", 1, "ㄈㄚˇ"), ("企", 0, "ㄑㄧˋ"),
    ("垃圾", 0, "ㄌㄜˋ"), ("垃圾", 1, "ㄙㄜˋ"),
])
def test_taiwan_readings_where_the_mainland_differs(text, i, want):
    assert zhuyin.reading(text, i) == want


@pytest.mark.parametrize("text,i,want", [("銀行", 1, "ㄏㄤˊ"), ("行李", 0, "ㄒㄧㄥˊ"),
                                          ("音樂", 1, "ㄩㄝˋ"), ("快樂", 1, "ㄌㄜˋ")])
def test_a_polyphone_reads_by_its_neighbour(text, i, want):
    assert len(zhuyin.readings(text[i])) > 1
    assert zhuyin.reading(text, i) == want


def test_no_neighbour_to_decide_means_no_reading():
    assert len(zhuyin.readings("行")) > 1
    assert zhuyin.reading("行", 0) is None
    assert zhuyin.reading("a", 0) is None and zhuyin.reading("㐀", 0) is None


@pytest.mark.parametrize("zy,want", [
    ("ㄒㄧㄝˋ", ("ㄝ", 4)), ("ㄧㄝˋ", ("ㄝ", 4)), ("ㄅㄟ", ("ㄟ", 1)), ("ㄉㄨㄟ", ("ㄟ", 1)),
    ("ㄉㄥ", ("ㄥ", 1)), ("ㄈㄥ", ("ㄥ", 1)), ("ㄩㄥˇ", ("ㄥ", 3)), ("ㄕˋ", ("ㄧ", 4)), ("ㄩˊ", ("ㄧ", 2)),
    ("ㄦˊ", ("ㄧ", 2)), ("ㄏㄨˊ", ("ㄨ", 2)), ("ㄏㄨㄛˇ", ("ㄛㄜ", 3)), ("ㄌㄜˋ", ("ㄛㄜ", 4)),
    ("˙ㄉㄜ", ("ㄛㄜ", 0)), ("ㄏㄨㄢ", ("ㄢ", 1)), ("ㄩㄣˊ", ("ㄣ", 2)), ("ㄧㄤˊ", ("ㄤ", 2)),
    ("ㄧㄠˋ", ("ㄠ", 4)), ("ㄐㄧㄡˇ", ("ㄡ", 3)), ("ㄏㄞˇ", ("ㄞ", 3)), ("ㄐㄧㄚ", ("ㄚ", 1)),
])
def test_rhyme_group_and_tone(zy, want):
    assert zhuyin.syllable_key(zy) == want
