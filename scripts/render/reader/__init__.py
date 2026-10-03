"""The v1.0 reader: one self-contained, offline HTML page, CSS-driven, whose only script is the
desktop centring constant in centre.py (spec §6)."""
from scripts.render.reader.page import render_reader

__all__ = ["render_reader"]
