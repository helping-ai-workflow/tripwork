"""Taiwan Mandarin readings from 教育部《國語小字典》 (v1.1 topic 7, spec §7.4).

The dictionary ships unmodified under assets/dict/moe-mini/ (CC BY-ND 3.0 TW; see
SOURCE.md there). pypinyin-style data gives mainland readings (星期 qī, 垃圾 lājī); a
rhyme checked on those is wrong for a Taiwanese reader, so this module reads the
Ministry's own 注音 with the standard library only (an xlsx is a zip of XML).

A polyphone is read by its neighbours: every 解釋 in the dictionary is annotated
character by character (`&&日ㄖˋ&&期ㄑㄧˊ&&`), so the readings a character takes
next to a given neighbour are on record. A pairing seen once may straddle two words
(排成行列 puts 行 ㄏㄤˊ after 成, wrong for 七人成行), so a reading counts only when
the pairing is on record at least twice. When neither neighbour settles it, there is
no reading -- a title is then never labelled a rhyme on a guess.
"""
import collections
import functools
import pathlib
import xml.etree.ElementTree as ET
import zipfile

XLSX = pathlib.Path(__file__).resolve().parents[1] / "assets" / "dict" / "moe-mini" / "dict_mini_2019_20260929.xlsx"
_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
TONES = {"ˊ": 2, "ˇ": 3, "ˋ": 4}
INITIALS = set("ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙ")
MEDIALS = set("ㄧㄨㄩ")
_GROUP = {"ㄚ": "ㄚ", "ㄛ": "ㄛㄜ", "ㄜ": "ㄛㄜ", "ㄝ": "ㄝ", "ㄞ": "ㄞ", "ㄟ": "ㄟ", "ㄠ": "ㄠ",
          "ㄡ": "ㄡ", "ㄢ": "ㄢ", "ㄣ": "ㄣ", "ㄤ": "ㄤ", "ㄥ": "ㄥ", "ㄦ": "ㄧ"}
# the rhyme groups (韻轍) of spec §7.1, in the order the picker names them
MIN_RECORDS = 2
RHYME_GROUPS = ("ㄚ", "ㄛㄜ", "ㄝ", "ㄞ", "ㄟ", "ㄠ", "ㄡ", "ㄢ", "ㄣ", "ㄤ", "ㄥ", "ㄧ", "ㄨ")


def _cells(z):
    strings = [("".join(t.text or "" for t in si.iter(_NS + "t")))
               for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall(_NS + "si")]
    for row in ET.fromstring(z.read("xl/worksheets/sheet1.xml")).iter(_NS + "row"):
        out = {}
        for c in row.findall(_NS + "c"):
            v = c.find(_NS + "v")
            if v is not None:
                out[c.get("r").rstrip("0123456789")] = strings[int(v.text)] if c.get("t") == "s" else v.text
        yield out


def _annotated(text):
    """[(char, reading)] from a 解釋 cell; punctuation tokens carry no reading."""
    out = []
    for tok in (text or "").split("&&"):
        if len(tok) >= 2 and ("ㄅ" <= tok[1] <= "ㄩ" or tok[1] in "˙ㄦ"):
            out.append((tok[0], tok[1:]))
        elif tok:
            out.append((None, None))
    return out


@functools.lru_cache(maxsize=1)
def _data():
    entries, before, after = {}, {}, {}
    with zipfile.ZipFile(XLSX) as z:
        for k, row in enumerate(_cells(z)):
            if k == 0:
                continue                                    # 單字 部首 … 注音 解釋
            ch, zy = row.get("A"), row.get("E")
            if ch and zy:
                entries.setdefault(ch, [])
                if zy not in entries[ch]:
                    entries[ch].append(zy)
            toks = _annotated(row.get("F"))
            for (c1, r1), (c2, r2) in zip(toks, toks[1:]):
                if c1 and c2:
                    after.setdefault((c1, c2), collections.Counter())[r1] += 1   # c1's reading when c2 follows
                    before.setdefault((c2, c1), collections.Counter())[r2] += 1  # c2's reading when c1 precedes
    return entries, before, after


def readings(ch):
    """Every reading the dictionary lists for one character (its own entries)."""
    return list(_data()[0].get(ch, []))


def reading(text, i):
    """The reading of text[i] in context, or None when the dictionary cannot say."""
    entries, before, after = _data()
    ch = text[i]
    own = entries.get(ch, [])
    if len(own) == 1:
        return own[0]
    if not own:
        return None
    def seen(table, key):                       # readings on record at least twice
        return {r for r, n in table.get(key, {}).items() if n >= MIN_RECORDS and r in own}

    sides = []
    if i > 0:
        sides.append(seen(before, (ch, text[i - 1])))
    if i + 1 < len(text):
        sides.append(seen(after, (ch, text[i + 1])))
    sides = [s for s in sides if s]
    if not sides:
        return None
    both = set.intersection(*sides) if len(sides) > 1 else sides[0]
    if len(both) == 1:
        return next(iter(both))
    union = set.union(*sides)
    return next(iter(union)) if len(union) == 1 else None


def syllable_key(zy):
    """(rhyme group, tone) of one 注音 syllable; tone 0 is the neutral tone (˙)."""
    tone = 0 if zy.startswith("˙") else TONES.get(zy[-1:], 1)
    body = [c for c in zy if c not in "˙ˊˇˋ"]
    if body and body[0] in INITIALS:
        body = body[1:]
    if body and body[-1] in _GROUP:
        return _GROUP[body[-1]], tone
    if body and body[-1] in MEDIALS:
        return ("ㄨ" if body[-1] == "ㄨ" else "ㄧ"), tone
    return "ㄧ", tone                                       # ㄓㄔㄕㄖㄗㄘㄙ alone: the empty rhyme
