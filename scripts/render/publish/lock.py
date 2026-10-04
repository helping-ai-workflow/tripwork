"""The publish build's lock page (v1.2 spec section 2): the user's pick K3, ported from
the board's prototype. A staticrypt 3.5.4 template in the reader's look -- reader tokens,
the ZenEmb subset, the reader's theme bubble, no external request.

The page is public (anyone with the link sees it), so it names no trip, date or place;
the copy is neutral and staticrypt injects it from staticrypt_args(). The field is
type="text" (an iPhone keeps the 注音 keyboard; type="password" forces English) with an
optional 隱藏/顯示 mask. Light by default, like the reader (system dark mode ignored);
the bubble's choice is kept in localStorage 'tripwork-theme', which PUBLISH_JS applies
to the reader. Every storage call is in try/catch: a private window or an embedded
preview still shows the form and still decrypts."""
import re

from scripts.render.reader.assets import font_faces, icon
from scripts.render.reader.theme import WARM_DARK, WARM_LIGHT

STATICRYPT = "staticrypt@3.5.4"

LOCK_COPY = {"title": "我們的旅程", "placeholder": "輸入密碼", "button": "打開行程", "remember": "記得密碼",
             "error": "密碼不對，再試一次。", "show": "顯示", "hide": "隱藏"}

_CSS = """:root{%(light)s;--f-body:system-ui,-apple-system,"PingFang TC","Noto Sans TC",sans-serif;--f-round:'ZenEmb','GenSenEmb',var(--f-body);color-scheme:light}
:root:has(#theme:checked){%(dark)s}
#theme{position:absolute;opacity:0;pointer-events:none}
.bubble{position:fixed;right:24px;bottom:24px;z-index:9;width:44px;height:44px;border-radius:50%%;display:grid;place-items:center;cursor:pointer;background:var(--card);color:var(--ink);box-shadow:0 2px 10px rgba(0,0,0,.35),0 0 0 1px var(--rule)}
.bubble>span{display:grid;place-items:center;line-height:0}.bubble svg{width:20px;height:20px;stroke:currentColor;fill:none}.bubble .moon{display:none}:root:has(#theme:checked) .bubble .moon{display:grid}:root:has(#theme:checked) .bubble .sun{display:none}
@media (max-width:1023px){.bubble{right:14px;top:calc(9px + env(safe-area-inset-top,0px));bottom:auto;width:28px;height:28px;background:transparent;box-shadow:none;border:1.5px solid var(--ink)}.bubble svg{width:16px;height:16px}}
#theme:focus-visible+.bubble{outline:2px solid var(--ink);outline-offset:2px}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%%}
body{margin:0;min-height:100dvh;background:var(--bg);color:var(--ink);font:16px/1.6 var(--f-body);display:grid;place-items:center;padding:24px 20px calc(24px + env(safe-area-inset-bottom,0px))}
.hidden{display:none!important}
.lock{width:100%%;max-width:360px;display:grid;gap:18px;justify-items:center;text-align:center}
.lock h1{font:700 26px/1.3 var(--f-round);margin:0}
form{width:100%%;display:grid;gap:12px}
.field{position:relative}
.field input{width:100%%;font:inherit;font-size:18px;padding:14px 64px 14px 16px;border-radius:14px;border:1.5px solid var(--rule);background:var(--card);color:var(--ink);outline:none}
.field input:focus-visible{border-color:var(--move)}
.field input.masked{-webkit-text-security:disc}
.field button{position:absolute;right:8px;top:50%%;transform:translateY(-50%%);font:600 13px var(--f-body);color:var(--mut);background:none;border:0;padding:8px}
.go{font:700 17px var(--f-round);border:0;border-radius:999px;padding:14px 20px;background:var(--move);color:var(--card);cursor:pointer}
.go:focus-visible,.field button:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.rem input{accent-color:var(--move);width:18px;height:18px;margin:0}.rem{display:flex;gap:8px;align-items:center;justify-content:center;font-size:14px;color:var(--mut)}
.err{margin:0;min-height:1.4em;font-size:14px;color:var(--plan)}
.spin{width:28px;height:28px;border-radius:50%%;border:3px solid var(--rule);border-top-color:var(--move);animation:s 1s linear infinite}
@keyframes s{to{transform:rotate(360deg)}}@media (prefers-reduced-motion:reduce){.spin{animation:none}}
"""

