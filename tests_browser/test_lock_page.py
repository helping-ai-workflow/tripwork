"""v1.2 spec section 2: the lock page (K3) in front of the publish build, encrypted with
the real staticrypt (pinned, via npx) and the shipped template -- WebKit (the iPhone) and
Chromium. Node is required: without npx the module fails, it never skips."""
import shutil
import subprocess

import pytest

from scripts.render.publish.lock import LOCK_COPY, lock_template, staticrypt_args, staticrypt_env

PHONE = {"width": 390, "height": 844}
PASSWORD = "旅行密碼"          # CJK on purpose: the field is type="text" so an iPhone keeps 注音


@pytest.fixture(scope="session")
def locked_url(tmp_path_factory, pages):
    if not shutil.which("npx"):
        pytest.fail("node/npx required: the lock page is made by staticrypt (npx staticrypt@3.5.4)")
    root = tmp_path_factory.mktemp("lock")
    tpl = root / "template.html"
    tpl.write_text(lock_template(), encoding="utf-8")
    html = root / "index.html"
    html.write_text(pages["publish"].read_text(encoding="utf-8"), encoding="utf-8")
    out = root / "out"
    subprocess.run(["npx", "--yes", *staticrypt_args(tpl, out, html)], cwd=root, check=True,
                   capture_output=True, text=True, timeout=300, env=staticrypt_env(PASSWORD))
    assert not (root / ".staticrypt.json").exists()          # -c false: no config file left behind
    return (out / "index.html").as_uri()


def _open(browser, url, scheme="light", storage=True):
    ctx = browser.new_context(viewport=PHONE, device_scale_factor=2, color_scheme=scheme)
    if not storage:                                        # a private window / embedded preview
        ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new DOMException('denied','SecurityError')}})")
    # staticrypt opens the trip with document.write; count it (the window outlives the write)
    ctx.add_init_script("if(!('__writes' in window)){window.__writes=0;const w=Document.prototype.write;"
                        "Document.prototype.write=function(...a){window.__writes++;return w.apply(this,a)}}")
    pg = ctx.new_page()
    dialogs, errs = [], []
    pg.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(url)
    pg.wait_for_selector("#staticrypt-password", state="visible")
    return ctx, pg, dialogs, errs


def _unlock(pg, password):
    pg.fill("#staticrypt-password", password)
    pg.click(".go")


def test_lock_page_is_light_with_the_readers_bubble(browser, locked_url):
    ctx, pg, _, _ = _open(browser, locked_url, scheme="dark")      # system dark mode is ignored
    assert pg.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(246, 243, 234)"
    r = pg.evaluate("(r=>[r.right,r.top,r.width,r.height])(document.querySelector('.bubble').getBoundingClientRect())")
    assert r == [PHONE["width"] - 14, 9, 28, 28]
    assert pg.title() == LOCK_COPY["title"]
    assert pg.get_attribute("#staticrypt-password", "type") == "text"
    assert pg.get_attribute("#staticrypt-password", "placeholder") == LOCK_COPY["placeholder"]
    assert pg.input_value(".go") == LOCK_COPY["button"]
    assert pg.is_checked("#staticrypt-remember") and pg.is_visible("#staticrypt-remember-label")
    ctx.close()


def test_wrong_password_shows_the_error_inline(browser, locked_url):
    ctx, pg, dialogs, errs = _open(browser, locked_url)
    _unlock(pg, "不對的密碼")
    pg.wait_for_function("document.getElementById('err').textContent.length > 0")
    assert pg.text_content("#err") == LOCK_COPY["error"]
    assert dialogs == [] and errs == []
    ctx.close()


def test_the_right_password_opens_the_trip_in_the_chosen_theme(browser, locked_url):
    ctx, pg, dialogs, errs = _open(browser, locked_url)
    pg.click(".bubble")                                     # dark, chosen on the lock page
    _unlock(pg, PASSWORD)
    pg.wait_for_selector(".page.home", state="attached")
    pg.wait_for_timeout(300)
    assert pg.evaluate("document.getElementById('theme').checked")    # the reader carries it
    assert pg.evaluate("window.__writes") == 1
    assert dialogs == [] and errs == []
    ctx.close()


def test_lock_page_works_without_storage(browser, locked_url):
    ctx, pg, dialogs, errs = _open(browser, locked_url, storage=False)
    assert pg.is_visible(".lock")
    pg.click(".bubble")                                     # the theme still toggles, unsaved
    _unlock(pg, PASSWORD)                                   # remember is checked: storage throws
    pg.wait_for_selector(".page.home", state="attached")
    pg.wait_for_timeout(500)
    # staticrypt writes the page first and stores the password after: storage throws
    # once the trip is open, and the trip must not be written a second time
    assert pg.evaluate("window.__writes") == 1
    assert dialogs == []
    ctx.close()


SALT = "0123456789abcdef0123456789abcdef"


@pytest.fixture(scope="session")
def locked_share(tmp_path_factory, pages):
    """The publish page locked with a known salt, and its share link's fragment
    (`#staticrypt_pwd=<hash>`, which depends on the salt)."""
    if not shutil.which("npx"):
        pytest.fail("node/npx required: the lock page is made by staticrypt (npx staticrypt@3.5.4)")
    from scripts.render.publish.lock import staticrypt_share_args
    root = tmp_path_factory.mktemp("lock-share")
    tpl = root / "template.html"
    tpl.write_text(lock_template(), encoding="utf-8")
    html = root / "index.html"
    html.write_text(pages["publish"].read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(["npx", "--yes", *staticrypt_args(tpl, root / "out", html, salt=SALT)], cwd=root, check=True,
                   capture_output=True, text=True, timeout=300, env=staticrypt_env(PASSWORD))
    out = subprocess.run(["npx", "--yes", *staticrypt_share_args(SALT, "X")], cwd=root, check=True,
                         capture_output=True, text=True, timeout=300, env=staticrypt_env(PASSWORD)).stdout
    return (root / "out" / "index.html").as_uri(), out[out.index("#staticrypt_pwd="):].split()[0]


@pytest.mark.parametrize("way", ["share link", "typed", "remembered", "remembered, share link"])
def test_every_way_in_opens_today_during_the_trip(browser, locked_share, way):
    """Today opens however the trip is unlocked -- the share link keeps its fragment in the
    address bar after the unlock, and that fragment once kept the trip on its overview."""
    from tests import reader_fixture as R
    url, frag = locked_share
    ctx = browser.new_context(viewport=PHONE)
    d2 = R.itinerary()["days"][1]["date"]
    ctx.add_init_script(f"(()=>{{const T=new Date('{d2}T10:00:00').getTime(),D=Date;"
                        "window.Date=class extends D{constructor(...a){super(...(a.length?a:[T]))}static now(){return T}}})()")
    pg = ctx.new_page()
    if way == "share link":
        pg.goto(url + frag)
    else:
        pg.goto(url)
        pg.wait_for_selector("#staticrypt-password", state="visible")
        _unlock(pg, PASSWORD)
        if way != "typed":                                # remember is checked: a later visit opens by itself
            pg.wait_for_selector(".page.home", state="attached")
            pg = ctx.new_page()
            pg.goto(url + (frag if way.endswith("share link") else ""))
    pg.wait_for_selector(".page.home", state="attached")
    pg.wait_for_timeout(500)
    assert pg.evaluate("document.querySelector('input[name=pg]:checked').id") == "pg-d2"
    ctx.close()
