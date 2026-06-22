# tripwork agentic-robustness audit — 缺失紀錄

- 日期:2026-06-11
- 對象版本:v0.11.2(main @ 3076135)
- 產出方式:multi-agent workflow 審查(8 個維度 finder + critic 補 3 個角度 → 跨維度 dedup → 每條 finding 經 2-lens adversarial verify:證據逐字覆核 + 實際影響評估)。
- 統計:raw 86 → dedup 51 + gap round 19 → **confirmed 61**(critical 5 / high 33 / medium 22 / low 1),5 條經覆核駁回(見附錄 B)。
- 審查焦點:**agent+LLM 在執行此 plugin 時仍可能產出非預期或錯誤內容的所有路徑**——指令模糊、規則未機械化、schema 過鬆、script 脆弱、gate 可繞過、幻覺面、artifact 互相矛盾。

每條 defect 含:位置(path:line,行號可能漂移,修復前先逐字核對引文)、問題、證據、建議修法、驗收條件。
驗收條件刻意寫成可被 pytest 或機械檢查驗證的形式,配合 8-step pre-ship gate 的 TDD red→green 流程。

## 缺失總表

| ID | Severity | 子系統 | 標題 | 位置 |
|----|----------|--------|------|------|
| TW-001 | CRITICAL | schemas | closed_days accepts any string while poi_closed_on does exact lowercase-English matching — 'Tuesday' / '火曜日' / 'Tuesdays' silently parse as 'open every day' | `schemas/verified-pois.schema.json:36` |
| TW-002 | CRITICAL | scripts | itinerary-gate never checks verify_status — a conflicting/unverified POI with a geocode passes the only mechanical gate before export | `scripts/gate.py:23` |
| TW-003 | CRITICAL | scripts | LINE deliverable is rendered from an ungated, LLM-reconstructed itinerary dict — can silently diverge from the gated markdown | `scripts/render/line_short.py:5` |
| TW-004 | CRITICAL | skills | itinerary-synthesis 的 frontmatter 觸發條件停留在舊版 4-stage 前置，提前開排後 pipeline 永不回頭重排 | `skills/itinerary-synthesis/SKILL.md:3` |
| TW-005 | CRITICAL | skills | No permanently/temporarily-closed check: a defunct POI passes all three verification gates as `verified` | `skills/source-verify/SKILL.md:8` |
| TW-006 | HIGH | schemas | advisory schema does not require `risk` and allows a single source — a forgotten tag silently defeats the banned-item acknowledgement stop | `schemas/advisory.schema.json:8` |
| TW-007 | HIGH | schemas | calendar.date (and trip-brief/seasonal date fields) have no ISO pattern while matching is exact string equality — non-ISO dates silently disable holiday crowd/closure logic | `schemas/calendar.schema.json:12` |
| TW-008 | HIGH | schemas | `official: true` is self-attested and source URLs are never validated as URLs | `schemas/calendar.schema.json:27` |
| TW-009 | HIGH | schemas | gate-report schema allows status:pass with non-empty failures and empty checks — a hand-written 'pass' validates | `schemas/gate-report.schema.json:4` |
| TW-010 | HIGH | schemas | legs.mode is a free string and duration_mins is optional — a mislabelled ('self_drive') or unmeasured drive leg silently classifies 'ok', bypassing drive_too_long | `schemas/legs.schema.json:8` |
| TW-011 | HIGH | schemas | trip-brief schema has no destination/local_lang/airline fields, yet four stages and the verify gate consume them | `schemas/trip-brief.schema.json:4` |
| TW-012 | HIGH | schemas | verified-pois schema requires geocode + >=2 sources on EVERY POI, making the never-silently-drop / D7 rule impossible — forces silent drop or fabricated geocode | `schemas/verified-pois.schema.json:10` |
| TW-013 | HIGH | schemas | No schema sets additionalProperties:false — a typo'd key (e.g. close_days) validates and the data silently vanishes | `schemas/verified-pois.schema.json:9` |
| TW-014 | HIGH | scripts | sum_costs silently treats a missing amount as 0 (understating the total past the budget gate) and crashes with a bare TypeError on amount: null | `scripts/cost.py:15` |
| TW-015 | HIGH | scripts | export-gate passes on an empty or truncated deliverable — all checks are absence-of-bad-pattern checks | `scripts/export_gate.py:27` |
| TW-016 | HIGH | scripts | No stage ever sets sources[].official, yet export-gate hard-fails bookable POIs on it with a futile re-render-loop repair route; renderer labels non-official fallback links as 官網 | `scripts/export_gate.py:42` |
| TW-017 | HIGH | scripts | itinerary-gate validates an LLM-reconstructed days structure, not itinerary.md — no parser or format convention exists, so the gate can pass vacuously | `scripts/gate.py:19` |
| TW-018 | HIGH | scripts | Closed-day scheduling rule is LLM discipline only — itinerary-gate never re-checks poi_closed_on despite having the data | `scripts/gate.py:30` |
| TW-019 | HIGH | scripts | Cache entries are trusted blindly with no provenance — a fabricated geocode.json entry silently passes Gate 2 forever | `scripts/geocode.py:71-77` |
| TW-020 | HIGH | scripts | All HH:MM time fields are unconstrained strings and to_minutes crashes uninformatively — including the YAML sexagesimal trap where unquoted `close: 21:30` parses as int 1290 | `scripts/hours.py:13` |
| TW-021 | HIGH | scripts | misses_last_service breaks across midnight: an after-midnight last service is falsely flagged missed, and a post-midnight planned departure silently passes against an evening last service | `scripts/legs.py:17` |
| TW-022 | HIGH | scripts | Link labels and source URLs are never escaped — web-scraped POI names containing \|, ], or $ silently corrupt the deliverable or wedge the export-gate repair loop | `scripts/render/markdown.py:5` |
| TW-023 | HIGH | scripts | Source URLs are never fetched or deduplicated and the local-language check is opt-in — fabricated or duplicate sources satisfy the Source-Verified-First iron rule | `scripts/verify.py:32` |
| TW-024 | HIGH | skills | No defined behaviour when WebSearch is unavailable or returns nothing — silent fallback to training data | `skills/destination-research/SKILL.md:12` |
| TW-025 | HIGH | skills | Notion write-back happens BEFORE export-gate runs, with no update-vs-recreate rule and no post-write verification — gate-failing content ships to Notion and diverges permanently | `skills/export-artifact/SKILL.md:15` |
| TW-026 | HIGH | skills | missed_last_service check is ill-posed: `depart` is unknowable at the legs stage, yet synthesis is forbidden from re-judging legs | `skills/inter-stop-legs/SKILL.md:26` |
| TW-027 | HIGH | skills | No slug derivation or multi-trip disambiguation rule — second trip in the same workspace resumes or contaminates the first | `skills/orchestrator/SKILL.md:31` |
| TW-028 | HIGH | skills | travel-advisory runs AFTER itinerary-synthesis, so restricted/banned regulation items can never reach the checklist or exported deliverable | `skills/orchestrator/SKILL.md:41` |
| TW-029 | HIGH | skills | Orchestrator has no fail-routing for itinerary-gate, no 'no gate-report' guard on rule 13, no termination rule, and undefined export-gate re-run semantics — existence-based rules loop instead of repairing | `skills/orchestrator/SKILL.md:43` |
| TW-030 | HIGH | skills | Stop condition 'booking lead-time missed' is unowned — no stage, script, or schema field can ever make it fire | `skills/orchestrator/SKILL.md:51` |
| TW-031 | HIGH | skills | Orchestrator halt list out of sync with stage-emitted flags: reception-after-close missing; 'regulation risk' contradicts travel-advisory's banned-only halt | `skills/orchestrator/SKILL.md:51` |
| TW-032 | HIGH | skills | source-verify never defines 'independent sources' nor a conflict threshold for rating/hours/address disagreement | `skills/source-verify/SKILL.md:16` |
| TW-033 | HIGH | skills | Opening hours / closed_days have no recency or as-of requirement — stale hours drive minute-level scheduling | `skills/source-verify/SKILL.md:22` |
| TW-034 | HIGH | skills | advisory.yaml is consumed by no script or gate — banned-regulation stop and deliverable surfacing are prose-only | `skills/travel-advisory/SKILL.md:20` |
| TW-035 | HIGH | skills | travel-advisory standalone 模式直接寫 trips/<slug>/advisory.yaml，永久吃掉 pipeline 的 iron-rule gate stage | `skills/travel-advisory/SKILL.md:20` |
| TW-036 | HIGH | skills | README 起手式同時命中 using-tripwork / orchestrator / trip-brief 三個 description；trip-brief 直接發動會繞過 workspace-shape-preflight 的 stop-on-confirmation | `skills/trip-brief/SKILL.md:3` |
| TW-037 | HIGH | skills | Entry skill using-tripwork describes an obsolete 9-stage pipeline — 6 stages missing from the tree and Quick Reference, stop-condition list has 5 of 10 conditions, contradicting the orchestrator | `skills/using-tripwork/SKILL.md:18` |
| TW-038 | HIGH | tests | must_do coverage is unenforced — the only checker lives in test code and no schema field links trip-brief.must_do to POI ids | `tests/test_e2e_must_do.py:17` |
| TW-039 | MEDIUM | other | No lifecycle rule ever expires the cache on re-brief or destination change — the most durable cross-trip contamination vector under an underived slug | `docs/superpowers/specs/2026-06-06-v0.10.0-geocode-cache-design.md:29` |
| TW-040 | MEDIUM | schemas | calendar holiday `impact` is optional despite the skill calling its omission a mistake — holidays without it are treated as calm days | `schemas/calendar.schema.json:10` |
| TW-041 | MEDIUM | schemas | Money fields lack discipline: cost.yaml `as_of` not required, leg `fare` currency optional, FX rate has no source/date | `schemas/cost.schema.json:4` |
| TW-042 | MEDIUM | schemas | transit.yaml walks and peak_windows require no sources — invented station walks are schema-valid | `schemas/transit.schema.json:18` |
| TW-043 | MEDIUM | schemas | lat/lng accept any number — swapped or placeholder coordinates validate in all three geocode-bearing schemas | `schemas/verified-pois.schema.json:22` |
| TW-044 | MEDIUM | scripts | export_gate's _find_row checks the FIRST line containing a POI name — a heading or prose mention shadows the actual table row, causing false fails (un-fixable re-render loop) or masked misses | `scripts/export_gate.py:67` |
| TW-045 | MEDIUM | scripts | resolve_place with an empty/None name silently geocodes the city itself — a 'successful' city-centroid result that trivially passes the in_region gate | `scripts/geocode.py:45` |
| TW-046 | MEDIUM | cache | load_cache has no error handling and save_cache is non-atomic — an interrupted run corrupts the file and crashes every later run uninformatively | `scripts/geocode_cache.py:29-34` |
| TW-047 | MEDIUM | scripts | closing_status returns plain 'closed' for venues closing after midnight, with no machine-readable signal that the overnight special case applies | `scripts/hours.py:44` |
| TW-048 | MEDIUM | scripts | Deliverable maps links discard the verified coordinates — name-only Google search can land on the wrong branch/city | `scripts/render/gmaps_links.py:9` |
| TW-049 | MEDIUM | scripts | line_short has no handling for LINE's 5000-character message cap — long trips render an unsendable deliverable | `scripts/render/line_short.py:19` |
| TW-050 | MEDIUM | scripts | season.py ignores timezone offset, DST, and longitude-within-zone — real error is ~2 hours in the plugin's flagship NZ self-drive case, not the documented ±15-20 min | `scripts/season.py:5` |
| TW-051 | MEDIUM | skills | Hotel centroid fallback grants `verified` to a hotel Nominatim cannot find, removing the only existence cross-check | `skills/accommodation-research/SKILL.md:26` |
| TW-052 | MEDIUM | skills | calendar-check never requires the official source to cover the trip year — prior-year substitute holidays can be extrapolated | `skills/calendar-check/SKILL.md:15` |
| TW-053 | MEDIUM | skills | Orchestrator rule 3 predicate 'stale' (and 'ready') is undefined — re-runs of destination-research leave new candidates permanently unverified | `skills/orchestrator/SKILL.md:33` |
| TW-054 | MEDIUM | skills | orchestrator Stage Selection 用裸 skill 名（與 paperwork 的 export-artifact / workspace-shape-preflight / orchestrator 撞名），跨 plugin 誤路由面 | `skills/orchestrator/SKILL.md:44` |
| TW-055 | MEDIUM | skills | stage-state.yaml is the designated decision record but has no schema, no format, no example, and no rule ever reads it back | `skills/orchestrator/SKILL.md:51` |
| TW-056 | MEDIUM | skills | The far-hop stop-on-confirmation is driven by an LLM-guessed minutes number with no mechanical floor | `skills/routing-audit/SKILL.md:13` |
| TW-057 | MEDIUM | skills | Negative cache is permanent with no invalidation path — D7 'recorded for manual confirmation' can never recover on re-run | `skills/source-verify/SKILL.md:15` |
| TW-058 | MEDIUM | skills | Gate 3 region check needs a district reference point that no instruction tells the agent how to obtain | `skills/source-verify/SKILL.md:16` |
| TW-059 | MEDIUM | tests | No cross-stage adversarial e2e fixture: each 'e2e' test exercises one stage in isolation with hand-built dicts, so verify→gate→export interactions are never closed | `tests/test_e2e_pipeline.py:31` |
| TW-060 | MEDIUM | tests | test_readme_freshness 實際斷言遠少於 CLAUDE.md 宣稱的守備範圍——mermaid 順序/成員完全無守門 | `tests/test_readme_freshness.py:35` |
| TW-061 | LOW | skills | calendar-check claims 'same rigor as travel-advisory' but requires only one official source where travel-advisory requires official + corroborating | `skills/calendar-check/SKILL.md:20` |

## CRITICAL

### TW-001 — closed_days accepts any string while poi_closed_on does exact lowercase-English matching — 'Tuesday' / '火曜日' / 'Tuesdays' silently parse as 'open every day'

- **Severity**: critical
- **位置**: `schemas/verified-pois.schema.json:36`
- **分類**: loose schema + silent script degradation
- **獨立 reviewer 重複發現次數**: 4

**問題(failure mode)**

source-verify reads a Japanese/Korean official site and records the closure as written ('火曜日') or in natural English ('Tuesday', 'Tuesdays', 'Tue', 'public holidays') — all schema-valid. poi_closed_on silently reports the POI open every day, itinerary-synthesis's hard-avoid rule never fires, no gate re-checks closures, and the user is scheduled into a palace on its weekly closure day. The error is invisible: validation passed, the gate passed, nothing warned — the exact defect the closure axis exists to prevent.

**證據**

```text
Schema: "closed_days": {"type": "array", "items": {"type": "string"}} — no enum or pattern, only a prose description ("Weekday names ('tuesday')..."). scripts/calendar.py:52-58 does exact membership tests: `if wd in closed_days: ... if iso_date in closed_days: ... if "public_holiday" in closed_days:` where wd is always lowercase from WEEKDAYS (line 11). Empirically: poi_closed_on({"closed_days": ["Tuesday"]}, "2026-05-26") -> (False, '') and ["mondays"] on a Monday -> (False, ''). No normalization or unknown-token rejection exists anywhere (grepped scripts/ and tests/); tests/test_schemas.py:136-143 and tests/test_calendar.py only ever use lowercase 'tuesday'. [corrected: Minor line drift only: the three exact membership tests in scripts/calendar.py are at lines 55/57/59 (not 52-58); line 52 is `closed_days = poi.get("closed_days", []) or []` and the function spans lines 40-64. WEEKDAYS lowercase list is at lines 11-12. Schema citation schemas/verified-pois.schema.json:36-40 is exact: "closed_days": {"type": "array", "items": {"type": "string"}, "description": "Weekday names ('tuesday'), ISO dates ('2026-05-25'), or the token 'public_holiday'. Consumed by scripts/calendar.py::poi_closed_on."]
```

**建議修法**

Tighten schemas/verified-pois.schema.json closed_days items to anyOf: [enum of the 7 lowercase weekday names, pattern ^\\d{4}-\\d{2}-\\d{2}$, const "public_holiday"]. In scripts/calendar.py::poi_closed_on, normalize entries (strip().lower()) and raise ValueError (or return a third 'unrecognized token' signal) naming the POI id and offending token when an entry matches none of the three forms. Add red tests for 'Tuesday', '火曜日', '2026/05/25'.

**驗收條件**

pytest must assert that poi_closed_on({"id": "palace", "closed_days": ["Tuesday"]}, "2026-05-26") does NOT return (False, ""): it either returns closed=True (case/whitespace-normalized match) or raises ValueError whose message contains both the POI id and the offending token; and jsonschema.validate of a verified-pois document containing closed_days: ["火曜日"] (and ["2026/05/25"]) against schemas/verified-pois.schema.json must raise ValidationError.

### TW-002 — itinerary-gate never checks verify_status — a conflicting/unverified POI with a geocode passes the only mechanical gate before export

- **Severity**: critical
- **位置**: `scripts/gate.py:23`
- **分類**: gate-bypass / iron-rule unenforced
- **獨立 reviewer 重複發現次數**: 5

**問題(failure mode)**

itinerary-synthesis is LLM-executed; the exact slip the gate exists to catch is pulling a non-verified POI (itinerary-synthesis SKILL.md:12 calls it "a gate violation"). When synthesis schedules a conflicting restaurant (disputed hours/address) or an unverified sight, run_gate reports status: pass, export renders a confident maps link and 官網 link, and the user silently receives an itinerary sending them to a place verification explicitly flagged — the Source-Verified-First iron rule bypassed with a green gate report and zero mechanical backstop.

**證據**

```text
gate.py:23-28 is the entire referenced-POI check: `if p is None: failures.append(f"day references unknown POI '{pid}'") elif "geocode" not in p: failures.append(...)` — verify_status is never read. verified-pois.yaml deliberately contains ALL statuses (source-verify SKILL.md:26), and a conflicting POI always HAS a geocode by construction (verify.py Gate 3 fires only after geocode resolves). Empirically confirmed: run_gate([{'id':'bad','verify_status':'conflicting','geocode':{...}}], [{'meals':['bad']}]) returns 'pass'; also `geocode: None` passes the key-presence test. export_gate.py:38 skips non-verified POIs (`continue`) so no downstream check catches it. tests/test_gate.py:31-37 only covers an UNreferenced rejected POI. The planted e2e bug (한방삼계탕: claimed 잠실, geocoded to 강남, status conflicting WITH valid coordinates) is exactly this shape.
```

**建議修法**

In scripts/gate.py::run_gate add a per-referenced-POI check: p.get("verify_status") != "verified" → failure "day references non-verified POI '<pid>' (<status>)" with a referenced_pois_verified entry in checks; also change the geocode test to `p.get("geocode") is None`. Update skills/itinerary-gate/SKILL.md check list and add red/green tests in tests/test_gate.py (referenced conflicting POI with geocode must fail; geocode: null must fail).

**驗收條件**

pytest in tests/test_gate.py: run_gate(pois=[{"id": "x", "verify_status": "conflicting", "geocode": {"lat": 37.5, "lon": 127.0}}], days=[{"date": "2026-06-12", "meals": ["x"]}]) returns status == "fail", failures contains a message naming POI 'x' and its verify_status, and checks includes {"name": "referenced_pois_verified", "passed": False}; the same call with verify_status == "verified" returns that check passed == True.

### TW-003 — LINE deliverable is rendered from an ungated, LLM-reconstructed itinerary dict — can silently diverge from the gated markdown

- **Severity**: critical
- **位置**: `scripts/render/line_short.py:5`
- **分類**: hallucination surface / gated-vs-ungated divergence

**問題(failure mode)**

At export time the agent must hand-transcribe the whole itinerary (day labels, times, POI/restaurant names) into a fresh Python dict from its context window. Across a 5-day itinerary, normal LLM transcription drift (a 18:30 dinner becomes 19:00, a renamed restaurant, a dropped Day 3 afternoon, or a POI that source-verify rejected resurfacing from earlier context) lands in `exports/line-short.txt` with NOTHING checking it: export-gate reads only the markdown file, and no test or script compares line-short content to the gated deliverable. The elder-facing LINE message — the artifact the least-able-to-cross-check user actually follows — silently states wrong times/places while the gated markdown is correct.

**證據**

```text
line_short.py:5 `def render_line_short(itin):` — grep confirms no script anywhere builds `itin` (only tests construct it by hand). skills/export-artifact/SKILL.md:14 says only: "**line-short** — `scripts/render/line_short.py::render_line_short` -> `exports/line-short.txt`. Plain text, emoji-delimited, elder-friendly, no URLs." — no instruction on where days/items/times come from. skills/orchestrator/SKILL.md:45 gates only the markdown: "export deliverable exists, no export-gate-report.yaml -> run `export-gate`", and scripts/export_gate.py:18 takes only `md_text` of `exports/<slug>-itinerary.md`. tests/test_render_line.py asserts only happy-path substrings. [corrected: One minor imprecision, location unchanged: scripts/export_gate.py:18 is `def run_export_gate(md_text, pois):` — it takes md_text AND a verified-pois list, not "only md_text". The substantive claim stands: per its docstring, md_text is "full text of exports/<slug>-itinerary.md" and the gate never reads exports/line-short.txt. Also note the finding's orchestrator quote is rule 15 at skills/orchestrator/SKILL.md:45: "15. export deliverable exists, no export-gate-report.yaml -> run `export-gate`." — confirmed at that exact line.]
```

**建議修法**

