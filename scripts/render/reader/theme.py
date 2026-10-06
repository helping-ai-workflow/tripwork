"""The reader's stylesheet: warm paper tokens (light by default since the v1.1 user
check, dark via the theme bubble) and the decided components (spec §6.1–§6.6). Ported from the
decided mockups (docs/superpowers/mockups/gen_dash.py / gen_deskhome.py /
gen_deskpanel.py); mockup-only frames are gone."""

WARM_DARK = ("--bg:#1b1814;--paper:#1b1814;--card:#25211c;--ink:#e6dfd2;--mut:#a2998a;--off:#5a5348;"
             "--rule:#3a342c;--r1:#93a9dc;--r2:#72c0a2;--r3:#e0958a;--r4:#d6b773;--r0:#a8a194;"
             "--sun:#e0958a;--sat:#93a9dc;--meal:#e0958a;--visit:#93a9dc;--activity:#b9a2e0;"
             "--move:#72c0a2;--lodging:#d6b773;--plan:#e2a660;--opt:#7fcf9f;--btnink:#1b1814;"
             "--tight:#e0958a;--mapf:brightness(.72) contrast(1.08) saturate(.85);--photof:brightness(.88);"
             "--pagebg:#141210;color-scheme:dark")
WARM_LIGHT = ("--bg:#f6f3ea;--paper:#f6f3ea;--card:#fffdf7;--ink:#2a2620;--mut:#7d776b;--off:#bdb7a8;"
              "--rule:#e2dccd;--r1:#27468c;--r2:#1d7a5f;--r3:#b2362b;--r4:#8a6a1f;--r0:#6d6a62;"
              "--sun:#c0392b;--sat:#2e5aa8;--meal:#b2362b;--visit:#27468c;--activity:#6a4a9c;"
              "--move:#1d7a5f;--lodging:#8a6a1f;--plan:#b8620f;--opt:#2f7d4f;--btnink:#fffdf7;"
              "--tight:#b2362b;--mapf:none;--photof:none;--pagebg:#ece7dc;color-scheme:light")

