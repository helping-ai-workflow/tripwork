#!/usr/bin/env python3
"""bump_version.py — sync the version across every declared plugin manifest.

Driven by .version-bump.json (files[] with type/key, current, next,
audit.exclude). Handles json (incl. nested dotted keys), toml (pyproject
version line), and the CHANGELOG top heading.

Usage:
  bump_version.py --check      Report each declared version; non-zero on drift.
  bump_version.py --audit      Grep tracked repo for the current version in any
                               undeclared, non-excluded file (a missed manifest).
  bump_version.py X.Y.Z        Write every json/toml key = X.Y.Z, advance
                               current/next, then audit.
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path

_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_CHANGELOG_TOP = re.compile(r"^##\s*(\d+\.\d+\.\d+)")
_TOML_VERSION = re.compile(r'^(version\s*=\s*")(\d+\.\d+\.\d+)(")', re.MULTILINE)


def load_config(root: Path) -> dict:
    return json.loads((root / ".version-bump.json").read_text(encoding="utf-8"))


def _resolve(data, dotted: str):
    cur = data
    for seg in dotted.split("."):
        cur = cur[int(seg)] if seg.isdigit() else cur[seg]
    return cur


def _assign(data, dotted: str, value: str) -> None:
    segs = dotted.split(".")
    cur = data
    for seg in segs[:-1]:
        cur = cur[int(seg)] if seg.isdigit() else cur[seg]
    last = segs[-1]
    if last.isdigit():
        cur[int(last)] = value
    else:
        cur[last] = value


def read_key(path: Path, dotted: str) -> str:
    return _resolve(json.loads(path.read_text(encoding="utf-8")), dotted)


def write_key(path: Path, dotted: str, value: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    _assign(data, dotted, value)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_toml_version(path: Path) -> str:
    m = _TOML_VERSION.search(path.read_text(encoding="utf-8"))
    if not m:
        raise AssertionError(f"{path} has no `version = \"X.Y.Z\"` line")
    return m.group(2)


def write_toml_version(path: Path, value: str) -> None:
    text = path.read_text(encoding="utf-8")
    new = _TOML_VERSION.sub(lambda m: m.group(1) + value + m.group(3), text, count=1)
    path.write_text(new, encoding="utf-8")


def _changelog_top(root: Path) -> str | None:
    for line in (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        m = _CHANGELOG_TOP.match(line)
        if m:
            return m.group(1)
    return None


def _version_entries(cfg: dict):
    return [e for e in cfg["files"] if e.get("type") in ("json", "toml")]


def _entry_version(root: Path, entry: dict) -> str:
    if entry["type"] == "toml":
        return read_toml_version(root / entry["path"])
    return read_key(root / entry["path"], entry["key"])


def check(root: Path) -> int:
    cfg = load_config(root)
    current = cfg["current"]
    drift = 0
    print(f"Version check (current = {current}):")
    for entry in _version_entries(cfg):
        ver = _entry_version(root, entry)
        flag = "" if ver == current else "  <-- DRIFT"
        print(f"  {entry['path']:<40} {ver}{flag}")
        drift |= (ver != current)
    top = _changelog_top(root)
    print(f"  {'CHANGELOG.md (top)':<40} {top}")
    if top != current:
        print("  CHANGELOG top does not match current")
        drift = 1
    print("All in sync." if not drift else "DRIFT DETECTED.")
    return 1 if drift else 0


def audit(root: Path) -> int:
    cfg = load_config(root)
    current = cfg["current"]
    declared = {e["path"] for e in cfg["files"]}
    excludes = list(cfg.get("audit", {}).get("exclude", []))
    tracked = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True,
                             text=True, check=True).stdout.splitlines()
    flagged = []
    for rel in tracked:
        if rel in declared:
            continue
        if any(rel == ex.rstrip("/") or rel.startswith(ex if ex.endswith("/") else ex + "/")
               for ex in excludes):
            continue
        try:
            text = (root / rel).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if current in text:
            flagged.append(rel)
    if flagged:
        print(f"UNDECLARED files containing '{current}':")
        for rel in sorted(flagged):
            print(f"  {rel}")
        print("Add them to .version-bump.json files[] or audit.exclude.")
        return 1
    print(f"No undeclared file contains '{current}'. All clear.")
    return 0


def bump(root: Path, version: str) -> int:
    if not _SEMVER.match(version):
        print(f"error: {version!r} is not X.Y.Z", file=sys.stderr)
        return 2
    cfg = load_config(root)
    for entry in _version_entries(cfg):
        path = root / entry["path"]
        old = _entry_version(root, entry)
        if entry["type"] == "toml":
            write_toml_version(path, version)
        else:
            write_key(path, entry["key"], version)
        print(f"  {entry['path']:<40} {old} -> {version}")
    cfg["current"] = version
    cfg["next"] = next_minor(version)
    (root / ".version-bump.json").write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  .version-bump.json current -> {version}, next -> {cfg['next']}")
    print(f"\nNote: CHANGELOG.md heading is hand-authored — add the `## {version}` entry yourself.\n")
    return audit(root)


def next_minor(version: str) -> str:
    major, minor, _ = (int(x) for x in version.split("."))
    return f"{major}.{minor + 1}.0"


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parents[1]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    if argv[0] == "--check":
        return check(root)
    if argv[0] == "--audit":
        return audit(root)
    return bump(root, argv[0])


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