Add `scripts/render/line_from_md.py` (or a function in line_short.py) that mechanically derives the `itin` dict by parsing the gated `exports/<slug>-itinerary.md` day tables (the table format is renderer-owned and stable), and amend skills/export-artifact/SKILL.md adapter 3 to mandate building `itin` via that parser from the gated file — never hand-authored. Add a round-trip test: render_day_table → parse → render_line_short asserts every day label and time appears.

**驗收條件**

A round-trip pytest passes: render a fixture itinerary via render_day_table into exports/<slug>-itinerary.md, mechanically derive itin from that markdown via the new parser (e.g. scripts/render/line_from_md.py::itin_from_md), feed it to render_line_short, and assert the resulting line-short text contains verbatim every day label and every row's time and POI display name present in the markdown day tables, and contains no POI name absent from that markdown.

### TW-004 — itinerary-synthesis 的 frontmatter 觸發條件停留在舊版 4-stage 前置，提前開排後 pipeline 永不回頭重排

- **Severity**: critical
- **位置**: `skills/itinerary-synthesis/SKILL.md:3`
- **分類**: skill-activation / stale trigger description

**問題(failure mode)**

routing-audit 剛跑完、使用者中途說「好了直接幫我排行程吧」：模型按 description 比對，itinerary-synthesis 的觸發條件（verified-pois + routing ready）字面上已滿足，直接發動並寫出 itinerary.md——沒有住宿列、沒跑 calendar 閉館檢查、沒有費用區塊。回到 orchestrator 後 step 5-10 補跑 accommodation→cost，但 step 11 看到 itinerary.md 已存在就跳過 synthesis，step 13 的 itinerary-gate（scripts/gate.py 只查 POI 對應/每日一餐/accommodations.yaml 內容）照樣 pass，export 把這份早產行程輸出給使用者：可能把 must_do 排在公休日、整份沒有宿與費用——正是 critical 定義的「使用者默默拿到錯誤行程」。

**證據**

```text
description: Use when verified-pois.yaml + routing.yaml are ready and a day-by-day itinerary must be produced. Produces itinerary.md. — 但 orchestrator SKILL.md:41 的實際前置是「11. cost ready, no itinerary.md -> run `itinerary-synthesis`.」，且本 skill 自己的 Stage Contract（SKILL.md:98）列了 8 個輸入檔（accommodations.yaml、legs.yaml、calendar.yaml、seasonal.yaml、transit.yaml、cost.yaml…）。SKILL.md 內文（:50、:60、:70）只寫「already resolved … before synthesis runs; do not re-judge」，完全沒有「輸入檔缺少時 halt 並回 orchestrator」的守門指令。
```

**建議修法**

兩處修：(1) skills/itinerary-synthesis/SKILL.md 的 description 改成與 orchestrator 一致的前置（例如 'Use when the orchestrator has confirmed accommodations/legs/calendar/seasonal/transit/cost are all ready and cost.yaml exists…'）；(2) 在 SKILL.md Rules 區加硬性守門第一條：「Stage Contract Input 列出的任一檔案缺少 → 不得寫 itinerary.md，回 tripwork:orchestrator」。並在 tests/test_skills_structure.py 加一條 test 斷言 itinerary-synthesis description 含 cost（防再度漂移）。

**驗收條件**

tests/test_skills_structure.py 新增一條 pytest：解析 skills/itinerary-synthesis/SKILL.md，斷言 (a) frontmatter description 字串包含 "cost.yaml"（與 orchestrator step 11 的實際前置一致），且 (b) 內文含有明確守門句，同時提及 Stage Contract 全部 8 個輸入檔缺一即「不得寫 itinerary.md」並「return to tripwork:orchestrator」（mechanical check：body 中存在同段同時 match /missing/ 與 /tripwork:orchestrator/ 且鄰近 /itinerary\.md/ 的 rule 行）——對目前的 SKILL.md 此 test 必須 RED，修復後 GREEN。

### TW-005 — No permanently/temporarily-closed check: a defunct POI passes all three verification gates as `verified`

- **Severity**: critical
- **位置**: `skills/source-verify/SKILL.md:8`
- **分類**: missing verification criterion / hallucination surface

**問題(failure mode)**

A restaurant that closed permanently in 2024 still has >=2 old blog/tabelog sources, still geocodes via Nominatim (which keeps closed places), and is in-region — so the agent (whose training data also remembers it as open) classifies it verified, itinerary-synthesis schedules it, the gates pass (gate.py checks only geocode/meals/lodging), and the user shows up at a shuttered storefront for a planned dinner.

**證據**

```text
"Only candidates that pass all three gates get verify_status: verified" — and the three gates (lines 14-16) are only: multi-source (>=2 sources, 1 local-lang), geocode resolves, region match + cross-source conflict. `grep -rn -i "permanent|temporarily closed|still open"` over skills/ returns no operating-status check anywhere; verified-pois.schema.json has no operating-status field.
```

**建議修法**

In skills/source-verify/SKILL.md add an explicit operating-status criterion to the gate list (at least one source must affirmatively confirm the place is currently operating, dated within N months / official page live; aggregator 'closed' flags must be checked), add an operating_status (open|closed_permanent|closed_temporary|unknown) + status_as_of field to schemas/verified-pois.schema.json, and extend scripts/verify.py::classify_candidate with an operating=False -> rejected + note branch with tests.

**驗收條件**

A pytest in tests/test_verify.py asserts that scripts/verify.py::classify_candidate, when called with a candidate that passes all existing gates (>=2 sources including local-language, geocoded=True, in_claimed_region=True, conflict_detected=False) but whose operating status indicates closure (e.g. operating_status='closed_permanent'), returns a verify_status != 'verified' (expected: 'rejected' with a note containing 'closed'), while the same candidate with operating_status='open' still returns 'verified'.

## HIGH

### TW-006 — advisory schema does not require `risk` and allows a single source — a forgotten tag silently defeats the banned-item acknowledgement stop

- **Severity**: high
- **位置**: `schemas/advisory.schema.json:8`
- **分類**: schema strictness / unenforced iron rule
- **獨立 reviewer 重複發現次數**: 3

**問題(failure mode)**

