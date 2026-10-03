"""v1.1 topic 7: six valid day-title candidates for test itineraries.

The gate requires `theme_candidates` on every day. Fixtures that predate topic 7 keep
their own theme (marked theme_user_written, so their assertions on the theme text stand)
and gain a generated six that passes scripts/day_titles.py: lengths 5/7, 8/9, 10/16;
skeletons whole x2, two x2, question, three; no keyword from the lexicon, no signature
shape, and every line varies by day: no line may sit on two days."""
from scripts.day_chain import node_poi_ids

POOL = "燈霧雪星月雲霞潮霜泉港湖河浪煙光"


def six(i=0, refs=("a",)):
    w, r = POOL[i % len(POOL)], list(refs)
    return [
        {"text": f"{w}在等我們", "shape": "sentence", "twist": "pov", "refs": r},
        {"text": f"{w}上的燈，山頂的風", "shape": "couplet", "twist": "rhyme", "refs": r},
        {"text": f"{w}會記得我嗎？", "shape": "question", "twist": "exaggerate", "refs": r},
        {"text": f"走到最後才看見{w}", "shape": "sentence", "twist": "turn", "refs": r},
        {"text": f"晨的光、午的港、夜的{w}", "shape": "triple", "twist": "contrast", "refs": r},
        {"text": f"山頂的{w}，在數我們的步伐", "shape": "couplet", "twist": "pov", "refs": r},
    ]


def add_titles(itinerary, keep_theme=True):
    """Give every day a valid six. keep_theme: an existing theme stays as the user's own."""
    for i, d in enumerate((itinerary or {}).get("days") or []):
        if "theme_candidates" in d:
            continue                                     # the test wrote its own
        nodes = sorted(node_poi_ids(d))
        refs = [r for r in d.get("theme_refs") or [] if r in nodes][:1] or nodes[:1] or ["a"]
        d["theme_candidates"] = six(i, refs)
        if keep_theme and d.get("theme"):
            d["theme_user_written"] = True
        else:
            d["theme"], d["theme_refs"] = d["theme_candidates"][0]["text"], refs
            d.pop("theme_user_written", None)
    return itinerary
