# tripwork 0.33.0 re-gate defects — 2026-08 嘉義 trip 復驗

- 日期:2026-08-09
- 對象版本:**v0.33.0**(consumer 端 `/plugin update` 後的 cache)
- 前一份:`docs/specs/2026-08-08-chiayi-dogfood-defects.md`(對 v0.31.0,TW-062 ~ TW-069)
- 產出方式:拿 0.31.0 時代產出的 `trips/2026-08-chiayi/` 當**未遷移的真實 artifact**,用 0.33.0
  重跑 `gate.py` / `export_gate.py` / `next_stage.py`,並把該 trip 的 POI 逐筆餵回 0.33.0 的
  `verify.py::verify_poi` 做**兩階段控制實驗**(先原樣、再假設 Gate 0 補齊)以分離降級主因。
- 統計:**4 條 confirmed**(critical 1 / high 2 / low 1)。全部是 0.32.0–0.33.0 新修法留下的
  **邊界**,不是回歸 —— 前一份的 8 條有 7 條在這兩版真的關掉了(見附錄 A)。
- 審查焦點:0.33.0 的中心設計是 **re-derivation**(「pure decision functions 存在,卻從沒有人拿它們
  回頭檢查已經寫進 artifact 的判定」)。本輪只問一件事:**那個設計理念自己有沒有留下未覆蓋的格子。**

每條 defect 含:位置(`path:line`,對 0.33.0 cache;行號可能漂移,修復前先逐字核對引文)、
問題、證據、建議方向、驗收條件。**建議方向刻意寫得比前一份淺** —— 依 consumer 要求,
修法設計交給 plugin agent,本文只負責把缺口與量測釘死。

## 缺失總表

| ID | Severity | 子系統 | 標題 | 位置 |
|----|----------|--------|------|------|
| TW-070 | CRITICAL | scripts | re-derivation 五軸涵蓋 legs/hops/cost/closing/lodging,**獨缺一般 POI 的 `verify_status`** — 17/17 已交付 POI 在新規則下全部該降級,gate 卻全綠於該軸 | `scripts/rederive.py:314`(有 lodging)、無 `rederive_pois` |
| TW-071 | HIGH | schemas | `verified-pois.schema.json` 是 `additionalProperties: false` 且無 `resolved_name` — POI 的 Gate 2b **被 schema 主動禁止**記錄可重算所需的欄位,accommodations 卻有 | `schemas/verified-pois.schema.json`(items props)、`schemas/accommodations.schema.json:193` |
| TW-072 | HIGH | scripts | Gate 2c 的 existence proof 兩條路徑對 keyless consumer 不對等 — Gate 0 明文承認 keyless 是誠實結果,Gate 2c 卻沒有等價出路,`verify_status` 因此變成執行環境的函數 | `scripts/verify.py:96`、`skills/source-verify/SKILL.md:30,36` |
| TW-073 | LOW | scripts | `operating_from_status(business_status, today=...)` 對 `today` 不做 ISO 容錯,同函數內 `as_of` 卻走 `_parse_iso` — 傳字串即 `TypeError` | `scripts/verify.py:88-89` |

---

## CRITICAL

### TW-070 — re-derivation 五軸涵蓋 legs/hops/cost/closing/lodging,獨缺一般 POI 的 `verify_status`

- **Severity**: critical
- **位置**: `scripts/rederive.py`(`rederive_legs:88` / `rederive_hops:119` / `rederive_cost:195` / `rederive_closing:238` / `rederive_lodging:314` — 無 `rederive_pois`)、`scripts/gate.py:22`
- **分類**: incomplete re-derivation coverage / stale verdict

**問題(failure mode)**

0.33.0 的立論是:純判定函數早就存在,缺的是「拿它們回頭檢查 artifact 裡已記錄的判定」。這個機制
上線後覆蓋了五個軸,但 **`verify_poi` 自己不在其中** —— 而它正是 iron rule「Only verified flows
downstream」的唯一守門人,也是 0.32.0/0.33.0 兩版改動最大的判定函數(Gate 0 sourced object、
Gate 2b 拒絕缺 `resolved_name`、Gate 2c cluster_fallback existence proof)。

結果是這一版最不該出現的形狀:**判定規則改了三處,而所有既有 artifact 的 `verify_status` 一次都
沒有被重新檢查過**。`rederive_lodging` 對住宿候選做了這件事(所以嘉義的 3 個飯店候選有 failure),
一般 POI 沒有對應物。

