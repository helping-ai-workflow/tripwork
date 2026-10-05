"""Share a trip with family (v1.2 spec sections 1-3): build the publish page, lock it
with staticrypt, and deploy it to Cloudflare Pages -- the deploy only after the user's
explicit yes, because it puts the page on the internet.

    python <plugin>/scripts/tripwork.py publish <slug> [--share-base https://<project>.pages.dev/]
    python <plugin>/scripts/tripwork.py deploy <slug> --project <name> --confirm

The password comes from TRIPWORK_PUBLISH_PASSWORD or a prompt and is never written to
the workspace. Only the locked page lands under trips/<slug>/publish/<code>/ (the plain
page lives in a temporary directory); <code> is a random 8-character path, so the URL
names no place or date.

A Pages deploy replaces the whole site, so `deploy` uploads every trip's locked page
under the same trips/ folder (each in its own <code>/), refuses any page that is not
locked -- a build with non-distributable photos may only go out encrypted -- and
uploads nothing else. The share link (`#staticrypt_pwd=…`) opens the page without
typing the password: it is printed for the user, never written next to the pages.

Exit 0 ok / 1 failure / 2 bad input. Node 18+ is required (npx)."""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py publish <slug>  (or: deploy <slug> --project NAME --confirm)")

import hashlib
import os
import pathlib
import re
import secrets
import shutil
import subprocess
import sys
import tempfile

import yaml

from scripts.export_gate import run_html_gate
from scripts.render.html_page import render_html_page
from scripts.trip_inputs import TripInputError, trip_inputs  # noqa: F401  (re-exported)
from scripts.render.publish.lock import lock_template, staticrypt_args, staticrypt_env, staticrypt_share_args

WRANGLER = "wrangler@3"
_CODE_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"
# every page staticrypt locks carries its config object; a plain reader never does
_LOCKED = "staticryptConfig"
_run = subprocess.run


class PublishError(RuntimeError):
    """A step failed; the message says what to do."""


def publish_code(trip_dir):
    """The trip's random URL path, made once and kept in trips/<slug>/publish/code.txt."""
    f = pathlib.Path(trip_dir) / "publish" / "code.txt"
    if f.is_file():
        code = f.read_text(encoding="utf-8").strip()
        if re.fullmatch(r"[a-z0-9]{8}", code):
            return code
    code = "".join(secrets.choice(_CODE_CHARS) for _ in range(8))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(code + "\n", encoding="utf-8")
    return code


def _salt(code):
    # one salt per trip, kept across rebuilds: the share link's hash depends on it, and a
    # new salt would break every link already sent. Public anyway (each locked page has it).
    return hashlib.sha256(f"tripwork-publish:{code}".encode()).hexdigest()[:32]


def _npx(run, args, **kw):
    try:
        return run(["npx", "--yes", *args], check=True, capture_output=True, text=True, **kw)
    except FileNotFoundError:
        raise PublishError("Node.js 18+ is required (npx was not found): install Node, then retry") from None
    except subprocess.CalledProcessError as exc:
        lines = [x for x in ((exc.stderr or "") + "\n" + (exc.stdout or "")).splitlines() if x.strip()]
        raise PublishError(f"{args[0]} failed: {lines[-1] if lines else exc}") from None


def build(trip_dir, password, *, run=None, share_base=None):
    """Render the publish page, lock it, keep only the locked page. Returns
    {"page": trips/<slug>/publish/<code>/index.html, "share": link or None}."""
    run = run or _run
    trip_dir = pathlib.Path(trip_dir)
    if not password:
        raise PublishError("an empty password locks nothing")
    itin, poi_map, kwargs, media_count = trip_inputs(trip_dir)
    html = render_html_page(itin, poi_map, build="publish", **kwargs)
    report = run_html_gate(html, list(poi_map.values()), min_days=len(itin.get("days") or []) or None,
                           media_count=media_count)
    if report.get("status") != "pass":
        raise PublishError("the publish page fails the html gate: " + "; ".join(report.get("failures") or []))
    code = publish_code(trip_dir)
    dest = trip_dir / "publish" / code / "index.html"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / "index.html").write_text(html, encoding="utf-8")
        (tmp / "template.html").write_text(lock_template(), encoding="utf-8")
        out = tmp / "locked"
        _npx(run, staticrypt_args(tmp / "template.html", out, tmp / "index.html", salt=_salt(code)),
             cwd=tmp, env=staticrypt_env(password))
        locked = out / "index.html"
        if not locked.is_file() or _LOCKED not in locked.read_text(encoding="utf-8"):
            raise PublishError("staticrypt wrote no locked page")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(locked, dest)
        share = None
        if share_base:
            url = share_base.rstrip("/") + f"/{code}/"
            got = _npx(run, staticrypt_share_args(_salt(code), url), cwd=tmp,
                       env=staticrypt_env(password)).stdout or ""
            share = next((x.strip() for x in got.splitlines() if "#staticrypt_pwd=" in x), None)
    return {"page": dest, "share": share}


