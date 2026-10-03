"""Fonts and icons the reader embeds (spec §6.6). Both ship with the plugin under
assets/, licences included; nothing is fetched at render time (the page must
open offline inside the iPhone Files app's Quick Look)."""
import base64
import functools
import io
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[3]
ASSETS = ROOT / "assets"
ICON_DIR = ASSETS / "icons" / "lucide"
_FONTS = ASSETS / "fonts"

# (family, weight) -> file. Order is the @font-face order in the page.
FONT_FILES = {
    ("ZenEmb", 500): _FONTS / "ZenMaruGothic-Medium.ttf",
    ("ZenEmb", 700): _FONTS / "ZenMaruGothic-Bold.ttf",
    ("GenSenEmb", 500): _FONTS / "GenSenRounded2TW-M.subset.otf",
    ("GenSenEmb", 700): _FONTS / "GenSenRounded2TW-B.subset.otf",
}

MODE_ICON = {"walk": "footprints", "rail": "train-front", "bus": "bus", "taxi": "car",
             "drive": "car", "ferry": "ship", "flight": "plane", "ropeway": "cable-car"}
SLOT_ICON = {"meal": "utensils", "visit": "map-pin", "activity": "mountain", "lodging": "bed-double"}
ICONS_USED = tuple(sorted(set(MODE_ICON.values()) | set(SLOT_ICON.values())
                          | {"book-open", "camera", "stamp", "list-checks", "navigation", "map", "moon", "sun"}))


@functools.lru_cache(maxsize=None)
def _svg(name):
    s = (ICON_DIR / f"{name}.svg").read_text(encoding="utf-8")
    s = re.sub(r"<!--.*?-->", "", s, flags=re.S)
    # the root <svg>'s fixed size only, so CSS sizes it -- a child's width / height is
    # its shape (cable-car's cabin is a <rect>; v1.1 fix)
    s = re.sub(r"<svg\b[^>]*>", lambda m: re.sub(r'\s(class|width|height)="[^"]*"', "", m.group(0)), s, count=1)
    return re.sub(r"\s*\n\s*", " ", s).strip()


def icon(name, cls="lu"):
    """Inline Lucide SVG: stroke=currentColor, no fixed size (CSS sizes it)."""
    return _svg(name).replace("<svg", f'<svg class="{cls}" aria-hidden="true"', 1)


@functools.lru_cache(maxsize=None)
def _font_bytes(path):
    return pathlib.Path(path).read_bytes()


@functools.lru_cache(maxsize=16)
def font_faces(text):
    """@font-face rules with each face subset to exactly `text`, woff2, base64."""
    from fontTools import subset
    from fontTools.ttLib import TTFont

    out = []
    for (family, weight), path in FONT_FILES.items():
        font = TTFont(io.BytesIO(_font_bytes(str(path))))
        opts = subset.Options()
        opts.flavor = "woff2"
        sub = subset.Subsetter(opts)
        sub.populate(text=text)
        sub.subset(font)
        font.flavor = "woff2"
        buf = io.BytesIO()
        font.save(buf)
        data = base64.b64encode(buf.getvalue()).decode()
        out.append(f"@font-face{{font-family:'{family}';src:url(data:font/woff2;base64,{data}) "
                   f"format('woff2');font-weight:{weight};font-display:block}}")
    return "".join(out)