gate 因此對一個「17 個 POI 全部不該是 verified」的 artifact,只報 32 個 provenance 缺失,
沒有任何一條指向 `verify_status` 本身。

**證據**

```text
scripts/rederive.py 的全部 rederive_* 函數:
  rederive_legs:88 / rederive_hops:119 / rederive_cost:195 /
  rederive_closing:238 / rederive_lodging:314
  ← grep "^def rederive" 無 rederive_pois。

scripts/gate.py:22 — from scripts.rederive import run_rederivation
scripts/gate.py 的 17 個 check 名稱中,無一項針對 pois[].verify_status:
  referenced_pois_verified 只檢查「itinerary 引用的 POI 在 artifact 裡是否標著 verified」,
  不重算那個標記本身是否仍成立。
```

**量測(兩階段控制實驗,可完全重現)**

拿 `trips/2026-08-chiayi/verified-pois.yaml`(18 POI,17 verified / 1 conflicting)逐筆餵
0.33.0 的 `verify_poi`,`geocoded=bool(geocode)`、`in_claimed_region=True`(沿用原判定)、
`local_lang="zh"`(取自 trip-brief)、`today=date(2026,8,9)`:

第一階段 —— **原樣**:

```text
verified    -> unverified   17     <== 全部降級
conflicting -> unverified    1
降級原因(全 18 筆一致):
  "operating status not established: business_status is self-attested: a bare string
   records a verdict with no source_url and no as_of, so it cannot be reviewed."
```

第二階段 —— 把每筆 `business_status` 換成合規 sourced 形式
(`{status: OPERATIONAL, source_url: https://…, as_of: 2026-08-05}`)以**排除 Gate 0 遮蔽**,
其餘欄位不動:

```text
通過 0 / 仍降級 17
  13 筆:"no resolved_name — Gate 2b (name match) cannot run"   → 見 TW-071
   4 筆:"geocode is a cluster_fallback centroid with no existence proof" → 見 TW-072
       (penshui-turkey-rice / taocheng-guwei / shanzhai-restaurant / atian-goose)
```

同一份 artifact 跑 `python scripts/gate.py trips/2026-08-chiayi`:

```text
status: fail   failures: 32
  13  AI-tone(em_dash 12 / markdown_bold 1)
   6  routing hop 無 duration_source        ← TW-066 修法生效
   9  itinerary row 無 closing_status
   3  accommodations 無 resolved_name       ← rederive_lodging,POI 無對應物
   0  任何指向 pois[].verify_status 的 failure
```

亦即:**gate 報的 32 條裡,沒有一條告訴使用者「這趟行程引用的 POI,依現行規則一個都不是
verified」**。若此刻依 oracle 指示重跑 source-verify,iron rule 會讓 itinerary 引用的 11 個 POI
全部失去來源 —— 行程會空掉,而 gate 事前完全沒有預警。

**建議方向**

補上第六軸(POI 的 `verify_status` 重算),並決定它的失敗如何路由(rule 13.5 目前沒有指向
`tripwork:source-verify` 以外的合理去處)。設計取捨留給 plugin agent,但兩件事值得先想清楚:
① TW-071 是它的硬前置 —— 沒有 `resolved_name` 欄位,Gate 2b 這一格永遠只能回報「不可重算」,
新軸一上線就會對每個既有 trip 產生大量無法自癒的 failure;
② 遷移量體:本 trip 18 筆全數降級,四個 corpus trip 的規模應先量過再決定是一次性 migration
還是分版收斂。

**驗收條件**

`tests/test_rederive.py` + `tests/test_corpus_gate.py`:
(a) 一個 `verified-pois.yaml` fixture,其中某 POI 記 `verify_status: verified` 但
`business_status` 為裸字串,`run_gate` 必須產生一條指名該 POI id 且訊息含 `verify_status`
(或等價語彙)的 failure,且對應 check `passed: false`;
(b) 同一 fixture 把 `business_status` 換成合規 sourced 形式後,該 failure 消失;
(c) 一個 `verify_status: verified` + `geocode_source: cluster_fallback` + 無 existence proof
的 POI,同樣產生 failure;
(d) 對四個 corpus trip 跑 `run_gate`,把新軸的 examined / failures 數字與現有五軸一樣
pin 在 `test_corpus_gate.py`(避免文件與機制再次漂開,比照 0.33.0 已建立的做法)。

---

## HIGH

