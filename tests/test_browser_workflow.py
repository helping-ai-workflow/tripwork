"""The two CI jobs, `test` (ci.yml) and `interaction` (browser.yml), are required checks
on main. A required check that never reports blocks the merge for good, so neither
workflow may carry a path filter: both run on every pull request and report.

browser.yml skips its work for a docs-only change instead, decided by
.github/docs-only.sh. Its allow-list must not take in any module the page under test
loads -- computed by importing the shipped reader, generator and gate and asking the
shipped script about each file, never a hand-kept list -- or a change to, say,
scripts/gate.py::poi_pool would reshape the page with the interaction checks skipped."""
import os
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"
DOCS_ONLY = ROOT / ".github" / "docs-only.sh"


def _workflow(name):
    doc = yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))                     # YAML 1.1 reads a bare `on` as True
    return doc, on


def _docs_only(*files, event="pull_request"):
    env = {**os.environ, "EVENT_NAME": event, "CHANGED_FILES": "\n".join(files)}
    env.pop("GITHUB_OUTPUT", None)
    out = subprocess.run(["bash", str(DOCS_ONLY)], cwd=ROOT, env=env,
                         capture_output=True, text=True, check=True).stdout
    verdict = [line for line in out.splitlines() if line.startswith("docs_only=")]
    assert verdict, out
    return verdict[-1] == "docs_only=true"


def test_neither_required_check_is_path_filtered():
    for name in ("ci.yml", "browser.yml"):
        _, on = _workflow(name)
        assert set(on) == {"pull_request", "workflow_dispatch"}, (name, on)
        assert not (on["pull_request"] or {}).get("paths"), name
        assert not (on["pull_request"] or {}).get("paths-ignore"), name


def test_the_required_job_names_are_the_ones_main_requires():
    assert set(_workflow("ci.yml")[0]["jobs"]) == {"test"}
    assert set(_workflow("browser.yml")[0]["jobs"]) == {"interaction"}


def test_both_jobs_run_on_a_pinned_image():
    for name, job in (("ci.yml", "test"), ("browser.yml", "interaction")):
        assert _workflow(name)[0]["jobs"][job]["runs-on"] == "ubuntu-24.04", name


def test_the_browser_cache_key_carries_the_runner_image():
    steps = _workflow("browser.yml")[0]["jobs"]["interaction"]["steps"]
    cache = [s for s in steps if str(s.get("uses", "")).startswith("actions/cache")]
    assert len(cache) == 1
    assert "image" in cache[0]["with"]["key"], cache[0]["with"]["key"]
    assert any("ImageOS" in str(s.get("run", "")) for s in steps)


def test_every_browser_step_after_the_scope_check_is_skipped_on_a_docs_only_change():
    steps = _workflow("browser.yml")[0]["jobs"]["interaction"]["steps"]
    names = [s.get("id") for s in steps]
    assert "scope" in names
    for s in steps[names.index("scope") + 1:]:
        assert "steps.scope.outputs.docs_only != 'true'" in str(s.get("if", "")), s


def test_docs_only_verdicts():
    assert _docs_only("README.md")
    assert _docs_only("README.md", "docs/images/readme/phone-day.jpg", "CHANGELOG.md")
    assert not _docs_only("README.md", "tests_browser/conftest.py")
    assert not _docs_only("skills/trip-brief/SKILL.md")    # a .md file is not docs by its suffix
    assert not _docs_only()                                # an empty diff proves nothing
    assert not _docs_only("README.md", event="workflow_dispatch")


def test_no_module_the_page_loads_counts_as_docs():
    # build the very pages tests_browser measures (lazy imports included) and gate one
    code = ("import sys, tempfile; sys.path[:0] = ['tests_browser', '.']; import conftest, scripts.export_gate; "
            "conftest.build_pages(tempfile.mkdtemp()); "
            "print('\\n'.join(m.__file__ for n, m in sys.modules.items() "
            "if n.split('.')[0] in ('scripts', 'tests', 'conftest') and getattr(m, '__file__', None)))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    files = sorted({pathlib.Path(f).resolve().relative_to(ROOT).as_posix() for f in out.stdout.split()})
    assert len(files) > 10, files                          # an import that loads nothing proves nothing
    assert [f for f in files if _docs_only(f)] == []


def test_no_browser_test_fixture_or_asset_counts_as_docs():
    for f in ("tests_browser/conftest.py", "tests/e2e_v1_fixture.py", "tests/reader_fixture.py",
              "tests/mech_fixtures.py", ".github/workflows/browser.yml", ".github/docs-only.sh",
              "assets/fonts/OFL.txt", "pyproject.toml"):
        assert not _docs_only(f), f