CSS = f"""
:root{{{WARM_LIGHT};--f-body:system-ui,-apple-system,"PingFang TC","Noto Sans TC","Microsoft JhengHei",sans-serif;--f-round:'ZenEmb','GenSenEmb',var(--f-body)}}
:root:has(#theme:checked){{{WARM_DARK}}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--pagebg);color:var(--ink);font:15px/1.6 var(--f-body)}}
.ck,#theme,.pgr{{position:absolute;opacity:0;pointer-events:none}}
.lu{{width:1.05em;height:1.05em;stroke:currentColor;fill:none;vertical-align:-.15em;flex:none}}
a{{color:inherit}}
.page{{display:none;max-width:560px;margin:0 auto;min-height:100vh;background:var(--bg);padding:16px 16px 88px}}
.empty{{color:var(--mut);font-size:14px;padding:12px 2px}}
/* home */
.ttl h1{{font:700 24px/1.3 var(--f-round);margin:6px 0 2px}}.ttl .dates{{margin:0 0 12px;font-size:13px;color:var(--mut)}}
.month h3{{font:700 13px var(--f-round);color:var(--mut);margin:8px 0 2px}}
.months{{display:grid;gap:10px}}
.g{{display:grid;grid-template-columns:repeat(7,1fr);font-variant-numeric:tabular-nums;font-family:var(--f-round)}}
.g>*{{display:grid;place-items:center;height:46px;font-size:14px}}.g .wd{{height:24px;font-size:12px;font-weight:700;color:var(--mut)}}
.wd.sun,.off.sun{{color:var(--sun)}}.wd.sat,.off.sat{{color:var(--sat)}}.off{{color:var(--off)}}.off.sun,.off.sat{{opacity:.55}}
.stamp{{--c:var(--r1);width:42px;height:42px;justify-self:center;border-radius:50%;color:var(--c);border:1.5px solid var(--c);cursor:pointer;
  outline:1px solid var(--c);outline-offset:1.5px;display:flex!important;flex-direction:column;align-items:center;justify-content:center;
  transform:rotate(var(--t));background:color-mix(in srgb,var(--c) 10%,var(--bg));font-family:var(--f-round)}}
.stamp b{{font-size:14px;line-height:1}}.stamp small{{font-size:8px;font-weight:700;line-height:1.2}}
.stamp.r2{{--c:var(--r2)}}.stamp.r3{{--c:var(--r3)}}.stamp.r4{{--c:var(--r4)}}.stamp.r0{{--c:var(--r0);border-style:dashed;outline-style:dashed}}
.stamp.cur{{background:var(--c);color:var(--card)}}
.tiles{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-top:14px}}.plist>.dh-list{{display:none}}
/* the 旅程與費用 card (v1.1 topic 6, picks C2 + S): stays in their stamp colours; many stays scroll
   inside the card, the edges fading where there is more (the chip row's S3, turned vertical) */
.trip{{margin-top:14px}}.trip h3{{font:700 14px var(--f-round);color:var(--mut);margin:0 0 10px}}
.trip ol{{--fz:40px;list-style:none;margin:0;padding:0 0 2px 4px}}
@supports not (animation-timeline: scroll()){{.trip ol{{-webkit-mask-image:linear-gradient(#000 calc(100% - var(--fz)),transparent);mask-image:linear-gradient(#000 calc(100% - var(--fz)),transparent)}}}}
.trip li{{position:relative;display:grid;grid-template-columns:minmax(0,1fr) auto;column-gap:8px;padding:0 0 14px 24px}}
.trip li::before{{content:'';position:absolute;left:0;top:4px;width:12px;height:12px;border-radius:50%;border:2px solid var(--c);background:color-mix(in srgb,var(--c) 20%,var(--bg))}}
.trip li:not(:last-child)::after{{content:'';position:absolute;left:7px;top:20px;bottom:2px;border-left:2px dotted var(--rule)}}
.trip li.r1{{--c:var(--r1)}}.trip li.r2{{--c:var(--r2)}}.trip li.r3{{--c:var(--r3)}}.trip li.r4{{--c:var(--r4)}}.trip li.r0{{--c:var(--r0)}}
.trip li b{{font:700 17px var(--f-round);color:var(--c)}}.trip li em{{font:700 14px var(--f-round);font-style:normal;align-self:center}}
.trip li span{{grid-column:1/-1;font-size:14px}}
.trip .tt{{display:flex;justify-content:space-between;margin:0;padding:8px 0 0;font-size:14px}}.trip ol+.tt{{border-top:1px solid var(--rule);margin-top:4px}}
.trip .tt em{{font:700 14px var(--f-round);font-style:normal}}.trip .tt.sum span,.trip .tt.sum em{{font-size:17px;font-weight:700}}
.trip .tn{{font-size:12px;color:var(--mut);margin:6px 0 0}}
@property --ft{{syntax:'<length>';inherits:false;initial-value:0px}}@property --fb{{syntax:'<length>';inherits:false;initial-value:0px}}
@keyframes listfade{{0%{{--ft:0px;--fb:var(--fz)}}8%{{--ft:var(--fz)}}92%{{--fb:var(--fz)}}100%{{--ft:var(--fz);--fb:0px}}}}
@supports (animation-timeline: scroll()){{.trip ol{{animation:listfade linear both;animation-timeline:scroll(y self);-webkit-mask-image:linear-gradient(transparent,#000 var(--ft),#000 calc(100% - var(--fb)),transparent);mask-image:linear-gradient(transparent,#000 var(--ft),#000 calc(100% - var(--fb)),transparent)}}}}
.tile{{display:flex;flex-direction:column;align-items:center;gap:2px;background:var(--card);border-radius:12px;box-shadow:0 0 0 1px var(--rule);padding:12px 6px;font:700 15px var(--f-round);cursor:pointer}}
.tile small{{font-size:12px;color:var(--mut);font-weight:500}}.tile .lu{{width:20px;height:20px}}
/* sub-screens */
.ph{{display:flex;align-items:center;justify-content:space-between;margin:0 0 12px}}.ph h2{{margin:0;font:700 18px var(--f-round)}}
.back,.ovx{{font:700 12px var(--f-round);padding:3px 12px;border:1.5px solid var(--ink);border-radius:999px;cursor:pointer;white-space:nowrap}}
.lrow{{--c:var(--r1);position:relative;display:flex;align-items:center;gap:10px;background:var(--card);border-radius:12px;box-shadow:0 0 0 1px var(--rule);padding:10px 78px 10px 12px;margin:0 0 8px}}
.lrow.r2{{--c:var(--r2)}}.lrow.r3{{--c:var(--r3)}}.lrow.r4{{--c:var(--r4)}}.dot{{width:12px;height:12px;border-radius:50%;background:var(--c);flex:none}}
.lt{{flex:1;min-width:0}}.lt b{{display:block;font:700 15px var(--f-round)}}.lt small{{font-size:12px;color:var(--mut)}}
.adv,.ci{{position:relative;background:var(--card);border-radius:12px;box-shadow:0 0 0 1px var(--rule);margin:0 0 8px}}
.adv summary,.ci summary{{position:relative;display:flex;flex-direction:column;gap:3px;padding:10px 34px 10px 12px;list-style:none;cursor:pointer}}
summary::-webkit-details-marker{{display:none}}
.tl2{{display:flex;gap:8px;align-items:flex-start;font-size:14px}}.tl2 b{{font-family:var(--f-round)}}
.rk{{flex:none;font:700 11px var(--f-round);border-radius:4px;padding:1px 6px;color:#fff}}
.risk-banned .rk{{background:#b2362b}}.risk-restricted .rk{{background:#b8620f}}.risk-info .rk{{background:#27468c}}
.risk-banned{{--mc:#e0958a}}.risk-restricted{{--mc:#e2a660}}.risk-info{{--mc:#93a9dc}}
.qbar{{border-left:3px solid var(--mc);padding-left:8px}}
.adv .do{{font-size:12.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.adv[open] .do{{display:none}}
.adv p,.ci p{{margin:0 12px 8px;font-size:13px;line-height:1.6}}.adv .act{{font-weight:700}}.adv .det{{color:var(--mut)}}
.lnk a{{display:inline-block;margin-right:10px;font-size:12px;color:var(--r1)}}
.ckg h3{{display:inline-block;font:700 15px var(--f-round);margin:10px 6px 6px 2px}}.ckg .n{{font-size:12px;color:var(--mut)}}
div.ci{{display:flex;flex-direction:column;gap:3px;padding:10px 12px}}
.tk{{font:700 14px/1.45 var(--f-round)}}.meta{{display:flex;gap:6px;align-items:center;flex-wrap:wrap}}
.due{{font:700 11px var(--f-round);border-radius:4px;padding:0 6px;border:1px solid var(--mut);color:var(--mut)}}.due.hard{{background:#b2362b;border-color:#b2362b;color:#fff}}
.origin{{font-size:11px;color:var(--mut)}}
.adv p,.ci p,.tk,.lt small{{overflow-wrap:anywhere}}
/* day page */
.ymrow{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;margin:0 0 4px}}.ymrow .back{{justify-self:start}}.ymrow .ym{{font:700 14px var(--f-round)}}.mini{{flex:1}}
.mini .g>*{{height:40px}}.mini .stamp{{width:34px;height:34px}}.mini .stamp b{{font-size:12px}}.mini .stamp small{{font-size:7px}}
.dh{{display:flex;align-items:center;gap:8px;font:700 19px/1.35 var(--f-round);margin:8px 0 12px}}
/* the phone's day stepper (user check, pick S1; pick T25b 2026-10-03: as tall as the title row,
   25.5 of its 25.6 px -- taller would grow the row -- with the desktop's 13 / 15 px glyphs).
   Centred by the glyphs' ink, measured in WebKit at 390 px (tripwork/CLAUDE.md): the pill
   sits 1.5 px low of its box centre, the text 1 px up, the arrows 3.5 px up; the arrows'
   tap area (::after) is re-centred on the pill */
.dstep{{flex:none;margin-left:auto;position:relative;top:1.5px;display:inline-flex;align-items:center;box-sizing:border-box;height:25.5px;border:1.5px solid var(--rule);border-radius:999px;font:700 12px var(--f-round);color:var(--mut)}}
.dstep .dn{{position:relative;top:-1px;font-size:13px;line-height:18px;padding:0 2px}}
.dstep label,.dstep .off{{position:relative;top:-3.5px;display:grid;place-items:center;width:22px;height:18px;color:var(--ink);font-size:15px;cursor:pointer}}
.dstep .off{{color:var(--off);cursor:default}}
.dstep label::after{{content:"";position:absolute;top:-3.5px;bottom:-10.5px;left:-6px;right:-6px}}
/* pinned at the row's right end (F1), the › tap area must not reach past it: it made the phone's
   day scroll 4 px sideways (the user's check) */
.dstep label:last-child::after,.dstep .sw:last-child label::after{{right:0}}
/* H1c2: the phone's arrow pairs (day.py) -- both labels on one spot, one shown (PHONE_CSS) */
.dstep .sw{{display:grid}}.dstep .sw>label{{grid-area:1/1}}.dstep .sf{{visibility:hidden}}
.ym{{position:relative}}.unf{{display:none;position:absolute;inset:-10px -14px;cursor:pointer}}
/* pick F1: pinned to the title row's right end (it followed the title's end); the desktop list
   title's stepper is 21 px = the 22 px title's ink, the same glyphs and offsets */
.dstep-d{{height:21px;top:2px}}.dayn{{flex:none;font:700 12px var(--f-round);color:var(--mut);border:1.5px solid var(--rule);border-radius:999px;padding:1px 9px;line-height:18px}}
.list{{display:flex;flex-direction:column;gap:6px}}
.s-meal{{--k:var(--meal)}}.s-visit{{--k:var(--visit)}}.s-activity{{--k:var(--activity)}}.s-lodging{{--k:var(--lodging)}}
.stop{{position:relative}}
.c3{{background:var(--card);border-radius:14px;box-shadow:0 0 0 1px var(--rule);overflow:hidden}}
.c3 .hd{{display:grid;grid-template-columns:52px minmax(0,1fr);align-items:center;column-gap:6px;padding:10px 72px 10px 12px;cursor:pointer}}
.c3 .hd-close,.c3 .in{{display:none}}
.stop:is(:target,:has(:target:not(.tx))) .hd-open{{display:none}}.stop:is(:target,:has(:target:not(.tx))) .hd-close{{display:grid}}.stop:is(:target,:has(:target:not(.tx))) .in{{display:block}}
.stop:is(:target,:has(:target:not(.tx))) .c3{{box-shadow:0 0 0 2px var(--k)}}.stop:is(:target,:has(:target:not(.tx))) .hd-close{{border-bottom:1px solid var(--rule)}}
/* v1.1 §8.1: anchors, not radios -- the jump itself scrolls; .tx = a 1 px target that means 'closed, stay here' */
a.hd,a.chip,.mnav a{{color:inherit;text-decoration:none}}
/* TW-096 (the user's pick A2): the address row's 給司機看 button and its big-print sheet -- a
   :target overlay, white on purpose in both themes so a driver reads it at a glance */
.drvbtn{{display:inline-block;margin-left:8px;padding:0 8px;border:1.5px solid var(--rule);border-radius:999px;font-size:12px;font-weight:700;color:var(--ink);text-decoration:none;vertical-align:1px;line-height:20px}}
.drv{{display:none;position:fixed;inset:0;z-index:60;background:#fffdf7;color:#1b1814;padding:56px 24px calc(24px + env(safe-area-inset-bottom,0px));flex-direction:column;justify-content:center;gap:18px;overflow-wrap:anywhere}}
.drv:target{{display:flex}}
.drvx{{position:absolute;top:16px;right:16px;z-index:1;color:#1b1814;font-weight:700;text-decoration:none}}
.drvbg{{position:absolute;inset:0}}.drv p{{position:relative;pointer-events:none}}
.drv .drvn{{font-size:30px;font-weight:700;margin:0;line-height:1.3}}.drv .drva{{font-size:34px;font-weight:700;margin:0;line-height:1.35}}
.drv .drvh{{color:#7d776b;margin:0}}
/* controls a person taps: no grey tap box, no text selection (iPhone report); in-page
   controls also drop the long-press callout, external links (導航, Google Maps) keep it */
label,summary,a.hd,a.chip,.mnav a,.vsum,.navb,.gbtn{{-webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none}}
label,summary,a.hd,a.chip,.mnav a,.vsum{{-webkit-touch-callout:none}}.list{{position:relative}}.stop{{scroll-margin-top:8px}}.anchor{{scroll-margin-top:8px}}
.tx{{position:absolute;top:0;left:0;width:1px;height:1px;pointer-events:none}}
.plist{{scroll-behavior:smooth}}
.c3 .t{{display:flex;flex-direction:column;line-height:1.15}}.c3 .t b{{font:700 15px var(--f-round);color:var(--k)}}.c3 .t small{{font:500 11px var(--f-round);color:var(--mut)}}
.c3 .n{{display:block;font:700 16px/1.35 var(--f-round)}}.c3 .one{{display:block;font-size:13px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.c3 dl{{display:grid;grid-template-columns:40px minmax(0,1fr);gap:6px 10px;margin:12px 14px 14px;font-size:14.5px;line-height:1.65}}
.c3 dt{{font:700 12px/1.9 var(--f-round);color:var(--mut)}}.c3 dd{{margin:0;overflow-wrap:anywhere}}
.bp{{margin:0;position:relative}}.bpi{{display:block;width:100%;height:220px;background-size:cover;background-position:center;filter:var(--photof)}}
.bpi,.mimg{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
.bp figcaption{{position:absolute;right:8px;bottom:8px;font-size:10px;color:#fff;background:rgba(0,0,0,.5);padding:1px 7px;border-radius:99px}}.bp figcaption a{{color:#fff;text-decoration:none}}
.navb{{position:absolute;top:12px;right:10px;display:inline-flex;align-items:center;justify-content:center;gap:3px;width:58px;height:24px;border-radius:999px;
  border:1px solid var(--k,var(--lodging));color:var(--k,var(--lodging));background:var(--card);font:700 11px var(--f-round);text-decoration:none}}
.navb .lu{{width:13px;height:13px}}
.anchor{{position:relative;display:flex;align-items:center;min-height:40px;padding:4px 72px 4px 0;font:500 14px var(--f-round);color:var(--lodging)}}
.anchor .navb{{top:8px;--k:var(--lodging)}}.lrow .navb{{top:50%;margin-top:-12px;--k:var(--c)}}
.leg{{display:flex;align-items:center;gap:8px;margin:0 0 0 22px;padding:3px 0 3px 16px;border-left:2px dashed var(--move);font-size:13px;color:var(--mut)}}
.leg.zero{{border-left:2px dotted var(--rule)}}.leg .lu{{width:20px;height:20px;color:var(--move)}}.lico{{width:20px;text-align:center}}
.ltx b{{color:var(--ink)}}.lkm{{font-size:12px;color:var(--mut)}}
.gap,.tight{{margin:0 0 0 22px;padding:2px 0 2px 16px;border-left:2px dashed var(--move);font-size:12px;color:var(--mut)}}.tight{{color:var(--tight);font-weight:700}}
.k備案{{--a:var(--plan)}}.k選項{{--a:var(--opt)}}
.altrow{{margin:-2px 0 2px 22px;border:1.5px dashed var(--a);border-radius:12px;background:color-mix(in srgb,var(--a) 7%,var(--card))}}
.altrow summary{{position:relative;display:flex;align-items:center;gap:8px;padding:6px 30px 6px 10px;cursor:pointer;list-style:none}}
.ai{{display:inline-grid;place-items:center;flex:none;width:22px;height:22px;border-radius:50%;background:var(--a);color:var(--card);font:700 13px var(--f-round)}}
.altrow .at{{font-size:13px}}.altrow .at b{{color:var(--a);margin-right:6px;font-family:var(--f-round)}}
.ab{{position:relative;padding:0 12px 10px;font-size:14px}}.ab p{{margin:4px 0}}.ab .navb{{position:static;--k:var(--a)}}
.ver summary,.vsum{{position:relative;display:flex;align-items:center;gap:6px;padding:3px 30px 3px 10px;border:1.5px solid var(--rule);border-radius:999px;cursor:pointer;list-style:none}}
.ver .nms{{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:12.5px}}
.ver ul{{list-style:none;margin:8px 0 0;padding:0;font-size:13px}}.vsum{{color:inherit;text-decoration:none}}.ver .vlist,.ver .vclose,.ver:target .vopen{{display:none}}.ver:target .vlist{{display:block}}.ver:target .vclose{{display:flex}}.vclose .cv{{transform:rotate(-135deg);margin-top:-2px}}.ver{{scroll-margin-top:8px}}.ver li{{padding:6px 0;border-top:1px dashed var(--rule)}}
.ver .sh{{display:flex;flex-wrap:wrap;gap:6px;align-items:center;text-decoration:none;color:var(--ink)}}.ver .snm{{font:700 13px var(--f-round)}}
.ver .sl{{display:block;font-size:11px;color:var(--mut)}}
.otag{{font:700 10px var(--f-round);color:var(--card);background:var(--visit);border-radius:4px;padding:1px 5px}}
.lg{{font:700 10px var(--f-round);color:var(--mut);border:1px solid var(--rule);border-radius:4px;padding:0 4px}}
.ver .su{{display:block;font-size:12px;color:var(--visit);overflow-wrap:anywhere}}.ver .sd{{margin:2px 0 0}}
.cv{{position:absolute;right:12px;top:50%;margin-top:-6px;width:8px;height:8px;border-right:2px solid var(--mut);border-bottom:2px solid var(--mut);transform:rotate(45deg)}}
details[open]>summary>.cv{{transform:rotate(-135deg);margin-top:-2px}}
.adv .cv,.ci .cv{{top:18px;margin-top:0}}details[open]>summary>.cv{{}}
.bubble{{position:fixed;left:16px;bottom:16px;z-index:9;width:44px;height:44px;border-radius:50%;display:grid;place-items:center;cursor:pointer;
  background:var(--card);color:var(--ink);box-shadow:0 2px 10px rgba(0,0,0,.35),0 0 0 1px var(--rule);font-size:20px}}
.bubble>span{{display:grid;place-items:center;line-height:0}}.bubble .lu{{width:20px;height:20px;vertical-align:0}}.bubble .moon{{display:none}}:root:has(#theme:checked) .bubble .moon{{display:grid}}:root:has(#theme:checked) .bubble .sun{{display:none}}
/* map card (spec §6.5) */
.mapc{{position:relative;background:var(--card);border-radius:14px;box-shadow:0 0 0 1px var(--rule);margin:0 0 12px}}
.mapc>summary{{position:relative;display:flex;align-items:center;gap:8px;padding:10px 36px 10px 12px;font:700 15px var(--f-round);list-style:none;cursor:pointer}}
.mapc .lu.big{{width:18px;height:18px}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;padding:0 12px 10px}}
.chip{{font:700 12px var(--f-round);padding:2px 10px;border:1.5px solid var(--rule);border-radius:999px;cursor:pointer}}.chip.hotel{{border-color:var(--lodging);color:var(--lodging)}}.chip.home{{border-color:var(--ink)}}
.views{{padding:0 12px}}.mv{{display:none}}
.mframe{{position:relative;display:block;width:100%;border-radius:10px;overflow:hidden;cursor:zoom-in;background:var(--bg)}}
.seg+.seg{{margin-top:8px}}
.mimg{{position:absolute;inset:0;background-size:100% 100%;filter:var(--mapf)}}
.pins,.grid{{position:absolute;inset:0;width:100%;height:100%}}
.gbg{{fill:var(--bg)}}.gline{{stroke:var(--rule);stroke-width:1.5;fill:none}}
.pin .pt{{stroke:#fff;stroke-width:3}}
.pin.k-meal .pt,.pin.k-meal .tl{{fill:var(--meal)}}.pin.k-visit .pt,.pin.k-visit .tl{{fill:var(--visit)}}
.pin.k-activity .pt,.pin.k-activity .tl{{fill:var(--activity)}}.pin.k-lodging .pt,.pin.k-lodging .tl{{fill:var(--lodging)}}.pin.k-home .pt,.pin.k-home .tl{{fill:var(--ink)}}
.pin.hl .pt{{stroke-width:6}}.tl{{font:700 14px var(--f-round);text-anchor:middle;paint-order:stroke;stroke:#fff;stroke-width:4px;stroke-linejoin:round}}
.mnav{{display:flex;justify-content:space-between;padding:6px 2px 0;font:700 12px var(--f-round);color:var(--mut)}}.mnav label{{cursor:pointer}}
.mv:has(.zck:checked){{position:fixed;inset:0;z-index:30;background:rgba(10,8,6,.92);display:flex!important;flex-direction:column;justify-content:safe center;overflow:auto;padding:12px}}
.mv:has(.zck:checked) .mframe{{flex:none;width:min(100%,calc((100vh - 24px - 56px) * var(--ar)));margin:0 auto;cursor:zoom-out;border-radius:0}}.mv:has(.zck:checked) .mnav{{display:none}}
.lgd{{list-style:none;margin:0;padding:8px 12px 10px;display:grid;gap:1px;font-size:13px}}.lgd b{{display:inline-block;min-width:52px;color:var(--mut);font:700 12px var(--f-round)}}
.attr{{margin:0;padding:0 12px 10px;font-size:10px;color:var(--mut)}}.attr a{{color:inherit;text-decoration:none}}
/* v1.1 (both widths): the selected day glows (E2), month labels, map canvas, photo fullscreen */
.mini .stamp.cur{{box-shadow:0 0 12px 3px color-mix(in srgb,var(--c) 70%,transparent)}}
.month h3{{text-align:center;font:700 14px var(--f-round);color:var(--ink);margin:0 0 6px}}
.stamp.m1 b{{font-size:11px;letter-spacing:-.02em}}.mini .stamp.m1 b{{font-size:9px}}
.mcanvas{{position:absolute;inset:0}}.mcanvas>.mimg,.mcanvas>svg{{position:absolute;inset:0;width:100%;height:100%}}
.attrmini{{position:absolute;right:6px;bottom:6px;font-size:9px;color:#fff;text-decoration:none;background:rgba(0,0,0,.45);padding:0 5px;border-radius:4px}}
/* the zoom bar (v1.1 topic 6, Z1-a + close rule A): under the enlarged map or photo, the source link
   and ✕ 關閉; the map, the dark layer (.zbg) and ✕ all close -- only the link leaves */
.zbar,.zbg{{display:none}}
/* fixed, not absolute: a split day's zoomed view scrolls, and the layer must cover the window wherever it is */
.mv:has(.zck:checked) .zbg,.bp:has(.pz:checked) .zbg{{display:block;position:fixed;inset:0;z-index:0;cursor:zoom-out}}
.mv:has(.zck:checked)>:not(.zbg):not(.ck),.bp:has(.pz:checked)>:not(.zbg):not(.ck){{position:relative;z-index:1}}
/* the user's check: a click beside the enlarged map, or between the bar's buttons, closes it --
   the frame's wrapper (.seg, full width) and the bar let clicks through to the dark layer;
   only the map itself and the two buttons take them */
.mv:has(.zck:checked) .seg,.mv:has(.zck:checked) .zbar,.bp:has(.pz:checked) .zbar{{pointer-events:none}}
.mv:has(.zck:checked) .mframe,.mv:has(.zck:checked) .zbar>*,.bp:has(.pz:checked) .zbar>*{{pointer-events:auto}}
.mv:has(.zck:checked) .zbar,.bp:has(.pz:checked) .zbar{{display:flex;justify-content:space-between;align-items:center;gap:10px;width:100%;margin:10px auto 0}}
.mv:has(.zck:checked) .zbar{{max-width:min(100%,calc((100vh - 80px) * var(--ar,4/3)))}}
.zbar a,.zbar label{{font:700 14px var(--f-round);border-radius:999px;padding:9px 16px;text-decoration:none;color:#f3ece0;background:rgba(255,255,255,.12);box-shadow:0 0 0 1px rgba(255,255,255,.22) inset;cursor:pointer}}
.zbar .zx{{background:#f3ece0;color:#1b1814;box-shadow:none;margin-left:auto}}.zbar .zc{{font-size:12px;color:#cfc6b8}}.zbar .zc a{{padding:0;background:none;box-shadow:none;color:#f3ece0;text-decoration:underline;font-size:12px}}
.bp:has(.pz:checked){{flex-direction:column}}.bp:has(.pz:checked) .bpi{{height:calc(92dvh - 56px)}}.bp:has(.pz:checked) figcaption{{display:none}}
.bp:has(.pz:checked) .zbar{{max-width:min(100%,960px);padding:0 12px}}
.bpz{{display:block;cursor:zoom-in}}
.bp:has(.pz:checked){{position:fixed;inset:0;z-index:40;margin:0;background:rgba(10,8,6,.94);display:flex;align-items:center;justify-content:center}}
.bp:has(.pz:checked) .bpz{{width:100%;cursor:zoom-out}}
.bp:has(.pz:checked) .bpi{{height:92dvh;background-size:contain;background-repeat:no-repeat;background-position:center;filter:none}}
.bp:has(.pz:checked) figcaption{{bottom:calc(12px + env(safe-area-inset-bottom,0px))}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important}}.plist{{scroll-behavior:auto}}}}
"""