### TW-071 — `verified-pois.schema.json` 是 `additionalProperties: false` 且無 `resolved_name`,POI 的 Gate 2b 被 schema 主動禁止記錄可重算所需的欄位

- **Severity**: high
- **位置**: `schemas/verified-pois.schema.json`(`pois[].items.properties` 20 個欄位、`additionalProperties: false`)、對照 `schemas/accommodations.schema.json:193`
- **分類**: schema asymmetry / structurally unre-derivable verdict

**問題(failure mode)**

0.33.0 讓 `verify_poi` 在 `resolved_name is None` 時從「靜默跳過 Gate 2b」改為「**拒絕**」——
方向正確(0.31.0 那個 `name_match = True if resolved_name is None` 是前一份 TW-062 點名的洞)。
但 POI 那一側,`resolved_name` **不是沒被記錄,而是不准被記錄**:

| schema | `resolved_name` | `additionalProperties` | Gate 2b 可重算? |
|---|---|---|---|
| `accommodations.schema.json` | 有(:193) | — | 可(`rederive_lodging:357` 讀它) |
| `verified-pois.schema.json` | **無** | **false** | **結構上不可能** |

`additionalProperties: false` 是 TW-013 的修法(防 typo 欄位靜默消失),本身正確;但它與「新 gate
需要一個 schema 未宣告的欄位」相乘,結果是:agent 就算在 source-verify 當下手上握有 Nominatim 回傳的
`display_name`,寫進 artifact 會被 `validate_artifact.py` 判為非法。那個值於是只能被丟棄,
而下一輪任何想重算 Gate 2b 的機制都拿不到它。

這也是 TW-070 的硬前置:先補 `rederive_pois`、後補欄位的話,新軸對每個既有 trip 都會產生
一批**無法用資料修復**的 failure(本 trip 13 筆)。

**證據**

```text
python -c "import json; d=json.load(open('schemas/verified-pois.schema.json'));
           it=d['properties']['pois']['items'];
           print(it['additionalProperties'], 'resolved_name' in it['properties'])"
  → False False

items.properties 實際 20 個欄位:
  booking, business_status, category, closed_days, conflict_note, district, geocode,
  gmaps_place_id, hours, id, name_display, name_local, name_roman, name_zh, photo,
  photo_attribution, photo_source, sources, status_reason, verify_status
  ← 無 resolved_name。

schemas/accommodations.schema.json:193 — "resolved_name": { ... }
scripts/rederive.py:357 — resolved = cand.get("resolved_name")
scripts/rederive.py:360 — f"{where}: no resolved_name — Gate 2b (name match) is not …"
  ← 這條 failure 訊息目前只可能來自 lodging;POI 側連產生它的資料通道都沒有。
```

量測:TW-070 第二階段實驗中,**13 / 17** 筆卡在這一格,是單一最大宗。

**建議方向**

`verified-pois.schema.json` 補 `resolved_name`(對齊 accommodations 的定義),並想清楚
「POI 走 `cluster_fallback` 時 `resolved_name` 該是什麼」—— 那條路徑本來就沒有 geocoder 回傳的
display_name,若一律視為缺失,TW-072 的族群會同時卡 Gate 2b 與 Gate 2c 兩格。這兩條的互動
建議一起設計,不要分兩版。

**驗收條件**

(a) 一個帶 `resolved_name` 的 `verified-pois.yaml` 通過 `scripts/validate_artifact.py`(exit 0);
(b) `verify_poi` 對「`geocode_source: nominatim` + 有 `resolved_name` 且與 `name_local` 相符」
的 POI 回 `verified`,對「同 POI 但 `resolved_name` 為另一家店名」回 `conflicting`;
(c) 一個新增 schema 對稱性測試:凡 `rederive.py` 讀取的欄位,都必須在它所屬 artifact 的 schema
中被宣告(以測試執行時的靜態掃描列舉,新增欄位自動納管) —— 這一條才是防止同型缺口再生的機械保證。

---

### TW-072 — Gate 2c 的 existence proof 兩條路徑對 keyless consumer 不對等,`verify_status` 因此成為執行環境的函數

- **Severity**: high
- **位置**: `scripts/verify.py:96`(`has_existence_proof`)、`skills/source-verify/SKILL.md:30`(Gate 0 三條路線)、`:36`(Gate 2c)
- **分類**: environment-dependent verdict / circular dependency

**問題(failure mode)**

`has_existence_proof` 接受兩種證據:`gmaps_place_id`,或一個 `official: true` 的來源。
SKILL.md:36 把後者描述成 Gate 0 的副產品:「the `gmaps_place_id` captured during the Gate 0
operating check」。

