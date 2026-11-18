"""Share a trip with family (v1.2 spec sections 1-3): build the publish page, lock it
with staticrypt, and deploy it to Cloudflare Pages -- the deploy only after the user's
explicit yes, because it puts the page on the internet.

    python <plugin>/scripts/tripwork.py publish <slug> [--share-base https://<project>.pages.dev/] [--new-code]
    python <plugin>/scripts/tripwork.py publish <slug> --freeze CODE | --retire CODE
    python <plugin>/scripts/tripwork.py deploy <slug> --project <name> --confirm

The password comes from TRIPWORK_PUBLISH_PASSWORD or a prompt and is never written to
the workspace. Only the locked page lands under trips/<slug>/publish/<code>/ (the plain
page lives in a temporary directory); <code> is a random 8-character path, so the URL
names no place or date.

One trip is one Pages project: a Pages deploy replaces the whole site, so `deploy`
uploads this trip's locked pages only (each in its <code>/), refuses one that is not
locked -- a build with non-distributable photos may only go out encrypted -- and
uploads nothing else. A trip may keep older pages frozen next to the current one (#24):
`publish/codes.yaml` lists every page, `publish <slug> --new-code` freezes the current
page and builds a new one, `--freeze CODE` registers a page already on disk, `--retire
CODE` takes a frozen page off the next deploy. A frozen page is uploaded byte for byte
as git holds it, its sha256 checked before the deploy and again online after it. The share link (`#staticrypt_pwd=…`) opens the page without
typing the password: it is printed for the user, never written next to the pages.

Exit 0 ok / 1 failure / 2 bad input. Node 18+ is required (npx)."""
if __name__ == "__main__":
    raise SystemExit("moved in tripwork 2.0: python <plugin>/scripts/tripwork.py publish <slug>  (or: deploy <slug> --project NAME --confirm)")

import datetime
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


# --- #24: one current page and any number of frozen ones -------------------------

def _codes_path(trip_dir):
    return pathlib.Path(trip_dir) / "publish" / "codes.yaml"


