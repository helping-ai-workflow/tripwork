"""v2.0.0: `scripts/tripwork.py` is the only way to run the pipeline scripts.

Replaces tests/test_cli_bootstrap.py, whose hand-kept ENTRYPOINTS list had already
drifted (it missed day_maps, publish, migrate_v1, design_board). Every list here is
derived: the covered modules come from `tripwork.COMMANDS`, the entry points from
an AST scan of scripts/, the stdlib names from `sys.stdlib_module_names`.

Runs that start a script from another directory use `python -S` on a COPY of the
repo: the dev venv has an editable install, so `import scripts` works from any cwd
there and would hide exactly the sys.path defects a consumer (no pip install of the
plugin) hits.
"""
import ast
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"

# Literal because these developer tools are not pipeline commands: nothing in the
# plugin lists them, and they keep running directly by design (spec §1 D8).
DEV_TOOLS = ("tripwork.py", "design_board.py", "bump_version.py",
             "render/reader/build_font_subsets.py")


# The `rest` arguments each command needs so its builder names its module(s) without
# touching the filesystem (validate without a name would list data/).
_SAMPLE_REST = {"picker": [[], ["回覆"]], "validate": [["itinerary"]],
                "fingerprint": [["advisory"]], "deploy": [["--project", "p", "--confirm"]]}


def _covered_modules():
    try:
        from scripts import tripwork
    except ImportError:                                   # red phase: make every case fail, not vanish
        return ["scripts.tripwork_missing"]
    mods = set()
    for name, build in tripwork.COMMANDS.items():
        for rest in _SAMPLE_REST.get(name, [[]]):
            for mod, _argv in build("demo", rest):
                mods.add(mod)
    return sorted(mods)


def _module_file(mod):
    return ROOT / (mod.replace(".", "/") + ".py")


def _is_main_guard(node):
    return (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
            and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__"
            and any(isinstance(c, ast.Constant) and c.value == "__main__" for c in node.test.comparators))


def _main_guards(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [n for n in ast.walk(tree) if _is_main_guard(n)]


def _repo_copy(tmp_path):
    dst = tmp_path / "repo"
    for d in ("scripts", "schemas", "assets"):
        shutil.copytree(ROOT / d, dst / d, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


# --- Task 2: the stdlib-shadow root cause -------------------------------------------

def test_no_script_module_shadows_the_stdlib():
    hits = [str(p.relative_to(ROOT)) for p in SCRIPTS.rglob("*.py")
            if p.stem not in ("__init__", "__main__") and p.stem in sys.stdlib_module_names]
    assert not hits, f"these modules shadow the stdlib when their directory is on sys.path: {hits}"


def test_build_font_subsets_starts():
    r = subprocess.run([sys.executable, "-S", str(SCRIPTS / "render/reader/build_font_subsets.py"), "--help"],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


# --- Task 4: retired entry points ------------------------------------------------------

@pytest.mark.parametrize("mod", _covered_modules())
def test_stub_is_the_first_statement(mod):
    path = _module_file(mod)
    tree = ast.parse(path.read_text(encoding="utf-8"))
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]                                   # the module docstring
    first = body[0]
    assert _is_main_guard(first), f"{path.name}: the moved-stub must come before every import"
    raise_ = first.body[0]
    assert isinstance(raise_, ast.Raise), path.name
    msg = ast.literal_eval(raise_.exc.args[0])
    assert msg.startswith("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py "), msg
    assert len(_main_guards(path)) == 1, f"{path.name}: one __main__ guard only (the stub)"


@pytest.mark.parametrize("mod", _covered_modules())
def test_old_path_fails_loudly(mod, tmp_path):
    repo = _repo_copy(tmp_path)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    r = subprocess.run([sys.executable, "-S", str(repo / (mod.replace(".", "/") + ".py")), "trips/x"],
                       cwd=elsewhere, capture_output=True, text=True)
    assert r.returncode != 0
    assert "tripwork.py" in r.stderr, r.stderr[-800:]
    assert "Traceback" not in r.stderr, r.stderr[-800:]


def test_only_known_entrypoints():
    covered = {str(_module_file(m).relative_to(SCRIPTS)) for m in _covered_modules()}
    real = []
    for p in SCRIPTS.rglob("*.py"):
        rel = str(p.relative_to(SCRIPTS))
        if _main_guards(p) and rel not in covered:
            real.append(rel)
    assert sorted(real) == sorted(DEV_TOOLS)


@pytest.mark.parametrize("tool,args", [("design_board.py", ["--help"]), ("bump_version.py", ["--help"]),
                                       ("render/reader/build_font_subsets.py", ["--help"])])
def test_dev_tools_start_from_a_foreign_cwd(tool, args, tmp_path):
    r = subprocess.run([sys.executable, "-S", "-P", str(SCRIPTS / tool), *args],
                       cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


def test_cli_bootstrap_is_gone():
    assert not (SCRIPTS / "_cli_bootstrap.py").exists()


def _covered_names():
    mods = _covered_modules()
    assert "scripts.tripwork_missing" not in mods, "scripts/tripwork.py does not exist yet"
    return sorted({_module_file(m).name for m in mods})


def _old_command_patterns():
    names = _covered_names()
    return [re.compile(rf"python3?\s+(?:\S*/)?scripts/{re.escape(n)}") for n in names]


def _text_sources():
    for p in sorted((ROOT / "skills").rglob("*.md")):
        yield str(p.relative_to(ROOT)), p.read_text(encoding="utf-8")
    yield "README.md", (ROOT / "README.md").read_text(encoding="utf-8")
    for p in sorted(SCRIPTS.rglob("*.py")):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield f"{p.relative_to(ROOT)}:{node.lineno}", node.value


def test_no_old_commands_in_text():
    pats = _old_command_patterns()
    hits = [(where, m.group(0)) for where, text in _text_sources() for pat in pats for m in pat.finditer(text)]
    assert not hits, hits[:20]


def test_tests_do_not_subprocess_old_paths():
    names = _covered_names()
    pat = re.compile(r"""["'](?:scripts/)?(%s)["']""" % "|".join(re.escape(n) for n in names))
    hits = []
    # Exempt: this file's job is to run the old paths and see them refuse.
    for p in sorted((ROOT / "tests").rglob("*.py")):
        if p.name == "test_entrypoints.py":
            continue
        text = p.read_text(encoding="utf-8")
        if "subprocess" not in text:
            continue
        for m in pat.finditer(text):
            line = text[:m.start()].count("\n") + 1
            hits.append(f"{p.relative_to(ROOT)}:{line} {m.group(1)}")
    assert not hits, hits
