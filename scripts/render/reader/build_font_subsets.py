"""One-off asset build: pre-subset 源泉圓體 TW (GenSen Rounded 2 TW) M/B to the
Big5 common set + kana + ASCII + CJK/fullwidth punctuation.

The full OTFs are ~15 MB each; shipping them whole would add 30 MB to every
plugin install for glyphs a trip page almost never uses. The subset (~2.5 MB each)
keeps every Big5 level-1 character; a rarer character falls through to the system
font, which is already the last step of the reader's font chain (spec §6.6 R3).
Zen Maru Gothic ships unsubset (it is the primary face).

    python scripts/render/reader/build_font_subsets.py <dir holding GenSenRounded2TW-{M,B}.otf>

Source: GenSen Rounded 2 TW v2.100 (https://github.com/ButTaiwan/gensen-font), SIL OFL 1.1.
"""
import pathlib
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

OUT = pathlib.Path(__file__).resolve().parents[3] / "assets" / "fonts"


def charset():
    chars = set()
    for hi in range(0xA4, 0xC7):                      # Big5 level 1 (常用字)
        for lo in list(range(0x40, 0x7F)) + list(range(0xA1, 0xFF)):
            try:
                chars.add(bytes([hi, lo]).decode("big5"))
            except UnicodeDecodeError:
                pass
    chars |= {chr(c) for c in range(0x20, 0x7F)}           # ASCII
    chars |= {chr(c) for c in range(0x3000, 0x3100)}       # CJK punctuation + kana
    chars |= {chr(c) for c in range(0xFF00, 0xFFF0)}       # fullwidth forms
    chars |= set("・–—…“”‘’→←↺＋")
    return "".join(sorted(chars))


def main(argv):
    src = pathlib.Path(argv[0])
    text = charset()
    for w in ("M", "B"):
        font = TTFont(src / f"GenSenRounded2TW-{w}.otf")
        sub = subset.Subsetter(subset.Options())
        sub.populate(text=text)
        sub.subset(font)
        out = OUT / f"GenSenRounded2TW-{w}.subset.otf"
        font.save(out)
        print(f"{out.name}: {out.stat().st_size / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