def _sha(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()


def _page(trip_dir, code):
    return pathlib.Path(trip_dir) / "publish" / code / "index.html"


def page_codes(trip_dir):
    """publish/codes.yaml's entries -- {code, created, frozen, sha256?, retired?} -- or,
    for a trip without one, its code.txt page as the only (current) entry."""
    f = _codes_path(trip_dir)
    if f.is_file():
        return list((yaml.safe_load(f.read_text(encoding="utf-8")) or {}).get("codes") or [])
    code_file = pathlib.Path(trip_dir) / "publish" / "code.txt"
    code = code_file.read_text(encoding="utf-8").strip() if code_file.is_file() else None
    return [{"code": code, "frozen": False}] if code else []


def _save_codes(trip_dir, codes):
    f = _codes_path(trip_dir)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(yaml.safe_dump({"codes": codes}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def freeze(trip_dir, code=None):
    """Freeze a locked page: it will be uploaded exactly as it is now. `code` defaults to
    the current page; a page already on disk but not yet listed is added (adopting a trip
    whose older page was deployed by hand). Returns the entry."""
    trip_dir = pathlib.Path(trip_dir)
    codes = page_codes(trip_dir)
    code = code or publish_code(trip_dir)
    page = _page(trip_dir, code)
    if not page.is_file() or _LOCKED not in page.read_text(encoding="utf-8", errors="ignore"):
        raise PublishError(f"no locked page at {page}: only a locked page can be frozen")
    entry = next((e for e in codes if e.get("code") == code), None)
    if entry is None:
        entry = {"code": code, "created": datetime.date.today().isoformat()}
        codes.append(entry)
    entry.update(frozen=True, sha256=_sha(page))
    _save_codes(trip_dir, codes)
    return entry


def new_code(trip_dir):
    """Freeze the current page and make a new current code (written to code.txt); the
    next build fills it. The frozen page keeps its own password: it is already locked."""
    trip_dir = pathlib.Path(trip_dir)
    freeze(trip_dir)
    codes = page_codes(trip_dir)
    taken = {e.get("code") for e in codes}
    code = next(c for c in iter(lambda: "".join(secrets.choice(_CODE_CHARS) for _ in range(8)), None)
                if c not in taken)
    (trip_dir / "publish" / "code.txt").write_text(code + "\n", encoding="utf-8")
    codes.append({"code": code, "created": datetime.date.today().isoformat(), "frozen": False})
    _save_codes(trip_dir, codes)
    return code


def retire(trip_dir, code):
    """Take a frozen page off the next deploy (its URL then stops working). Only ever on
    the user's word: `deploy` lists it as removed before its --confirm."""
    trip_dir = pathlib.Path(trip_dir)
    codes = page_codes(trip_dir)
    entry = next((e for e in codes if e.get("code") == code), None)
    if entry is None or not entry.get("frozen"):
        raise PublishError(f"{code} is not a frozen page of {trip_dir.name}: only a frozen page can be retired")
    entry["retired"] = True
    _save_codes(trip_dir, codes)
    return entry


def deploy_plan(trip_dir):
    """What a deploy uploads and removes: {"current": code, "frozen": [codes], "removed":
    [codes]}. Refuses a frozen page whose file no longer matches its recorded sha256, and
    a locked page on disk that codes.yaml does not list (the deploy would delete it)."""
    trip_dir = pathlib.Path(trip_dir)
    codes = page_codes(trip_dir)
    current = (trip_dir / "publish" / "code.txt")
    current = current.read_text(encoding="utf-8").strip() if current.is_file() else None
    if not current or not _page(trip_dir, current).is_file():
        raise PublishError(f"no locked page for {trip_dir.name}: run `python <plugin>/scripts/tripwork.py publish {trip_dir.name}` first")
    frozen = [e for e in codes if e.get("frozen") and not e.get("retired") and e.get("code") != current]
    for e in frozen:
        page = _page(trip_dir, e["code"])
        if not page.is_file() or _sha(page) != e.get("sha256"):
            raise PublishError(f"frozen page {e['code']} has changed on disk (sha256 differs from codes.yaml): "
                               f"restore it from git; a frozen page is never rebuilt")
    listed = {e.get("code") for e in codes} | {current}
    strays = sorted(p.parent.name for p in (trip_dir / "publish").glob("*/index.html")
                    if p.parent.name not in listed)
    if strays:
        raise PublishError(f"publish/ holds page(s) codes.yaml does not list: {', '.join(strays)} -- "
                           f"a deploy would delete them online. Keep each with "
                           f"`tripwork.py publish {trip_dir.name} --freeze CODE`, or remove its folder")
    return {"current": current, "frozen": [e["code"] for e in frozen],
            "removed": [e["code"] for e in codes if e.get("retired")]}


def _fetch(url):
    import urllib.request
    with urllib.request.urlopen(url, timeout=30) as r:     # noqa: S310 (https only, below)
        return r.read()


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
                           media_count=media_count, reservations=kwargs["reservations"])
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


def _site(page, into):
    """Copy this trip's locked page into `into`/<code>/index.html -- one trip is one Pages
    project, so nothing else goes up. Refuses a page that is not locked."""
    if _LOCKED not in page.read_text(encoding="utf-8", errors="ignore"):
        raise PublishError(f"{page} is not encrypted: rebuild it with "
                           f"`python <plugin>/scripts/tripwork.py publish <slug>` before deploying")
    (into / page.parent.name).mkdir()
    shutil.copyfile(page, into / page.parent.name / "index.html")
    return [page]


def deploy(trip_dir, project, *, confirm=False, run=None, fetch=None):
    """Upload this trip's locked pages -- the current one and every frozen one (#24) -- to
    its own Cloudflare Pages project (one trip, one project: a Pages deploy replaces the
    whole site, so the project holds this trip only). Needs confirm=True (the user's
    explicit yes) and a wrangler login. After the upload each frozen page is fetched from
    the deployment and must match its recorded sha256."""
    trip_dir = pathlib.Path(trip_dir)
    if not confirm:
        try:
            plan = deploy_plan(trip_dir)
            what = (f" -- it would upload {', '.join([plan['current'], *plan['frozen']])}"
                    + (f" and REMOVE {', '.join(plan['removed'])}" if plan["removed"] else ""))
        except PublishError:
            what = ""
        raise PublishError("deploy needs --confirm: it publishes to the internet" + what)
    run = run or _run
    fetch = fetch or _fetch
    plan = deploy_plan(trip_dir)
    code = plan["current"]
    with tempfile.TemporaryDirectory() as tmp:
        site = pathlib.Path(tmp) / "site"
        site.mkdir()
        for c in [code, *plan["frozen"]]:
            _site(_page(trip_dir, c), site)
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
    deployment = m.group(0) if m else base
    sums = {e["code"]: e["sha256"] for e in page_codes(trip_dir) if e.get("code") in plan["frozen"]}
    for c in plan["frozen"]:
        try:
            live = hashlib.sha256(fetch(f"{deployment}/{c}/")).hexdigest()
        except OSError as exc:
            raise PublishError(f"deployed, but the frozen page {c} could not be fetched to check it "
                               f"({exc.__class__.__name__}): open {base}/{c}/ and compare it by hand") from None
        if live != sums[c]:
            raise PublishError(f"deployed, but the frozen page {c} online differs from codes.yaml's sha256: "
                               f"stop and check {base}/{c}/ before sharing anything")
    return {"url": f"{base}/{code}/", "frozen": [f"{base}/{c}/" for c in plan["frozen"]],
            "removed": [f"{base}/{c}/" for c in plan["removed"]]}


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
    b.add_argument("--new-code", action="store_true",
                   help="freeze the current page and build the new one at a new code (#24)")
    b.add_argument("--freeze", metavar="CODE", default=None,
                   help="register a locked page already on disk as frozen; builds nothing")
    b.add_argument("--retire", metavar="CODE", default=None,
                   help="take a frozen page off the next deploy; builds nothing")
    d = sub.add_parser("deploy")
    d.add_argument("trip_dir")
    d.add_argument("--project", required=True)
    d.add_argument("--confirm", action="store_true")
    args = ap.parse_args(argv)
    trip_dir = pathlib.Path(args.trip_dir)
    if not trip_dir.is_dir():
        print(f"no trip folder: {trip_dir}", file=sys.stderr)
        return 2
    if args.cmd == "build" and (args.freeze or args.retire):
        try:
            if args.freeze:
                e = freeze(trip_dir, args.freeze)
                print(f"frozen: {e['code']} (sha256 {e['sha256'][:12]}…)")
            else:
                retire(trip_dir, args.retire)
                print(f"retired: {args.retire} -- the next deploy removes it online")
        except PublishError as exc:
            print(exc, file=sys.stderr)
            return 1
        return 0
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
            if args.new_code:
                print(f"frozen the current page; new code: {new_code(trip_dir)}")
            res = build(trip_dir, password, run=_run, share_base=args.share_base)
            print(f"locked page: {res['page']}")
            if res["share"]:
                print(f"share link (opens without the password -- send it to family only): {res['share']}")
        else:
            res = deploy(trip_dir, args.project, confirm=args.confirm, run=_run)
            print(f"published: {res['url']}")
            for u in res["frozen"]:
                print(f"kept (frozen, sha256 checked online): {u}")
            for u in res["removed"]:
                print(f"removed: {u}")
    except TripInputError as exc:
        print(exc, file=sys.stderr)
        return 2
    except PublishError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0
