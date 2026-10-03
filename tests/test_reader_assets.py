"""v1.0 P4 — the reader's fonts and icons ship with the plugin, licences included."""
import pathlib
import re

from scripts.render.reader.assets import FONT_FILES, ICON_DIR, ICONS_USED, icon

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_font_files_and_their_licence_ship():
    for path in FONT_FILES.values():
        assert path.is_file(), path
    assert (ROOT / "assets" / "fonts" / "OFL.txt").is_file()


def test_every_icon_the_reader_uses_ships_with_its_licence():
    for name in ICONS_USED:
        assert (ICON_DIR / f"{name}.svg").is_file(), name
    assert (ICON_DIR / "LICENSE").is_file()


def test_icons_are_stroke_currentcolor_and_sizeless():
    svg = icon("train-front", "lu m-rail")
    assert svg.startswith('<svg class="lu m-rail" aria-hidden="true"')
    assert 'stroke="currentColor"' in svg and "<!--" not in svg
    assert not re.search(r'\s(width|height)="', svg)          # stroke-width is fine


def test_every_lucide_icon_comes_from_one_release():
    """v1.1: the bundle had mixed lucide-static 0.460.0 and 0.469.0 (later additions
    fetched from a newer release). One release for all, so a refresh is one step."""
    versions = {re.search(r"lucide-static v([\d.]+)", (ICON_DIR / f"{n}.svg").read_text(encoding="utf-8")).group(1)
                for n in ICONS_USED}
    assert versions == {"0.469.0"}, versions
