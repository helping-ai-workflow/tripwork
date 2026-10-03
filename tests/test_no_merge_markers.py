"""A merge conflict left in a tracked file shipped once (v1.1: CHANGELOG, committed by
the topic-2 merge). No tracked text file may carry a conflict marker line."""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKER = re.compile(r"^(<<<<<<< |>>>>>>> )", re.M)


def test_no_tracked_file_carries_a_conflict_marker():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split()
    hit = []
    for f in files:
        p = ROOT / f
        if p.suffix not in {".md", ".py", ".yaml", ".yml", ".json", ".toml", ".txt", ".sh"} or not p.is_file():
            continue
        if MARKER.search(p.read_text(encoding="utf-8", errors="replace")):
            hit.append(f)
    assert hit == [], hit