# The phone (spec v1.1 §3–§7): the page never scrolls. A day stacks the dashboard's three
# blocks -- fixed header (.pcal), fixed map row (.pmap), and the list card (.plist), the
# only scroller; the home is one screen; the toggle sits top-right; the map card drops
# prev/next and the legend and fills its width with a 4:3 frame. Ported from the decided
# mockup (docs/superpowers/mockups/v11/gen_skeleton.py).
PHONE_CSS = """
@media (max-width:1023px){
html,body{height:100%;overflow:hidden}
.page.home,.page.day,.page.sub{height:100dvh;min-height:0;padding:10px 14px calc(12px + env(safe-area-inset-bottom,0px))}
.page.day .dash{height:100%;display:flex;flex-direction:column}
/* the mini calendar's rows are fixed -- weekdays 22, each week 38 -- so its height is known from
   its weeks (--wk, day.py): the fold (a week whose seven days are all stamps drew 30) */
.pcal .mini .g{grid-template-rows:22px;grid-auto-rows:38px}.page.day{--fold:calc(22px + 38px * var(--wk,2))}
/* the user's pick H1c (2026-10-03; H1b's scrolling page undone): the page stays, the list card
   is fixed to the foot and is the only scroller (topic 1), yet scrolling it first puts the
   small calendar away -- its own height (--fold: 98 px for two weeks, 60 for one). The list's scroll timeline (--lst,
   shared with its siblings by timeline-scope) moves the title, the map row and the card's top
   up with the finger and closes the calendar's window; the card itself sits a calendar higher
   than it looks (margin -fold, padding +fold) with its top clipped, so the content moves 1:1.
   Only transform / clip-path / opacity animate: no layout per frame. Every day scrolls at least
   the fold (the ::after strut) so a short one (10/12) can put its calendar away. The clipped top
   has no outline of its own: .lcap draws it, riding with the map; .lfoot fades the foot.
   The map card open or closed, the fold holds (the user's check: opening the map brought a folded
   calendar back -- an H1b-era guard, moot with a transform fold); where scroll timelines are
   unsupported the topic-1 layout holds. The card's resting clip is also set
   statically: WebKit can paint a newly shown day before its timeline resolves, and the card's
   raised background then covered the calendar's foot (the glow read as cut). */
@supports (animation-timeline: scroll()){
/* open or folded, never between (the user's call, 2026-10-04). With no script (Files / LINE
   previews) the fold jumps at half its height: a scroll-linked animation cannot settle by itself,
   and WebKit decides scroll snapping when a gesture starts (three snap designs measured: each
   failed one direction). centre.py adds .jsfold where a script runs (e.g. the password-protected
   copy opened in Safari): the fold follows the finger 1:1 again and a scroll that stops between
   settles to the nearer end. */
.page.day{--foldease:steps(1,jump-end);--foldend:calc(var(--fold) / 2)}
.jsfold .page.day{--foldease:linear;--foldend:var(--fold)}
@keyframes cardclip{from{clip-path:inset(var(--fold) -1px -1px -1px round 15px)}to{clip-path:inset(0px -1px -1px -1px round 15px)}}
@keyframes calup{to{transform:translateY(calc(-1 * var(--fold)))}}
@keyframes calwin{from{clip-path:inset(0px -20px -20px -20px)}to{clip-path:inset(0px -20px var(--fold) -20px)}}
@keyframes edgein{from{opacity:0}to{opacity:1}}
@keyframes stepopen{0%,49%{visibility:visible}50%,100%{visibility:hidden}}@keyframes stepfold{0%,49%{visibility:hidden}50%,100%{visibility:visible}}
@keyframes monthtop{0%,99%{visibility:visible}100%{visibility:hidden}}
.page.day .dash{timeline-scope:--lst}
.page.day .plist{scroll-timeline:--lst y;position:relative;margin-top:calc(-1 * var(--fold));padding-top:calc(var(--fold) + 12px);clip-path:inset(var(--fold) -1px -1px -1px round 15px);animation:cardclip var(--foldease) both;animation-timeline:--lst;animation-range:0px var(--foldend)}
.page.day .plist::after{content:"";position:absolute;top:0;left:0;width:1px;height:calc(100% + var(--fold));pointer-events:none}
/* the card's clip would clip the full-screen layers that live in it too (給司機看, a photo opened
   full screen): while one is up the card goes unclipped -- the layer covers the screen anyway */
.page.day:has(.drv:target,.pz:checked) .plist{clip-path:none!important;animation:none!important}
/* the zoomed map is a position:fixed layer inside the map row, and the fold's transform on the row
   would make the row its frame: while zoomed the row drops the transform (the zoom covers it) */
.page.day:has(.zck:checked) .pmap{transform:none!important;animation:none!important}
.page.day :is(.pcal .mini .g,.pcal .dh,.pmap,.lcap){animation:calup var(--foldease) both;animation-timeline:--lst;animation-range:0px var(--foldend)}
/* the window closes faster than the calendar rises: open, the current day's 15 px glow
   (.stamp.cur) reaches past the calendar's foot as it always has; away, none of it shows
   between the month and the title (the user saw both cut and leak) */
.page.day .pcal .mini{animation:calwin var(--foldease) both;animation-timeline:--lst;animation-range:0px var(--foldend)}
.page.day .lcap{display:block;height:0;position:relative;z-index:3;flex:none}
.lcap::after{content:"";position:absolute;left:0;right:0;top:0;height:14px;border-radius:14px 14px 0 0;background:var(--bg);box-shadow:0 0 0 1px var(--rule);clip-path:inset(-2px -2px 0 -2px)}
.lcap::before{content:"";position:absolute;left:0;right:0;top:14px;height:18px;pointer-events:none;background:linear-gradient(var(--bg),transparent);opacity:0;animation:edgein linear both;animation-timeline:--lst;animation-range:var(--fold) calc(var(--fold) + 20px)}
.page.day .lfoot{display:block;height:0;position:relative;z-index:3;flex:none}
.lfoot::before{content:"";position:absolute;left:0;right:0;bottom:0;height:28px;border-radius:0 0 14px 14px;pointer-events:none;background:linear-gradient(transparent,var(--bg))}
/* H1c2: the stepper keeps the calendar as it is (no script). Its arrows show the label to the
   neighbour opened as usual while the calendar is mostly out, to the neighbour opened with it
   away (pg-dNf, page.py) once it is mostly away. A day opened away shows its list from the top
   with the calendar away; at that list's top the month, with a ⌄, opens the calendar (the
   tap would not open it from further down, so it is no button there). Its strut stays 9 px:
   iOS read a zero scroll range as 'at the end' and hid the ⌄ (the user's check). */
.page.day .dstep .so{animation:stepopen linear both;animation-timeline:--lst;animation-range:0px var(--fold)}
.page.day .dstep .sf{animation:stepfold linear both;animation-timeline:--lst;animation-range:0px var(--fold)}
body:has(.pgf:checked) .page.day .plist{padding-top:12px;animation:none;clip-path:inset(0px -1px -1px -1px round 15px)}
body:has(.pgf:checked) .page.day .plist::after{height:calc(100% + 9px)}
body:has(.pgf:checked) .page.day :is(.pcal .mini .g,.pcal .dh,.pmap,.lcap){animation:none;transform:translateY(calc(-1 * var(--fold)))}
body:has(.pgf:checked) .page.day .pcal .mini{animation:none;clip-path:inset(0px -20px var(--fold) -20px)}
body:has(.pgf:checked) .page.day .lcap::before{animation-range:0px 20px}
body:has(.pgf:checked) .page.day .dstep .so{animation:none;visibility:hidden}body:has(.pgf:checked) .page.day .dstep .sf{animation:none;visibility:visible}
body:has(.pgf:checked) .page.day .unf{display:block;animation:monthtop linear both;animation-timeline:--lst;animation-range:0px 8px}
body:has(.pgf:checked) .page.day .unf::after{content:"";position:absolute;right:1px;top:calc(50% - 5px);width:6px;height:6px;border:solid var(--mut);border-width:0 1.75px 1.75px 0;transform:rotate(45deg)}
}
.pcal{flex:none}
.pmap{flex:0 1 auto;min-height:44px;overflow-y:auto;overscroll-behavior:contain;margin:0 0 8px;background:var(--bg);border-radius:14px;box-shadow:0 0 0 1px var(--rule)}
.pmap:empty{display:none}
.plist{flex:1 0 120px;min-height:120px;overflow-y:auto;overscroll-behavior:contain;padding:12px 12px 64px;background:var(--bg);border-radius:14px;box-shadow:0 0 0 1px var(--rule)}
.pcal .mini .g>:not(.stamp){height:38px}.pcal .mini .g .wd{height:22px}
.pcal .mini .stamp{width:30px;height:30px;align-self:center}
.bubble{left:auto;right:14px;top:calc(9px + env(safe-area-inset-top,0px));bottom:auto;width:28px;height:28px;
  background:transparent;box-shadow:none;border:1.5px solid var(--ink);display:grid;place-items:center}
.bubble .lu{width:16px;height:16px}
.page.home{overflow-y:auto;overscroll-behavior:contain}
.page.home .ttl{padding-right:40px}
.page.home .month{background:var(--card);border-radius:14px;box-shadow:0 0 0 1px var(--rule);padding:10px 12px 12px}
/* v1.1 topic 6 (pick P1): the day page mini stamp's proportion -- 14 px date in 34 px */
.page.home .months .stamp{width:34px;height:34px}
.page.home .hwrap{display:flex;flex-direction:column}.page.home .hside{display:contents}.page.home .ttl{order:1}.page.home .hcal{order:2}.page.home .tiles{order:3}.page.home .trip{order:4;background:var(--card);border-radius:14px;box-shadow:0 0 0 1px var(--rule);padding:14px 16px}.page.home .trip ol{max-height:168px;overflow:auto}.page.home .trip li{grid-template-columns:auto minmax(0,1fr) auto;align-items:baseline;padding-bottom:12px}.page.home .trip li b{font-size:15px}.page.home .trip li span{grid-column:2;grid-row:1;font-size:13px}.page.home .trip li em{grid-column:3;font-size:13px}.page.home .trip li::before{top:3px}.page.home .trip li:not(:last-child)::after{top:18px}
.page.sub .ovbox{height:100%;display:flex;flex-direction:column}.page.sub .ph{padding-right:40px}
.page.sub .pb{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain}
/* v1.2.1: the cards' outline is a 1 px shadow outside their box; the scroller widens by 1 px a side
   (padding gives it back) so its overflow no longer cuts the side lines -- nothing else moves */
.ovbox .pb{margin-inline:-1px;padding-inline:1px}
.pmap .mapc{margin:0;position:relative;background:none;box-shadow:none}.pmap .mapc[open]{padding-bottom:12px}
.pmap .mapc>summary{min-height:44px;padding:0 44px 0 12px}.pmap .mapc[open]>summary{margin-bottom:4px}
.pmap .chips{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;padding:0 12px 8px}.pmap .chips::-webkit-scrollbar{display:none}
/* v1.1 (user pick S3): the chip row says there is more -- the right edge fades while chips
   remain to the right, the left edge while some are scrolled past; crisp at either end. A
   static right fade where scroll timelines are unsupported. */
.pmap .chips{-webkit-mask-image:linear-gradient(to right,#000 calc(100% - 32px),transparent);mask-image:linear-gradient(to right,#000 calc(100% - 32px),transparent)}
@supports (animation-timeline: scroll()){.pmap .chips{animation:chipfade linear both;animation-timeline:scroll(x self);-webkit-mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent);mask-image:linear-gradient(to right,transparent,#000 var(--fl),#000 calc(100% - var(--fr)),transparent)}}
.pmap .chip{flex:none}
.pmap .mnav,.pmap .lgd,.pmap .attr{display:none}
.pmap .mframe.cover{aspect-ratio:4/3!important;container-type:inline-size}
.pmap .mframe.cover .mcanvas{inset:auto;left:50%;top:50%;transform:translate(-50%,-50%);width:max(100cqw,calc(75cqw * var(--ar)));aspect-ratio:var(--ar)}
.mv:has(.zck:checked) .mframe.cover{aspect-ratio:var(--ar)!important}
.mv:has(.zck:checked) .mframe.cover .mcanvas{inset:0;left:0;top:0;transform:none;width:100%}
}
"""
CSS += PHONE_CSS
# the chip-row fade's animated edges (registered so they interpolate; top level, as
# @property cannot sit inside @media)
CSS += ("@property --fl{syntax:'<length>';inherits:false;initial-value:0px}"
        "@property --fr{syntax:'<length>';inherits:false;initial-value:32px}"
        "@keyframes chipfade{0%{--fl:0px;--fr:32px}8%{--fl:32px}92%{--fr:32px}100%{--fl:32px;--fr:0px}}")