但 SKILL.md:30 自己列的 Gate 0 三條路線,只有第一條會產生 place_id:

| Gate 0 路線 | 需要 key? | 產生 `gmaps_place_id`? |
|---|---|---|
| (1) Places API `businessStatus` | **是** | 是 |
| (2) 店家近期社群貼文 / 官方頁(有日期) | 否 | **否** |
| (3) 行前電話確認(`source_url: tel:…`) | 否 | **否** |

於是 keyless consumer 的 cluster_fallback POI 只剩「official: true 來源」一條路 —— 而
cluster_fallback 的**觸發族群恰恰是 Nominatim 查不到的小店**,這類店最常見的狀態就是沒有官網、
只有社群頁。兩個條件在母體上高度負相關。

更根本的是兩個 gate 對 keyless 的態度不一致:Gate 0 明文承認「When no route is available, leave
the POI `unverified` and put a 行前電話確認營業 line in the checklist; **that is the honest
outcome, not a defect**」——它為 keyless 準備了 route (2)(3) 這兩條真的走得通的路。Gate 2c 沒有
等價出路:它唯一的 keyless 證據(official source)對它自己的目標族群最不可得。

淨效果:**同一份 `candidates.yaml`,有 key 的 consumer 得到的 verified 集合大於 keyless
consumer。** `verify_status` 不再是資料的性質,而是執行環境的性質 —— 兩台機器對同一家餐廳
得出不同的可信度結論,而 artifact 上看不出差別。

附帶一個時序問題:本 repo 的 `gmaps_place_id` 實際上由 **export 階段**的
`scripts/gmaps_media.py` 回填,不是 source-verify 當下記的。所以即使有 key,第一次跑
source-verify 時該欄位仍是空的 —— Gate 2c 讀的是一個由下游階段寫入的欄位,依 pipeline
順序嚴格執行時它不存在。

**證據**

```text
scripts/verify.py:96-108 has_existence_proof(poi):
    if (poi.get("gmaps_place_id") or "").strip(): return True
    return any(s.get("official") for s in (poi.get("sources") or []))

skills/source-verify/SKILL.md:30 — "Routes that actually work, in order:
  (1) **Places API** `businessStatus`, when the consumer has a key …;
  (2) the venue's own recent social post or official page stating current operation, dated …;
  (3) **行前電話確認** (a phone call), recorded as `source_url: tel:<number>` …
  … **When route (1) is used, the Places API response also carries the place's `place_id`
  — record it as `gmaps_place_id`**"
  ← place_id 只掛在 route (1)。

skills/source-verify/SKILL.md:36 — "keeps the POI `verified` ONLY when something independent
  of the coordinate proves the venue exists: a source flagged `official: true`, or the
  `gmaps_place_id` captured during the Gate 0 operating check."
```

量測(`trips/2026-08-chiayi/verified-pois.yaml` 的 8 個 `cluster_fallback` POI):

```text
POI                    place_id  official  has_existence_proof  keyless 下?
penshui-turkey-rice      無        無         False              False
taocheng-guwei           無        無         False              False
shanzhai-restaurant      無        無         False              False
atian-goose              無        無         False              False
chunyen-restaurant       無        有         True               True
xiyanfang                無        有         True               True
qingfeng-taoyue          有        有         True               True
yuxing-yuxiangwu         有        無         True             **False**  ← 只靠 place_id
```

其中 `yuxing-yuxiangwu`(源興御香屋)**已排進交付行程**。有 key 的這台機器判它 `verified`;
keyless consumer 跑同一份 candidates,同一家店會落 `unverified`,行程少一格。

**建議方向**

給 Gate 2c 一條與 Gate 0 route (2)(3) 對等的 keyless 證據路徑,或明確接受「keyless 環境下
cluster_fallback POI 一律 `unverified`」並讓 SKILL 講明後果(比照 Gate 0 已有的誠實聲明)。
兩者都是可辯護的立場,但目前是第三種狀態:規則寫得像有出路,實際只對有 key 的人成立。
另請一併決定 `gmaps_place_id` 的**寫入階段** —— 若它是 Gate 2c 的合法證據,就不該由 export 回填。

**驗收條件**

