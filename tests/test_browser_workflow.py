"""The browser workflow (spec §7) runs only when its path filter matches. The filter
must cover every module the page under test actually loads -- computed by importing
the shipped reader, generator and gate, never a hand-kept list -- or a change to,
say, scripts/gate.py::poi_pool would reshape the page with the interaction checks
never running."""
import pathlib
import subprocess
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "browser.yml"


def _patterns(event):
    doc = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    on = doc.get("on", doc.get(True))                     # YAML 1.1 reads a bare `on` as True
    return on[event]["paths"]


def _covered(path, patterns):
    return any(path.startswith(p[:-2]) if p.endswith("/**") else path == p for p in patterns)


def test_both_events_filter_on_the_same_paths():
    assert _patterns("push") == _patterns("pull_request")


def test_the_filter_covers_every_module_the_page_loads():
    # build the very pages tests_browser measures (lazy imports included) and gate one
    code = ("import sys, tempfile; sys.path[:0] = ['tests_browser', '.']; import conftest, scripts.export_gate; "
            "conftest.build_pages(tempfile.mkdtemp()); "
            "print('\\n'.join(m.__file__ for n, m in sys.modules.items() "
            "if n.split('.')[0] in ('scripts', 'tests', 'conftest') and getattr(m, '__file__', None)))")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
    files = sorted({pathlib.Path(f).resolve().relative_to(ROOT).as_posix() for f in out.stdout.split()})
    assert len(files) > 10, files                          # an import that loads nothing proves nothing
    patterns = _patterns("pull_request")
    assert [f for f in files if not _covered(f, patterns)] == []


def test_the_filter_covers_the_browser_tests_and_their_fixtures():
    patterns = _patterns("pull_request")
    for f in ("tests_browser/conftest.py", "tests/e2e_v1_fixture.py", "tests/reader_fixture.py",
              "tests/mech_fixtures.py", ".github/workflows/browser.yml", "assets/fonts/OFL.txt"):
        assert _covered(f, patterns), f