# The desktop (spec §6.7): the same DOM re-laid at >= 1024 px -- the DH2 big calendar
# home, the sub-screens as V2 overlays, each day a fixed-height dashboard whose list is
# the only scrolling area. Ported from gen_dash.py / gen_deskhome.py / gen_deskpanel.py.
DESKTOP_CSS = """
.ovbg,.ovx,.ring{display:none}.fb,.ft,.lcap,.lfoot{display:none}
.seg{position:relative}
@media (min-width:1024px){
body{overflow:hidden}
.bubble{left:auto;right:24px;bottom:24px}            /* user check (pick W): bottom-right */
/* home (v1.1 topic 6): the phone's month card in its own panel, zoomed x1.9 -- title 27,
   weekdays 23, days 27; the stamp 65 px with whole-px lines 3 / 2 at 3; the theme on its ring */
.page.home{max-width:1240px;height:100vh;min-height:0;padding:14px;background:none}
.hwrap{display:grid;grid-template-columns:280px minmax(0,1fr);gap:14px;height:100%}
.hside{padding-bottom:64px;display:flex;flex-direction:column;background:var(--bg);border-radius:16px;box-shadow:0 0 0 1px var(--rule);padding:16px;min-height:0;overflow:auto}
.hside .tile{flex-direction:row;gap:10px;padding:12px}.hside .tile small{margin-left:auto}
.hside .tiles{grid-template-columns:1fr}
.hside .dates .dl{display:block}.hside .dates .dsep{display:none}.hside{overflow:hidden}.hside .trip{flex:1;min-height:0;display:flex;flex-direction:column;margin:22px 0 8px}.hside .trip ol{flex:1;min-height:0;overflow:auto;--fz:56px}
/* M-1 (topic 6): a short desktop window shrinks a split day's frames to ~150 px, where the fixed-size
   corner credit covers half the map; the desktop shows the card's credit line instead (OSMF: one
   attribution per document of static images) and the zoom bar carries the link */
.pmap .attrmini{display:none}.pmap .mv:has(.zck:checked) .attrmini{display:block}
.hcal{display:block;background:var(--bg);border-radius:16px;box-shadow:0 0 0 1px var(--rule);padding:10px 14px;min-height:0}
.hcal .months,.hcal .month{height:100%}.hcal .month{display:flex;flex-direction:column}
.hcal .month h3{font:700 27px var(--f-round);color:var(--ink);text-align:center;margin:4px 0 2px}
.hcal .g{flex:1;grid-template-rows:auto;grid-auto-rows:minmax(0,1fr);align-items:center;container-type:size}
.hcal .g>*{height:auto}.hcal .g>.wd{font-size:23px;padding:4px 0}.hcal .g>span:not(.wd){font-size:27px}
/* review I3: 65 px, unless the column or the row is too small for a ring's theme to clear
   its neighbours -- a ring reaches ~1.66 stamps wide and ~0.86 of a stamp above it; the
   ring, its text and the stamp text all scale with --s (the 3 / 2 px lines stay whole) */
.hcal .stamp{--s:max(36px,min(65px,calc(100cqw / 7 * .6 - 5px),calc((100cqh - 36px) / var(--wk,5) * .74 - 8px)));width:var(--s);height:var(--s);border-width:3px;outline-width:2px;outline-offset:3px;position:relative}
.hcal .stamp b{font-size:calc(var(--s) * 25 / 65)}.hcal .stamp small{font-size:calc(var(--s) * 13 / 65)}.hcal .stamp.m1 b{font-size:calc(var(--s) * 21 / 65)}
.hcal .ring{display:block;position:absolute;left:50%;top:50%;width:calc(var(--s) * 140 / 65);height:calc(var(--s) * 140 / 65);transform:translate(-50%,-50%);pointer-events:none;overflow:visible}
.ring text{font:700 13px var(--f-round);letter-spacing:.02em;fill:var(--c)}
/* the three sub-screens = V2 overlays over the calendar */
body:has(#pg-lodging:checked,#pg-advisory:checked,#pg-checklist:checked) .page.home{display:block}
.page.sub{position:fixed;inset:0;z-index:20;max-width:none;min-height:0;padding:0;background:none}
.ovbg{display:block;position:absolute;inset:0;background:rgba(10,8,6,.72);cursor:pointer}
.ovbox{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(760px,90vw);max-height:86vh;display:flex;flex-direction:column;
  background:var(--bg);border-radius:16px;box-shadow:0 0 0 1px var(--rule),0 12px 40px rgba(0,0,0,.5);padding:14px}
.ovbox .pb{min-height:0;overflow:auto;margin-inline:-1px;padding-inline:1px}
/* the user's check, pick T1 with B1's bar: a thin scrollbar in the reader's colours, and the
   list / sub-screens fade at the edges by gradients of their own background laid over the
   content -- not a mask, which cut content hard under the title and faded the bar too.
   The top gradient hangs from the title once scrolled; the bottom one goes at the end (2 px
   early: Chromium's whole-pixel scroll position stops just short of 100%). */
.plist,.pmap .lgd,.ovbox .pb{scrollbar-width:thin;scrollbar-color:var(--rule) transparent}
/* every day's list keeps its bar's track (a day that does not scroll has no thumb to drag), so the
   list -- and the stepper at its title's end -- has the same width on every day (the user's check) */
.page.day .plist{overflow-y:scroll;scrollbar-color:var(--off) color-mix(in srgb,var(--rule) 45%,transparent)}  /* the track shows (greyed) on a day with nothing to drag */
@supports (animation-timeline: scroll()){
@keyframes edgeshow{from{opacity:0}to{opacity:1}}@keyframes edgehide{from{opacity:1}to{opacity:0}}
/* a list that does not scroll has an inactive timeline: the gradients rest invisible */
.plist>.dh-list::after,.ovbox .pb>.ft,.plist>.fb,.ovbox .pb>.fb{opacity:0}
/* both gradients of a scroller run on the one timeline it names: on two anonymous
   scroll(nearest y) timelines the first scroll after opening a day stalled for seconds on the
   user's computer (either gradient alone did not; their cross-test I, 2026-10-03) */
.plist{scroll-timeline:--lst y}.ovbox .pb{scroll-timeline:--pb y}
.plist>.dh-list::after{content:"";position:absolute;left:0;right:0;top:100%;height:32px;pointer-events:none;background:linear-gradient(var(--bg) 10%,transparent);animation:edgeshow linear both;animation-timeline:--lst;animation-range:0px 32px}
.ovbox .pb>.ft{display:block;position:sticky;top:-1px;z-index:2;height:32px;margin-bottom:-32px;pointer-events:none;background:linear-gradient(var(--bg) 10%,transparent);animation:edgeshow linear both;animation-timeline:--pb;animation-range:0px 32px}
.plist>.fb,.ovbox .pb>.fb{display:block;position:sticky;bottom:-1px;height:44px;margin-top:-44px;pointer-events:none;background:linear-gradient(transparent,var(--bg) 85%);animation:edgehide linear both;animation-timeline:--lst;animation-range:calc(100% - 46px) calc(100% - 2px)}.ovbox .pb>.fb{animation-timeline:--pb}
.plist>.fb{bottom:-61px}                       /* the list's 60 px bottom padding: meet the panel's edge */
}.ovbox .back{display:none}.ovx{display:inline-block}
/* a day = dashboard: fixed viewport, only the right column scrolls */
.page.day{max-width:none;min-height:0;padding:0;background:none}
.dash{height:100vh;max-width:1240px;margin:0 auto;display:grid;grid-template-columns:minmax(360px,440px) minmax(0,1fr);grid-template-rows:auto minmax(0,1fr);gap:14px;padding:14px}
/* review I4: the theme button sits 24-68 px from the right edge; a window under ~1360 px leaves
   no gutter for it, so the page makes one (74 px), shrinking to 14 px as the margin grows */
.page.home,.dash{padding-right:max(14px,calc(74px - max(0px,(100vw - 1240px) / 2)))}
.pcal,.pmap,.plist{display:block;background:var(--bg);border-radius:16px;box-shadow:0 0 0 1px var(--rule);padding:12px 14px}
.pcal{grid-column:1;grid-row:1}.pcal .dh{display:none}.plist>.dh-list{display:flex;position:sticky;top:-14px;z-index:3;margin:-14px -16px 10px;padding:14px 16px 10px;background:var(--bg);font-size:22px}.plist{scroll-padding-top:56px}.plist{overflow-anchor:none;grid-column:2;grid-row:1/3;min-height:0;overflow-y:auto;padding:14px 16px 60px}
.pmap{grid-column:1;grid-row:2;min-height:0;overflow-y:auto;display:flex;flex-direction:column;--mvd:flex}
.dash:not(:has(.mapc)) .pmap{display:none}
.pmap .mapc{flex:1;min-height:0;display:flex;flex-direction:column;margin:0;background:none;box-shadow:none}
/* forced open where the browser can style the details body; elsewhere it stays a working toggle */
@supports selector(::details-content){
.pmap .mapc::details-content{content-visibility:visible;display:contents}
.pmap .mapc>summary{pointer-events:none;padding:0 0 8px}.pmap .mapc>summary .cv{display:none}
}
.pmap .chips{padding:0 0 8px}.pmap .views{flex:1;min-height:160px;display:flex;flex-direction:column;padding:0}
.pmap .mv{flex:1;min-height:0;flex-direction:column;gap:8px}
.pmap .seg{flex:1;min-height:0;container-type:size;display:flex;align-items:center;justify-content:center}.pmap .seg+.seg{margin:0}
.pmap .mframe{width:min(100cqw,calc(100cqh * var(--ar)))}
.mv:has(.zck:checked) .seg{flex:none;container-type:normal}.mv:has(.zck:checked) .seg+.seg{margin-top:8px}
.pmap .lgd{max-height:5.4em;overflow:auto;padding:6px 0 0;grid-auto-flow:column;grid-template-rows:repeat(4,auto);gap:1px 12px;font-size:12px}.pmap .attr{padding:2px 0 0}
.altrow{scroll-margin-block:16px}.stop,.anchor{scroll-margin-top:calc(50vh - 160px)}
.bpi{height:260px}
}
/* the left gutter is narrower than the theme bubble until ~1360 px */
@media (min-width:1024px) and (max-width:1359px){.pmap{padding-bottom:60px}}
"""
CSS += DESKTOP_CSS
