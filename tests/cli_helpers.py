"""v2.0.0: how tests run a script now that `python scripts/<x>.py` is retired.

- run_main(module, argv): the script's own main() in this process, returned in the
  shape of subprocess.CompletedProcess (returncode / stdout / stderr), so a test
  that checks a CLI's output or exit code keeps doing exactly that.
- run_tripwork(workspace, *argv): the real single entry point in a child process,
  from the workspace root -- for tests whose subject is the command line itself.
"""
import contextlib
import importlib
import io
import pathlib
import subprocess
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parents[1]
TRIPWORK = ROOT / "scripts" / "tripwork.py"


def run_main(module, argv):
    mod = importlib.import_module(module)
    out, err = io.StringIO(), io.StringIO()
    argv = [str(a) for a in argv]
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = mod.main(argv)
        except SystemExit as exc:
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        except Exception:                                 # a crash: what a child process would show
            traceback.print_exc()
            code = 1
    return subprocess.CompletedProcess([module, *argv], code or 0, out.getvalue(), err.getvalue())


def run_tripwork(workspace, *argv, **kw):
    return subprocess.run([sys.executable, str(TRIPWORK), *map(str, argv)], cwd=workspace,
                          capture_output=True, text=True, **kw)