_JS = """const staticryptInitiator = /*[|js_staticrypt|]*/ 0;
const templateError = "/*[|template_error|]*/0", isRememberEnabled = /*[|is_remember_enabled|]*/ 0, staticryptConfig = /*[|staticrypt_config|]*/ 0;
const templateConfig = {rememberExpirationKey:"staticrypt_expiration",rememberPassphraseKey:"staticrypt_passphrase",replaceHtmlCallback:null,clearLocalStorageCallback:null};
const staticrypt = staticryptInitiator.init(staticryptConfig, templateConfig);
// storage can be refused (a private window, an embedded preview): then just ask for the password
window.onload = async function () { let isSuccessful = false; try { ({ isSuccessful } = await staticrypt.handleDecryptOnLoad()); } catch (e) {}
 if (!isSuccessful) { document.getElementById("staticrypt_loading").classList.add("hidden"); document.getElementById("staticrypt_content").classList.remove("hidden");
  if (isRememberEnabled) document.getElementById("staticrypt-remember-label").classList.remove("hidden"); } };
// the theme chosen here carries into the trip (same key the reader reads)
const th = document.getElementById("theme"); try { th.checked = localStorage.getItem("tripwork-theme") === "dark"; } catch (e) {}
th.addEventListener("change", () => { try { localStorage.setItem("tripwork-theme", th.checked ? "dark" : "light"); } catch (e) {} });
const pw = document.getElementById("staticrypt-password"), tg = document.getElementById("tg");
// a text field (not type=password): iPhone keeps the 注音 keyboard; the dots are optional
tg.addEventListener("click", () => { const m = pw.classList.toggle("masked"); tg.textContent = m ? "%(show)s" : "%(hide)s"; pw.focus(); });
document.getElementById("staticrypt-form").addEventListener("submit", async function (e) { e.preventDefault();
 // staticrypt opens the trip first and stores the password after: storage refusing then
 // means the trip is already open -- retry without remember only if this form is still here
 let ok; try { ok = await staticrypt.handleDecryptionOfPage(pw.value, document.getElementById("staticrypt-remember").checked); }
 catch (err) { if (!document.getElementById("staticrypt-form")) return; ok = await staticrypt.handleDecryptionOfPage(pw.value, false); }
 const { isSuccessful } = ok;
 if (!isSuccessful) { document.getElementById("err").textContent = templateError; pw.select(); } });"""


def lock_template():
    """The staticrypt template (`-t`): an HTML page with staticrypt's /*[|name|]*/0
    placeholders, filled at encryption time."""
    c = LOCK_COPY
    lock = ('<div class="lock"><h1>/*[|template_title|]*/0</h1>'
            '<form id="staticrypt-form" action="#" method="post"><div class="field">'
            '<input id="staticrypt-password" type="text" name="password" placeholder="/*[|template_placeholder|]*/0"'
            ' autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" enterkeyhint="go">'
            f'<button type="button" id="tg">{c["hide"]}</button></div>'
            '<p class="err" id="err" role="status"></p>'
            '<label id="staticrypt-remember-label" class="rem hidden"><input id="staticrypt-remember" type="checkbox"'
            ' name="remember" checked>/*[|template_remember|]*/0</label>'
            '<input type="submit" class="go" value="/*[|template_button|]*/0"></form></div>')
    # the font subset covers the page's own text and every string staticrypt injects
    glyphs = "".join(sorted(set(re.sub(r"<[^>]+>|/\*\[\|[a-z_]+\|\]\*/0", "", lock) + "".join(c.values()))))
    css = font_faces(glyphs) + _CSS % {"light": WARM_LIGHT, "dark": WARM_DARK}
    return ('<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>/*[|template_title|]*/0</title><meta name="robots" content="noindex"><style>' + css
            + '</style></head><body class="staticrypt-body">'
            '<div id="staticrypt_loading"><div class="spin" aria-label="載入中"></div></div>'
            '<input type="checkbox" id="theme" autocomplete="off"><label class="bubble" for="theme"'
            ' aria-label="切換深色／淺色"><span class="moon">' + icon("moon") + '</span><span class="sun">'
            + icon("sun") + '</span></label>'
            '<div id="staticrypt_content" class="hidden">' + lock + '</div><script>' + _JS % c
            + '</script></body></html>')


def staticrypt_args(password, template_path, out_dir, html_path, salt=None):
    """argv after `npx --yes`. `-c false`: staticrypt otherwise writes ./.staticrypt.json
    (the salt) into its working directory, which may be the user's workspace. Without a
    salt staticrypt draws a new one, which changes every share link; pass the trip's own
    to keep them."""
    c = LOCK_COPY
    argv = [STATICRYPT, str(html_path), "-p", password, "-t", str(template_path), "-c", "false", "--short",
            "--remember", "0", "--template-title", c["title"], "--template-button", c["button"],
            "--template-placeholder", c["placeholder"], "--template-remember", c["remember"],
            "--template-error", c["error"], "--template-toggle-show", c["show"],
            "--template-toggle-hide", c["hide"], "-d", str(out_dir)]
    if salt:
        argv[argv.index("-d"):argv.index("-d")] = ["-s", salt]
    return argv
