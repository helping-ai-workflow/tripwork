"""The publish build's lock page (v1.2 spec section 2, K3): a staticrypt template in
the reader's look. The page is public, so it names no trip; staticrypt fills its
/*[|…|]*/0 placeholders and injects the copy from staticrypt_args()."""
from scripts.render.publish.lock import LOCK_COPY, STATICRYPT, lock_template, staticrypt_args, staticrypt_share_args

# every placeholder staticrypt 3.5.4's own template carries that this page uses:
# a literal because the names live in the npm package, not in this repo
PLACEHOLDERS = ("js_staticrypt", "staticrypt_config", "template_title", "template_button", "template_placeholder",
                "template_remember", "template_error", "is_remember_enabled")


def test_template_keeps_every_staticrypt_placeholder():
    t = lock_template()
    for name in PLACEHOLDERS:
        assert f"/*[|{name}|]*/0" in t or f"/*[|{name}|]*/ 0" in t, name


def test_template_lets_the_ime_work_and_has_no_hint():
    t = lock_template()
    assert 'type="text"' in t and 'type="password"' not in t
    assert "template_instructions" not in t


def test_template_is_light_by_default_with_the_readers_theme_bubble():
    t = lock_template()
    assert "prefers-color-scheme" not in t and 'id="theme"' in t and 'class="bubble"' in t
    assert "tripwork-theme" in t


def test_template_names_no_trip():
    from tests import reader_fixture as R
    t = lock_template()
    for d in R.itinerary()["days"]:
        assert d["date"] not in t
    for p in R.poi_map().values():
        for k in ("name_local", "name_display", "name_zh"):
            assert not p.get(k) or p[k] not in t, p[k]


def test_storage_is_guarded():
    t = lock_template()
    assert "localStorage" in t
    assert t.count("try {") + t.count("try{") >= 3


def test_args_carry_the_copy():
    a = staticrypt_args("pw", "/t.html", "/out", "/in.html")
    assert a[0] == STATICRYPT == "staticrypt@3.5.4" and a[1] == "/in.html"
    assert a[a.index("--remember") + 1] == "0"
    for flag, key in (("--template-title", "title"), ("--template-button", "button"),
                      ("--template-placeholder", "placeholder"), ("--template-remember", "remember"),
                      ("--template-error", "error")):
        assert a[a.index(flag) + 1] == LOCK_COPY[key]
    assert LOCK_COPY["title"] == "我們的旅程" and LOCK_COPY["error"] == "密碼不對，再試一次。"


def test_args_never_write_a_config_file():
    # staticrypt writes ./.staticrypt.json (the salt) into its working directory
    # unless --config false; that directory may be the user's workspace
    a = staticrypt_args("pw", "/t.html", "/out", "/in.html")
    assert a[a.index("-c") + 1] == "false"
    assert "-s" not in a
    b = staticrypt_args("pw", "/t.html", "/out", "/in.html", salt="0" * 32)
    assert b[b.index("-s") + 1] == "0" * 32


def test_share_args_print_a_link_with_the_pages_salt():
    a = staticrypt_share_args("pw", "1" * 32, "https://x.pages.dev/abc/")
    assert a[0] == STATICRYPT and a[a.index("-s") + 1] == "1" * 32 and a[a.index("--share") + 1] == "https://x.pages.dev/abc/"
    assert a[a.index("-c") + 1] == "false"