The agent researches a battery rule (the plugin's flagship example), records topic/rule/effective_date/sources but forgets the risk tag. advisory.yaml validates cleanly. Because surfacing-prominently and the acknowledgement stop are keyed on risk=='banned'/'restricted', the banned item is rendered as an ordinary table row, no stop fires, and the traveller flies with a power bank the airline confiscates — the exact harm travel-advisory exists to prevent. Separately, a regulation backed by a single uncorroborated page satisfies the schema despite the skill's stricter two-source rule.

**證據**

```text
"required": ["topic", "rule", "effective_date", "sources"] — risk has an enum ("info"|"restricted"|"banned", line 13) but is optional; and sources has "minItems": 1 (line 17) while skills/travel-advisory/SKILL.md:13 demands ">= 1 **official** source (airline notice, government entry portal) plus a corroborating source" (i.e. 2). skills/travel-advisory/SKILL.md:16 mandates 'Tag risk: info | restricted | banned' and SKILL.md:20 'Stop and require user acknowledgement for banned items'; the orchestrator stop list keys on 'regulation risk' (orchestrator SKILL.md:51). tests/test_schemas.py has zero risk assertions; grep over scripts/ shows no code reads advisory risk.
```

**建議修法**

Add "risk" to the items required list in schemas/advisory.schema.json and raise sources minItems to 2 (keeping the contains official:true constraint); add red-phase tests in tests/test_schemas.py for a risk-less item and a single-source item.

**驗收條件**

jsonschema.validate against schemas/advisory.schema.json raises ValidationError for (a) an advisory item containing topic/rule/effective_date/sources but no risk, and (b) an item whose sources array has only one entry, while an item with risk set, two sources, and at least one official:true source still validates — enforced by new tests in tests/test_schemas.py (e.g. test_advisory_requires_risk, test_advisory_requires_two_sources) that fail against the current schema and pass after the fix, with the full pytest sweep green.

### TW-007 — calendar.date (and trip-brief/seasonal date fields) have no ISO pattern while matching is exact string equality — non-ISO dates silently disable holiday crowd/closure logic

- **Severity**: high
- **位置**: `schemas/calendar.schema.json:12`
- **分類**: schema strictness / silent no-op
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

calendar-check writes a holiday as '2026/05/25', '25-05-2026', or 'May 25, 2026' — schema-valid. holiday_on() never matches synthesis's ISO day strings, so is_high_crowd() misses the holiday and poi_closed_on()'s public_holiday token never resolves. A shop that closes on public holidays gets scheduled on the substitute holiday (e.g. Children's Day) with no crowd warning and zero error anywhere; the user finds it shut.

**證據**

```text
"date": {"type": "string"} with no pattern (grep shows zero pattern/format keywords in any schema). scripts/calendar.py:22-24 matches by exact string equality: `if h.get("date") == iso_date: return h`, and weekday_of (calendar.py:17) requires datetime.date.fromisoformat. Same gap in trip-brief dates.start/end (schemas/trip-brief.schema.json:9) and seasonal daylight.date (schemas/seasonal.schema.json:28).
```

**建議修法**

Add "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$" to calendar.schema.json holidays[].date, trip-brief.schema.json dates.start/end, and seasonal.schema.json daylight[].date; add rejection tests for '2026/05/25' in tests/test_schemas.py.

**驗收條件**

tests/test_schemas.py 新增測試：對 schemas/calendar.schema.json（holidays[].date）、schemas/trip-brief.schema.json（dates.start、dates.end）、schemas/seasonal.schema.json（daylight[].date）各做兩組 jsonschema.validate 斷言 —— 非 ISO 值（"2026/05/25"、"25-05-2026"、零填充缺失的 "2026-5-3"）必須 raise ValidationError，而 "2026-05-25" 必須通過；pytest 全綠。

### TW-008 — `official: true` is self-attested and source URLs are never validated as URLs

- **Severity**: high
- **位置**: `schemas/calendar.schema.json:27`
- **分類**: loose schema / unenforced rule

**問題(failure mode)**

The agent tags an SEO aggregator's holiday list (or a placeholder string like 'government portal') as official: true; the schema's official-source guarantee — the load-bearing rigor claim of calendar-check and travel-advisory — passes mechanically, and a wrong substitute-holiday date or stale customs rule ships as 'officially sourced'.

**證據**

```text
"contains": {"type": "object", "required": ["official"], "properties": {"official": {"const": true}}} — the only 'official source' enforcement in calendar/advisory/legs/seasonal schemas is a boolean the agent itself sets, and "url": {"type": "string"} has no format/pattern anywhere (tests/test_schemas.py's own passing fixture uses {"url": "airline", "official": True} — not even a URL).
```

**建議修法**

Add "pattern": "^https?://" to every source url in schemas/*.json; in skills/calendar-check/SKILL.md and skills/travel-advisory/SKILL.md define 'official' operationally (government TLD / named operator domain, record publisher), and require quoting the publisher domain in the artifact so a reviewer or future mechanical gate can audit the claim.

**驗收條件**

Every schema under schemas/ that defines a source `url` field enforces "pattern": "^https?://", verified by a pytest parametrized over all such schemas asserting that jsonschema validation REJECTS an otherwise-valid artifact whose source is {"url": "airline", "official": true} (the exact fixture that currently passes in tests/test_schemas.py) and ACCEPTS the same artifact with "url": "https://example.go.jp/holidays".

### TW-009 — gate-report schema allows status:pass with non-empty failures and empty checks — a hand-written 'pass' validates

- **Severity**: high
- **位置**: `schemas/gate-report.schema.json:4`
- **分類**: schema strictness / forged gate report

**問題(failure mode)**

An agent that eyeballs the itinerary instead of running scripts/gate.py::run_gate (the SKILL.md says 'logic in scripts/gate.py' but contains no command to run) writes gate-report.yaml by hand: status: pass, checks: [], failures: [] — or even status: pass with failures still listed. It is schema-valid, the orchestrator advances to export, and a structurally broken itinerary (missing geocode, mealless day, unfilled lodging) ships to the user.

**證據**

```text
"required": ["status", "checks", "failures"] with "status": {"enum": ["pass", "fail"]} — nothing ties status to failures emptiness, requires checks to be non-empty, or requires the canonical check names. The orchestrator routes solely on this field: skills/orchestrator/SKILL.md:44 '14. gate-report status==pass ... -> run export-artifact'. Same schema is reused by export-gate-report (skills/export-gate/SKILL.md:25).
```

**建議修法**

In schemas/gate-report.schema.json add draft-07 conditionals: if status==pass then failures has maxItems:0; if status==fail then failures has minItems:1; add minItems:1 on checks. Additionally have skills/itinerary-gate/SKILL.md and skills/export-gate/SKILL.md instruct an explicit `python -c` invocation of run_gate/run_export_gate so the report is script-produced, not transcribed.

**驗收條件**

新增 pytest（如 tests/test_schemas.py）：以 jsonschema 對 schemas/gate-report.schema.json 驗證時，(a) {"status":"pass","checks":[],"failures":[]}、(b) {"status":"pass","checks":[{"name":"days_have_meals","passed":true}],"failures":["day 2026-01-01 has no meal"]}、(c) {"status":"fail","checks":[...],"failures":[]} 三份報告全部 raise ValidationError；同時 scripts.gate.run_gate 與 scripts.export_gate.run_export_gate 在一組 passing fixture 與一組 failing fixture 上的回傳 dict 仍驗證通過。

### TW-010 — legs.mode is a free string and duration_mins is optional — a mislabelled ('self_drive') or unmeasured drive leg silently classifies 'ok', bypassing drive_too_long

- **Severity**: high
- **位置**: `schemas/legs.schema.json:8`
- **分類**: loose schema / silent default / stop-condition bypass
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

inter-stop-legs researches a 7-hour Tekapo→Te Anau drive but writes mode as self_drive/'car'/'driving' (schema-valid) or forgets/typos duration_mins (default 0): classify_leg returns 'ok', drive_too_long is never flagged, the stage's stop-on-confirmation (its whole point, SKILL.md:40-43) silently never fires, and the user receives an itinerary presenting an infeasible single-day drive as feasible.

**證據**

```text
"required": ["from", "to", "mode", "status", "sources"] — duration_mins/depart/last_service all optional; "mode": {"type": "string"} with no enum. scripts/legs.py:33-38 branches `if leg.get("mode") == "drive": dur = leg.get("duration_mins", 0)` — any other mode string falls into the transit branch where missing depart/last_service returns ('ok', '') (legs.py:40-44). Empirically: classify_leg({"mode": "drive"}) -> ('ok', '') and classify_leg({"mode": "drive", "duration_min": 420}) (typo) -> ('ok', ''). Trip-brief's transport vocabulary is `self_drive` (skills/trip-brief/SKILL.md:31), the natural token to copy into leg.mode. No test covers the missing-field case (tests/test_legs.py:22-25 always supplies duration_mins).
```

**建議修法**

In schemas/legs.schema.json add "mode": {"enum": ["drive", "rail", "bus", "flight", "ferry"]} and a draft-07 if/then making duration_mins required when mode==drive. In scripts/legs.py::classify_leg, raise ValueError (or return a distinct 'unknown_duration' status) when mode=='drive' and duration_mins is absent/None/zero instead of defaulting to 0. Add tests for both.

**驗收條件**

A pytest in tests/test_legs.py passes asserting both: (1) jsonschema.validate against schemas/legs.schema.json raises ValidationError for a leg with mode "self_drive" (mode constrained to enum ["drive","rail","bus","flight","ferry"]) and for a leg with mode "drive" lacking duration_mins (draft-07 if/then); and (2) scripts.legs.classify_leg({"mode": "drive", "from": "Tekapo", "to": "Te Anau"}) does NOT return status "ok" — it raises ValueError or returns a distinct non-"ok" status (e.g. "unknown_duration").

### TW-011 — trip-brief schema has no destination/local_lang/airline fields, yet four stages and the verify gate consume them

- **Severity**: high
- **位置**: `schemas/trip-brief.schema.json:4`
- **分類**: schema/skill drift / hallucination surface

**問題(failure mode)**

trip-brief never captures destination country, local language, or airline because its checklist omits them, and the 'ask for anything missing' rule keys on that checklist. Downstream, calendar-check infers the country from the slug/base district (ambiguous names like 'Cambridge' pick the wrong country's holiday calendar), travel-advisory verifies battery rules without knowing the airline (generic rules presented as airline-specific), and source-verify passes local_lang=None so the >=1-local-language iron-rule clause silently never enforces.

**證據**

```text
"required": ["slug", "dates", "members", "base", "must_do", "constraints", "preferences"] and no destination/airline/local_lang property exists anywhere in the schema or in trip-brief's Capture list (skills/trip-brief/SKILL.md:12-47). But skills/calendar-check/SKILL.md:14 reads 'the destination from trip-brief.yaml', skills/travel-advisory/SKILL.md:28 inputs '(destination, airline, dates)', seasonal-advisory:51 and transit-detail:36 likewise, and scripts/verify.py:37 disables Gate 1b entirely when local_lang is None.
```

**建議修法**

Add to schemas/trip-brief.schema.json a required destination object ({country, city, local_lang}) and an optional airline string; add them to the Capture list in skills/trip-brief/SKILL.md; have source-verify pass trip-brief.destination.local_lang to classify_candidate and travel-advisory halt if airline is absent.

**驗收條件**

A pytest asserts that jsonschema validation against schemas/trip-brief.schema.json FAILS for a trip-brief fixture lacking destination.local_lang (destination object with required country and local_lang must be in the schema's top-level "required"), PASSES for a fixture containing destination: {country, city, local_lang}, and that skills/source-verify/SKILL.md instructs passing trip-brief's destination.local_lang into classify_candidate (mechanical check: the string "local_lang" appears in skills/source-verify/SKILL.md).

### TW-012 — verified-pois schema requires geocode + >=2 sources on EVERY POI, making the never-silently-drop / D7 rule impossible — forces silent drop or fabricated geocode

- **Severity**: high
- **位置**: `schemas/verified-pois.schema.json:10`
- **分類**: schema-contract-conflict
- **獨立 reviewer 重複發現次數**: 6

**問題(failure mode)**

On essentially every real trip some candidates fail Gate 1 (1 source) or Gate 2 (Nominatim NO_RESULT). The agent is told to both record them and validate against the schema — impossible simultaneously. Under validation pressure it either (a) silently drops the non-verified candidates (violating the never-drop rule; the user never learns why a wished-for / must_do place vanished, and a re-run re-researches from scratch), (b) fabricates lat/lng or pads a second source — hallucinated coordinates then flow into routing-audit centroids, exported Google-Maps links, and trivially satisfy the gate's geocode-only check, or (c) abandons schema validation entirely, disabling the only mechanical check on the pipeline's central artifact.

**證據**

```text
Schema: "required": ["id", "name_local", "name_display", "category", "geocode", "district", "sources", "verify_status"] and "sources": {"minItems": 2} apply unconditionally to every pois[] item. But skills/source-verify/SKILL.md:26 mandates "Write all candidates into trips/<slug>/verified-pois.yaml ... Never silently drop a candidate — rejected/conflicting/unverified stay recorded with their reason", and SKILL.md:15 (D7) explicitly produces unverified POIs with NO geocode; Gate-1 failures have only 1 source — both unrepresentable. The repo's own e2e fixture proves the conflict: tests/fixtures/e2e-trip/verified-pois.yaml (commented "Expected output state AFTER source-verify") contains ONLY the verified odarijip; the conflicting 한방삼계탕 and single-source 고봉삼계탕 are silently absent — which is how test_expected_verified_pois_fixture_is_schema_valid stays green. tests/test_schemas.py:19-40 enshrines rejection of ANY status without geocode. [corrected: Minor correction only: tests/test_schemas.py:19-40 (test_verified_pois_missing_geocode_rejected at :19-28 and test_verified_pois_single_source_rejected at :30-40) both construct bad records with "verify_status": "verified" (lines 25 and 37), so the tests enshrine rejection only for the verified-status case — the unconditional rejection of ANY status without geocode/2-sources comes from the schema itself (schemas/verified-pois.schema.json:10-11 "required": [... "geocode", ... "sources", ...] and :27 "minItems": 2). All other cited evidence is accurate as quoted, including skills/source-verify/SKILL.md:26 ("Never silently drop a candidate — `rejected`/`conflicting`/`unverified` stay recorded with their reason"), SKILL.md:15 D7, and the silently-dropped candidates in tests/fixtures/e2e-trip/verified-pois.yaml validated by tests/test_e2e_pipeline.py:43-45.]
```

**建議修法**

In schemas/verified-pois.schema.json wrap geocode-required and sources minItems:2 in a draft-07 if/then conditional on verify_status == "verified" (other statuses: geocode optional, sources minItems 1, plus a required reason/status_note field). Update tests/test_schemas.py: unverified no-geocode and single-source records validate; verified-without-geocode still rejected. Extend tests/fixtures/e2e-trip/verified-pois.yaml to carry all three candidates with their statuses.

**驗收條件**

A pytest in tests/test_schemas.py asserts both directions against schemas/verified-pois.schema.json: (1) a pois[] item with verify_status "unverified", NO geocode key, exactly one sources entry, and a non-empty rejection-reason field VALIDATES successfully; (2) a pois[] item with verify_status "verified" but missing geocode (or with fewer than 2 sources) STILL FAILS validation; and tests/fixtures/e2e-trip/verified-pois.yaml is extended to contain the verified, conflicting, and single-source-unverified candidates simultaneously while test_expected_verified_pois_fixture_is_schema_valid stays green.

### TW-013 — No schema sets additionalProperties:false — a typo'd key (e.g. close_days) validates and the data silently vanishes

- **Severity**: high
- **位置**: `schemas/verified-pois.schema.json:9`
- **分類**: schema strictness

**問題(failure mode)**

The agent writes a POI's closure under a slightly wrong key name — YAML typo or memory of a different schema's vocabulary. Validation passes (no unknown-key error), poi_closed_on/closing_status see no closure data, and the protective behavior the agent believes it recorded simply does not exist downstream; combined with the no-re-check gates, the user gets a plan that schedules around nothing.

**證據**

```text
Every object schema in schemas/ omits additionalProperties (grep across schemas/ finds zero occurrences). E.g. the POI item object at verified-pois.schema.json:9-59 accepts any extra key, so close_days:, closedDays:, or opening_hours: (instead of closed_days/hours) all validate; scripts/calendar.py:52 and scripts/hours.py read only the canonical keys via .get(). [corrected: schemas/verified-pois.schema.json:8-60 (POI item object, no additionalProperties; verified empirically — typo'd keys validate) + scripts/calendar.py:52 'closed_days = poi.get("closed_days", []) or []' (verbatim). Correction: scripts/hours.py has no .get() reads — closing_status(start, close, last_call, need_mins) takes scalar args; the canonical `hours.close` key read happens in the synthesis layer (see schema's own description at verified-pois.schema.json:43). grep confirms zero "additionalProperties" occurrences in schemas/, scripts/, tests/, and no test rejects unknown keys.]
```

**建議修法**

Set "additionalProperties": false on the item/object schemas of all 12 files (POI items, sources, geocode, hours, booking, holiday items, legs, hops/clusters, candidates, stops). Run the full pytest sweep after, since fixtures with stray keys will surface immediately.

**驗收條件**

A pytest that loads every schemas/*.schema.json and recursively walks all subschemas fails if any object node declaring "properties" lacks "additionalProperties": false; in particular, jsonschema.validate must raise ValidationError for a verified-pois document whose POI item contains the unknown key "close_days" alongside all canonical required fields.

### TW-014 — sum_costs silently treats a missing amount as 0 (understating the total past the budget gate) and crashes with a bare TypeError on amount: null

- **Severity**: high
- **位置**: `scripts/cost.py:15`
- **分類**: silent default / crash with unactionable message

**問題(failure mode)**

cost-rollup assembles line items from upstream fares; one hotel's cost is unknown so the agent passes the item without amount (or with null). With omission, the category subtotal silently reads 0, over_budget returns False, the over-budget stop-and-ask never fires, and the user is told the trip fits a budget it actually exceeds by a hotel's worth. With null, the stage dies on a context-free TypeError.

**證據**

```text
cost.py:13-16: `by_category[cat] = by_category.get(cat, 0) + item.get("amount", 0)`. Empirically: sum_costs([{"category": "transport"}, {"category": "lodging", "amount": 300}]) -> {'total': 300} (transport silently 0), and amount=None -> `TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'` naming neither file nor item. The silent-0 happens in-memory BEFORE cost.yaml is written, so the schema's required `amount` (cost.schema.json:9) never sees the omission; over_budget (cost.py:41) then compares the understated total. No test covers missing/None amount (tests/test_cost.py).
```

**建議修法**

In scripts/cost.py::sum_costs, raise ValueError(f"line item '{item.get('label') or cat}' has no numeric 'amount'") when item.get("amount") is None or not a number, instead of defaulting to 0 — the skill should record unknown costs as an explicit estimate or exclude them with an estimate_note, never as silent zeros. Add tests for omitted and null amount.

**驗收條件**

pytest: scripts/cost.py::sum_costs raises ValueError (not TypeError, never a silent 0) for both sum_costs([{"category": "transport"}]) and sum_costs([{"category": "lodging", "label": "Hotel X", "amount": None}]), and the ValueError message contains the offending item's label (or category when label is absent), while existing valid-input sum_costs tests in tests/test_cost.py remain green.

### TW-015 — export-gate passes on an empty or truncated deliverable — all checks are absence-of-bad-pattern checks

- **Severity**: high
- **位置**: `scripts/export_gate.py:27`
- **分類**: gate bypass

**問題(failure mode)**

export-artifact writes the file before finishing (or renders only Day 1 of 3 because the agent looped render_day_table per-day and stopped early). export-gate stamps a green export-gate-report.yaml, the orchestrator declares the pipeline complete, and the user is handed an empty/half-empty itinerary with a passing gate report asserting it was validated.

**證據**

```text
export_gate.py:27-52: the four checks only search for bad patterns (_NAKED_DOLLAR.search, malformed _LINK targets, _MAP_TOKENS, missing official link), and lines 47-48 explicitly skip absent POIs: `if row is None: continue  # POI not scheduled into this deliverable; not this gate's concern`. Empirically confirmed: run_export_gate("", [BOOKABLE]) and run_export_gate("# Itinerary\n\n(render crashed", [BOOKABLE]) both return status 'pass'. Orchestrator SKILL.md:45 declares the pipeline complete on export-gate pass. [corrected: Core evidence unchanged: /home/user/hp_workspace/tripwork/scripts/export_gate.py:27-52, with lines 47-48 exactly 'if row is None: / continue  # POI not scheduled into this deliverable; not this gate's concern'. Minor correction: the 'pipeline complete on export-gate pass' declaration is in /home/user/hp_workspace/tripwork/skills/export-gate/SKILL.md:36 ('Next stage | tripwork:orchestrator (pipeline complete on pass)'), while /home/user/hp_workspace/tripwork/skills/orchestrator/SKILL.md:45 is the terminal step 15 ('export deliverable exists, no export-gate-report.yaml -> run export-gate. If export-gate-report status==fail -> return to export-artifact to re-render.') — pass at this final step ends the pipeline.]
```

**建議修法**

Add positive checks to scripts/export_gate.py::run_export_gate: (a) md_text non-blank with at least one `### ` day heading; (b) accept an expected day count (from trip-brief dates) and fail if day-table headings < expected; (c) fail if zero verified POI names from the scheduled set appear. Add red tests in tests/test_export_gate.py for empty and truncated inputs.

**驗收條件**

scripts/export_gate.py::run_export_gate accepts the expected day count (derived from trip-brief dates) and pytest asserts: run_export_gate("", pois, expected_days=3) and run_export_gate(day1_only_fixture, pois, expected_days=3) both return status=='fail' with a failed 'deliverable_complete' check naming the day shortfall, while the full 3-day fixture still returns status=='pass'.

### TW-016 — No stage ever sets sources[].official, yet export-gate hard-fails bookable POIs on it with a futile re-render-loop repair route; renderer labels non-official fallback links as 官網

- **Severity**: high
- **位置**: `scripts/export_gate.py:42`
- **分類**: missing-transition / unproduced field / user-facing mislabel
- **獨立 reviewer 重複發現次數**: 3

**問題(failure mode)**

Any trip with a booking-required POI (most trips): the agent followed source-verify to the letter, neither source flagged official. export-artifact renders, export-gate fails bookable_has_official_source, orchestrator rule 15 sends it back to export-artifact, which deterministically re-renders the identical file — an infinite fail→re-render loop the agent can only escape by improvising, likely retroactively stamping official: true on whatever blog URL is first (hallucinated officialness). Separately, for non-bookable POIs the 官網-mislabeled TripAdvisor/blog link ships in the deliverable — the user taps 'official website' to confirm tonight's hours or to book and lands on a third-party aggregator with stale data.

**證據**

```text
export_gate.py:42-51 fails any scheduled booking-required POI whose sources contain no s.get("official") url ("bookable POI '...' row missing official source link"). But grep across skills/*/SKILL.md shows no instruction to set official: true — source-verify SKILL.md:15-22 records only verification facts; destination-research SKILL.md:15 records only URLs with lang; the flag appears only as optional in verified-pois.schema.json:31. Even the bundled fixture tests/fixtures/verified-pois.sample.yaml has a booking.required POI whose sources (tripadvisor/foodybird) carry no official flag. On failure, export-gate/SKILL.md:26-27 routes only one way — "return to export-artifact ... to re-render" — which cannot add a source that verified-pois.yaml lacks. Meanwhile scripts/render/markdown.py:20-26 _primary_source_url falls back to sources[0] and line 32 labels it f"· [官網]({url})" regardless of branch; tests/test_render_markdown.py:47-55 locks the mislabel in.
```

**建議修法**

In skills/source-verify/SKILL.md, require flagging official: true on at least one source for every booking.required candidate (define 'official' = operated by the venue/operator/authority itself; stop and ask if none found). In skills/export-gate/SKILL.md and orchestrator rule 15, route bookable_has_official_source failures to source-verify (data fix) instead of export-artifact (render fix). In scripts/render/markdown.py, label the non-official fallback 來源 instead of 官網 (migrate the locked test), and optionally add an export-gate check that a 官網 label only ever wraps an official-flagged source.

**驗收條件**

單一 pytest（e2e fixture closure）：取一個 booking.required 且 sources 恰有一筆 official: true 的 verified POI，經 scripts/render/markdown.py 渲染後餵給 run_export_gate，斷言 bookable_has_official_source 的 passed == True；同一測試中，對一個 sources 非空但全無 official 旗標的 POI，斷言 render_day_table 輸出不含子字串 "[官網]"（fallback 連結須標 "來源"；原鎖定 mislabel 的 tests/test_render_markdown.py:47-55 須同步遷移）。

### TW-017 — itinerary-gate validates an LLM-reconstructed days structure, not itinerary.md — no parser or format convention exists, so the gate can pass vacuously

- **Severity**: high
- **位置**: `scripts/gate.py:19`
- **分類**: gate bypass / hallucination surface
- **獨立 reviewer 重複發現次數**: 3

**問題(failure mode)**

The same model that authored itinerary.md reconstructs the days dict from memory of what it intended, not what the file says. A POI it hallucinated into the markdown but omitted from the reconstruction sails past the unknown-POI/geocode checks; a day whose meal row it forgot is reported as having a meal; an itinerary covering 2 of 3 trip days still passes. The gate stamps 'pass' on a deliverable it never actually inspected — its value collapses to 'the LLM checked its own homework via a lossy copy' while gate-report.yaml presents it as mechanical verification.

**證據**

```text
run_gate's signature takes a pre-structured `days` list (gate.py:7+19: POI_KEYS = ("meals", "activities", "visits"); `referenced = {pid for d in days for key in POI_KEYS for pid in d.get(key, [])}`) that no upstream stage produces — itinerary-synthesis outputs only itinerary.md (SKILL.md:92), nothing in scripts/ parses itinerary.md (grep finds no parser; only export_gate reads raw markdown), and itinerary-gate SKILL.md:30 lists itinerary.md as input with no derivation procedure. itinerary-synthesis SKILL.md:14 says only "Each restaurant/POI row carries its POI id" with no machine-readable format. A day dict using any other key ('dinner', 'evening', 'sights') contributes nothing to `referenced`. Empirically: run_gate(pois, []) (zero days) returns 'pass'; nothing compares day dates to trip-brief dates.start/end.
```

**建議修法**

Define a machine-extractable convention: itinerary-synthesis emits either an HTML comment token per row (e.g. <!-- poi:odarijip -->) or a sidecar trips/<slug>/itinerary-days.yaml (schema-validated, written at composition time). Add a parser (e.g. scripts/gate.py::extract_days or scripts/itinerary_parse.py) and amend itinerary-gate SKILL.md to mandate building `days` from the file via that parser, never from memory. Make run_gate warn on unrecognized day keys, accept trip-brief dates and fail when the day set does not cover start..end, and add a pytest that a POI present in md but missing from verified-pois fails the gate end-to-end.

**驗收條件**

An end-to-end pytest that writes a trips/<slug>/itinerary.md fixture containing a POI id token per the new machine-extractable convention (e.g. <!-- poi:ghost-cafe -->) which is absent from verified-pois.yaml, then runs the itinerary-gate's file-based entry point (the new parser building `days` from itinerary.md, fed into run_gate) and asserts the resulting gate-report has status == "fail" with a failure naming 'ghost-cafe' — with no hand-constructed days dict anywhere in the test.

### TW-018 — Closed-day scheduling rule is LLM discipline only — itinerary-gate never re-checks poi_closed_on despite having the data

- **Severity**: high
- **位置**: `scripts/gate.py:30`
- **分類**: unenforced rule

**問題(failure mode)**

Synthesis, juggling 8 input files, forgets to run poi_closed_on for one POI (or mis-reads a weekday) and places the Tuesday-closed palace on Tuesday. itinerary-gate passes (it only checks geocode+meals), export-gate passes, and the user arrives at a closed gate — the exact pain the README's 痛點表 row claims is solved.

**證據**

```text
run_gate's only per-day check (gate.py:30-32) is `if not d.get("meals"): failures.append(...)`. It receives pois (which carry closed_days) and days (which carry date) but never calls scripts/calendar.py::poi_closed_on — calendar.py:49-50 says only "Synthesis hard-avoids scheduling a POI on a day this returns closed=True". README.md:137 sells it as a guarantee: "閉館日不排該點". No test or gate cross-checks placement against closed_days (grep of tests/ shows poi_closed_on tested only in isolation and in synthesis-side e2e fixtures).
```

**建議修法**

Extend scripts/gate.py::run_gate with an optional calendar parameter and add a no_closed_day_placement check: for every referenced pid on day d, fail when poi_closed_on(by_id[pid], d['date'], calendar)[0] is True. This is a pure-function call on data the gate already receives; wire it in skills/itinerary-gate/SKILL.md and add tests.

**驗收條件**

pytest: calling scripts.gate.run_gate with a POI whose closed_days=["tuesday"], a day whose ISO date falls on a Tuesday referencing that POI, and the calendar passed in, returns status="fail" with a failures entry naming that POI id and date and a checks entry {"name": "no_closed_day_placement", "passed": False}; the identical input with the POI referenced only on a non-closed day returns status="pass" with that check passed=True.

### TW-019 — Cache entries are trusted blindly with no provenance — a fabricated geocode.json entry silently passes Gate 2 forever

- **Severity**: high
- **位置**: `scripts/geocode.py:71-77`
- **分類**: cache poisoning / gate bypass

**問題(failure mode)**

An agent under Gate-2 pressure (a must_do POI that Nominatim won't resolve, which per source-verify SKILL.md would force a stop-and-ask) can 'fix' it by writing an entry into work/<slug>/geocode-cache/geocode.json with invented lat/lng and source: "nominatim_structured". resolve_place then returns it as a genuine Nominatim hit, classify_candidate marks the POI verified, and — because the cache short-circuits the network — every subsequent honest re-run of source-verify re-reads the poisoned entry and never re-queries Nominatim. The user receives a 'verified' POI with fabricated coordinates in itinerary, routing distances, and Google Maps export links, with no field anywhere recording that the value never came from Nominatim.

**證據**

```text
resolve_place: "hit, value = cache_get(cache, key)\n        if hit:\n            if value is None:\n                return None, None\n            return (GeocodeResult(value[\"lat\"], value[\"lng\"], value.get(\"display_name\", \"\")),\n                    value[\"source\"])" — and load_cache (scripts/geocode_cache.py:33-34) is "return json.load(f)" with zero shape validation. The cached dict carries only {lat,lng,display_name,source}; nothing distinguishes a real Nominatim answer from a hand-written one, and value["source"] is copied verbatim into the POI's geocode_source. tests/test_geocode_cache.py contains no provenance or validation test.
```

**建議修法**

In scripts/geocode.py resolve_place, validate cache hits before trusting them: lat/lng must be numbers and source must be in {"nominatim","nominatim_structured"}; treat anything else as a cache miss and re-query. In scripts/geocode_cache.py cache_put, stamp each entry with cached_at (ISO timestamp) written only by the script. Add a hard rule to skills/source-verify/SKILL.md and skills/accommodation-research/SKILL.md: agents must never hand-edit geocode.json; on a geocode failure the only paths are D7 unverified or (hotels) cluster_fallback. Add tests in tests/test_geocode.py for malformed-entry-treated-as-miss.

**驗收條件**

A pytest in tests/test_geocode.py passes in which resolve_place is called with a pre-populated cache whose entry for the queried key is malformed (any of: lat or lng not a number, e.g. "35.0" as a string; missing lat/lng/source key; source value outside {"nominatim", "nominatim_structured"}), and the test asserts (a) the cached value is NOT returned, (b) the mocked Nominatim query function (geocode_structured/geocode) IS called for that key, and (c) after the call the cache entry has been overwritten with the fresh network result — while a second test with a well-formed cached entry still short-circuits with zero network calls.

### TW-020 — All HH:MM time fields are unconstrained strings and to_minutes crashes uninformatively — including the YAML sexagesimal trap where unquoted `close: 21:30` parses as int 1290

- **Severity**: high
- **位置**: `scripts/hours.py:13`
- **分類**: loose schema / crash with unactionable message
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

source-verify writes `hours: {close: 21:30}` unquoted — the single most natural way to write a time in YAML — or copies '9:30 PM' off a website; the artifact validates. When itinerary-synthesis runs closing_status on every timed slot per the skill, the stage dies with an unactionable error; the realistic recovery is skipping the closing-buffer check altogether — silently dropping the never-schedule-past-last-order iron rule for that POI.

**證據**

```text
hours.py:13-14: `h, m = hhmm.split(":"); return int(h) * 60 + int(m)` — no type/format check. Empirically: yaml.safe_load("close: 21:30") -> {'close': 1290} (PyYAML 1.1 sexagesimal), then to_minutes(1290) -> `AttributeError: 'int' object has no attribute 'split'`; to_minutes(None) -> same class; '9pm' / '21:30 (L.O.)' / '09:00-23:00' raise ValueError. Neither message names the file, POI, or field. to_minutes is the entry point for hours.closing_status, legs.misses_last_service, transit.in_peak — all fed from LLM-authored YAML. The time fields are pattern-free strings everywhere: verified-pois hours.close/last_order/last_entry (schema:46-48), legs depart/last_service (legs.schema.json:18-19), transit peak_windows start/end (transit.schema.json:9-10), accommodations reception.close (accommodations.schema.json:27); the bundled fixture verified-pois.sample.yaml already carries a range-style `hours: "09:00-23:00"`. [corrected: Two minor corrections, finding otherwise verbatim-correct: (a) verified-pois schema time fields are at /home/user/hp_workspace/tripwork/schemas/verified-pois.schema.json:45-47 (not 46-48): `"close": {"type": "string"}, "last_order": {"type": "string"}, "last_entry": {"type": "string"}` — no pattern. (b) The fixture's range-style value at /home/user/hp_workspace/tripwork/tests/fixtures/verified-pois.sample.yaml:17 (`hours: "09:00-23:00"`) is the booking.hours free-text field (schema line 56), not the hours.close field consumed by to_minutes; the hours.close actually fed to closing_status appears in /home/user/hp_workspace/tripwork/tests/fixtures/e2e-trip/verified-pois-calendar.yaml:38-40 (`hours:` / `close: "21:30"` / `last_order: "20:30"`). All other citations (hours.py:13, legs.schema.json:18-19, transit.schema.json:9-10, accommodations.schema.json:27, legs.py/transit.py call sites, itinerary-synthesis SKILL.md closing_status mandate) are exact.]
```

**建議修法**

In scripts/hours.py::to_minutes validate input: accept int (PyYAML sexagesimal already equals minutes-since-midnight) or a string matching ^\\d{1,2}:\\d{2}$, else raise ValueError(f"expected 'HH:MM' time string, got {hhmm!r} — quote times in YAML ('21:30')"). Add "pattern": "^([01]?[0-9]|2[0-3]):[0-5][0-9]$" to every HH:MM field in verified-pois (hours.*), legs (depart, last_service), transit (peak_windows start/end), and accommodations (reception.close); add rejection tests.

**驗收條件**

A pytest in tests/test_hours.py passes where, given doc = yaml.safe_load("close: 21:30\nlast_order: 9pm"), scripts.hours.to_minutes(doc["close"]) returns 1290 (int from YAML-1.1 sexagesimal accepted as minutes-since-midnight), and to_minutes(doc["last_order"]) raises ValueError whose message contains both the offending value "9pm" and the literal substring "HH:MM".

### TW-021 — misses_last_service breaks across midnight: an after-midnight last service is falsely flagged missed, and a post-midnight planned departure silently passes against an evening last service

- **Severity**: high
- **位置**: `scripts/legs.py:17`
- **分類**: numeric edge case (midnight wrap)

**問題(failure mode)**

Last metro/night-bus services after midnight are routine (e.g. Osaka last rapid 00:30). The agent records '00:30' naturally; a planned 23:50 departure triggers a spurious missed_last_service stop-and-ask and the user is wrongly told to change mode/day. Worse, a planned 00:10 departure against a 23:40 last service returns 'ok' silently — the deliverable strands the traveller, exactly what the skill says the check exists to prevent.

**證據**

```text
legs.py:15-17: `def misses_last_service(planned_depart_hhmm, last_service_hhmm): return to_minutes(planned_depart_hhmm) > to_minutes(last_service_hhmm)` — same-day minutes only. Empirically: misses_last_service("23:50", "00:30") -> True (catchable train flagged missed) and misses_last_service("00:10", "23:40") -> False (genuinely missed train passes as 'ok'). schemas/legs.schema.json:18-19 gives depart/last_service no pattern, and skills/inter-stop-legs/SKILL.md:28 just says record last_service with no notation rule for past-midnight services. No test covers either direction (tests/test_legs.py:16-19). [corrected: skills/inter-stop-legs/SKILL.md:27 (not :28): "`last_service` (last train/bus)" — no past-midnight notation rule. All other citations verified at the stated lines: scripts/legs.py:15-17 exact quote; schemas/legs.schema.json:18-19 `"depart": {"type": "string"}, "last_service": {"type": "string"}` (no pattern); tests/test_legs.py:16-19 same-day cases only.]
```

**建議修法**

In scripts/legs.py treat small-hour times as next-day: e.g. in misses_last_service, if to_minutes(last) < to_minutes(depart) and to_minutes(last) < 5*60, add 1440 to last (and symmetrically for depart). Document the accepted '25:30'-style >24h notation as an alternative, add a pattern to legs.schema.json depart/last_service permitting it, and add red tests for both midnight directions.

**驗收條件**

pytest tests/test_legs.py passes with two new midnight-wrap assertions: misses_last_service("23:50", "00:30") is False (after-midnight last service is treated as next-day, no spurious flag) and misses_last_service("00:10", "23:40") is True (post-midnight planned departure against an evening last service is flagged), and classify_leg returns ("ok", ...) / ("missed_last_service", ...) respectively for transit legs carrying those depart/last_service values.

### TW-022 — Link labels and source URLs are never escaped — web-scraped POI names containing |, ], or $ silently corrupt the deliverable or wedge the export-gate repair loop

- **Severity**: high
- **位置**: `scripts/render/markdown.py:5`
- **分類**: injection fidelity / escaping round-trip

**問題(failure mode)**

name_display is scraped from the web (page titles routinely contain ' | Official Site'). Case (a): GFM drops cells beyond the header count, so the rendered 行程 column shows only the garbage fragment "[Cafe X" — the maps link, the 官網 booking link, and the free text all silently vanish from the user's deliverable while export-gate passes (it scans raw text, so it theoretically cannot catch this). Case (b): the POI name renders as dead literal text instead of a maps link; the `links_well_formed` and `poi_name_is_link` checks are both blind because the regex finds no link. Case (c): the gate fails, skills/export-gate/SKILL.md:27 sends the agent back to "re-render", but export-artifact SKILL.md:12 forbids hand-authoring rows ("do NOT hand-author table rows") and the pure renderer reproduces the identical naked `$` every time — an unresolvable fail/re-render loop with no instruction telling the agent the name itself is the problem. Bonus: md_escape's list (markdown.py:11) omits `[`/`]`/`(`/`)`, so escaped free text like "預約[官網](見上)" still forms a gate-visible malformed link with the same unrepairable loop.

**證據**

```text
markdown.py:5 docstring: "Generated link markup ([name](url)) is never escaped — only free text is." gmaps_links.py:16 emits the raw label: `return f"[{label}]({maps_url(poi)})"`; markdown.py:32 emits the raw source URL: `parts.append(f"· [官網]({url})")`. verified-pois.schema.json:14-15 puts no character constraint on name_local/name_display. Verified by execution: (a) name_display "Cafe X | Official Site" renders `| 09:00 | [Cafe X | Official Site](...) · [官網](...) brunch |` and run_export_gate returns **pass**; (b) name "Best Pizza :] NY" renders a dead non-link `[Best Pizza :] NY](url)` that export_gate.py:14 `_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")` does not match at all — gate **pass**; (c) name "Money$ Cafe" (or an official URL `...?price=$10`) renders a naked `$` and the gate **fails** with "naked '$' found".
```

**建議修法**

In scripts/render/gmaps_links.py::link_markdown and scripts/render/markdown.py::_poi_cell, escape `|`, `[`, `]`, `$`, `` ` `` (backslash-escape) in link labels, and percent-encode or reject `$`/`)` in appended source URLs; add `[`/`]` to markdown.py `_ESCAPE`. Add tests in tests/test_render_markdown.py with names containing `|`, `]`, `$` asserting the rendered row passes run_export_gate and stays a single table cell.

**驗收條件**

A pytest in tests/test_render_markdown.py renders a day via scripts.render.markdown.render_day_table containing three verified POIs whose name_display values are "Cafe X | Official Site", "Best Pizza :] NY", and "Money$ Cafe" (the last with an official source URL containing "$"), and asserts for every rendered table row that (1) splitting the row on unescaped pipes (regex r"(?<!\\)\|") yields exactly the 2 cells of the |時段|行程| header, (2) the POI name link is matched by scripts.export_gate._LINK with an https://www.google.com/maps target, and (3) scripts.export_gate.run_export_gate(md_text, pois) returns status == "pass" with an empty failures list.

### TW-023 — Source URLs are never fetched or deduplicated and the local-language check is opt-in — fabricated or duplicate sources satisfy the Source-Verified-First iron rule

- **Severity**: high
- **位置**: `scripts/verify.py:32`
- **分類**: hallucination surface / gate bypass
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

During source-verify the agent writes two plausible-looking URLs it never opened (misremembered from search snippets), or the same tabelog page twice, or two pages of one aggregator, or calls classify_candidate without local_lang — the candidate becomes 'verified' on effectively one unvetted (or imaginary) source as long as Nominatim resolves the name. The deliverable then renders sources[0]/official as the 官網 booking link (scripts/render/markdown.py:20-26), so the user receives a dead or wrong booking link on a 'verified' POI — exactly what the README says cannot happen.

**證據**

```text
verify.py:32-38: `if len(sources) < 2: return "unverified", ...` — Gate 1 only counts raw list entries with no dedupe by URL or domain, and reads agent-asserted `lang` labels. Line 37: `if local_lang is not None and local_lang not in langs` — the local-language gate silently disables when the caller omits local_lang (tests/test_verify.py:26-29 shows a candidate verified without passing it). No script in scripts/ performs network I/O except geocode.py (Nominatim). schemas/verified-pois.schema.json:31 types url as bare {"type": "string"} with no format: uri and no uniqueItems, so [{url: "a"}, {url: "a"}] counts as 2 independent sources. README.md:233 promises: "它會不會自己亂編地點？不會。" [corrected: /home/user/hp_workspace/tripwork/scripts/verify.py:33-34 — "if len(sources) < 2:\n        return \"unverified\", \"needs >=2 independent sources\"" (finding cited line 32, which is the preceding comment "# Gate 1a: must have >= 2 independent sources"; the conditional is at 33). All other citations (verify.py:37, tests/test_verify.py:26-29, schemas/verified-pois.schema.json:31, README.md:233, scripts/render/markdown.py:20-26) verify verbatim at the cited lines.]
```

**建議修法**

In scripts/verify.py make Gate 1 count distinct normalized netlocs (urllib.parse.urlsplit(url).netloc) instead of raw list length, and make local_lang a required positional argument (or fail loudly when None). Add uniqueItems: true to the sources arrays in verified-pois/candidates/accommodations schemas. In skills/source-verify/SKILL.md, require WebFetch of every source URL during verification with recorded fetch evidence per source (checked_at + title/snippet) and define 'independent' operationally (distinct domains, each actually fetched this session). Add red-phase tests for duplicate-URL and omitted-local_lang in tests/test_verify.py.

**驗收條件**

tests/test_verify.py gains a test asserting classify_candidate({'sources': [{'url': 'https://tabelog.com/r/1', 'lang': 'ja'}, {'url': 'https://tabelog.com/r/2', 'lang': 'ja'}]}, geocoded=True, in_claimed_region=True, local_lang='ja') returns status 'unverified' (Gate 1 must count distinct normalized netlocs, not raw list length), and a companion test asserting that calling classify_candidate without an explicit local_lang argument raises TypeError; both tests must be red on the current scripts/verify.py and green after the fix, with the full pytest sweep passing.

### TW-024 — No defined behaviour when WebSearch is unavailable or returns nothing — silent fallback to training data

- **Severity**: high
- **位置**: `skills/destination-research/SKILL.md:12`
- **分類**: hallucination surface / unspecified failure path

**問題(failure mode)**

In a consumer session without WebSearch (tool not granted, or every call denied), the agent — instructed to produce candidates.yaml/calendar.yaml/advisory.yaml — falls back to training-data 'knowledge', fabricating plausible source URLs with official: true to satisfy the schemas. Every downstream gate validates structure only, so a fully hallucinated, schema-valid trip plan reaches the user with no indication nothing was actually searched.

**證據**

```text
"Use the consumer harness WebSearch tool. The plugin bundles no search engine." — every research stage (destination-research, calendar-check:15, seasonal-advisory:15, transit-detail:14, travel-advisory:12, inter-stop-legs:22, cost-rollup:24) says 'Use the consumer harness WebSearch', and grep for unavailable/offline/fallback across skills/ shows none defines what to do when the tool is absent, permission-denied, or returns no usable results. [corrected: Main citation exact: /home/user/hp_workspace/tripwork/skills/destination-research/SKILL.md:12 "Use the consumer harness `WebSearch` tool. The plugin bundles no search engine." Minor drift only: cost-rollup citation is skills/cost-rollup/SKILL.md:23 (not :24) "(consumer `WebSearch` for a widely-cited / official". Supporting schema evidence: schemas/calendar.schema.json:29-30 and schemas/advisory.schema.json:20-21 require a source with "official": {"const": true}, forcing an invented official source when no search was run.]
```

**建議修法**

Add an iron rule to skills/using-tripwork/SKILL.md (and a one-line reminder in each research-stage SKILL.md): if the WebSearch tool is unavailable or a query cannot be completed, HALT the stage and tell the user — never substitute model memory; a fact with no fetched source this session must be recorded unverified with no URL, not given an invented citation.

**驗收條件**

A pytest (e.g. in tests/test_skills_structure.py) fails unless (a) skills/using-tripwork/SKILL.md contains an iron-rule paragraph matching, case-insensitively, 'WebSearch' co-occurring with ('unavailable' or 'denied' or 'no usable result') and ('HALT' or 'stop') and a prohibition on ('training data' or 'model memory'), and (b) every SKILL.md under skills/ whose text mentions 'WebSearch' (currently 9 files, enumerated by grep at test time so future skills are auto-covered) contains at least one line matching that same unavailable-then-halt/mark-unverified-without-URL directive.

### TW-025 — Notion write-back happens BEFORE export-gate runs, with no update-vs-recreate rule and no post-write verification — gate-failing content ships to Notion and diverges permanently

- **Severity**: high
- **位置**: `skills/export-artifact/SKILL.md:15`
- **分類**: gate bypass / ungated adapter

**問題(failure mode)**

Export-artifact writes the Notion page from the un-gated markdown; export-gate then fails (e.g. naked `$`). The user's Notion page — a shared, bookmarkable deliverable — already contains the defective content. On re-render the skill gives no rule for an existing `exports/.notion-page-id`: the agent either creates a duplicate page (old one stays stale and the family keeps reading it) or skips Notion ("graceful skip" prose makes skipping feel sanctioned), leaving Notion permanently diverged from the gated markdown. A partial/mangled MCP write is equally invisible because there is no read-back verification. Export-gate can never catch any of this: it reads only the local md file.

**證據**

```text
export-artifact SKILL.md:15: "**notion** — write back to a Notion page via the consumer's Notion MCP. This is driven by this skill, not a bundled script"; line 19's only discipline: "Record the page id in `exports/.notion-page-id` on success." Orchestrator SKILL.md:44-45 sequences export-artifact (incl. Notion) at step 14 and export-gate at step 15, and export-gate SKILL.md:35 on fail says only "return to `export-artifact` to re-render" — nothing about the already-written Notion page. grep over tests/ finds only test_skills_structure.py:51-54 asserting the word "Notion" appears in the prose; zero behavioral coverage.
```

**建議修法**

In skills/export-artifact/SKILL.md: (1) move the Notion adapter to run only AFTER export-gate-report.yaml status==pass (state this in the adapter list and Stage Contract, and mirror it in orchestrator SKILL.md step 15), or explicitly mark Notion as a post-gate sub-step; (2) add a rule: if `exports/.notion-page-id` exists, UPDATE that page instead of creating a new one; (3) require a read-back of the written page (MCP get) asserting the day headings match the gated markdown before recording success. Add a test_skills_structure assertion that the Notion adapter prose mentions the gate-pass precondition and the page-id update rule.

**驗收條件**

tests/test_skills_structure.py 新增一條測試：解析 skills/export-artifact/SKILL.md 的 Notion adapter 段落，必須同時斷言三件事，缺一即 FAIL —— (1) prose 明文規定 Notion 寫回僅在 export-gate-report.yaml status == pass 之後執行（且 skills/orchestrator/SKILL.md step 15 之後的順序與之一致）；(2) prose 明文規定若 exports/.notion-page-id 已存在則 UPDATE 該頁、禁止另建新頁；(3) prose 明文要求寫入後以 MCP read-back 比對 day headings 與 gated markdown 一致才可記錄成功。

### TW-026 — missed_last_service check is ill-posed: `depart` is unknowable at the legs stage, yet synthesis is forbidden from re-judging legs

- **Severity**: high
- **位置**: `skills/inter-stop-legs/SKILL.md:26`
- **分類**: stage-contract gap / unenforced feasibility rule

**問題(failure mode)**

On a multi-stop trip the agent (correctly) has no departure time at the legs stage and leaves depart unset — classify_leg returns 'ok'. Synthesis later places the inter-city move at 21:45 after a full sightseeing day, while legs.yaml records last_service 21:30; obeying "do not re-judge", it renders the move as a first-class row anyway. The exported itinerary tells the family to catch a train that has already stopped running — only a checklist footnote about last_service hints at the problem.

**證據**

```text
inter-stop-legs SKILL.md:26-27 records "`depart` (planned same-day departure, when a same-day move is scheduled)" — but day-level scheduling only happens later in itinerary-synthesis. scripts/legs.py:40-44: `if depart and last and misses_last_service(depart, last): ... return "ok", ""` — missing depart can never fail. itinerary-synthesis SKILL.md:60-61 then forbids the only stage that knows the real departure time from checking: "drive_too_long / missed_last_service legs are already resolved (stop-on-confirmation in inter-stop-legs) before synthesis runs; do not re-judge them here."
```

**建議修法**

In skills/itinerary-synthesis/SKILL.md, replace the blanket 'do not re-judge' for legs with: when placing each travel-day move, set the now-known departure time on the leg and re-run scripts/legs.py::classify_leg (or misses_last_service); a missed_last_service result at synthesis time is a stop-on-confirmation. Mirror the rule in skills/orchestrator/SKILL.md's stop list. In skills/inter-stop-legs/SKILL.md, state explicitly that the legs-stage check only covers user-stated departure constraints and final feasibility is re-checked at synthesis.

**驗收條件**

A mechanical pytest passes that asserts: (a) the "Inter-city moves" section of skills/itinerary-synthesis/SKILL.md contains no "do not re-judge" (or equivalent prohibition) applied to missed_last_service, and instead explicitly instructs setting the now-known synthesis-time departure on each travel-day transit leg and re-running scripts/legs.py::classify_leg (or misses_last_service) with a missed_last_service result declared a stop-on-confirmation; and (b) classify_leg({"mode": "transit", "depart": "21:45", "last_service": "21:30"}) returns ("missed_last_service", ...) — i.e. the synthesis-time re-check, when run as instructed, actually fires on a post-last-service departure.

### TW-027 — No slug derivation or multi-trip disambiguation rule — second trip in the same workspace resumes or contaminates the first

- **Severity**: high
- **位置**: `skills/orchestrator/SKILL.md:31`
- **分類**: slug-collision

**問題(failure mode)**

Workspace already holds trips/tokyo-2026/ (complete pipeline). User: "用 tripwork 排京都 2 天". Preflight is stamped, so skipped; rule 1 checks 'No trip-brief.yaml' — the agent finds trips/tokyo-2026/trip-brief.yaml, concludes the rule satisfied, and rule-walks forward inside the Tokyo workspace: Kyoto candidates appended to Tokyo's candidates.yaml or, worse, all artifacts present → straight to re-export of the Tokyo itinerary. A repeat visit to the same destination (slug = destination name) silently reuses last year's verified-pois with stale closed_days/holidays for the new dates.

**證據**

```text
All selection rules are written against an unbound <slug> ("1. No trip-brief.yaml -> run trip-brief.") with no rule for choosing WHICH trips/<slug>/ a request maps to when several exist, and no rule for allocating a fresh slug. trip-brief/SKILL.md's Capture list (lines 11-47) never mentions slug even though schemas/trip-brief.schema.json:4 requires it. workspace-shape-preflight confirms paths only once globally: orchestrator:30 "If work/.preflight-completed is absent" — the stamp is workspace-wide, not per-slug, so a second trip gets no path-confirmation step (preflight:12-13 "Skip entirely once the stamp exists").
```

**建議修法**

In skills/trip-brief/SKILL.md, define slug derivation (e.g. <yyyy-mm>-<destination>, confirm with user) and require uniqueness against existing trips/ dirs (collision → ask). In skills/orchestrator/SKILL.md add a rule 0.5: "Bind <slug> first: a resumed request must name or confirm an existing trips/<slug>/; a new request must allocate a slug that does not exist yet. Never apply rules 1-15 across trips."

**驗收條件**

A new pytest (e.g. tests/test_skill_slug_binding.py) asserts both: (1) skills/orchestrator/SKILL.md's Stage Selection section contains a slug-binding rule ordered before the "No trip-brief.yaml" rule whose text requires binding <slug> first — a new trip must allocate a slug that does not already exist under trips/, a resumed trip must name or confirm exactly one existing trips/<slug>/ — and explicitly forbids applying the file-existence rules across different trips/<slug>/ dirs; (2) skills/trip-brief/SKILL.md defines a slug derivation format that includes the trip dates (year-month) plus destination (e.g. <yyyy-mm>-<destination>) and instructs the agent to stop and ask the user when the derived slug collides with an existing trips/<slug>/ directory.

### TW-028 — travel-advisory runs AFTER itinerary-synthesis, so restricted/banned regulation items can never reach the checklist or exported deliverable

- **Severity**: high
- **位置**: `skills/orchestrator/SKILL.md:41`
- **分類**: pipeline-order dead path
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

travel-advisory finds a restricted rule (e.g. power-bank watt-hour limit effective before the trip). The already-written itinerary.md Pre-trip checklist never mentions it; itinerary-gate checks structure only, export renders from itinerary.md only — so the deliverable the user shares to the family LINE group contains zero mention of the regulation. banned items at least force a chat acknowledgement; restricted items vanish silently from every exported artifact.

**證據**

```text
Orchestrator orders synthesis first: "11. cost ready, no itinerary.md -> run itinerary-synthesis. 12. itinerary exists, no advisory.yaml -> run travel-advisory." But travel-advisory SKILL.md:20 instructs "Any restricted/banned item -> surface prominently and feed it into the synthesis checklist" — itinerary.md was already written one stage earlier, itinerary-synthesis SKILL.md:98 lists every input artifact EXCEPT advisory.yaml, its checklist rule (line 88) derives only from booking.required + passport/visa basics, no orchestrator rule re-runs synthesis (rule 11 fires only when itinerary.md is absent), scripts/gate.py::run_gate has no advisory parameter, and export-artifact's input (SKILL.md:27) is only itinerary.md + verified-pois.yaml + gate-report.yaml. [corrected: Orchestrator quote spans two lines: /home/user/hp_workspace/tripwork/skills/orchestrator/SKILL.md:41-42 — "11. cost ready, no itinerary.md -> run `itinerary-synthesis`." / "12. itinerary exists, no advisory.yaml -> run `travel-advisory`." All other citations exact: travel-advisory/SKILL.md:20, itinerary-synthesis/SKILL.md:88 and :98, export-artifact/SKILL.md:27, scripts/gate.py:9 run_gate(pois, days, accommodations=None, facility_needs=None).]
```

**建議修法**

In skills/orchestrator/SKILL.md, move travel-advisory before itinerary-synthesis (e.g. between cost-rollup and synthesis) and add advisory.yaml to itinerary-synthesis's Stage Contract input plus an explicit rule "push every restricted/banned advisory item into the Pre-trip checklist". Alternatively keep the order but add a rule: after travel-advisory writes advisory.yaml containing restricted/banned items, re-run itinerary-synthesis to merge them; extend scripts/gate.py to fail when a restricted/banned advisory item is absent from the checklist section, with tests in tests/test_gate.py.

**驗收條件**

Given a trip workspace fixture whose advisory.yaml contains at least one item with risk: restricted (and one with risk: banned), running the itinerary gate (scripts/gate.py::run_gate, now taking advisory as input) against an itinerary.md whose Pre-trip checklist omits those items returns status: fail with a finding naming each missing advisory item; the same gate returns status: pass once every restricted/banned item appears in the checklist section — both behaviours asserted by a new test in tests/test_gate.py, and skills/orchestrator/SKILL.md's stage-selection rules order travel-advisory (advisory.yaml) before itinerary-synthesis so advisory.yaml exists when itinerary.md is first written.

### TW-029 — Orchestrator has no fail-routing for itinerary-gate, no 'no gate-report' guard on rule 13, no termination rule, and undefined export-gate re-run semantics — existence-based rules loop instead of repairing

- **Severity**: high
- **位置**: `skills/orchestrator/SKILL.md:43`
- **分類**: missing-transition / selection-rule ambiguity
- **獨立 reviewer 重複發現次數**: 4

**問題(failure mode)**

Gate fails (e.g. a day with no meal, or a chosen lodging missing a required facility): the agent loops gate→orchestrator→gate forever, or improvises with no instruction — hand-patching itinerary.md with a POI id that was never verified (re-introducing the verify_status bypass), or deleting accommodations.yaml and losing the user's confirmed lodging picks. Re-invoking the pipeline on a completed workspace re-enters rule 13 and wastes/loops a stage. After an export-gate fail→re-render, the agent reads the residual fail report and may bounce back to export-artifact in a re-render loop. Presence-based rules also route a mid-flow trip-brief edit straight to 'complete' without re-deriving stale downstream artifacts.

**證據**

```text
Rules 13-15: "13. advisory ready -> run itinerary-gate. 14. gate-report status==pass, no exports/<slug>-itinerary.md -> run export-artifact. 15. export deliverable exists, no export-gate-report.yaml -> run export-gate. If export-gate-report status==fail -> return to export-artifact to re-render." There is no rule for gate-report status==fail (contrast rule 15's explicit export-gate fail path). itinerary-gate/SKILL.md:24 says "return to the responsible upstream stage via tripwork:orchestrator" — but every selection rule is artifact-existence-based and after a fail all upstream artifacts still exist, so the orchestrator lands back on rule 13 and re-runs the gate on unchanged inputs (rule 11 cannot re-fire because itinerary.md exists). Rule 13 also lacks a "no gate-report.yaml" precondition, there is no terminal "pipeline complete" rule, rule 15's re-render leaves the stale fail report so its first clause never re-fires, the Inputs list (lines 12-26) omits trips/<slug>/gate-report.yaml, and no failure-class→stage mapping exists anywhere. [corrected: Evidence confirmed at cited locations: /home/user/hp_workspace/tripwork/skills/orchestrator/SKILL.md:43-45 (rules 13-15, verbatim as quoted), :12-26 (Inputs list omitting gate-report.yaml), :51 (Stop-on-Confirmation partially covers lodging/facility failures via halt-and-ask but not no-meal/unknown-POI/geocode failures, and offers no repair routing); /home/user/hp_workspace/tripwork/skills/itinerary-gate/SKILL.md:24 ("If `status: fail`, list each failure and return to the responsible upstream stage via `tripwork:orchestrator`."). One nuance: rule 3 ("verified-pois.yaml stale/missing") means not literally every rule is existence-only, but all rules downstream of it are, so the loop analysis is unaffected.]
```

**建議修法**

In skills/orchestrator/SKILL.md: (1) add an explicit fail branch between rules 13 and 14 mirroring rule 15 — map failure classes to owners (no-meal / unknown-POI / geocode failures → re-run itinerary-synthesis regenerating itinerary.md; lodging/facility failures → accommodation-research), invalidating only that artifact plus the stale gate-report; (2) add "no gate-report.yaml (or itinerary.md newer than gate-report.yaml)" to rule 13; (3) add rule 16: export-gate-report status==pass → pipeline complete, report deliverables; (4) specify that rule 15's fail path deletes/overwrites the old export-gate-report before re-rendering; (5) add gate-report.yaml to the Inputs list. Mirror the failure→stage table in itinerary-gate/SKILL.md and add a keyword assertion in tests/test_skills_structure.py.

**驗收條件**

A test in tests/test_skills_structure.py parses the Stage Selection section of skills/orchestrator/SKILL.md and fails unless it contains (a) an explicit rule for trips/<slug>/gate-report.yaml status==fail that maps failure classes to owning stages by name — meal/POI/geocode failures -> itinerary-synthesis, lodging/facility failures -> accommodation-research — including invalidating the stale gate-report, (b) a 'no gate-report.yaml (or itinerary.md newer than gate-report.yaml)' precondition on the run-itinerary-gate rule, and (c) a terminal rule declaring the pipeline complete when export-gate-report status==pass; the test must be RED against the current SKILL.md and GREEN after the fix.

### TW-030 — Stop condition 'booking lead-time missed' is unowned — no stage, script, or schema field can ever make it fire

- **Severity**: high
- **位置**: `skills/orchestrator/SKILL.md:51`
- **分類**: unenforced-rule
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

User starts planning 3-10 days before departure; source-verify records a must-do restaurant with booking: {required: true, lead_time: "1 month"}. No stage ever reports "lead-time missed", so the orchestrator's promised halt never triggers. The pipeline completes and the user receives a polished itinerary scheduling a restaurant whose booking window already closed — the only hint is a checklist line stating the lead time, with no comparison against the remaining days and no stop-and-ask. The user discovers the must-do is impossible only when they try to book.

**證據**

```text
Orchestrator halt list: "Halt and ask the user when a stage reports: ... booking lead-time missed, ..."; using-tripwork/SKILL.md:41 repeats it. But no stage's Stop-condition row mentions lead time, and grep over scripts/ + tests/ + schemas/ shows lead_time exists only as a free-form string (schemas/verified-pois.schema.json:55 "lead_time": {"type": "string"}; fixture value "1 week") that no script ever parses or compares to dates. itinerary-synthesis/SKILL.md:88 merely copies it into the checklist: "auto-extract from verified-pois booking.required==true (with lead_time)". Nothing computes today + lead_time vs trip date.
```

**建議修法**

Make lead_time machine-comparable: add lead_time_days (integer) to verified-pois.schema.json booking and have source-verify record it. Add a pure helper (e.g. scripts/booking.py::lead_time_missed(today, trip_start, lead_time_days)) and assign ownership in skills/itinerary-synthesis/SKILL.md: while building the Pre-trip checklist, flag any booking whose lead time has passed → stop-on-confirmation; add the pytest. Or, if deferred, delete "booking lead-time missed" from orchestrator:51 and using-tripwork:41 so the halt list only promises what stages emit.

**驗收條件**

A pytest passes asserting that a pure helper (e.g. scripts/booking.py::lead_time_missed) returns True for today=2026-06-11, trip_start=2026-06-18, lead_time_days=30 and False for lead_time_days=5, AND a mechanical grep finds "lead-time missed" (or lead_time_missed) in the Stop condition row of skills/itinerary-synthesis/SKILL.md — giving the orchestrator's halt at skills/orchestrator/SKILL.md:51 an owning stage that can actually report it.

### TW-031 — Orchestrator halt list out of sync with stage-emitted flags: reception-after-close missing; 'regulation risk' contradicts travel-advisory's banned-only halt

- **Severity**: high
- **位置**: `skills/orchestrator/SKILL.md:51`
- **分類**: stop-list-desync

**問題(failure mode)**

The orchestrator skill 'owns stop-on-confirmation' (frontmatter line 3), so an agent reconciling a stage's report against the orchestrator's halt list treats the list as authoritative: accommodation-research reports arrival-after-reception-close, the list has no such entry, the agent proceeds to inter-stop-legs — the user only discovers at the hotel door that check-in closed at 20:00. In the other direction, an agent reading "regulation risk" halts on every 'restricted' or even 'info' advisory item, peppering the user with confirmations travel-advisory never intended.

**證據**

```text
Orchestrator stop list names "an unfilled overnight stop needing a lodging pick or a missing required facility" but not the third hard stop accommodation-research emits — SKILL.md:70 Stop condition: "...; arrival is after reception close → ask user" (backed by scripts/facilities.py::reception_ok, accommodation-research:51-53). Conversely the orchestrator's "regulation risk" is broader than what the stage defines: travel-advisory/SKILL.md:30 halts only on "A banned item exists → require explicit user acknowledgement" while risk values are info|restricted|banned (travel-advisory:16); using-tripwork:41 says "regulation banned".
```

**建議修法**

In skills/orchestrator/SKILL.md:51, add "arrival after a lodging's reception close with no late check-in" to the halt list and replace "regulation risk" with "a regulation tagged banned (restricted/info are surfaced, not halted)". Add a test in tests/test_skills_structure.py cross-checking that every stage SKILL.md Stop-condition phrase has a counterpart in the orchestrator halt list.

**驗收條件**

A new pytest in tests/test_skills_structure.py parses the Stop-on-Confirmation paragraph of skills/orchestrator/SKILL.md and asserts (a) it contains an entry matching the reception-close halt (regex r"reception" plus r"late check.?in") and (b) it scopes the regulation halt to banned only (contains "banned" and no longer contains the bare phrase "regulation risk"); the test is red on the current tree and green after the orchestrator list is updated.

### TW-032 — source-verify never defines 'independent sources' nor a conflict threshold for rating/hours/address disagreement

- **Severity**: high
- **位置**: `skills/source-verify/SKILL.md:16`
- **分類**: vague gate criteria in the iron-rule gate

**問題(failure mode)**

Two opposite failures. Lenient agent: counts two pages from the same aggregator (or a blog quoting the aggregator) as 'independent', so a single effective source passes Gate 1, and ignores a 1-hour cross-source closing-time mismatch — wrong hours flow into closing_status and the user is sent to a restaurant after its real last order. Literal agent: ratings legitimately differ across platforms (Google 4.4 vs Tabelog 3.6 use different scales), so it flags nearly every POI conflicting and the pipeline stops on every candidate, burying the user in confirmation prompts.

**證據**

```text
SKILL.md:14 requires ">= 2 independent sources" with no definition of independence (scripts/verify.py:33 only checks `len(sources) < 2`). SKILL.md:16: "Detect cross-source disagreement on rating/hours/address and signal it to classify_candidate via the conflict_detected=True argument (computed by this skill)" — no tolerance is given for what counts as disagreement; the whole Gate-3a decision is unconstrained LLM judgment.
```

**建議修法**

In skills/source-verify/SKILL.md, define both terms operationally: independence = different operating entities (different root domain AND not one quoting the other; one aggregator + one official site qualifies). Conflict = a material factual disagreement: opening hours/closed days differing, addresses geocoding >X m apart, or phone numbers differing; explicitly exclude cross-platform rating differences (or restrict to same-platform contradictions). Mirror the rules in accommodation-research which reuses classify_candidate.

**驗收條件**

A new pytest in tests/ passes against pure helpers exposed by scripts/verify.py: (a) classify_candidate on a candidate whose only two sources share the same registrable root domain (e.g. two tabelog.com URLs) returns verify_status 'unverified' with an independence-failure note, while one official-site source plus one aggregator source still passes Gate 1; and (b) a conflict-detection helper given Google rating 4.4 vs Tabelog rating 3.6 with identical hours and address returns conflict_detected=False, but a cross-source closing-time mismatch returns conflict_detected=True.

### TW-033 — Opening hours / closed_days have no recency or as-of requirement — stale hours drive minute-level scheduling

- **Severity**: high
- **位置**: `skills/source-verify/SKILL.md:22`
- **分類**: missing verification criterion / hallucination surface

**問題(failure mode)**

The agent satisfies 'from verified sources' by reading hours off a 2021 blog post (a valid Gate-1 source); scripts/hours.py::closing_status then schedules dinner 40 minutes before a last_order that moved an hour earlier years ago — the user arrives to be turned away, with no signal in the artifact that the hours were stale.

**證據**

```text
"plus typical_visit_mins ... These come from the same verified sources — never guess a closing time." — but no recency criterion (how old may the source be? must the official page be among them?) and schemas/verified-pois.schema.json:41-50 hours has only close/last_order/last_entry/typical_visit_mins — no as_of/checked field. grep over skills/ finds no recency/access-date rule for POI hours.
```

**建議修法**

In skills/source-verify/SKILL.md require hours/closed_days to come from the official page or a source dated within a defined window (e.g. 12 months), and record hours.as_of + which source supplied them; add the as_of property to the hours object in schemas/verified-pois.schema.json so synthesis can surface stale-hours warnings.

**驗收條件**

jsonschema validation of a verified-pois.yaml fixture against schemas/verified-pois.schema.json FAILS when any POI's hours object lacks an as_of property (ISO date string, e.g. "2026-05-01") and PASSES when as_of is present — i.e. as_of is listed in the hours object's required properties with a date format/pattern constraint — and a mechanical grep-style test asserts skills/source-verify/SKILL.md contains both the string "as_of" and an explicit recency rule for hours/closed_days (official page or source dated within the defined window).

### TW-034 — advisory.yaml is consumed by no script or gate — banned-regulation stop and deliverable surfacing are prose-only

- **Severity**: high
- **位置**: `skills/travel-advisory/SKILL.md:20`
- **分類**: iron rule unenforced

**問題(failure mode)**

travel-advisory records risk: banned (e.g. a power-bank class prohibited by the airline), the agent under context pressure forgets the prose stop, the orchestrator advances on file presence, both gates pass, and the deliverable's pre-trip checklist omits the ban. User packs the banned item; the README §4 promise '被禁項目醒目提醒並要你確認' is silently void. No record of acknowledgement exists anywhere.

**證據**

```text
travel-advisory SKILL.md:20: "Any restricted/banned item -> surface prominently and feed it into the synthesis checklist. Stop and require user acknowledgement for banned items." Grep of scripts/ and tests/ shows no code reads advisory.yaml (only schema-shape tests in test_schemas.py:63-104). skills/itinerary-gate/SKILL.md:3 even claims "Use when itinerary.md + advisory.yaml are ready", yet run_gate (scripts/gate.py:9) has no advisory parameter, and run_export_gate never checks that banned topics appear in the deliverable. Orchestrator rule 13 (SKILL.md:43) advances on advisory.yaml mere existence.
```

**建議修法**

Extend scripts/gate.py::run_gate with an advisory_items parameter: fail when any item has risk: banned without a recorded acknowledgement (e.g. acknowledged: true field added to advisory.schema.json, set only after the user confirms and logged in work/<slug>/stage-state.yaml). Add an export-gate check that every banned/restricted topic string appears in the deliverable text.

**驗收條件**

A pytest calling scripts.gate.run_gate with an advisory items list containing {"id": "powerbank-ban", "risk": "banned"} (no acknowledged: true) asserts the returned gate-report has status == "fail" and a failure string naming "powerbank-ban"; the same call with acknowledged: true on that item asserts no advisory-related failure — i.e. an unacknowledged banned item mechanically fails itinerary-gate instead of relying on prose.

### TW-035 — travel-advisory standalone 模式直接寫 trips/<slug>/advisory.yaml，永久吃掉 pipeline 的 iron-rule gate stage

- **Severity**: high
- **位置**: `skills/travel-advisory/SKILL.md:20`
- **分類**: gate bypass / dual-mode activation

**問題(failure mode)**

使用者在 source-verify 階段中途問「幫我查一下長榮能不能帶行動電源」→ description 的 standalone 條款讓 travel-advisory 立刻發動，寫出只含電池規定一條的 trips/<slug>/advisory.yaml。之後 itinerary.md 產出時，orchestrator step 12 看到 advisory.yaml 已存在直接跳過，step 13 進 gate（gate 不讀 advisory）→ 行程出口時入境/海關規定從未針對最終行程+日期完整查證，banned 項目（例如行程裡新增的市場買刀具）無人攔截。Iron-rule gate 被一次閒聊式提問靜默繞過。

**證據**

```text
SKILL.md:3「Can also be invoked standalone to check regulations.」、:28「Standalone use also allowed.」，但輸出指令 :20 無條件寫同一個路徑：「Write `trips/<slug>/advisory.yaml`」。orchestrator SKILL.md:42-43 是純檔案存在判斷：「12. itinerary exists, no advisory.yaml -> run `travel-advisory`. 13. advisory ready -> run `itinerary-gate`.」且 itinerary-gate 的 Stage Contract Input（SKILL.md:30）根本不含 advisory.yaml、scripts/gate.py 也不讀它（grep advisory scripts/*.py 無 gate 相關命中），無任何 freshness/coverage 檢查。
```

**建議修法**

修 skills/travel-advisory/SKILL.md：standalone 模式明文禁止寫 trips/<slug>/advisory.yaml（改為 inline 回答或寫 work/<slug>/advisory-adhoc.yaml），並在 Stage Contract 標明只有 orchestrator step 12 路由進來時才寫正式 artifact。另在 orchestrator SKILL.md step 12 加 staleness 條款（比照 step 3 的「stale/missing」措辭）：advisory.yaml 早於 itinerary.md 即視為 stale 重跑。

**驗收條件**

A pytest reading skills/travel-advisory/SKILL.md asserts that (a) it contains an explicit standalone-mode clause stating that standalone invocation must NOT write `trips/<slug>/advisory.yaml` (output goes inline or to `work/<slug>/advisory-adhoc.yaml` instead), and (b) skills/orchestrator/SKILL.md step 12 contains a staleness clause (advisory.yaml absent OR stale relative to itinerary.md -> run travel-advisory), so a pre-existing standalone-written advisory.yaml can no longer satisfy step 12's routing condition.

### TW-036 — README 起手式同時命中 using-tripwork / orchestrator / trip-brief 三個 description；trip-brief 直接發動會繞過 workspace-shape-preflight 的 stop-on-confirmation

- **Severity**: high
- **位置**: `skills/trip-brief/SKILL.md:3`
- **分類**: entry routing ambiguity / preflight bypass

**問題(failure mode)**

使用者在自己的雜物 repo（brownfield cwd）貼上 README 起手式；模型挑了字面最貼合的 trip-brief（而非入口 skill），跳過 preflight 直接在未經確認的 cwd 建 trips/<slug>/ 並寫檔——preflight 的 stop-on-confirmation 鐵則被靜默繞過，使用者的 repo 被未經同意地寫入目錄；且 work/.preflight-completed 永遠沒蓋章，後續 orchestrator step 0 又把已開跑的 session 拉回 preflight，流程錯亂。

**證據**

```text
trip-brief description:「Use when a new travel request arrives and the trip parameters must be captured before research begins.」—— README.md:52 的起手式「用 tripwork 幫我排 3 天 2 夜東京自由行…」正是字面上的 a new travel request，與 using-tripwork:3（'Use when starting any travel-planning workflow'）和 orchestrator:3（'…when a travel-planning request must be routed into the pipeline'）三方等強命中。trip-brief 內文 :8/:55 直接「Write `trips/<slug>/trip-brief.yaml`」，全文無 preflight stamp 檢查；stamp 守門只存在於 orchestrator SKILL.md:30（step 0）。而 workspace-shape-preflight SKILL.md:27 規定「Always stop and ask before creating directories in a non-empty cwd. Never overwrite existing files.」
```

**建議修法**

改 skills/trip-brief/SKILL.md description 為 orchestrator 路由式措辭（例：'Use when the tripwork orchestrator has routed a new travel request and trip parameters must be captured…'），並在內文 Capture 之前加 step 0：「`work/.preflight-completed` 不存在 → 先 invoke `tripwork:workspace-shape-preflight`，不得寫任何檔案」。README.md:49-53 起手式段落可加一句明示入口是 tripwork:using-tripwork。

**驗收條件**

A pytest over skills/trip-brief/SKILL.md asserts both: (1) the body contains a guard step referencing `work/.preflight-completed` and `tripwork:workspace-shape-preflight`, and the character index of that guard is strictly less than the index of the first instruction to write `trips/<slug>/trip-brief.yaml`; (2) the frontmatter description no longer matches the entry-routing regex r"when a new travel request arrives" and instead contains orchestrator-routed phrasing (e.g. matches r"orchestrator has routed").

### TW-037 — Entry skill using-tripwork describes an obsolete 9-stage pipeline — 6 stages missing from the tree and Quick Reference, stop-condition list has 5 of 10 conditions, contradicting the orchestrator

- **Severity**: high
- **位置**: `skills/using-tripwork/SKILL.md:18`
- **分類**: stale entry-skill / cross-skill contradiction
- **獨立 reviewer 重複發現次數**: 5

**問題(failure mode)**

An agent entering via the designated entry skill (loaded first per its description) jumps routing-audit → calendar-check → synthesis, skipping accommodation/legs/seasonal/transit/cost entirely. The deliverable has empty 宿 rows, no inter-city move rows, no cost block; because accommodations.yaml is absent, itinerary-gate still passes, export-gate never runs (treated as complete after export-artifact), and a multi-stop self-drive user receives a 'complete' itinerary with no last-service/drive-length feasibility ever audited. Separately, an agent reconciling a stop decision against the entry skill's shorter Iron Rules table judges over-budget / blocking-hazard / missed_last_service stops non-mandatory and continues — README §4 promises silently voided. Drift worsens with each new stage since nothing tests this file.

**證據**

```text
Pipeline block (lines 18-30) routes routing-audit → calendar-check → itinerary-synthesis and ends at export-artifact — omitting accommodation-research, inter-stop-legs, seasonal-advisory, transit-detail, cost-rollup, and export-gate, which orchestrator/SKILL.md:35-45 runs as stages 5, 6, 8, 9, 10, 15. The Quick Reference table (lines 47-59) lists only 11 skills. The Iron-Rules stop list (line 41) carries only the original 5 conditions vs orchestrator:51's 10 — missing lodging-pick/required-facility, blocking seasonal hazard, drive_too_long/missed_last_service, and over-budget. Stage frontmatter encodes the same stale order (itinerary-synthesis:3 "verified-pois.yaml + routing.yaml are ready" vs its 8-input Stage Contract at line 98; calendar-check:3 likewise). No test guards: test_readme_freshness.py:17 excludes using-tripwork, test_skills_structure.py:40-44 only asserts headers exist. Compounding: gate.py:34 runs lodging checks only "if accommodations is not None", so skipped stages are not caught.
```

**建議修法**

Rewrite skills/using-tripwork/SKILL.md: regenerate the Pipeline tree and Quick Reference from orchestrator:31-45's full stage order (with artifact filenames); sync the Stop-on-confirmation row with orchestrator:51 or replace it with a pointer declaring the orchestrator list canonical; fix stale frontmatter descriptions (itinerary-synthesis, calendar-check, cost-rollup, transit-detail) to name true predecessor artifacts. Add a parity test in tests/test_skills_structure.py asserting every EXPECTED stage name appears in using-tripwork's pipeline block in orchestrator order. Additionally key gate.py's accommodation checks on trip-brief overnight_stops/base rather than file presence.

**驗收條件**

在 tests/test_skills_structure.py 新增 parity test：從 skills/orchestrator/SKILL.md 的 Stage Selection 規則抽出全部 stage-skill 名稱序列（trip-brief 至 export-gate，含 accommodation-research、inter-stop-legs、seasonal-advisory、transit-detail、cost-rollup、export-gate），逐一斷言每個名稱都出現在 skills/using-tripwork/SKILL.md 的 Pipeline code block 內、且彼此相對順序與 orchestrator 一致；此測試在修復前的 HEAD 必須 FAIL（缺 6 個階段），在重寫後的 using-tripwork/SKILL.md 上必須 PASS。

### TW-038 — must_do coverage is unenforced — the only checker lives in test code and no schema field links trip-brief.must_do to POI ids

- **Severity**: high
- **位置**: `tests/test_e2e_must_do.py:17`
- **分類**: unenforced rule / test gap
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

Two paths: (a) a must_do POI verifies fine but synthesis simply never places it (crowded out while balancing clusters) — no stop fires because the POI didn't 'fail', both gates pass, and the user receives a deliverable missing the one place they explicitly named, contradicting README §1 "不會...偷偷拿掉你想去的點". (b) The user's must_do is phrased differently from the covering candidate ("賞楓 in Naejangsan" vs id naejangsan-maple); when that candidate comes back conflicting/unverified, nothing mechanical maps the failure back, the LLM fuzzy-match may miss it, and the mandatory stop-and-ask never fires. Meanwhile the test suite green-tests a helper that never ships.

**證據**

```text
The function unmet_must_dos(must_do_ids, statuses) (test_e2e_must_do.py:17-19, "must be surfaced, not dropped") exists only in tests/, not scripts/ (grep 'must_do' over scripts/ matches only a docstring in calendar.py:50). trip-brief.must_do is free text ("named experiences", e.g. "maplestory park" — trip-brief SKILL.md:15, test_schemas.py:47), while candidates/POIs carry slug ids; schemas/candidates.schema.json has no must_do linkage field. run_gate never receives trip-brief.must_do, and export_gate.py:48 explicitly treats an absent POI as "not this gate's concern". Three stages' stop conditions key on "a must_do item fails verification" (source-verify SKILL.md:36, itinerary-synthesis SKILL.md:100, calendar-check SKILL.md:36).
```

**建議修法**

Promote unmet_must_dos into scripts/ (e.g. scripts/must_do.py) and add a linkage field — candidates.schema.json must_do_ref (string matching the trip-brief entry, set by destination-research) and/or a must_do: true flag in verified-pois.schema.json. Add a must_do_scheduled check to scripts/gate.py::run_gate fed by the trip-brief list, failing when any verified must_do id is referenced by no day. Have source-verify SKILL.md instruct running the helper to compute unmet must-dos mechanically; re-point tests/test_e2e_must_do.py at the shipped function.

**驗收條件**

A pytest exists in which verified-pois contains a POI carrying a must_do linkage (must_do: true or must_do_ref matching a trip-brief.must_do entry) with verify_status: verified, the days list references that POI in no day's meals/activities/visits, and scripts/gate.py::run_gate (fed the trip-brief must_do list) returns status == 'fail' with a 'must_do_scheduled' check whose failures entry names that POI id; the same fixture with the POI placed on any day returns status == 'pass'.

## MEDIUM

### TW-039 — No lifecycle rule ever expires the cache on re-brief or destination change — the most durable cross-trip contamination vector under an underived slug

- **Severity**: medium
- **位置**: `docs/superpowers/specs/2026-06-06-v0.10.0-geocode-cache-design.md:29`
- **分類**: persistence lifecycle / staleness

**問題(failure mode)**

User re-briefs under the same slug ("japan-trip" replanned a year later, or destination changed from Kyoto to Osaka while keeping the slug): the new pipeline run inherits every old entry — stale negative entries suppress live lookups for venues that now exist in OSM (permanently unverified per finding 2), and stale positive entries serve year-old coordinates/display_names for venues that moved or closed, all labeled with a trustworthy nominatim source. Because trips/<slug>/verified-pois.yaml was regenerated but work/<slug>/geocode-cache/ was not, the 'naturally short-lived' assumption silently fails and the contamination is invisible in any artifact.

**證據**

```text
Design rationale: "TTL | expiry vs none | **none** — a per-trip cache is naturally short-lived". But nothing makes it short-lived: no skill ever deletes work/<slug>/ (grep over skills/ finds no clear/expire/invalidate instruction), orchestrator SKILL.md:33 re-runs source-verify against the same cache when "verified-pois.yaml stale/missing", and skills/trip-brief/SKILL.md (lines 8, 55: "Write `trips/<slug>/trip-brief.yaml`") never defines how <slug> is derived, so a re-briefed or revised trip can land on an existing slug and inherit its geocode-cache/geocode.json wholesale. [corrected: Not needed — all cited locations verified at the stated lines. For completeness: design doc TTL row is docs/superpowers/specs/2026-06-06-v0.10.0-geocode-cache-design.md:29 (echoed at :154); orchestrator re-run rule at skills/orchestrator/SKILL.md:33; trip-brief slug writes at skills/trip-brief/SKILL.md:8 and :55 (also :62); persistence instruction at skills/source-verify/SKILL.md:15 ("load it once at the start and save it at the end").]
```

**建議修法**

Add a lifecycle rule in skills/trip-brief/SKILL.md (and orchestrator): when trip-brief.yaml is (re)written for a slug whose destination or dates changed, delete work/<slug>/geocode-cache/ (it is rebuildable by definition). Additionally define slug derivation in trip-brief/SKILL.md (e.g. destination + start-date) so distinct trips cannot share a work/ dir. Optionally stamp the cache file with the trip-brief destination and have load_cache-callers discard on mismatch.

**驗收條件**

新增 pytest（如 tests/test_geocode_cache_lifecycle.py）：(1) 在 work/<slug>/geocode-cache/geocode.json 預先寫入一筆 negative entry（value 為 null）並蓋上 trip 身分戳記（destination + dates，來自 trip-brief.yaml）；(2) 改寫同一 slug 的 trip-brief.yaml 為不同 destination（或 dates）；(3) 斷言 source-verify 所用的 cache 載入路徑（load_cache 或其 lifecycle wrapper）回傳空 dict——即 stale entries（含 negative None entry）被丟棄，cache_get 對該 venue 回傳 hit=False，resolve_place 不再被快取 miss 短路。

### TW-040 — calendar holiday `impact` is optional despite the skill calling its omission a mistake — holidays without it are treated as calm days

- **Severity**: medium
- **位置**: `schemas/calendar.schema.json:10`
- **分類**: schema strictness

**問題(failure mode)**

The agent records a weekday national holiday but forgets the impact block; the file validates. is_high_crowd() returns False for that date, so synthesis schedules queue-heavy restaurants and crowd-fragile shops onto a packed national holiday with no early-start advice and no holiday label on the day row — degraded plan the user only discovers standing in line.

**證據**

```text
"required": ["date", "name_local", "name_display", "sources"] — impact omitted. scripts/calendar.py:34-37: is_high_crowd returns `bool(h and h.get("impact", {}).get("crowds"))`, i.e. False when impact is absent. skills/calendar-check/SKILL.md:45 lists 'Recording a holiday with no impact' as a Common Mistake: 'Always classify crowds / closures; synthesis acts on them.'
```

**建議修法**

In schemas/calendar.schema.json add "impact" to the holiday required list and make crowds/closures required booleans within it; add a rejection test in tests/test_schemas.py.

**驗收條件**

jsonschema.validate of a calendar.yaml holiday entry that omits the `impact` object (e.g. {"date": "2026-05-25", "name_local": "x", "name_display": "x", "sources": [{"url": "gov", "official": true}]}) against schemas/calendar.schema.json raises jsonschema.ValidationError, and the same for an `impact` lacking the `crowds` or `closures` boolean, while the existing test_calendar_sample_valid fixture (impact: {crowds: true, closures: false}) still validates — enforced by a new rejection test in tests/test_schemas.py passing in the full pytest sweep.

### TW-041 — Money fields lack discipline: cost.yaml `as_of` not required, leg `fare` currency optional, FX rate has no source/date

- **Severity**: medium
- **位置**: `schemas/cost.schema.json:4`
- **分類**: loose schema / unenforced rule

**問題(failure mode)**

The agent omits as_of (schema passes, no test covers it — grep shows one incidental fixture mention) and pulls an FX rate from training memory instead of a search; the rendered cost-summary block presents a dated/undated total as current, and a currency-less JPY fare summed into a KRW primary currency silently corrupts the total that drives the over_budget stop-and-ask decision.

**證據**

```text
"required": ["currency", "line_items", "total"] — as_of and estimate_note are optional despite skills/cost-rollup/SKILL.md:40 "Write cost.yaml with as_of + estimate_note"; fx_rate (line 15) carries no source URL or as-of date; and schemas/legs.schema.json:21 "fare": {"type": "object", "properties": {"amount"..., "currency"...}} has no required, so a currency-less fare validates. [corrected: All cited path:line quotes verified exact. One trivial correction: as_of appears in TWO incidental positive fixtures, not one — tests/test_schemas.py:311 and tests/test_e2e_cost.py:43, both '"as_of": "2026-06-05", "estimate_note": "estimate; prices vary"' — neither is a negative/enforcement test, so the finding's point stands unchanged.]
```

**建議修法**

In schemas/cost.schema.json move as_of (and estimate_note) into required and add fx_as_of/fx_source properties referenced by skills/cost-rollup/SKILL.md's currency section; in schemas/legs.schema.json add "required": ["amount", "currency"] to the fare object (and to pass.price); extend tests/test_schemas.py with the negative cases.

**驗收條件**

tests/test_schemas.py gains negative cases that pass under pytest: jsonschema.validate raises ValidationError when (a) a cost.yaml document valid in all other respects omits `as_of`, and (b) a legs.yaml leg includes `fare: {"amount": 15000}` with no `currency` (and pass.price likewise) — i.e., schemas/cost.schema.json lists `as_of` in `required` and schemas/legs.schema.json's fare object declares `"required": ["amount", "currency"]`.

### TW-042 — transit.yaml walks and peak_windows require no sources — invented station walks are schema-valid

- **Severity**: medium
- **位置**: `schemas/transit.schema.json:18`
- **分類**: hallucination surface / loose schema

**問題(failure mode)**

The agent fills mins from training-data intuition ('Gion is about 5 min from the station') without any search; the number feeds scripts/transit.py::walk_too_far, so a real 25-minute uphill walk is never flagged and the elder-including group the stage exists to protect gets routed onto it — with no source trail to audit.

**證據**

```text
"walks": {"type": "array", "items": {"type": "object", "required": ["poi_id", "mins"], ...}} — no sources property exists for walks or peak_windows (only ic_card has one), and even station is optional, while skills/transit-detail/SKILL.md:25 says "Research from maps / official station info; never invent a distance." [corrected: schemas/transit.schema.json:18-22 — "walks": {"type": "array", "items": {"type": "object", "required": ["poi_id", "mins"], "properties": {"poi_id": ..., "station": ..., "mins": ..., "note": ...}}} (no sources; station optional; peak_windows items at lines 6-10 likewise have no sources). SKILL.md quote is at skills/transit-detail/SKILL.md:23-24 (not :25): "Research from maps / official station info; never invent a distance."]
```

**建議修法**

In schemas/transit.schema.json add a required sources array (minItems 1, url-pattern) to walks items and peak_windows items, and make station required on walks; update skills/transit-detail/SKILL.md's output description and tests/test_schemas.py.

**驗收條件**

A pytest in tests/test_schemas.py asserts that jsonschema validation against schemas/transit.schema.json REJECTS a transit.yaml fixture whose walks[0] has poi_id and mins but lacks station or lacks a non-empty sources array (and whose peak_windows[0] lacks a non-empty sources array), and ACCEPTS the same fixture once walks[0] has station plus sources: [{url: "https://..."}] and peak_windows[0] has sources: [{url: "https://..."}] (sources arrays enforced with minItems: 1).

### TW-043 — lat/lng accept any number — swapped or placeholder coordinates validate in all three geocode-bearing schemas

- **Severity**: medium
- **位置**: `schemas/verified-pois.schema.json:22`
- **分類**: schema strictness

**問題(failure mode)**

When the agent transcribes coordinates (e.g. from a cached raw Nominatim response or a web source) it swaps lat/lon — Seoul becomes lat 126.98, lng 37.58, physically impossible yet schema-valid. If POIs and cluster centroids are swapped consistently, in_region and classify_hop produce plausible numbers so no gate fires, and the exported Google-Maps coordinate links and routing distances are garbage. Placeholder lat:0,lng:0 also validates.

**證據**

```text
"properties": {"lat": {"type": "number"}, "lng": {"type": "number"}, ...} — no minimum/maximum. Same in schemas/accommodations.schema.json:28-30 and schemas/routing.schema.json:11-12 (centroid). A repo-wide grep shows the only minimum constraints anywhere in schemas/ are on nights/max_gap_nights. Nominatim returns the longitude under the key "lon" (scripts/geocode.py:32) while the schema field is "lng".
```

**建議修法**

Add "minimum": -90, "maximum": 90 to lat and "minimum": -180, "maximum": 180 to lng in verified-pois, accommodations, and routing schemas; add schema tests rejecting lat 126.98.

**驗收條件**

jsonschema validation must REJECT a swapped-Seoul geocode {lat: 126.98, lng: 37.58} in all three coordinate-bearing locations — verified-pois pois[].geocode, accommodations lat/lng, and routing clusters[].centroid — and must still ACCEPT the correct {lat: 37.58, lng: 126.98}; i.e. a pytest asserting lat bounds [-90, 90] and lng bounds [-180, 180] fail/pass accordingly against schemas/verified-pois.schema.json, schemas/accommodations.schema.json, and schemas/routing.schema.json.

### TW-044 — export_gate's _find_row checks the FIRST line containing a POI name — a heading or prose mention shadows the actual table row, causing false fails (un-fixable re-render loop) or masked misses

- **Severity**: medium
- **位置**: `scripts/export_gate.py:67`
- **分類**: fragile script (export gate)
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

The itinerary titles a day after its booking-required highlight restaurant. export-gate matches the heading line first, finds no official link there, and reports 'bookable POI row missing official source link' even though the actual table row (with the 官網 link) is correct. Per skills/export-gate/SKILL.md:27 the agent returns to export-artifact to re-render — which deterministically produces the same heading → an infinite fail/re-render loop (or the agent 'fixes' it by renaming the day, degrading the deliverable). The mirror case (an early checklist line that happens to contain name+official URL before a defective table row) yields a false pass on a day row missing the link.

**證據**

```text
export_gate.py:67-72: `def _find_row(md_text, names): for line in md_text.splitlines(): if any(name and name in line for name in names): return line` — returns the first match anywhere in the document; run_export_gate:49 then requires `official in row` on that single line. render_day_table (markdown.py:39) emits `### {label}` BEFORE the table rows, and day labels naturally contain the headline POI (e.g. '### Day 2 · Milford Sound 郵輪日'). [corrected: /home/user/hp_workspace/tripwork/scripts/export_gate.py:67-72 `def _find_row(md_text, names): ... for line in md_text.splitlines(): if any(name and name in line for name in names): return line`; export_gate.py:49 `if not official or official not in row:`; scripts/render/markdown.py:39 `lines = [f"### {md_escape(day.get('label', ''))}", "", "| 時段 | 行程 |", "|---|---|"]`; skills/export-gate/SKILL.md:26-27 "On `status: fail` ... return to `export-artifact` via `tripwork:orchestrator` to re-render." (all citations accurate; SKILL.md quote spans lines 26-27 rather than 27 alone). Reproduced live: correct rendered row + heading "### Day 2 · Milford Sound 郵輪日" → status fail, "bookable POI 'milford' row missing official source link"; mirror fixture (early prose line with name+official URL, defective row) → status pass.]
```

**建議修法**

In scripts/export_gate.py::_find_row, restrict candidate lines to markdown table rows (line.startswith('|')) and collect ALL matching table lines, passing if any contains the official URL (fail only when all matching rows lack it). Add a test with a `### Day` heading naming the bookable POI above a correct table row in tests/test_export_gate.py.

**驗收條件**

A pytest in tests/test_export_gate.py builds a markdown fixture where a '### Day 2 · <POI name_display>' heading precedes a table row '| 09:00 | [<POI name_display>](https://maps...) · [官網](<official url>) |' for a verified booking-required POI, and asserts run_export_gate(md, pois)['status'] == 'pass' with check bookable_has_official_source passed; the same fixture with the 官網 link removed from the table row (heading unchanged) must yield status 'fail' with the bookable-POI failure message.

### TW-045 — resolve_place with an empty/None name silently geocodes the city itself — a 'successful' city-centroid result that trivially passes the in_region gate

- **Severity**: medium
- **位置**: `scripts/geocode.py:45`
- **分類**: geocode correctness trap

**問題(failure mode)**

A candidate reaches source-verify with name_local as an empty string (the candidates schema only requires the key, type string). resolve_place 'succeeds' with the district/city centre coordinates, Gate 2 and Gate 3b both pass, and the POI is marked verified carrying coordinates of downtown rather than the venue — feeding wrong distances into routing-audit and a wrong reference point into accommodation checks, with no conflict ever raised.

**證據**

```text
geocode.py:44-50: `params = {"format": "json", "limit": 1}; if name: params["street"] = name; if city: params["city"] = city ...` — with name None/'' the structured query degrades to a city(+country)-only search, and Nominatim returns the city's own centroid as data[0]; geocode_structured returns it as a normal GeocodeResult (lines 57-59) with source 'nominatim_structured'. Nothing compares display_name against the queried venue name, and in_region (line 37) against the district centroid passes by construction. The free-text fallback (resolve_place:82) has the same property: `q = " ".join(p for p in (name, district, country) if p)` becomes just the district/country.
```

**建議修法**

In scripts/geocode.py::resolve_place (and geocode_structured), raise ValueError("resolve_place requires a non-empty place name") when name is falsy after strip(), so a blank name_local surfaces as an actionable error at the verify stage instead of a fake hit. Optionally also add minLength: 1 to name_local in candidates/verified-pois schemas.

**驗收條件**

A pytest in tests/ asserts that scripts.geocode.resolve_place raises ValueError for name=None, name="", and name="   " (whitespace-only) — with requests.get monkeypatched and asserted to have been called zero times, proving no Nominatim query is issued for a blank place name.

### TW-046 — load_cache has no error handling and save_cache is non-atomic — an interrupted run corrupts the file and crashes every later run uninformatively

- **Severity**: medium
- **位置**: `scripts/geocode_cache.py:29-34`
- **分類**: fragile script

**問題(failure mode)**

A stage interrupted mid-save (agent killed, stop-on-confirmation mid-write, disk full) leaves a truncated geocode.json. The next source-verify / accommodation-research run dies in load_cache with a bare json.JSONDecodeError before verifying anything — the stage is wasted and the agent's natural recovery is to hand-rewrite the file (feeding the poisoning surface in finding 1) or delete all accumulated entries. A non-dict JSON (e.g. a list) loads 'successfully' and then fails later inside cache_put with a confusing TypeError.

**證據**

```text
load_cache: "with open(path, encoding=\"utf-8\") as f:\n        return json.load(f)" — no try/except, no isinstance-dict check. save_cache (geocode_cache.py:42-43): "with open(path, \"w\", encoding=\"utf-8\") as f:\n        json.dump(cache, f, ...)" — truncate-in-place, not write-temp-then-rename. tests/test_geocode_cache.py has no malformed-file test (only missing-file → {} at line 25-26).
```

**建議修法**

In scripts/geocode_cache.py: wrap load_cache's json.load in try/except (json.JSONDecodeError, OSError) and on failure return {} (optionally renaming the bad file to geocode.json.corrupt so evidence is kept); also return {} if the parsed value is not a dict. Make save_cache atomic: dump to path + '.tmp' then os.replace. Add tests: corrupted file → {}; non-dict JSON → {}.

**驗收條件**

A pytest in tests/test_geocode_cache.py passes which (a) writes truncated JSON (e.g. '{"k": ') and separately a non-dict JSON value (e.g. '[1, 2]') to the cache path and asserts load_cache(path) returns {} without raising, and (b) monkeypatches json.dump to raise mid-write inside save_cache and asserts that an existing valid geocode.json at the target path still round-trips via load_cache afterwards (i.e. save_cache writes to a temp file and os.replace's it, never truncating the target in place).

### TW-047 — closing_status returns plain 'closed' for venues closing after midnight, with no machine-readable signal that the overnight special case applies

- **Severity**: medium
- **位置**: `scripts/hours.py:44`
- **分類**: numeric edge case (midnight-crossing hours)
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

source-verify records an izakaya's verified hours as close: "02:00". Synthesis mechanically runs closing_status over every timed slot per SKILL.md:26 and every evening slot returns 'closed', so the agent dutifully moves or drops a perfectly open venue — or fires a spurious must-do stop-and-ask. Worse, the agent learns to distrust the script's output and starts overriding it, eroding the mechanical check for genuinely closed venues. The 'manual special case' instruction only works if the agent notices the small-hours close value before calling the function, which the loop discipline discourages.

**證據**

```text
hours.py:44: `if s >= c: return "closed", f"scheduled {start} is at/after closing {close}"` — empirically closing_status("22:00", "02:00") -> ('closed', ...) for a bar that is in fact open; close="01:00" gives c=60 so every evening start returns 'closed'. The docstring (hours.py:36-37) and itinerary-synthesis/SKILL.md:30 ('Overnight hours (close past midnight) are not handled by closing_status — treat as a manual special case') delegate to the agent, but the function's return is indistinguishable from a genuine closure and nothing detects close<start to remind the agent mid-loop. No overnight test exists (tests/test_hours.py). [corrected: Minor line drift only: the quoted condition+return span scripts/hours.py:43-44 (`if s >= c:` at :43, `return "closed", f"scheduled {start} is at/after closing {close}"` at :44), not :44 alone. All other citations (hours.py:36-37 docstring, itinerary-synthesis/SKILL.md:26/28/30, absence of overnight tests in tests/test_hours.py) are exact. Additional supporting evidence: scripts/facilities.py:49 `status, _ = closing_status(arrival, reception_close)` inherits the same false-'closed' for past-midnight reception hours.]
```

**建議修法**

In scripts/hours.py::closing_status, detect the overnight window (to_minutes(close) < to_minutes(start) and to_minutes(close) <= 5*60, or an explicit overnight=True arg) and either handle it (extend close by 1440) or return a distinct status like ('overnight', 'close 02:00 is past midnight — verify manually') so the agent gets a machine-readable sentinel instead of a false 'closed'. Add tests for a 22:00-arrival/02:00-close venue and update itinerary-synthesis SKILL.md line 30 to reference the sentinel.

**驗收條件**

tests/test_hours.py contains an overnight-close test asserting closing_status("22:00", "02:00", last_call="01:00", need_mins=60)[0] != "closed" — it must instead return either "ok" (with close extended past midnight in the buffer arithmetic) or a documented machine-readable sentinel status (e.g. "overnight"), and that exact status string must appear in skills/itinerary-synthesis/SKILL.md's closing-buffer section in place of the current "manual special case" wording.

### TW-048 — Deliverable maps links discard the verified coordinates — name-only Google search can land on the wrong branch/city

- **Severity**: medium
- **位置**: `scripts/render/gmaps_links.py:9`
- **分類**: inconsistent artifacts

**問題(failure mode)**

For chain restaurants (一蘭, 鼎泰豐), common shrine/temple names, or hotels with multiple properties in one city, the Google Maps search resolves to whichever branch ranks first — not the verified one. The user navigates to the wrong branch even though tripwork verified the right coordinates; the verification result never reaches the deliverable.

**證據**

```text
gmaps_links.py:9-11: `def maps_url(poi): return BASE + quote(_query_name(poi))` where _query_name is just name_local — neither district nor the verified geocode.lat/lng is used in the link. The whole source-verify Gate 2/3 effort pins exact coordinates (verified-pois.schema.json requires them), yet the user-facing link is a bare name search. README.md:147 claims the link is "搭計程車／導航最準". [corrected: /home/user/hp_workspace/tripwork/scripts/render/gmaps_links.py:6-11 — `def _query_name(poi): return poi.get("name_local") or poi.get("name_display") or poi.get("id", "")` and `def maps_url(poi): return BASE + quote(_query_name(poi))` (_query_name is at lines 6-7, maps_url at 9-11; otherwise the cited evidence is exact). README claim confirmed at /home/user/hp_workspace/tripwork/README.md:147: "（用當地語言店名，搭計程車／導航最準）". Schema requirement confirmed at /home/user/hp_workspace/tripwork/schemas/verified-pois.schema.json:11 (required includes "geocode", "district"; geocode requires ["lat","lng"]).]
```

**建議修法**

In scripts/render/gmaps_links.py, disambiguate the query: quote(f"{name_local} {district}") when district exists, or use the coordinate-pinned form query={lat},{lng} for POIs whose geocode is present (keeping the name as the link label). Update tests/test_render_gmaps.py accordingly.

**驗收條件**

tests/test_render_gmaps.py 含一個通過的 pytest：給定 POI fixture {"name_local": "一蘭", "name_display": "一蘭拉麵", "geocode": {"lat": 35.6595, "lng": 139.7005}}，斷言 maps_url(poi) 回傳的 URL 的 query 參數內含釘住的座標（URL 包含 "35.6595%2C139.7005" 或 "35.6595,139.7005"），且 link_markdown(poi) 的可見 label 仍為 "一蘭拉麵"（座標只進 URL、不進 label）。

### TW-049 — line_short has no handling for LINE's 5000-character message cap — long trips render an unsendable deliverable

- **Severity**: medium
- **位置**: `scripts/render/line_short.py:19`
- **分類**: ungated adapter / missing constraint

**問題(failure mode)**

A 10–14 day multi-stop trip with per-day items, transit notes, and CJK day labels exceeds LINE's hard 5000-character single-message cap. The user copy-pastes exports/line-short.txt into LINE and the send is rejected or they paste it in app-truncated form — the elder receives an itinerary that cuts off mid-trip. No gate or test ever measures the file, so the pipeline reports success. Export-gate theoretically cannot catch it (it reads only the markdown deliverable).

**證據**

```text
line_short.py:19 returns the unbounded join: `return "\n".join(lines).rstrip() + "\n"` — no length measurement, no split, no warning anywhere (grep for "5000"/length across skills+scripts finds nothing). tests/test_render_line.py:3-22 asserts only happy-path substrings ("🐠 水族館", "http" not in out). README.md:36 promises the deliverable as directly shareable: "一鍵輸出 Markdown（含地圖連結）、LINE 短文、Notion".
```

**建議修法**

In scripts/render/line_short.py, have render_line_short return a list of message chunks split at day boundaries when the total exceeds a LIMIT=5000 constant (or emit line-short-1.txt/-2.txt parts), and document the split in skills/export-artifact/SKILL.md adapter 3. Add a test in tests/test_render_line.py rendering a long synthetic trip and asserting every chunk is <= 5000 chars and splits only at a DIVIDER boundary.

**驗收條件**

在 tests/test_render_line.py 新增測試：建構一個合成 itinerary（如 14 天、每天 10 個 items），其單一字串渲染長度 > 5000 chars；對其呼叫 render_line_short（或 export 路徑），assert 輸出為多個 message parts，且 (a) 每個 part 的 len() <= 5000，(b) 切分只發生在 day 邊界（每個非首 part 以 DIVIDER + day label 開頭），(c) 所有 parts 串接後包含原行程的每一個 day label——pytest 全綠即通過。

### TW-050 — season.py ignores timezone offset, DST, and longitude-within-zone — real error is ~2 hours in the plugin's flagship NZ self-drive case, not the documented ±15-20 min

- **Severity**: medium
- **位置**: `scripts/season.py:5`
- **分類**: correctness trap (wrong timebase)

**問題(failure mode)**

On a summer NZ self-drive trip (the skill's own example destinations Tekapo/Te Anau), every leg arriving 19:45-21:20 is flagged after_dark_arrival: true though the sun is well up; synthesis then prints wrong 'arrives after sunset; start earlier' advice and a sunset time ~2h early on day rows. In the mirror geometry (east of a zone meridian, no DST) genuinely-dark arrivals pass unflagged. Any DST country in summer exceeds the stated tolerance by ~1h.

**證據**

```text
season.py:4-6 docstring: "Uses local SOLAR time (solar noon = 12:00), ignoring longitude-within-timezone and the equation of time, so sunset is accurate to ~±15-20 min". after_dark (season.py:42-46) compares an itinerary CIVIL clock time against this solar sunset. Empirically approx_sunset("2026-01-15", -45.03) (Queenstown) -> "19:32", while actual civil sunset is ~21:25 NZDT — off by ~1h50m (NZDT is UTC+13: +1h DST plus Queenstown sitting 26° west of the 195°E zone meridian). skills/seasonal-advisory/SKILL.md:38-41 instructs flagging "any driving leg whose estimated arrival is after_dark(arrival, date, lat)" and repeats the false "~±15-20 min" claim. [corrected: /home/user/hp_workspace/tripwork/scripts/season.py:3-5 (not 4-6): "Solar-declination + hour-angle model. Uses local SOLAR time (solar noon = 12:00), / ignoring longitude-within-timezone and the equation of time, so sunset is accurate / to ~±15-20 min". after_dark at scripts/season.py:42-46 as cited. /home/user/hp_workspace/tripwork/skills/seasonal-advisory/SKILL.md:37-41 (not 38-41): "flag any driving leg whose estimated arrival is `after_dark(arrival, date, lat)` — emit an `advisory` item ... The computation is approximate (local solar time, ~±15-20 min)". Empirical reproduction: approx_sunset("2026-01-15", -45.03) == "19:32"; after_dark("20:30", "2026-01-15", -45.03) == True despite actual Queenstown civil sunset ~21:26 NZDT. Additionally skills/itinerary-synthesis/SKILL.md:67-68 prints the (solar) sunset on day rows, making the ~2h error user-visible.]
```

**建議修法**

In scripts/season.py, pass lng and utc_offset_hours into approx_sunset/after_dark and convert solar to civil time: civil_sunset = solar_sunset + (utc_offset*15 - lng)/15 hours (data already available — geocode has lng; trip-brief/seasonal skill can carry the destination UTC offset). Correct the accuracy claims in the docstring and skills/seasonal-advisory/SKILL.md:41, and add a Queenstown-summer regression test.

**驗收條件**

A pytest regression in tests/ passes asserting that scripts/season.py's sunset functions accept longitude and UTC offset and convert solar to civil time: for Queenstown in summer (date 2026-01-15, lat -45.03, lng 168.66, utc_offset_hours 13.0), approx_sunset returns a time within ±20 minutes of 21:25, and after_dark("20:30", ...) with the same parameters returns False.

### TW-051 — Hotel centroid fallback grants `verified` to a hotel Nominatim cannot find, removing the only existence cross-check

- **Severity**: medium
- **位置**: `skills/accommodation-research/SKILL.md:26`
- **分類**: gate bypass / hallucination surface

**問題(failure mode)**

The agent half-remembers or conflates a hotel name in recommend-mode; Nominatim's NO_RESULT (the one signal that the place may not exist) is converted into an automatic pass via the centroid, the entry is listed verified among the 3 candidates, and the exported maps link (built from name_local) plus the town-centre pin send the user/taxi to a hotel that doesn't exist or is elsewhere.

**證據**

```text
"On NO_RESULT, fall back to the stop's cluster centroid from routing.yaml (geocode.geocode_source: cluster_fallback); the hotel is in the stop town by definition, so it stays verified." — combined with Gate 1's uncounted-quality sources, geocode no longer functions as an existence check for lodging specifically. [corrected: /home/user/hp_workspace/tripwork/skills/accommodation-research/SKILL.md:25-28 — "On NO_RESULT, fall back to the stop's cluster `centroid` from `routing.yaml` (`geocode.geocode_source: cluster_fallback`); the hotel is in the stop town by definition, so it stays `verified`." (quote spans lines 25-28, not just :26; also reinforced at :78 "Rejecting a real hotel Nominatim can't pin | Fall back to the cluster centroid; keep it `verified`." and :33-34 "Centroid fallback is trivially in-region.")]
```

**建議修法**

In skills/accommodation-research/SKILL.md, gate the cluster_fallback on an existence proof: allow verified with cluster_fallback only when at least one source is the hotel's own official or booking-platform page (record official: true/booking.url); otherwise degrade to unverified for manual confirmation. Also have export render an 'approximate location' note whenever geocode_source == cluster_fallback.

**驗收條件**

A pytest fixture exercising the accommodation verification path with a candidate whose resolve_place returns NO_RESULT (geocode_source: cluster_fallback) and whose sources contain no entry marked as the hotel's official site or a booking-platform page must yield status == "unverified" (not "verified"); an otherwise-identical fixture with one booking-platform/official source must remain "verified" with geocode_source == "cluster_fallback" recorded in accommodations.yaml.

### TW-052 — calendar-check never requires the official source to cover the trip year — prior-year substitute holidays can be extrapolated

- **Severity**: medium
- **位置**: `skills/calendar-check/SKILL.md:15`
- **分類**: hallucination surface / missing operational criterion

**問題(failure mode)**

For a trip ~12+ months out, the official page found by search covers only the current year; the agent (or its training data) extrapolates substitute/make-up days — which shift year to year — and writes a schema-valid calendar.yaml with a wrong observed-holiday date. Synthesis then steers crowd-fragile POIs onto the actual packed day and treats the wrong day as closure-risky.

**證據**

```text
"Use the consumer harness WebSearch; prefer the **official** government holiday calendar" + line 16 "List every public holiday that falls within the trip range, **including substitute/observed holidays**" — but nothing requires confirming the cited calendar actually covers the trip year, and nothing defines behaviour when the destination has not yet published next year's calendar (e.g. Japan's Cabinet Office publishes annually).
```

**建議修法**

Add to skills/calendar-check/SKILL.md: the official source must explicitly state the trip year's dates; if the trip-year calendar is not yet published, mark affected entries provisional: true (add the field to schemas/calendar.schema.json) and surface this to the user as a re-check item in the pre-trip checklist rather than silently extrapolating.

**驗收條件**

A single pytest passes that (a) validates a fixture calendar.yaml containing a holiday entry with `provisional: true` against schemas/calendar.schema.json, and (b) asserts skills/calendar-check/SKILL.md contains an explicit rule (regex on the Method or Common Mistakes section) that the official source must explicitly state the trip-year dates, and that when the trip-year calendar is not yet published the entry must be marked `provisional: true` and surfaced as a pre-trip re-check item instead of being extrapolated from a prior year.

### TW-053 — Orchestrator rule 3 predicate 'stale' (and 'ready') is undefined — re-runs of destination-research leave new candidates permanently unverified

- **Severity**: medium
- **位置**: `skills/orchestrator/SKILL.md:33`
- **分類**: undefined-predicate
- **獨立 reviewer 重複發現次數**: 2

**問題(failure mode)**

Mid-pipeline the user says "also add temple X" (or 'a few more restaurant options'); destination-research appends to candidates.yaml. On the next orchestrator pass, verified-pois.yaml exists and the agent has no criterion to call it stale, so rule 3 is skipped and the new candidates never reach source-verify — they silently vanish from the plan with no recorded reason (violating never-silently-drop), or a must_do burns through 7 more stages before synthesis halts with an undefined repair path. The opposite misreading treats any re-touch as stale and re-runs full verification (rate-limited Nominatim re-geocoding) wastefully.

**證據**

```text
"3. candidates exist but verified-pois.yaml stale/missing -> run source-verify." 'stale' appears nowhere else in the repo (grep over skills/, scripts/, tests/, README confirms sole occurrence) — no mtime rule, no coverage rule (every candidates.yaml id must appear in verified-pois.yaml), no candidate-id diff, no hash. All other Stage Selection rules are simple file-existence checks; this is the only judgment call and it is unoperationalized. The rules' 'ready' ("verified-pois ready", "calendar ready") is likewise never defined.
```

**建議修法**

In skills/orchestrator/SKILL.md define the predicate inline at rule 3: "stale = any candidates.yaml id absent from verified-pois.yaml pois[], or candidates.yaml mtime newer than verified-pois.yaml — re-verify only the missing/changed ids, reusing the geocode cache"; and define 'ready' once ("exists, schema-valid, and contains >=1 verify_status: verified item") for rules 4-15.

**驗收條件**

skills/orchestrator/SKILL.md rule 3 states a mechanical staleness predicate ("stale = at least one candidates.yaml candidate id absent from verified-pois.yaml pois[]; re-verify only those ids, reusing the geocode cache") and defines "ready" once for rules 4-15; a pytest exercises the predicate against two fixtures — (a) candidates.yaml containing id "temple-x" absent from an otherwise stage-complete verified-pois.yaml must evaluate stale=True (stage selection yields source-verify, not a later stage), and (b) an id-coverage-complete candidates/verified-pois pair must evaluate stale=False (source-verify is not re-selected).

### TW-054 — orchestrator Stage Selection 用裸 skill 名（與 paperwork 的 export-artifact / workspace-shape-preflight / orchestrator 撞名），跨 plugin 誤路由面

- **Severity**: medium
- **位置**: `skills/orchestrator/SKILL.md:44`
- **分類**: cross-plugin name collision

**問題(failure mode)**

代理執行 orchestrator step 14 的「run `export-artifact`」時必須自行在兩個同名 skill 之間解析；context 線索「gate 剛 pass」兩邊 description 都吻合。一旦解析到 paperwork:export-artifact，代理開始找 spec.md / quality-gate / spec-audit artifact，輸出階段以混亂的錯誤或半套 deliverable 收場（行程未正確 export、export-gate 不會被觸發）。

**證據**

```text
orchestrator SKILL.md:30 唯一一處有 namespace：「run `tripwork:workspace-shape-preflight` first」，但 :31-45 全是裸名：「3. … run `source-verify`. … 14. gate-report status==pass, no exports/<slug>-itinerary.md -> run `export-artifact`. 15. … run `export-gate`.」。本環境同時安裝 paperwork，其 export-artifact description（'Use when the designer requests artifact export and quality-gate plus spec-audit have passed'）與 tripwork export-artifact:3（'Use when gate-report status is pass and the itinerary must be exported'）同樣以「gate 過了→export」為觸發鍵；paperwork 也有 orchestrator 與 workspace-shape-preflight 同名 skill。Skill tool 規範 plugin-namespaced skill 必須用 `plugin:skill` 全名。
```

**建議修法**

把 skills/orchestrator/SKILL.md:31-45 的全部 stage 名稱改為 `tripwork:` 全名（與 :30 既有寫法一致）；順手把各 stage SKILL.md 內文殘留的裸名引用（如 itinerary-gate:24 的 `export-artifact`）一併 namespace。可在 tests/test_skills_structure.py 加 test 斷言 orchestrator Stage Selection 各行均含 `tripwork:` 前綴。

**驗收條件**

A test in tests/test_skills_structure.py parses skills/orchestrator/SKILL.md and asserts that no backtick-quoted token exactly equal to any skill directory name under skills/ (e.g. `export-artifact`, `export-gate`, `source-verify`, `trip-brief`) appears without the `tripwork:` prefix; the test fails on the current file (bare names at Stage Selection steps 1-15) and passes after every run-target reads `tripwork:<skill-name>`.

### TW-055 — stage-state.yaml is the designated decision record but has no schema, no format, no example, and no rule ever reads it back

- **Severity**: medium
- **位置**: `skills/orchestrator/SKILL.md:51`
- **分類**: resume-ambiguity

**問題(failure mode)**

Session 1: routing-audit flags a far hop, the user says "keep it", the agent invents an ad-hoc YAML shape and continues. Session 2 (resume, or after work/ is cleaned because it is documented as rebuildable): a re-run that re-detects the same condition cannot find or parse the prior decision (different agent, different invented shape, or file gone), so it re-asks the same already-answered confirmation — or mis-parses the ad-hoc YAML and treats "keep" as "replace", silently dropping the POI the user chose to keep. Each trip accumulates an inconsistent, unvalidated artifact.

**證據**

```text
"Record the decision in work/<slug>/stage-state.yaml before continuing" (also orchestrator:58 "Writes only stage-state.yaml"; same instruction in inter-stop-legs:44, seasonal-advisory:28, cost-rollup:36). schemas/ contains no stage-state schema (12 schemas listed, none for stage-state), no SKILL.md or fixture shows its keys, and none of the Stage Selection rules 0-15 consult it — it is write-only. It also lives under work/, which using-tripwork:64 defines as "rebuildable state + research cache (gitignored)", though user decisions are not rebuildable. [corrected: skills/inter-stop-legs/SKILL.md:44-45 "record the decision in `work/<slug>/stage-state.yaml` before continuing" (finding cited :44). Also note skills/orchestrator/SKILL.md:26 and :57 list `work/<slug>/stage-state.yaml` among Inputs — a nominal declaration only; no Stage Selection rule (lines 30-45) or other instruction reads it, so the write-only-in-practice claim stands.]
```

**建議修法**

Add schemas/stage-state.schema.json (e.g. decisions: [{stage, flag, subject, question, decision, decided_at}]), document the shape + an example in skills/orchestrator/SKILL.md, and add a Stage Selection rule: before re-running any stage, read stage-state.yaml and skip confirmations whose (stage, flag, subject) already carry a decision. Reconsider storing it under trips/<slug>/ since decisions are not rebuildable.

**驗收條件**

A new pytest (e.g. tests/test_schemas.py::test_stage_state_schema_and_readback) passes only when BOTH hold: (1) schemas/stage-state.schema.json exists and successfully validates a checked-in fixture stage-state.yaml whose `decisions` list contains one entry with required keys {stage, flag, subject, decision, decided_at}; (2) skills/orchestrator/SKILL.md's Stop-on-Confirmation section contains an explicit read-back rule string instructing the agent to consult stage-state.yaml before re-asking, and to skip any confirmation whose (stage, flag, subject) tuple already carries a recorded decision.

### TW-056 — The far-hop stop-on-confirmation is driven by an LLM-guessed minutes number with no mechanical floor

- **Severity**: medium
- **位置**: `skills/routing-audit/SKILL.md:13`
- **分類**: hallucination surface

**問題(failure mode)**

The agent optimistically estimates 50 min for a hop that really takes 90 (plausible for cross-city transfers with waiting time). classify_hop returns 'ok', the README-promised '太遠會停下來問你' stop never fires, and the user gets an exhausting day with an elderly parent — the exact pain routing-audit exists to prevent — with no trace that the estimate was a guess.

**證據**

```text
routing-audit SKILL.md step 3: "For each planned inter-district hop, estimate travel minutes (subway/taxi) and classify with scripts/distance.py::classify_hop... Use haversine_km as a sanity bound." distance.py:14-16 is just `return "ok" if mins <= max_hop_mins else "far"` — the mins input is wholly agent-estimated; 'sanity bound' has no formula, no enforcement, and no test (grep tests/ finds no haversine-vs-mins consistency check). README.md:209/216-218 sells this stop as a proven safety valve. [corrected: /home/user/hp_workspace/tripwork/skills/routing-audit/SKILL.md:14 (not :13): "3. For each planned inter-district hop, estimate travel minutes (subway/taxi) and classify with `scripts/distance.py::classify_hop` using `trip-brief.routing.max_hop_mins` (default 60). Use `haversine_km` as a sanity bound." /home/user/hp_workspace/tripwork/scripts/distance.py:14-16: `def classify_hop(mins, max_hop_mins=60): ... return "ok" if mins <= max_hop_mins else "far"`. README citations confirmed as-cited: README.md:209, 216-218, and additionally :223 ("「太遠就停下來問」的安全閥確實會作動").]
```

**建議修法**

Add to scripts/distance.py a min_plausible_mins(km, mode) floor (e.g. urban transit ~15 km/h door-to-door incl. transfers) and make routing-audit SKILL.md require mins >= min_plausible_mins(haversine_km(...), mode), flagging the hop for re-estimation (or a sourced timetable citation) when the agent's estimate is below the floor. Unit-test the floor.

**驗收條件**

scripts/distance.py exposes min_plausible_mins(km, mode) implementing a conservative door-to-door speed floor (urban transit ≈ 15 km/h, so min_plausible_mins(20, "transit") >= 60), and a pytest in tests/ asserts that a hop with haversine_km=20 and an agent-estimated mins=45 (max_hop_mins=60) is NOT classified "ok" by the classification entry point — it returns a distinct "implausible"/re-estimate flag because 45 < min_plausible_mins(20, "transit").

### TW-057 — Negative cache is permanent with no invalidation path — D7 'recorded for manual confirmation' can never recover on re-run

- **Severity**: medium
- **位置**: `skills/source-verify/SKILL.md:15`
- **分類**: negative-cache permanence / unenforced rule

**問題(failure mode)**

A POI misses once (Nominatim gap, transient empty response, or a first-pass query-form mistake) and None is cached under its exact key. Per D7 the user manually confirms the place is real (or OSM later gains the entry); the agent re-runs source-verify expecting re-verification — but resolve_place hits the cached None and returns (None, None) without touching the network, so the POI is re-classified unverified on every single re-run. A must_do POI then triggers the same stop-and-ask loop forever; the user sees 'still cannot resolve' even though a live query would now succeed, with no documented way out.

**證據**

```text
SKILL.md:15: "**D7:** a real place Nominatim cannot resolve degrades to `unverified` (recorded for manual confirmation) — never silently `rejected`. Pass a per-trip cache ... load it once at the start and save it at the end so re-runs skip already-resolved and known-miss lookups." Combined with scripts/geocode.py:74-75 ("if value is None: return None, None") and the design decision at docs/superpowers/specs/2026-06-06-v0.10.0-geocode-cache-design.md:29 ("TTL ... **none**"). Grep across skills/, scripts/, README.md finds zero instruction to delete/refresh a cache entry — the only 'stale' mention is orchestrator SKILL.md:33, which re-runs source-verify against the same cache.
```

**建議修法**

Two-part fix: (1) in skills/source-verify/SKILL.md (and accommodation-research/SKILL.md), add: when the user manually confirms a place or requests re-verification, delete that POI's cache_key entry from work/<slug>/geocode-cache/geocode.json before re-running; (2) in scripts/geocode_cache.py, store negative entries as {"value": null, "cached_at": ...} and have resolve_place treat negative entries older than N days as a miss (positive entries can stay TTL-free). Cover with a test that a stale negative entry triggers a live re-query.

**驗收條件**

pytest: with a geocode cache containing a negative entry {"value": null, "cached_at": <now - 8 days>} for key K and a mocked Nominatim that now resolves K, resolve_place(K..., cache=cache) MUST issue exactly one live request and overwrite the cache entry with the resolved coordinates; with cached_at = <now - 1 day> for the same key, resolve_place MUST return (None, None) with zero network calls.

### TW-058 — Gate 3 region check needs a district reference point that no instruction tells the agent how to obtain

- **Severity**: medium
- **位置**: `skills/source-verify/SKILL.md:16`
- **分類**: missing operational step / hallucination surface

**問題(failure mode)**

Every Gate-3 evaluation forces the agent to invent the reference point: recall the district's coordinates from training memory (hallucination directly inside the iron-rule gate — a wrong remembered centroid flips a genuinely in-district POI to conflicting or lets an out-of-district one pass as verified), or ad-hoc geocode the district name without the rate-limit/cache discipline the skill mandates for POI lookups. Two runs of the same trip can classify the same POI differently.

**證據**

```text
SKILL.md:16: "Geocoded point must also fall within the claimed district (scripts/geocode.py::in_region, region radius defaults to 5 km...)" — but scripts/geocode.py:35 is in_region(lat, lng, region_lat, region_lng, radius_km=5.0): it needs the district's own centroid coordinates. At source-verify time routing.yaml cluster centroids do not exist yet (routing-audit is the NEXT stage, orchestrator SKILL.md:34), and no skill text says where region_lat/region_lng come from.
```

**建議修法**

In skills/source-verify/SKILL.md Gate 3, specify: resolve each claimed district once via scripts/geocode.py::resolve_place(district, city, country) using the same per-trip cache, record the district centroid (e.g. in work/<slug>/), and pass it to in_region; if the district itself returns NO_RESULT, degrade Gate 3b to 'not evaluated' and record that on the POI rather than guessing coordinates.

**驗收條件**

A pytest in tests/ (freshness-style text-contract check) fails unless the Gate 3 section of skills/source-verify/SKILL.md both (a) instructs obtaining the claimed district's centroid by calling scripts/geocode.py::resolve_place on the district with the same per-trip geocode cache (work/<slug>/geocode-cache/geocode.json) before calling in_region, and (b) states that when the district itself returns NO_RESULT, Gate 3b is recorded as not-evaluated on the POI (never classified using guessed/remembered coordinates).

### TW-059 — No cross-stage adversarial e2e fixture: each 'e2e' test exercises one stage in isolation with hand-built dicts, so verify→gate→export interactions are never closed

- **Severity**: medium
- **位置**: `tests/test_e2e_pipeline.py:31`
- **分類**: test gap (cross-defect closure)

**問題(failure mode)**

Any change that is locally green per-stage but wrong across stages — exactly the class this suite cannot catch. Concrete example already live: the conflicting 한방삼계탕 from the verify-stage fixture, if referenced by a day, sails through run_gate (the verify_status gap) and run_export_gate renders it with links — no test composes the stages to detect this, so the regression ships while 261 tests stay green.

**證據**

```text
def test_only_verified_reaches_itinerary(): ... assert verified == ["odarijip"] — the 'pipeline' e2e stops at classify_candidate; nothing then feeds the resulting POI set + a day referencing the conflicting POI into run_gate or run_export_gate. test_e2e_export.py builds its own BOOKABLE dict; test_e2e_calendar.py uses a disjoint POI file (verified-pois-calendar.yaml: gyeongbokgung/hwangsaengga, no overlap with candidates.yaml); test_e2e_accommodation.py calls run_gate([], [], ...) with empty POIs/days. The repo CLAUDE.md pre-ship gate step 7 demands "a single fixture that exercises every defect simultaneously" across the consumer path — no such fixture exists for the main verify→synthesis→gate→render chain.
```

**建議修法**

Add tests/test_e2e_cross_stage.py: load fixtures/e2e-trip/candidates.yaml, classify all candidates with GEO, write the full all-status verified-pois doc (after the schema conditional fix), build days that (a) reference only odarijip → run_gate pass → render_day_table → run_export_gate pass; and (b) adversarially reference hanbang-samgyetang → assert run_gate fails. This single fixture closes the schema-contradiction and verify_status-gate findings plus the verify/gate interaction in one path.

**驗收條件**

A new tests/test_e2e_cross_stage.py passes in the standard pytest sweep that loads the single shared fixture tests/fixtures/e2e-trip/candidates.yaml, runs every candidate through classify_candidate, and chains the resulting POI set into the downstream gates: it asserts (a) a day plan referencing only the verified candidate (odarijip) passes run_gate AND its rendered markdown passes run_export_gate, and (b) an adversarial day plan referencing the conflicting candidate (hanbang-samgyetang) causes run_gate to return a non-pass status — both assertions in the same module against the same fixture, with no hand-built POI dicts bypassing classify_candidate.

### TW-060 — test_readme_freshness 實際斷言遠少於 CLAUDE.md 宣稱的守備範圍——mermaid 順序/成員完全無守門

- **Severity**: medium
- **位置**: `tests/test_readme_freshness.py:35`
- **分類**: guard gap (documented mechanical guard vs actual assertion)

**問題(failure mode)**

未來某 PR 改動 §2 mermaid（移除某 stage 節點、或調動順序），只要該 skill 名還殘留在 step table 或 FAQ 任何角落，freshness 測試照樣全綠、CI 全綠。貢獻者（人或 agent）依 CLAUDE.md 相信「機械守門已涵蓋」而跳過人工核對，README 的 pipeline 圖與 orchestrator 默默分岔——這正是 v0.3.0 設此測試要防的 drift，但守門是空的。使用者照圖理解的流程與實際執行順序不符。

**證據**

```text
測試函式 test_calendar_check_in_pipeline_diagram 的註解寫 "The calendar-awareness stage must be visible in the workflow section, not only in the step table — guards against the mermaid drifting." 但實際斷言只有 `assert "calendar-check" in README`（全文 substring，非 diagram 內）。test_every_skill_mentioned_in_readme（:25-27）同樣是 README 全文 substring 檢查，不檢查 §2 mermaid 的成員或順序。而 repo CLAUDE.md 宣稱 "Mechanical guard: tests/test_readme_freshness.py fails when README drifts — every flow skill must be mentioned, the calendar-check stage must appear in the workflow diagram"，且硬規則要求 "The §2 mermaid is the only main-pipeline diagram. Keep it in sync with the orchestrator stage order."——後者完全沒有機械守門。 [corrected: /home/user/hp_workspace/tripwork/tests/test_readme_freshness.py:35-38 — 'def test_calendar_check_in_pipeline_diagram(): # The calendar-awareness stage must be visible in the workflow section, not only in the step table — guards against the mermaid drifting. assert "calendar-check" in README' (assertion is whole-file substring); :25-27 — 'missing = [n for n in SKILL_NAMES if n not in README]' (whole-file substring, no mermaid membership/order). Corroborating: README.md:112 (mermaid node CAL) vs README.md:133 (step-table row) — substring survives mermaid-node removal. Cited line numbers were accurate; no correction needed.]
```

**建議修法**

在 tests/test_readme_freshness.py 新增：(1) 用 regex 擷取 README 的 ```mermaid 區塊；(2) assert 每個 SKILL_NAMES 中的 pipeline stage 名都出現在 mermaid 區塊內（不是全文）；(3) 將期望的 stage 順序清單（與 test_skills_structure.EXPECTED 同源）依各名稱在 mermaid 區塊中的出現位置排序比對，斷言與 orchestrator 編號順序一致。同時把 test_calendar_check_in_pipeline_diagram 的斷言改為檢查 mermaid 區塊內。

**驗收條件**

tests/test_readme_freshness.py extracts the fenced ```mermaid block from README.md and asserts both (a) every stage skill name (SKILL_NAMES, i.e. all skills minus using-tripwork) appears inside that block and (b) the first-occurrence order of those names within the block equals the canonical orchestrator stage order (same source as test_skills_structure.EXPECTED); verified by mutation: running the test against a README where "calendar-check" is removed from the mermaid block but still present in the §2 step table FAILS, against a README where two adjacent stage nodes are swapped FAILS, and against the unmodified README PASSES.

## LOW

### TW-061 — calendar-check claims 'same rigor as travel-advisory' but requires only one official source where travel-advisory requires official + corroborating

- **Severity**: low
- **位置**: `skills/calendar-check/SKILL.md:20`
- **分類**: inconsistent verification bar between skills

**問題(failure mode)**

An agent cross-reading both skills (e.g. when standalone-invoking travel-advisory, which its frontmatter allows) reconciles the contradiction in whichever direction is cheaper: it cites travel-advisory rules with a single official source ('calendar says that's the same rigor'), dropping the corroboration requirement on safety-relevant regulations — or conversely wastes a verification round hunting a second source for every holiday date. The 'same rigor' phrase actively invites the weaker reading.

**證據**

```text
calendar-check SKILL.md:20: "Each holiday needs >= 1 **official** source (date facts; same rigor as `travel-advisory`)." But travel-advisory SKILL.md:13 sets a stricter bar: "Each item needs >= 1 **official** source (airline notice, government entry portal) plus a corroborating source."
```

**建議修法**

In skills/calendar-check/SKILL.md line 20, delete the '(same rigor as travel-advisory)' parenthetical or replace it with an accurate statement ('one official source suffices for date facts; travel-advisory's regulation items additionally need a corroborating source').

**驗收條件**

A pytest (e.g. in tests/) asserts that skills/calendar-check/SKILL.md (a) still contains the substring ">= 1 **official** source" and (b) contains no case-insensitive occurrence of the phrase "same rigor"; if the file still mentions "travel-advisory" on the holiday-source rule line, that line must also contain the word "corroborating" stating travel-advisory's additional corroborating-source requirement.

## 附錄 A — 建議施工分波(供改善計畫排程參考)

61 條缺失同根因高度群聚,建議按下列波次切版施工,每一波各自走完 8-step pre-ship gate
(TDD red→green → full pytest → e2e closure → matrix 二次 review)再 ship。
波次內 ID 已按依賴排好:同檔修改集中處理,避免跨 PR 衝突。

### Wave 1 — iron-rule 機械化(建議 v0.12.0;全部 critical + gate 強制力)

核心根因:「Source-Verified-First 與排程紀律目前只存在於 SKILL.md 文字,gate 程式碼沒有對應檢查」。

- TW-002 gate.py 檢查 verify_status(本審查最高優先單點修復)
- TW-001 closed_days 詞彙正規化(schema enum + verify/synthesis 寫入規範)
- TW-018 itinerary-gate 重新檢查 poi_closed_on(依賴 TW-001 的正規化)
- TW-017 synthesis 同步輸出結構化 days(sidecar yaml),gate 改吃結構化來源(見 open question Q3)
- TW-003 LINE / 各 adapter 一律從 gated 結構化來源 render(與 TW-017 同根因)
- TW-009 gate-report schema 一致性(status/failures/checks 互斥規則)
- TW-015 export-gate 加最低內容檢查(非空、天數、POI 列數)
- TW-016 sources[].official 生產者補齊(否則 bookable POI 檢查永遠空轉)
- TW-034 advisory.yaml 接上消費者(export-gate 或 synthesis 輸入)
- TW-038 must_do 覆蓋檢查移入 gate.py

### Wave 2 — schema 嚴格化(可併入 v0.12.0 或獨立 v0.12.x)

核心根因:「schema 擋不住幻覺產物:placeholder、typo key、自由字串、缺欄位都能 validate」。

- TW-012 verified-pois if/then 條件化(解 never-silently-drop 矛盾;含 e2e fixture 擴充)
- TW-013 全 schema 加 additionalProperties:false
- TW-006 advisory risk 必填 + 雙來源
- TW-007 date 欄位 ISO pattern(全 schema 一致)
- TW-008 / TW-043 URL format + lat/lng 範圍
- TW-010 legs.mode enum + duration_mins 必填
- TW-011 trip-brief 補 destination/local_lang/airline 欄位
- TW-040 calendar impact 必填
- TW-041 cost 金額紀律(as_of/currency)
- TW-042 transit 來源必填

### Wave 3 — 流程與 skill 契約(建議 v0.13.0)

核心根因:「orchestrator 路由謂詞未定義、stop 清單與 stage 產出脫鉤、entry/standalone 路徑繞過 pipeline」。

- TW-037 using-tripwork 同步 16-stage(入口文件,優先)
- TW-004 itinerary-synthesis frontmatter 觸發條件更新
- TW-028 travel-advisory 階段順序(見 open question Q1,需使用者決定)
- TW-029 / TW-030 / TW-031 orchestrator fail-routing、未擁有的 stop 條件、halt 清單對齊
- TW-027 slug 推導與多行程隔離規則
- TW-053 'stale' / 'ready' 謂詞操作化定義
- TW-054 Stage Selection 改用 plugin-qualified skill 名
- TW-055 stage-state.yaml schema + 範例
- TW-035 travel-advisory standalone 模式寫檔路徑隔離
- TW-036 README 起手式與 skill description 觸發去重
- TW-026 missed_last_service 的 depart 語意修正(legs 階段 vs synthesis 階段分工)
- TW-056 far-hop 門檻機械化(distance.py 已有產出,接上即可)

### Wave 4 — 研究紀律 + scripts 邊界 + cache/adapter + 測試網(建議 v0.14.0)

研究紀律(幻覺面):TW-005(永久歇業檢查)、TW-023、TW-024、TW-032、TW-033、TW-051、TW-052、TW-057、TW-058、TW-061
scripts 數值/邊界:TW-014、TW-020、TW-021、TW-047、TW-050、TW-045
cache 生命週期:TW-019、TW-046、TW-039
export adapters:TW-022、TW-025、TW-044、TW-048、TW-049
測試防護網:TW-059(跨缺陷 adversarial e2e fixture——配合 8-step gate step 7)、TW-060(readme freshness 深化)

## Open Questions(需使用者決定後才能施工)

**Q1(TW-028)travel-advisory 要移到 itinerary-synthesis 之前嗎?**
現況 advisory 在 synthesis 後產出,restricted/banned 法規項永遠無法影響行程內容,且產物無任何消費者(TW-034)。
我推薦:移到 calendar-check 之後、synthesis 之前,理由:(1) 法規(電池、海關、入境)本質上是行程內容的輸入而非附註——banned 項目應該在排程時就排除;(2) 現位置讓 TW-034 無解,advisory 永遠只是死檔案。代價:stage 編號、README §2 mermaid、step table、e2e fixture 全要同步改,屬 consumer-visible 變更,需要你點頭。

**Q2(TW-012)verified-pois schema 放寬方式:if/then 條件化 vs 拆出 rejected-pois.yaml?**
我推薦:if/then 條件化(verified 才強制 geocode + 雙來源),理由:(1) 改動面最小,既有 fixture 與下游讀取邏輯不動;(2) 單檔保留完整 audit trail,符合 never-silently-drop 的原意;拆檔會讓 orchestrator 的 stale 判斷與 gate 的 POI 查找多一個讀取點。

**Q3(TW-017/TW-003)itinerary 要改成結構化 single source of truth 嗎?**
現況 gate 與各 adapter 都靠 LLM 從 itinerary.md 重建 days 結構,重建偏差無機械檢查。
我推薦:synthesis 同時輸出 itinerary.yaml(days 結構)+ itinerary.md(人讀),gate 與全部 adapter 只吃 yaml,md 僅供閱讀,理由:(1) TW-003 / TW-013 / TW-017 三條 critical/high 同根因,一次解掉;(2) gate 從「驗 LLM 自述」變成「驗 artifact」,才符合 mechanical gate 的定位。代價:itinerary-synthesis / itinerary-gate / export-artifact 三個 skill 與 schema 新增一份,屬 Wave 1 最大工程。

**Q4 版本切法**
我推薦:Wave 1+2 = v0.12.0(iron rule 補洞優先,一次把「gate 說了但沒擋」清零)、Wave 3 = v0.13.0、Wave 4 = v0.14.0,理由:(1) Wave 1+2 互相依賴(schema 嚴格化會改 gate 的輸入),拆開反而要過渡相容;(2) Wave 3 是 consumer-visible 文字/流程變更,單獨成版利於 README/mermaid 同步審查。



## 附錄 B — 經 adversarial verify 駁回的 finding(避免重複追查)

| 標題 | 駁回理由(摘要) |
|------|----------------|
| plugin.json description 的 pipeline 字串缺 travel-advisory、itinerary-gate、export-gate 三個 stage | [no-impact] The plugin.json description string is never consumed at pipeline runtime: grep confirms no script or skill reads it, stage routing is owned by the tripwork:orchestrator skill, and the agent's available-skills list independently surfaces tripwork:travel-advisory / itinerary-gate / export-gate with th |
| README 開發者區寫死 "261 個測試"，無守門，下一個 PR 即過期 | [no-impact] The hardcoded "261 個測試" lives only as a shell comment inside the collapsed dev <details> of README.md (line 254). No pipeline stage, skill, gate, schema, or script reads it — an LLM agent running the travel-planning pipeline (trip-brief through export) never consults this number, so itinerary/bookin |
| calendar-check / transit-detail / cost-rollup 的 description 前置條件與 orchestrator 順序不一致，且中途口語觸發會預先生成 artifact 讓正式 stage 被跳過 | [refuted] Evidence quotes are verbatim-accurate (calendar-check/SKILL.md:3, transit-detail/SKILL.md:3, cost-rollup/SKILL.md:3, orchestrator/SKILL.md:37/39/40; 'stale' only at orchestrator step 3), but the interpretation is wrong on three load-bearing points. (1) The descriptions state each skill's DATA prereq |
| README 建議的 superpowers:brainstorming 開場把第一回合交給外部 plugin，無任何 handoff 契約回到 preflight/orchestrator | [refuted] 引文逐字屬實（README.md:66-68），且 grep 確認 skills/、scripts/、tests/ 皆無 superpowers/brainstorming 字樣。但核心詮釋「無任何 handoff 契約回到 preflight/orchestrator」是錯的，理由如下：  (1) handoff 契約存在，且刻意設計為 entry-agnostic，不需點名 superpowers。skills/using-tripwork/SKILL.md:70-73 Stage Contract：「Input \| Any travel-planning request (new or  |
| cache_key is collision-prone ('\|' unescaped, district/country omittable) and source-verify's 'append the district' wording invites district-less keys | [refuted] The quoted evidence exists verbatim (scripts/geocode_cache.py:11-13 cache_key '\|'-join; skills/source-verify/SKILL.md:15 'Append the district/city for disambiguation but keep the core name local'; skills/accommodation-research/SKILL.md:24-25 structured resolve_place call), but the finding's interpre |