(a) 一個 `geocode_source: cluster_fallback`、無 `gmaps_place_id`、無 `official` 來源,但帶著
keyless 可得證據(依 plugin agent 選定的設計 —— 例如 `tel:` 來源或 dated 社群頁)的 POI,
`verify_poi` 的結果必須是**設計上明確的**那一個,並有測試釘住;
(b) 一個環境不變性測試:同一份 candidates 在「有 place_id」與「無 place_id」兩種輸入下,
`verify_poi` 的 `verify_status` 差異必須為零,或差異被明確列舉在測試的預期集合中
(即差異是設計決定,不是副作用);
(c) 若採「keyless 一律 unverified」,`skills/source-verify/SKILL.md:36` 必須含與 :30 對稱的
誠實聲明句,並由 `tests/test_skills_structure.py` 斷言其存在。

---

## LOW

### TW-073 — `operating_from_status` 的 `today` 參數不做 ISO 容錯,同函數內 `as_of` 卻走 `_parse_iso`

- **Severity**: low
- **位置**: `scripts/verify.py:88-89`
- **分類**: API asymmetry / latent TypeError

**問題(failure mode)**

同一個函數裡,`as_of` 經 `_parse_iso()` 容錯(接受字串、失敗回 None),`today` 直接參與
`date` 減法。傳入 ISO 字串即 `TypeError: unsupported operand type(s) for -: 'str' and
'datetime.date'`,而且錯誤發生在算式而非入口,訊息不指向真正的原因。

目前 plugin 內唯一的 caller(`scripts/source_verify_run.py:226`)傳的是
`datetime.date.today()`,所以**產品路徑不受影響** —— 這條純粹是介面一致性與未來
caller(例如替 CLI 加一個 `--today` 旗標做可重現測試)的絆索。復現於本次復驗:外部呼叫
`verify_poi(..., today="2026-08-09")` 直接拋出。

**證據**

```text
scripts/verify.py:46-50 —
  def _parse_iso(d):
      try: return datetime.date.fromisoformat(str(d))
      except (TypeError, ValueError): return None

scripts/verify.py:86-89 —
    as_of = _parse_iso(business_status.get("as_of"))
    if as_of is None: return None, "business_status has no valid as_of date"
    ref = today or datetime.date.today()
    age = (ref - as_of).days          ← today 若為 str 即 TypeError

scripts/verify.py:53 — def operating_from_status(business_status, today=None):
  docstring 未說明 today 的型別要求。
scripts/source_verify_run.py:226 — today = datetime.date.today()   (唯一 caller,型別正確)
```

**建議方向**

`ref = _parse_iso(today) or datetime.date.today()`,或在 docstring/型別註記明講只收
`datetime.date`。取捨很小,但兩者擇一即可,別留在中間。

**驗收條件**

`tests/test_verify.py`:`operating_from_status(<合規 sourced object>, today="2026-08-09")`
與 `today=datetime.date(2026,8,9)` 回傳相同結果(若採容錯),或明確拋出帶說明訊息的
`TypeError`/`ValueError`(若採嚴格型別) —— 兩種設計都可,但必須有測試釘住其中一種。

---

## 附錄 A — 前一份(v0.31.0,TW-062 ~ TW-069)的處置狀態

逐條在 0.33.0 cache 上核對過原始碼,不採信 CHANGELOG 宣稱:

| ID | 狀態 | 核對到的實作 |
|---|---|---|
| TW-062 cluster_fallback 全域開放 | **部分修** | `verify.py:96 has_existence_proof` + `classify_candidate(..., geocode_source=)`:`cluster_fallback` 無 existence proof → `unverified`;`GEOCODE_SOURCE_MISSING` 亦為拒絕。**schema 層 `allOf` 約束 deferred 0.34.0**,且既有 artifact 無重算軸(→ TW-070);keyless 對等性未解(→ TW-072) |
| TW-063 business_status 自我宣告 | **已修** | `operating_from_status` 收 `{status, source_url, as_of}`,裸字串明確視為 self-attested → `unverified`;新增 `OPERATING_MAX_AGE_DAYS` recency;`candidates.schema.json` 放寬為 object 形式。SKILL.md:30 改寫成三條「actually work」的路線,並刪掉實測不可行的「WebFetch Google Maps 頁」 |
| TW-064 WebSearch-HALT 綁工具名 | **已修** | iron rule 更名 `No unsourced fact`,改為 provenance 綁定 + 三層 **source ladder**(WebSearch → WebFetch 官方頁 → 搜尋 HTML 端點僅作發現層),`HALT only when every route is unavailable`;9 個 SKILL 各補一行指向 ladder(`grep -rc WebFetch skills/` 由 0 變成每檔 1) |
| TW-065 home drive 無 owner | **已修** | `trip-brief.schema.json:117,121` 新增 `home_origin`/`home_return`(description 直接引用本 trip);`legs.schema.json:26` 新增 `kind`;`gate.py:104 _home_legs_rendered_failures` + check `home_legs_rendered` |
| TW-066 implausible 可調數字規避 | **已修** | hop 需 `duration_source`;`rederive.py:119 rederive_hops` 重算。**本次復驗實測生效**:嘉義 6 個 hop 全被抓出 `no duration_source`,正是當初猜測與上修的那 6 個 |
| TW-067 advisory staleness 用 mtime | **已修** | `next_stage.py` rule 11 改為 content fingerprint(`input_fingerprint(brief_doc, ADVISORY_PROJECTION)`),無 fingerprint 的舊 artifact 才退回 mtime。註解明載動機與本文前一份相同 |
| TW-068 source-verify 無 driver CLI | **已修** | 新增 `scripts/source_verify_run.py`(含 `--offline` / `--official-domain` 旗標,取代 consumer 硬編白名單) |
| TW-069 markdown 無頁級入口 | **已修** | `render/markdown.py` 新增 `render_markdown_page`;itinerary 新增 `contingency` 容器 |

