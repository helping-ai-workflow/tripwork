"""Privacy guard: the public repo never carries a user's trip (2026-10-03).

The first public tripwork repo shipped one user's trips -- screenshots of a future trip
(hotels, dates, costs), test fixtures copying its hotels and dates, defect reports and
corpus tests reading their trips by name. It was rebuilt from one clean commit. Two layers
keep it from happening again:

- Rules that run everywhere (CI included): what may be tracked at all, which images and
  e-mail addresses, and the shape of the de-identified corpus under tests/corpus/.
- A check that runs where a consumer workspace exists (the maintainer's machine, before
  every PR -- the pre-ship gate runs the full suite): every identifying string of the
  workspace's trips (slugs, the hotels actually stayed at, members, home endpoints, the
  dates of trips still ahead) is derived from the workspace itself and must appear in no
  tracked file. The list is never written into the repo -- that would be the leak.
"""
import datetime
import os
import pathlib
import re
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKSPACE = pathlib.Path(os.environ.get("TRIPWORK_WORKSPACE", str(ROOT.parent / "tripwork-workspace")))
TRIPS = WORKSPACE / "trips"

FORBIDDEN_DIRS = ("trips/", "work/", "docs/specs/", "docs/superpowers/", ".design-board/")
IMAGE_DIRS = ("assets/icons/", "docs/images/readme/")
IMAGE = re.compile(r"\.(png|jpe?g|gif|webp|svg|ico|heic)$", re.I)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
EMAIL_OK = re.compile(r"(^git@github\.com$|@users\.noreply\.github\.com$|@example\.(com|org)$|\.example$|^noreply@anthropic\.com$)")
BINARY = re.compile(r"\.(png|jpe?g|gif|webp|ico|woff2?|ttf|otf|pdf|zip|gz)$", re.I)


def tracked(root=ROOT):
    """Tracked files AND new files git would add (untracked, not ignored): a file about to be
    committed is checked before the commit, not after (the guard once missed its own new
    file for exactly this reason)."""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"],
                         cwd=root, capture_output=True, text=True, check=True).stdout
    return sorted({f for f in out.splitlines() if f and (pathlib.Path(root) / f).is_file()})


def texts(root=ROOT):
    for f in tracked(root):
        if BINARY.search(f):
            continue
        try:
            yield f, (pathlib.Path(root) / f).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue


def test_a_new_file_is_checked_before_it_is_committed(tmp_path):
    """git ls-files alone lists only what is already tracked; a new file carrying a trip
    would pass the pre-PR run and be caught only after the commit."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text("ignored/\n", encoding="utf-8")
    (tmp_path / "new.md").write_text("x", encoding="utf-8")
    (tmp_path / "ignored").mkdir()
    (tmp_path / "ignored" / "local.md").write_text("x", encoding="utf-8")
    assert tracked(tmp_path) == [".gitignore", "new.md"]


# --- rules that run everywhere ---------------------------------------------------------

def test_nothing_from_a_workspace_is_tracked():
    bad = [f for f in tracked() if f.startswith(FORBIDDEN_DIRS)]
    assert not bad, f"tracked files under a private path: {bad}"


def test_images_live_only_in_the_allowed_folders():
    """Screenshots come from the made-up demo trip (docs/images/readme/demo_trip.py)."""
    bad = [f for f in tracked() if IMAGE.search(f) and not f.startswith(IMAGE_DIRS)]
    assert not bad, f"images outside {IMAGE_DIRS}: {bad}"


def test_no_personal_email_address():
    bad = sorted({(f, m) for f, s in texts() for m in EMAIL.findall(s) if not EMAIL_OK.search(m)})
    assert not bad, f"e-mail addresses that are not placeholders: {bad[:10]}"


def test_the_corpus_stays_de_identified():
    corpus = ROOT / "tests" / "corpus"
    trips = sorted(p for p in corpus.iterdir() if p.is_dir())
    assert trips, "tests/corpus is empty"
    for t in trips:
        assert re.fullmatch(r"trip-[a-z]", t.name), t.name
        brief = yaml.safe_load((t / "trip-brief.yaml").read_text(encoding="utf-8"))
        assert brief.get("slug") == t.name, (t.name, brief.get("slug"))
        names = [m.get("name") for m in brief.get("members") or [] if isinstance(m, dict)]
        assert all(re.fullmatch(r"成員\d+", str(n)) for n in names), (t.name, names)
        for y in t.glob("*.yaml"):
            commented = [ln for ln in y.read_text(encoding="utf-8").splitlines() if ln.lstrip().startswith("#")]
            assert not commented, (str(y), commented[:2])     # comments carried the personal notes


# --- the workspace check (runs where a consumer workspace exists) ------------------------

AREA = re.compile(r"[^\d號号路街巷弄丁目番]+[市区區町村縣県鄉鎮郡]")   # an administrative area alone
GENERIC = {"成員", "使用者", "先生", "太太", "count", "composition", "elderly", "children", "總人數"}


def _load(p):
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _artifact(trip, name):
    for d in (trip / "data", trip):
        if (d / name).is_file():
            return _load(d / name)
    return {}


def workspace_terms(trips_dir, today=None):
    """{term: why} -- every identifying string of the workspace's trips.

    Slugs; the hotels a trip stays at (its chosen candidate and the brief's base); member
    names other than placeholders; home endpoints (the brief's origin / home fields and the
    ends of `kind: home` legs); and, for trips not yet over, every date of the trip. Past
    trips' dates are left out: fixtures legitimately carry ordinary dates.
    """
    today = today or datetime.date.today()
    terms = {}

    def add(t, why):
        t = str(t or "").strip()
        if t and t not in GENERIC and not re.fullmatch(r"成員\d+", t) and (len(t) >= 4 or re.search(r"[぀-鿿]{2,}", t)):
            terms.setdefault(t, why)

    for trip in sorted(p for p in pathlib.Path(trips_dir).iterdir() if p.is_dir()):
        add(trip.name, f"slug {trip.name}")
        brief = _artifact(trip, "trip-brief.yaml")
        for m in brief.get("members") or []:
            add(m.get("name") if isinstance(m, dict) else m, f"member {trip.name}")
        base = brief.get("base")
        add(base.get("name") if isinstance(base, dict) else base, f"base {trip.name}")
        for k in ("origin", "home_origin", "home_return", "home"):
            v = brief.get(k) or (brief.get("preferences") or {}).get(k)
            add(v.get("name") if isinstance(v, dict) else v, f"home {trip.name}")
        acc = _artifact(trip, "accommodations.yaml")
        for st in acc.get("stops") or []:
            for c in st.get("candidates") or []:
                if c.get("id") == st.get("chosen"):
                    for k in ("name_local", "name_display", "name_zh", "resolved_name"):
                        add(c.get(k), f"hotel {trip.name}")
        for leg in (_artifact(trip, "legs.yaml").get("legs") or []):
            if isinstance(leg, dict) and leg.get("kind") == "home":
                for end in (leg.get("from"), leg.get("to")):
                    if not AREA.fullmatch(str(end or "")):          # a bare ward / city names no one
                        add(end, f"home {trip.name}")
        dates = brief.get("dates") or {}
        try:
            start = datetime.date.fromisoformat(str(dates.get("start")))
            end = datetime.date.fromisoformat(str(dates.get("end") or dates.get("start")))
        except ValueError:
            continue
        if end > today:                                             # a trip that ends today is over by tomorrow
            d = start
            while d <= end:
                add(d.isoformat(), f"date of the trip ahead {trip.name}")
                d += datetime.timedelta(days=1)
    return terms


def leaks(terms, files):
    """[(file, term, why)] for every term found in a (path, text) pair."""
    return [(f, t, why) for f, s in files for t, why in terms.items() if t in s]


def test_the_check_finds_a_planted_leak(tmp_path):
    """The guard can fail: a slug, a stayed-at hotel, a home endpoint and a future date
    planted in a file are each reported; a past trip's date is not."""
    t = tmp_path / "trips" / "2027-01-somewhere"
    t.mkdir(parents=True)
    (t / "trip-brief.yaml").write_text(yaml.safe_dump(
        {"slug": t.name, "dates": {"start": "2027-01-10", "end": "2027-01-11"},
         "members": [{"name": "成員1"}, {"name": "某甲（駕駛）"}], "base": {"name": "某某溫泉旅館"},
         "preferences": {"origin": "某市某區某路1號"}}, allow_unicode=True), encoding="utf-8")
    (t / "accommodations.yaml").write_text(yaml.safe_dump(
        {"stops": [{"chosen": "h1", "candidates": [{"id": "h1", "name_local": "某某溫泉旅館"},
                                                   {"id": "h2", "name_local": "沒住的旅館"}]}]}, allow_unicode=True), encoding="utf-8")
    (t / "legs.yaml").write_text(yaml.safe_dump(
        {"legs": [{"from": "某市某區某路1號", "to": "某某溫泉旅館", "kind": "home"},
                  {"from": "札幌市中央区", "to": "某某溫泉旅館", "kind": "home"}]}, allow_unicode=True), encoding="utf-8")
    old = tmp_path / "trips" / "2020-01-past"
    old.mkdir()
    (old / "trip-brief.yaml").write_text(yaml.safe_dump({"slug": old.name, "dates": {"start": "2020-01-05", "end": "2020-01-06"}}), encoding="utf-8")
    terms = workspace_terms(tmp_path / "trips", today=datetime.date(2026, 10, 3))
    files = [("a.md", "trip 2027-01-somewhere stays at 某某溫泉旅館 from 某市某區某路1號 on 2027-01-11"),
             ("b.md", "沒住的旅館 2020-01-05 成員1")]
    found = {t for _f, t, _w in leaks(terms, files)}
    assert {"2027-01-somewhere", "某某溫泉旅館", "某市某區某路1號", "2027-01-11"} <= found
    assert "某甲（駕駛）" in terms                                   # a member's own name is a term too
    assert not {"沒住的旅館", "2020-01-05", "成員1"} & found       # unchosen hotels, past dates, placeholders
    assert "札幌市中央区" not in terms                               # a ward is not a home
    today_trip = workspace_terms(tmp_path / "trips", today=datetime.date(2027, 1, 11))
    assert "2027-01-11" not in today_trip                         # the trip ends today: over


@pytest.mark.skipif(not TRIPS.is_dir(), reason="no consumer workspace here (set TRIPWORK_WORKSPACE)")
def test_no_tracked_file_carries_a_workspace_trip():
    terms = workspace_terms(TRIPS)
    assert terms, f"no terms derived from {TRIPS}"
    found = leaks(terms, texts())
    assert not found, "personal trip data in tracked files:\n" + "\n".join(f"  {f}: {t!r} ({w})" for f, t, w in found[:30])
