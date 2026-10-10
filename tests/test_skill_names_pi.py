"""Skill-name guards for hosts with a flat skill namespace (pi).

pi (earendil-works/pi) names a skill by its SKILL.md frontmatter `name` and keeps
only the first skill it finds under a name: a second plugin's skill with the same
name is skipped with a warning. Claude Code namespaces plugin skills
(`tripwork:<skill>`), so a collision never shows there. v3.0.0 renamed the three
tripwork skills that collided with paperwork / chipwork (orchestrator,
export-artifact, workspace-shape-preflight) to `tripwork-<skill>`.

1. Every SKILL.md frontmatter passes a strict YAML parser and pi's naming rules
   (pi's docs/skills.md: lowercase a-z0-9 words joined by single hyphens, at most
   64 characters, equal to the directory name; description at most 1024 characters).
   Claude Code's frontmatter parser is lenient, so a description with an unquoted
   `: ` loads there and is dropped by pi.
2. No tripwork skill name is taken by a sibling plugin, read from the checked-in
   snapshot `tests/fixtures/sibling-skill-names.json`. It is a literal because the
   siblings (paperwork, chipwork) are private repositories that CI cannot read with
   its GITHUB_TOKEN. Regenerate it from the siblings' `skills/*/SKILL.md` directory
   names when one of them adds or renames a skill.
3. No live file names a renamed skill by its old id (`tripwork:<old>` or a
   `skills/<old>/` path). CHANGELOG.md is history (and its 3.0.0 migration table
   names the old ids on purpose), so it is not scanned.
"""
import json
import pathlib
import re
import subprocess

import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
SIBLINGS = ROOT / "tests" / "fixtures" / "sibling-skill-names.json"

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

# The ids v3.0.0 retired (old name -> new name).
RENAMED = {
    "orchestrator": "tripwork-orchestrator",
    "export-artifact": "tripwork-export-artifact",
    "workspace-shape-preflight": "tripwork-workspace-shape-preflight",
}


def _skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())


def _frontmatter(skill_dir):
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    assert m, f"{skill_dir.name}: SKILL.md has no --- frontmatter --- block"
    doc = yaml.safe_load(m.group(1))
    assert isinstance(doc, dict), f"{skill_dir.name}: frontmatter is not a mapping"
    return doc


@pytest.mark.parametrize("skill_dir", _skill_dirs(), ids=lambda p: p.name)
def test_frontmatter_is_strict_yaml_and_follows_pi_rules(skill_dir):
    doc = _frontmatter(skill_dir)
    name, desc = doc.get("name"), doc.get("description")
    assert isinstance(name, str) and name.strip(), f"{skill_dir.name}: empty name"
    assert isinstance(desc, str) and desc.strip(), f"{skill_dir.name}: empty description"
    assert name == skill_dir.name, f"{skill_dir.name}: frontmatter name {name!r} != directory"
    assert NAME_RE.fullmatch(name), f"{name!r}: not lowercase a-z0-9 words joined by '-'"
    assert len(name) <= 64, f"{name!r}: {len(name)} chars > 64"
    assert len(desc) <= 1024, f"{name}: description {len(desc)} chars > 1024"


def test_no_skill_name_is_taken_by_a_sibling_plugin():
    siblings = json.loads(SIBLINGS.read_text(encoding="utf-8"))
    ours = {p.name for p in _skill_dirs()}
    clashes = {plugin: sorted(ours & set(names)) for plugin, names in siblings.items()}
    clashes = {k: v for k, v in clashes.items() if v}
    assert not clashes, f"skill names also used by a sibling plugin (pi keeps only one): {clashes}"


def test_sibling_snapshot_covers_the_plugins_pi_loads_together():
    siblings = json.loads(SIBLINGS.read_text(encoding="utf-8"))
    assert set(siblings) == {"paperwork", "chipwork", "writing-humanizer", "superpowers"}
    for plugin, names in siblings.items():
        assert names, f"{plugin}: empty snapshot"
        assert all(NAME_RE.fullmatch(n) for n in names), plugin


def test_renamed_skills_exist_under_their_new_names():
    ours = {p.name for p in _skill_dirs()}
    assert set(RENAMED.values()) <= ours
    assert not set(RENAMED) & ours, "an old skill directory is still present"


def _tracked_text_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
    for rel in out.stdout.decode("utf-8").split("\0"):
        if not rel or rel == "CHANGELOG.md":
            continue
        p = ROOT / rel
        if p.is_symlink() or not p.is_file():
            continue
        try:
            yield rel, p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def test_no_live_file_names_an_old_skill_id():
    # Built from parts so this file does not name the old ids itself.
    needles = [f"tripwork:{old}" for old in RENAMED] + [f"skills/{old}/" for old in RENAMED]
    hits = []
    for rel, text in _tracked_text_files():
        for n, line in enumerate(text.splitlines(), 1):
            for needle in needles:
                if needle in line:
                    hits.append(f"{rel}:{n}: {needle}")
    assert not hits, "old skill ids still in live files:\n" + "\n".join(hits)
