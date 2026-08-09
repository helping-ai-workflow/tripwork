"""sys.path repair for the `python scripts/<x>.py` CLI entrypoints. Import for
its side effect; there is nothing to call.

    if __name__ == "__main__" and __package__ in (None, ""):
        import _cli_bootstrap      # noqa: F401  (side effect: fixes sys.path)

Two jobs, in this order:

1. DROP the script's own directory. Python auto-prepends it to `sys.path[0]`
   before the first line of the script runs, and that directory contains
   `scripts/calendar.py`, which then SHADOWS the stdlib `calendar` module for
   any bare `import calendar` anywhere downstream. `http.cookiejar` does exactly
   that (`from calendar import timegm`), so any CLI whose import graph reaches
   `requests` — gate.py and export_gate.py reach it through
   rederive -> verify -> geocode — dies with "cannot import name 'timegm' from
   'calendar'" pointing at OUR file. The CLI is dead on the first line; no test
   that imports the module as `scripts.gate` can see it.

2. ADD the repo root, so `from scripts.X import ...` resolves. That is all the
   scripts ever needed; none of them ever needed `scripts/` itself on the path.

Why a bare `import _cli_bootstrap` and not `from scripts._cli_bootstrap import
...`: this must run BEFORE the repo root is on sys.path, and at that moment the
only importable location is the `scripts/` directory this module is about to
remove. The guard is deliberately `__name__ == "__main__"` — under
`python -m scripts.gate` or a plain `import scripts.gate`, `__package__` is set
and none of this applies.

Why each caller puts `scripts/` on sys.path FIRST, when Python normally does
that for it: under `python -P` / `PYTHONSAFEPATH=1` Python does NOT auto-add the
script's directory, so the bare import above raises ModuleNotFoundError and
every CLI dies on its first line. The callers' two-line preamble makes the
import work in both modes; it carries no policy, only the path this module
needs to be reachable at. That is why the removal below filters ALL occurrences
instead of calling list.remove (which drops only the first): in normal mode the
preamble adds a SECOND copy of `scripts/` alongside Python's own, and leaving
either one behind re-arms the `calendar` shadow this module exists to disarm.

Extracted (final v0.33.0 whole-branch review) because the block was duplicated
verbatim in four files while next_stage.py and input_fingerprint.py kept an
older, unpatched shape that added the repo root without dropping `scripts/` —
a latent copy of the same landmine, waiting for either to gain an import that
reaches `requests`. tests/test_cli_bootstrap.py pins that all six use this.
"""
import pathlib
import sys

_here = str(pathlib.Path(__file__).resolve().parent)
sys.path[:] = [p for p in sys.path if p != _here]
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