八條裡七條在兩個版本內關掉,其中 TW-064 / TW-067 是照原文件的建議方向實作的。本輪四條新缺口
**全部落在 TW-062 這條唯一未完全關閉的線上**,或落在 0.33.0 新機制自己的邊界。

## 附錄 B — 本次復驗的完整量測

環境:`/home/user/.claude/plugins/cache/tripwork/tripwork/0.33.0`;輸入為 consumer repo
`trips/2026-08-chiayi/`(0.31.0 時代產出,未做任何遷移),複製到 scratchpad 後執行,原檔未改。

```text
$ python scripts/gate.py trips/2026-08-chiayi
gate exit=1   status: fail   checks: 17   failures: 32
  FAIL no_ai_tone / FAIL verdicts_rederivable
  13 AI-tone(em_dash 12 + markdown_bold 1)
   6 routing hop 無 duration_source
   9 itinerary row 無 closing_status
   3 accommodations 無 resolved_name
   0 指向 pois[].verify_status

$ python scripts/export_gate.py trips/2026-08-chiayi
export-gate: pass (retryable=True, distributable=False)   ← 與 0.31.0 相同

$ python scripts/next_stage.py trips/2026-08-chiayi --work-dir work/2026-08-chiayi
next: tripwork:accommodation-research
reason: 'rule 13.5: gate fail routes to tripwork:accommodation-research'
```

verify_poi 兩階段控制實驗結果見 TW-070 內文(原樣 18/18 降級;補齊 Gate 0 後仍 17/17 降級,
拆解為 13 筆 Gate 2b + 4 筆 Gate 2c)。

行程實際引用的 11 個 POI 中,2 個為 `cluster_fallback`:`qingfeng-taoyue`(place_id + official,
keyless 亦通過)、`yuxing-yuxiangwu`(僅 place_id,keyless 不通過 → TW-072)。四個無 existence
proof 的 cluster_fallback POI 均**未**排進行程 —— 這是選店過程的偶然(山寨改由友人訂串燒、
桃城古味僅列為備案),不是任何 gate 擋下的。

## 附錄 C — 流程觀察(非產品 defect,供 plugin agent 參考)

1. **consumer repo 被當成 corpus 就地寫回。** 復驗當下,consumer repo 的
   `trips/2026-06-yilan/`、`2026-07-sun-moon-lake/`、`2026-09-northeast-coast/`、
   `trips/hokkaido-7d/` 四份 `gate-report.yaml` 皆為未提交的 `M` 狀態,mtime 落在
   plugin 發版當日。consumer 端無從分辨哪些是自己跑的、哪些是 plugin 開發跑的。
2. **寫回的內容是中間版本。** `trips/2026-08-chiayi/gate-report.yaml`(當日 14:24)記
   **35** failures;用最終 0.33.0 重跑為 **32**。差額 3 筆全是 `maison-de-chine` 的
   `slot: lodging` 行 closing-buffer failure —— 即 CHANGELOG Migration 明載「Seven corpus
   rows moved out of scope」之前的產物。若 corpus 量測要寫回真實 consumer 目錄,建議
   限定在發版完成後執行一次,或寫到 plugin 自己的 fixture 目錄。