def _site(trips_root, into):
    """Copy every trip's locked page into `into`/<code>/index.html. Refuses a page that is
    not locked; copies nothing else (code.txt and the trips stay home)."""
    pages = sorted(trips_root.glob("*/publish/*/index.html"))
    for page in pages:
        if _LOCKED not in page.read_text(encoding="utf-8", errors="ignore"):
            raise PublishError(f"{page} is not encrypted: rebuild it with `python <plugin>/scripts/tripwork.py publish <slug>` before deploying")
        (into / page.parent.name).mkdir()
        shutil.copyfile(page, into / page.parent.name / "index.html")
    return pages


def deploy(trip_dir, project, *, confirm=False, run=None):
    """Upload every locked trip page to the Cloudflare Pages project. Needs confirm=True
    (the user's explicit yes) and a wrangler login."""
    if not confirm:
        raise PublishError("deploy needs --confirm: it publishes to the internet")
    run = run or _run
    trip_dir = pathlib.Path(trip_dir)
    code_file = trip_dir / "publish" / "code.txt"
    code = code_file.read_text(encoding="utf-8").strip() if code_file.is_file() else None
    if not code or not (trip_dir / "publish" / code / "index.html").is_file():
        raise PublishError(f"no locked page for {trip_dir.name}: run `python <plugin>/scripts/tripwork.py publish {trip_dir.name}` first")
    with tempfile.TemporaryDirectory() as tmp:
        site = pathlib.Path(tmp) / "site"
        site.mkdir()
        _site(trip_dir.parent, site)
        try:
            _npx(run, [WRANGLER, "whoami"])
        except PublishError:
            raise PublishError("not logged in to Cloudflare: run `! npx wrangler login` "
                               "(or set CLOUDFLARE_API_TOKEN), then retry") from None
        listed = _npx(run, [WRANGLER, "pages", "project", "list"]).stdout or ""
        if not re.search(rf"(?<![\w-]){re.escape(project)}(?![\w-])", listed):
            _npx(run, [WRANGLER, "pages", "project", "create", project, "--production-branch", "main"])
        done = _npx(run, [WRANGLER, "pages", "deploy", str(site), "--project-name", project,
                          "--branch", "main", "--commit-dirty=true"]).stdout or ""
    # the deployment URL is https://<hash>.<subdomain>.pages.dev; the subdomain can differ
    # from the project name when that name was taken
    m = re.search(r"https://[a-z0-9]+\.([a-z0-9-]+)\.pages\.dev", done)
    base = f"https://{m.group(1) if m else project}.pages.dev"
    return {"url": f"{base}/{code}/"}


NO_PASSWORD = ("no password: ask the user for one in the conversation and run again as "
               "TRIPWORK_PUBLISH_PASSWORD='<password>' python <plugin>/scripts/tripwork.py publish <slug> "
               "(or the user runs that command in their own terminal, which asks without echo)")


def _password():
    """The page password for this one run: TRIPWORK_PUBLISH_PASSWORD, else a hidden prompt
    when a person is at a terminal, else None -- an agent's shell has no terminal, and
    getpass there dies with EOFError."""
    pw = os.environ.get("TRIPWORK_PUBLISH_PASSWORD")
    if pw:
        return pw
    if not sys.stdin.isatty():
        return None
    import getpass
    return getpass.getpass("password for the page: ")


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("trip_dir")
    b.add_argument("--share-base", default=None)
    d = sub.add_parser("deploy")
    d.add_argument("trip_dir")
    d.add_argument("--project", required=True)
    d.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    trip_dir = pathlib.Path(args.trip_dir)
    if not trip_dir.is_dir():
        print(f"no trip folder: {trip_dir}", file=sys.stderr)
        return 2
    if args.cmd == "build":
        from scripts.paths import is_legacy_layout
        if is_legacy_layout(trip_dir):
            print(f"pre-v1.0 trip layout — run `python <plugin>/scripts/tripwork.py migrate {trip_dir.name}` "
                  f"(dry run), then with --apply", file=sys.stderr)
            return 2
        try:
            trip_inputs(trip_dir)                       # what the page needs, before any password
        except TripInputError as exc:
            print(exc, file=sys.stderr)
            return 2
    password = _password() if args.cmd == "build" else None
    if args.cmd == "build" and not password:
        print(NO_PASSWORD, file=sys.stderr)
        return 2
    try:
        if args.cmd == "build":
            res = build(trip_dir, password, run=_run, share_base=args.share_base)
            print(f"locked page: {res['page']}")
            if res["share"]:
                print(f"share link (opens without the password -- send it to family only): {res['share']}")
        else:
            res = deploy(trip_dir, args.project, confirm=args.confirm, run=_run)
            print(f"published: {res['url']}")
    except TripInputError as exc:
        print(exc, file=sys.stderr)
        return 2
    except PublishError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
