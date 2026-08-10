# Changelog

## 0.35.0 — guards that measure what they claim: ten audit defects

An adversarial audit of v0.34.0 found ten defects sharing one root cause: a guard obtained the
pipeline state it claimed to check by hand-rebuilding an equivalent copy — a literal number, a
hand-kept list, a manually-summed denominator — instead of calling the shipped function or
constant. The two copies could then drift apart silently, and every real instance in this release
did drift: a consumer fixing their own data turned eight guards red for no plugin defect; a
schema-symmetry allowlist had grown large enough to leave two re-derivation axes with zero fields
under guard; a staleness check had a blind spot for one of the two files it was supposed to be
watching. This release closes all ten (TW-074–TW-083) and, because the pattern repeated across
three releases, writes the rule itself into `CLAUDE.md` so the next instance is caught in review
rather than discovered by audit.

- **TW-074 — corpus figures stop living as literals inside tests.** Every guard that measured the
  consumer corpus (`tests/test_corpus_gate.py`, `tests/test_rederive.py`) had its expected numbers
  typed in by hand at the time it was written. When the consumer later fixed real data using the
  mechanism v0.34.0 shipped, eight of those guards went red with no plugin defect anywhere — the
  corpus had changed, not the code. `tests/corpus_measure.py` now provides `measure_corpus()`,
  built on the same `gate()` / `classify()` / `drain()` machinery the shipped CLI uses, and every
  migrated guard reads its expected values from `tests/corpus-baseline.json` instead of a literal.
  **Regenerate the baseline with `python -m tests.corpus_measure --write`** whenever the corpus
  changes — commit the regenerated diff in the same PR so a human reviews what moved.
  `tests/test_corpus_baseline_is_current.py` fails the suite if the checked-in baseline and a fresh
  measurement disagree, so a stale baseline cannot hide. Before trusting the rewritten guards, the
  original P4-fold deadlock (`scripts/gate.py::poi_pool`) was re-injected by hand: the suite went
  from 15 passed to 8 failed, confirming the baseline swap had not hollowed the guards out.
- **TW-075 — published test counts now name the environment they were measured in.** v0.34.0's
  entry stated "zero skipped or xfailed" for a figure that only holds with the consumer corpus
  mounted; CI (the environment that actually gates a merge) runs without it and produces a lower
  passed count plus a batch of corpus-gated skips — the two numbers cannot both be true of the same
  run. `tests/test_changelog_test_count_is_qualified.py` now requires every `Tests:` line in the
  **newest** CHANGELOG entry to say `CI` or `corpus`; historical entries are left as the point-in-
  time record they are. A matching guard requires the README's `pytest` line to carry the same
  qualifier.
- **TW-076 — the schema-symmetry allowlist had grown large enough to blind two axes completely.**
  `tests/test_schema_symmetry.py`'s allowlist — meant to exempt container-wrapper and sub-object
  field names from the "every field `rederive_*` reads must be schema-declared" check — had grown
  to 45 names, 12 of them ordinary record fields that had no business being exempt. The practical
  effect: `rederive_legs` and `rederive_hops` had **zero** fields under guard, meaning TW-071's
  original deadlock (an unschematized field silently read by a re-derivation axis) could be
  re-injected into either axis and the full suite would stay green. Trimmed to the 9 names that are
  genuinely container wrappers or sub-object fields (`as_of`, `candidates`, `centroid`, `clusters`,
  `district`, `geocode_source`, `hops`, `legs`, `stops`) — two independent derivations of the
  minimal set (one done ahead of the task, one done from scratch during implementation) agreed
  exactly. Fields under guard go from 11 to 26 across all axes, `rederive_legs` from 0 to 8 and
  `rederive_hops` from 0 to 7. Re-injecting TW-071's deadlock now fails immediately
  (`assert not ['last_service_exempt']`).
- **TW-077 — rule 15's staleness check now compares every export deliverable, HTML included.**
  `export_gate.py` reads and judges `exports/<slug>-itinerary.html` whenever it exists
  (`run_html_gate`), but `scripts/next_stage.py`'s rule 15 only ever compared the markdown
  deliverable and the four `EXPORT_GATE_INPUTS` yaml files against `export-gate-report.yaml`'s
  mtime — a re-render that left a stale HTML file (a leftover raw `<script>` tag, say) behind a
  fresh, passing report was invisible to the oracle. No corpus trip happened to exercise the gap,
  which is why it stayed latent through two prior releases. `scripts/orchestration.py` gains
  `EXPORT_DELIVERABLES`, the single source for the `exports/` filename templates; rule 14 and rule
  15 both read it instead of hard-coding the markdown filename a second time, so rule 15 now names
  any stale deliverable, not just the markdown one. Safety check: `next_stage.py`'s routing output
  across all four corpus trips is byte-identical before and after, including the two trips that
  reach rule 16 and so actually exercise the new HTML comparison — no verdict moved.
- **TW-078 — `--audit` now catches a manifest that was never bumped, not just one that lags.**
  `bump_version.py --audit` only grepped every file for the **current** version string, so its one
  real job — catching drift among the eight version-bearing manifests — had a blind spot for the
  single most likely real-world failure: a manifest never added to `.version-bump.json`'s file
  list, therefore never written by `bump()`, therefore stuck on the **previous** version forever,
  invisible to `--audit`, `--check`, and the whole pytest gate at once. `.version-bump.json` gains a
  `previous` field that `bump()` maintains explicitly (`cfg["previous"] = cfg["current"]` before
  overwriting, guarded so re-running `bump()` at the same version cannot clobber it); `audit()` runs
  a second scan, restricted to undeclared `.json`/`.toml` files, for that previous-version string,
  reported under its own heading — restricted to manifest-shaped files on purpose, since CHANGELOG
  and README legitimately reference old versions forever and flagging that would make every future
  `--audit` noisy. An older `.version-bump.json` with no `previous` field skips the second scan with
  an explicit `SKIPPED` line rather than silently doing nothing — this release's own thesis, that a
  check which cannot fail is indistinguishable from one that passed, applies to the release tooling
  itself. Documented limit, deliberately not built out further: this closes a **one-release**
  detection window (a manifest stuck at 0.34.0 is caught bumping to 0.35.0; skip straight to 0.36.0
  and it matches neither scan) — a real version history is scope this task does not take on.
- **TW-079 — the README mermaid order guard now derives from `_CHAIN`, not a hand-kept list.**
  `tests/test_readme_freshness.py`'s `_PIPELINE_ORDER` used to be typed in by hand, parallel to
  `scripts/next_stage.py::_CHAIN` rather than sourced from it — the two could disagree and the
  guard would never notice. Its first 11 entries now derive directly from `_CHAIN`; the trailing 4
  (rule branches 12–16: `itinerary-synthesis` through `export-gate`) stay literal with a comment
  stating why — there is no importable sequence constant covering that stretch. No new test was
  needed: `test_tw060_mermaid_stage_order_matches_pipeline` becomes load-bearing simply by having
  its comparison target now be a real derivation instead of a copy. Verified both directions:
  swapping `calendar-check` and `seasonal-advisory` inside `_CHAIN` now reds that test (it stayed
  green before this fix), and the reverse — editing the README's stage order without updating
  `_CHAIN` — reds it too.
- **TW-080/081/082 — three specific stale claims, plus a wider grep-driven pass.** A CHANGELOG passage
  described the `superseded` bucket's routing using only two of the three `business_status` shapes
  that route there (bare-string, absent), silently omitting the third (a dict-shaped but unusable
  value) while phrasing the pair as exhaustive — corrected to name all three, worded to match the
  code's own reason strings (TW-080). `scripts/rederive.py`'s `run_rederivation` docstring (and a
  duplicate in `tests/test_rederive.py`) claimed `run_gate` "does not forward" `pois` — false since
  v0.34.0 Task 4, which made `scripts/gate.py:333-335` pass `pois=pois` unconditionally; the false
  claim and its dependent consequence were deleted, the still-true part of the surrounding rationale
  kept (TW-081). README's `gmaps_place_id` shape-check line cited an all-corpus count (86)
  inconsistent with the denominator every other figure in its own section used, and both numbers
  were additionally stale; now states both denominators explicitly, measured live: four
  schema-clean trips = 64, all seven corpus trips = 99, both exactly 27 characters (TW-082).
  A follow-up grep-driven pass over `tests/`, `scripts/`, `skills/` for docstrings/comments
  carrying a numeric claim near corpus-shaped language — not another reactive one-site fix — found
  **18 more present-tense corpus figures across 11 files**, of which **4 were outright false**
  against the live corpus, not merely stale: an "0 unresolved" figure recorded as 5 (a full
  inversion, the same shape TW-074 exists to prevent); a "six real trips" denominator that is now
  seven; a "6 legs, all kind-absent" claim now 7 legs (and no longer all kind-absent, since TW-065
  legalized `kind: home` on some of them); and a "two excluded trips" comment now three. Every
  category-(a) hit (a live, unbound, present-tense corpus claim) was de-numbered in favor of
  pointing at `tests/corpus-baseline.json` or a named commit/task/release anchor; bounded historical
  records, synthetic-fixture counts, and code-structure counts were left untouched. A final pass
  re-examined the AI-tone calibration family (~15 sites previously treated as one bounded-historical
  unit) **per site** rather than by blanket rationale, and found three of those specific claims were
  themselves outright false — a cited "31 of 32" em-dash hit and a markdown-bold checklist
  attribution that no longer exist in the live corpus file they named, plus one propagated copy of
  the same false attribution — each rebound explicitly to v0.33.0, the release whose own CHANGELOG
  entry carries the point-in-time figures, rather than merely softened.
- **TW-083 — the rule this release exists to demonstrate, now written down.** `CLAUDE.md` gains
  "Guards must call their subject, not rebuild it": a guard obtains pipeline state by **calling**
  the shipped function or constant (`scripts/gate.py::poi_pool`, `scripts/next_stage.py::_CHAIN`,
  `scripts/orchestration.py::EXPORT_DELIVERABLES`, `tests/corpus_measure.py::measure_corpus`, and
  siblings), never by hand-assembling an equivalent; where no importable source exists, a literal is
  allowed but must say why in a comment; and before trusting a new guard, inject the bug it names
  and confirm it goes red. The rule cites three real instances across three releases as evidence,
  not hypotheticals: v0.33.0's C1 (a corpus guard hand-built `by_id` from 58 rows while the shipped
  gate used 63), v0.34.0's inert re-derive guard (a default fixture that folded nothing, staying
  green through the exact bug it named), and this release's own TW-074/TW-076/TW-079.

**What stays out, recorded rather than silently dropped:**

- A **pre-existing flake**, not introduced by this branch: `tests/test_e2e_mechanized_pipeline.py::test_full_walk_in_new_order`
  fails intermittently (measured 1/90 and 2/30 across two points on this branch, roughly 1–7%) on the
  test's own step-by-step `assert got["next"] == expected` walk against `EXPECTED_WALK`. Which step,
  and why, is not established — no failing run was ever captured with `next_stage.py`'s `reason`
  string attached (the assertion used to report only the step name), and a follow-up 220-run sample
  at HEAD reproduced zero failures. `tests/test_e2e_mechanized_pipeline.py::_next` now returns the
  full `{next, reason}` dict so the next occurrence is diagnosable without another blind rerun hunt.
  An earlier draft of this entry named the cause as "an mtime race in rule 13's staleness comparison"
  — that was an inference, never measured, and is withdrawn here rather than repeated. Root-causing
  the actual signature is out of scope for the ten defects here, surfaced for a future release
  instead.
- The schema-symmetry guard's failure message names one cause ("the allowlist absorbed every read")
  when an empty coverage set can come from either that or a schema loosened to
  `additionalProperties: true` — reproduced by flipping `routing.schema.json`'s `hops` items to
  permissive and watching the allowlist-shaped message fire with the allowlist untouched. The new
  ceiling test (`test_the_allowlist_does_not_blind_an_entire_axis`) also only asserts non-empty
  coverage, not a minimum retained fraction — re-adding 6 of `rederive_hops`'s 7 checked names still
  passes it. Both recorded for a future pass, not fixed here.
- `EXPORT_DELIVERABLES`, `GATE_INPUTS`, and `EXPORT_GATE_INPUTS` are each single-sourced inside
  `scripts/orchestration.py` for `next_stage.py`'s own staleness comparisons only; the CLI that
  actually reads each set of filenames still hand-lists them a second time with its own literals.
  `export_gate.py`'s `main()` (plus five test fixtures) re-builds `EXPORT_DELIVERABLES`'s and
  `EXPORT_GATE_INPUTS`'s filenames with its own f-strings/`opt()` calls, and `scripts/gate.py`'s
  `main()` hand-lists the same nine artifacts `GATE_INPUTS` names, across its two required loads and
  seven `opt()` calls. Renaming any of these filenames would still silently reproduce TW-077's shape
  under a new name. Next-version follow-up: have each CLI import the constant it currently
  re-lists by hand.
- `test_no_failure_class_routes_to_a_stage_that_cannot_write_it[2026-08-chiayi]` used to iterate an
  empty failure list (the consumer's chiayi trip is clean today) and so execute zero assertions while
  still reporting pass — precisely the "a check that cannot fail is indistinguishable from one that
  passed" shape this whole release is about. Fixed with a two-line addition: before the loop, assert
  that the failure list's emptiness matches what `tests/corpus-baseline.json`'s per-trip `total`
  says it should be, so an empty trip is now asserted rather than silently skipped over. The fuller
  design — recording per-trip counts of each individually routed failure class in the baseline — is
  a bigger change than this defect needs and stays a next-version follow-up.
- `scripts/gate.py`'s two-trip id-collision note (POIs and lodging candidates sharing an id within
  `2026-07-sun-moon-lake` and `hokkaido-7d`) was independently recomputed against all seven live trip
  directories during the doc sweep above and still matches exactly; left as an open, id-anchored
  v0.35.0 follow-up note, unchanged.

Tests: 1095 passed with the consumer corpus mounted, 0 failed; 1075 passed + 20 corpus-gated skips
in CI (no corpus). (Post-review fix wave added 2 tests to the original 1093/1073 figures — F1's
rule-14 required-deliverable test and F12's shipped-`.version-bump.json` `previous` guard — no
count regressed.) Every corpus number this entry publishes remains independently reproducible by
anyone with the consumer repo, which v0.34.0's entry could not claim.

## 0.34.0 — the POI verdict axis, and the two channels it needed

v0.33.0 shipped five re-derivation axes — legs, hops, cost, the closing-buffer
rule, lodging name/geocode provenance — and omitted the one gatekeeping the
plugin's own iron rule, **only verified flows downstream**: nothing re-examined
a POI's own `verify_status`. Three gates changed shape across 0.32.0–0.33.0
(Gate 0's sourced-object `business_status`, Gate 2b's refusal on an absent
`resolved_name`, Gate 2c's existence proof) and not one recorded `verify_status`
was ever re-checked against the rules that now govern it. This release closes
that gap (TW-070) and ships the two channels the new axis needed to exist
without producing failures no consumer could fix with data (TW-071, TW-072),
plus a low-severity input-tolerance fix found alongside them (TW-073).

- **The sixth axis (TW-070): `verdicts_rule_current`, and three buckets because
  a superseded verdict is not a wrong one.** `scripts/rederive.py::rederive_pois`
  re-derives every `verified-pois.yaml` record's `verify_status` and reports it
  as one of three FIRST-APPLICABLE buckets, in this order, so one record
  produces at most one failure and names the one thing to fix first:
  `superseded` (the recorded verdict cannot stand because the rules that
  produced it were superseded — today: a `business_status` that is not the
  sourced `{status, source_url, as_of}` form at all (bare-string or absent,
  superseded by TW-063's object form), or one that IS that dict shape but
  unusable — an unrecognised status, a blank `source_url`, or an unparseable
  `as_of`), `missing` (an input
  needed to recompute is absent — today: no `resolved_name` recorded at all),
  `mismatches` (every input is present and the verdict does not follow). A
  bare-string `business_status` is deliberately **not** folded into `missing`:
  it is not an absent input and not a wrong verdict, it is a verdict produced
  under rules this release supersedes, and reporting it as "missing" would
  misdescribe what the consumer needs to do. Measured against the four
  schema-clean corpus trips through the shipped function, not estimated:
  **found 127, superseded 105, 0 missing, 0 mismatches** — the last two read
  zero because `superseded` is first-applicable, not because those buckets are
  untested (both have dedicated fixtures; the corpus alone cannot exercise
  them). 105 is not 100: the 5 recorded-`conflicting` POIs also change verdict
  under current rules, on top of the 100 recorded-`verified` ones; the 22
  unchanged are the POIs already correctly `unverified`. `rederive_lodging`
  gains the identical Gate 0 half in the same release (see below): **found 18,
  superseded 18** — every lodging candidate in the corpus, because
  `accommodations.schema.json` could not even carry a sourced `business_status`
  before this release. Combined, the `verdicts_rule_current` check reports
  **examined 145, superseded 123**.
- **Most of this flood is not new damage — but not all of it, and the parts
  differ.** The 123 decomposes exactly three ways, measured by each record's
  RECORDED verdict:
  - **100 — already announced.** 0.32.0 published that re-running
    `source-verify` demotes **100 of 100** currently-`verified` POIs (see that
    release's Migration section). This axis does not create that consequence;
    it makes a consequence that was already true the moment those verdicts
    were written **visible at gate time**, before a consumer discovers it the
    hard way by re-running `source-verify` and watching a finished trip empty
    out.
  - **5 — newly surfaced, same root cause.** Five POIs recorded `conflicting`
    also change verdict under current rules. 0.32.0's figure counted only the
    `verified` ones, so these were never in the published number even though
    the cause is identical.
  - **18 — newly surfaced, and it could not have been announced.** Every
    lodging candidate in the corpus. This is not an oversight in 0.32.0's
    count: `accommodations.schema.json` had no `business_status` field at all
    until this release, so there was no sourced Gate 0 for a lodging verdict
    to be superseded *from*. The demotion becomes statable only in the same
    release that gives the field somewhere to live — which is why the 0.33.0
    entry recorded "Gate 0 stays open, deferred to 0.34.0" rather than a
    count.
- **The clock is anchored to the artifact, not to wall-clock** — same
  precedent as the R5 deferral in the 0.33.0 CHANGELOG. `rederive_pois` (and,
  since Task 6, `rederive_lodging`'s Gate 0 half) asks "was this verdict
  correct when it was written", reading the record's own
  `business_status.as_of` era. `OPERATING_MAX_AGE_DAYS` is 90, so a wall-clock
  read would turn a trip's gate red 91 days after verification with zero
  artifact change — the exact calendar-driven class 0.33.0 cited when
  deferring R5. A fix-round leak closed the same class one gate deeper: Gate
  2c's `has_existence_proof` originally read wall-clock regardless, so a
  stale `as_of` could flip the re-derived verdict even though Gate 0 itself
  agreed with the recorded one; `today` now threads into it from the same
  anchor.
- **Gates 3a/3b are not re-derived for POIs.** The artifact records neither
  `in_claimed_region` nor `conflict_detected` — both are computed by the agent
  at research time and never written back — so the permissive values are
  passed and a region mismatch or cross-source conflict is invisible to this
  axis. Recording them was considered and rejected: each new agent-authored
  field is another self-attestation, the defect family this whole programme
  exists to shrink.
- **TW-071 — a POI can finally record `resolved_name`.**
  `verified-pois.schema.json` was `additionalProperties: false` with no such
  field, while `accommodations.schema.json` already had it — Gate 2b's own
  input was schema-illegal to record on a POI, which would have made every
  re-derived Gate-2b failure permanently unfixable with data the moment
  `rederive_pois` shipped. Callers now pass the geocoder's `display_name` or
  the literal `NO_RESULT` sentinel (mirroring `verify.NO_RESOLVED_NAME`) — an
  absent field still means "nobody looked", distinct from "the lookup ran and
  found nothing". The same commit adds a **discovered, not hard-coded**
  schema-symmetry ratchet (`tests/test_schema_symmetry.py`): every
  `rederive_*` function found in `scripts/rederive.py` must be OWNER-mapped to
  the schema it reads records from, or explicitly EXEMPT with a stated reason
  — so a future axis is enrolled in the check the moment it is written,
  instead of the scan silently staying blind to it.
- **TW-072 — Gate 2c accepts Gate 0's evidence, and the keyless asymmetry
  dissolves by construction.** Gate 2c's stated job is existence — "something
  independent of the coordinate says this place exists" — and a dated, sourced
  first-party statement that the venue is operating already is that.
  `has_existence_proof` now accepts a third proof: a `business_status` in the
  same sourced object form Gate 0 requires. Gate 0 already guaranteed two
  keyless-reachable routes (a dated official/social statement; a phone
  confirmation recorded as `tel:`); whichever one a keyless consumer took now
  satisfies Gate 2c too, so `verify_status` stops being a function of whether
  the machine happens to carry an API key. `gmaps_place_id` stays an accepted
  proof and gains a minimum-length shape check (measured on the **four
  schema-clean trips**, the same denominator every other figure in this entry
  uses: 57 POIs carry one, every one exactly 27 characters, none shorter than
  8 — the floor demotes nothing real. Across all six corpus trips it is 86,
  also every one exactly 27; the conclusion is identical on either
  denominator).
  **That shape check has no production reader as of this release.** Its only
  caller is `has_existence_proof`, whose own production callers disappeared
  when Gate 2c was retired (below) — so the floor is currently **inert**,
  exercised by `tests/test_verify.py` and nowhere else. It is documented here
  rather than quietly rewired: the one place that still reads
  `gmaps_place_id` in production is
  `scripts/render/gmaps_links.py::maps_url`'s deep-link refinement, and
  wiring the check into it is new behaviour that needs its own red→green
  cycle. Tracked for the next version, deliberately not smuggled into this
  one.
- **TW-073 — `operating_from_status`'s `today` now tolerates an ISO string.**
  `as_of` already went through `_parse_iso`; `today` did not, so passing a
  string raised `TypeError` inside the same function. Now
  `ref = _parse_iso(today) or date.today()`. No production caller was
  affected (`source_verify_run.py` always passed a `datetime.date`); this
  closes a tripwire for any future caller such as a reproducible-testing
  `--today` flag.
- **Gate 2c was RETIRED — subsumed by Gate 0, not fixed.** Accepting a sourced
  `business_status` as an existence proof has a consequence beyond closing the
  keyless asymmetry: it makes Gate 2c **unreachable** on both paths. A POI (or,
  once lodging gained the same field, a lodging candidate) that clears Gate 0
  necessarily already carries a proof identical to what Gate 2c would ask for,
  read through the identical field; one that Gate 0 refuses never reaches Gate
  2c at all. This was measured and confirmed — including for a stale `as_of`,
  after the wall-clock leak above was closed — before the check was deleted
  from `classify_candidate` rather than left in as dead code that could never
  fire. **The retirement itself changes no verdict**: `Gate 0 ∧ Gate 2c ≡
  Gate 0`, because every record Gate 2c could still be asked about has already
  satisfied it through the identical field. A release whose whole point is
  closing "a check that cannot fail is indistinguishable from a check that
  passed" must not ship an unreachable gate inside itself.
- **TW-062's shape IS now permitted, and TW-072 is what permits it — not the
  retirement.** Earlier drafts of this entry claimed the retirement "does not
  reopen TW-062". Half of that claim is true and the other half is false, and
  the two were run together. **True:** the *evidence vocabulary* narrowed —
  Gate 0 demands a *dated, sourced* statement, strictly more than the retired
  check ever accepted (an undated official link, or a bare `gmaps_place_id` of
  plausible shape, used to satisfy Gate 2c; neither satisfies Gate 0).
  **False:** the *outcome*. A place whose only evidence is a sourced
  `business_status` — no official source, no `gmaps_place_id` — now reaches
  `verified` while its coordinate is still a district centroid, which is
  precisely TW-062's shape. That follows from TW-072 making a sourced
  `business_status` an existence proof in its own right: Gate 2c, had it been
  left in place, would have *passed* these records too. The retirement is
  verdict-neutral; the loosening is TW-072's.
  Measured across the corpus, five records do this once migrated to the sourced
  form this release asks for — four `cluster_fallback` POIs in `2026-08-chiayi`
  (`penshui-turkey-rice`, `taocheng-guwei`, `shanzhai-restaurant`,
  `atian-goose`) and one lodging candidate in `2026-07-sun-moon-lake` (`d2-6`,
  the single record the retired check ever caught on real data). All five flip
  `has_existence_proof` from `False` to `True` on the strength of the new
  proof alone. Whether a centroid coordinate paired with a real operating
  statement deserves `verified` is the **coordinate-trustworthiness** question
  recorded under *What stays out* below — this version does not answer it.
- **Lodging gets a real Gate 0.** `accommodations.schema.json` gains
  `business_status` — the identical sourced object form, copied verbatim so
  the two schemas cannot disagree in detail — closing the 0.33.0 deferral (
  "Gate 0 stays open, deferred to 0.34.0"). `rederive_lodging` re-derives it
  for every candidate; a fix-round defect (M1) in the first draft is worth
  recording on its own: `operating is not False` treated "not established" as
  operating, the exact "not established defaults to open" shape TW-005/P1
  already closed for POIs, and it made the anchored-clock fixture pass for the wrong
  reason (a stale record, read wall-clock, degrades to `None`, and the
  fail-open then silently matched it as operating — leniency, not the
  calendar-driven redness the anchor was believed to prevent). Closed by
  making an unparseable/unsourced `business_status` land in `superseded`
  unconditionally, never fall through to `classify_candidate` as an implicit
  `True`.
- **The one wrong citation in the consumer report, corrected.**
  `docs/specs/2026-08-09-chiayi-regate-0.33.0-defects.md` (committed with this
  release, per this repo's convention of shipping the report alongside the
  release that closes it) states that `gmaps_place_id` is backfilled by an
  export-stage `scripts/gmaps_media.py`. That module does not exist:
  `gmaps_place_id` is read in exactly two places
  (`scripts/verify.py::has_existence_proof` — **not** "Gate 2c": that gate is
  retired, and this function is now the test-only primitive it used to back,
  so naming the read site after the gate would describe a caller that no
  longer exists — and `scripts/render/gmaps_links.py::maps_url`'s deep-link
  refinement, the sole surviving PRODUCTION reader) and
  **written by no plugin code at all** — it is an agent-authored field, recorded by hand per
  `skills/source-verify/SKILL.md`'s instruction only when the Places API route
  was actually used. That is precisely why TW-072 gave it a shape check
  instead of trusting it as machine-verified.
- **TW-062's `verified-pois.schema.json` `allOf` constraint leaves the
  roadmap — SUPERSEDED, not deferred again.** It was held back so that
  existing trips carrying the shape (a `cluster_fallback` geocode paired with
  `verify_status: verified` and no existence proof) would get a routed,
  fixable gate failure instead of a hard `validate_artifact` exit 1. The sixth
  axis's `superseded` bucket **is** that routed failure. Shipping the schema
  constraint on top would let the harsher check pre-empt the gentler one — a
  schema-invalid artifact fails `validate_artifact` before the gate ever runs
  — so the routing message this whole release is built around would never
  once be emitted. It is dropped from scope for that reason, not deferred to
  a future version a second time.
- **What stays out:** R5 (`lead_time_missed`) and R6 (`in_peak`)
  re-derivation; re-deriving `reception_ok` (lodging's counterpart of the
  closing-buffer check); wiring `deps_stale` into the router; `export_gate`
  rebuilding its P4 lodging fold with the opposite precedence; `resolve_place`'s
  five-request burst inside one pace interval; the hand-maintained
  `GATE_INPUTS` / `EXPORT_GATE_INPUTS` mirrors; and the
  coordinate-trustworthiness question this release's own design notes raise
  and explicitly decline to answer — a hop or a candidate can match its
  recorded verdict and still be measuring against a coordinate TW-062 already
  showed can be a fiction.

### Migration

- **60/60 consumer artifacts across the four clean corpus trips still pass
  `validate_artifact`** — every schema change this release makes
  (`resolved_name`, lodging `business_status`) is additive, so nothing on disk
  needs to change to stay schema-valid.
- **Re-gating an existing trip will report far more failures than before**,
  concentrated entirely on `verdicts_rule_current`: 105 of 127 POI records and
  all 18 lodging candidates in the corpus. As decomposed above, **100 of those
  123 are 0.32.0's already-published demotion**, surfaced at the gate instead
  of discovered by re-running `source-verify` cold; the other 23 are newly
  surfaced — 5 POIs recorded `conflicting` (same cause, outside 0.32.0's
  `verified`-only count) and 18 lodging candidates (which no earlier release
  could have counted, since lodging had no `business_status` field to be
  superseded from). Both
  failure classes route automatically: a POI verdict fix routes to
  `tripwork:source-verify` (the only stage that writes `verified-pois.yaml`),
  a lodging one to `tripwork:accommodation-research`.

Tests: 1047 → 1082 with the consumer corpus mounted; 1063 pass + 19 corpus-gated skips in CI (no corpus).

## 0.33.0 — verdict re-derivation + AI-tone gate + TW-068/TW-069

0.32.0 closed the self-attestation defect **at write time only**: a fixed value could
no longer be typed past a gate, but nothing re-checked a verdict already sitting in a
finished artifact. The root cause carried into this release too — pure decision
functions (`classify_leg`, `classify_hop`, `sum_costs`, the closing-buffer rule)
existed and nothing ever ran them against a recorded verdict to see whether the two
still agreed. This release closes that gap for four of the six candidate checks, adds
a mechanical AI-tone gate, gives `source-verify` and the markdown renderer the batch
entrypoints they never had (TW-068, TW-069), and gives lodging and Gate 2c the closure
0.32.0 left open.

- **Re-derivation, for four of six candidate checks (R1–R4).** `scripts/rederive.py`
  re-runs `classify_leg` over `legs[]`, `classify_hop` over `routing.hops[]`,
  `sum_costs` over `cost.yaml`, and the closing-buffer rule over every scheduled row,
  then compares the fresh verdict against the one recorded in the artifact.
  `verdicts_match` measured **zero** mismatches across the four schema-clean consumer
  trips (29 records) — the mechanism costs nothing when the data is already correct.
  It is also **structurally blind** by design to shapes it cannot even attempt to
  compare — a non-drive leg with no `depart` recorded, for instance, since
  `classify_leg` cannot re-derive a `missed_last_service` verdict without one. Only
  the second check, `verdicts_rederivable` — which asks "could this verdict even be
  recomputed from what the artifact kept?" — sees that; `verdicts_match` only ever
  compares two verdicts once both exist.
  Re-derivation proves **internal consistency, never truth**: `classify_hop`'s
  `min_plausible_mins` runs over cluster centroids, and TW-062 already showed those
  centroids can themselves be fictions (a POI's coordinate borrowed from a neighbour).
  A hop can match its own recorded verdict and still be measuring distance between two
  points that are not where the trip actually goes.
  `gate.py` now fails the gate outright when `legs.yaml`, `routing.yaml` or `cost.yaml`
  is absent — previously it passed. This is deliberate (an absent artifact means the
  pipeline ran out of order) but it is a **breaking change for every existing trip
  directory**, not only the two already known to be schema-dirty. See Migration below.
- **A mechanical AI-tone gate (`no_ai_tone`).** `scripts/gate.py` now scans canonical
  itinerary text (checklist + every row) via `scripts/text_hygiene.py`. Measured
  against the five canonical itineraries that have one: **32 hits, 32 true positives,
  zero false positives** — but all 32 are the em-dash and markdown-bold detectors
  (31 + 1); the em-dash one is deliberately narrow (the corpus contains 28
  non-flagged dash-adjacent characters — 22 U+2013, 6 U+FF5E — in legitimate date
  ranges and opening-hours notation, and widening the pattern to catch them would
  fail every one of those lines). The other **five word-list lexicons — slop words,
  sentence templates, promo clichés, meaning stamps, chatbot residue — measured zero
  hits on the same five itineraries: 0 true positives and 0 false positives.** They ship as
  **regression locks, not fixes**: nothing in the shipped corpus currently trips
  them, so their job this release is to stay silent and catch a future regression,
  not to have found anything today. A sixth candidate lexicon, `rule_of_three`, was
  measured too (21 hits, **21 false positives**) and **dropped** — it is
  unmechanizable on real Chinese travel prose, not merely imperfect.
- **`source-verify` gets the batch driver it never had (TW-068).** `scripts/source_verify_run.py`
  runs the existing per-candidate decision logic (`verify.py`) over a whole
  `candidates.yaml`, replacing a pattern where every consumer hand-rolled their own
  driver (one hardcoded a 9-entry official-domain allowlist). Running it exposed a
  latent Gate 0 defect: `candidates.schema.json`'s `business_status` only permitted the
  bare-string form, which `verify.py` treats as self-attested and **never lets pass** —
  so no schema-valid `candidates.yaml` could ever produce a single verified POI through
  this driver. `candidates.schema.json` is widened to the same sourced object form
  `{status, source_url, as_of}` that `verified-pois.schema.json` already carries
  (purely additive; a bare string stays schema-valid, still self-attested, still
  `unverified`).
- **The markdown renderer gets a page-level entrypoint, and `contingency` gets a
  container (TW-069).** `render_markdown_page` (`scripts/render/markdown.py`) replaces
  every consumer's hand-rolled per-trip render script (one silently rendered a missing
  lodging POI as `**宿**：<id>` with no link). Synthesis now writes 備案 into a
  `contingency` block, mirrored into the HTML checklist section the same way the
  existing checklist is. A new gate check, `home_legs_rendered`, closes the gap where a
  home leg (`legs[].kind: home`) could be fed into cost and feasibility but never
  actually appear in the rendered itinerary: an itinerary row may now carry an optional
  `leg_index` linking it back to `legs[]`, and the check fails if a recorded home leg
  has no row pointing at it. Building the fixture for that check uncovered
  `export_gate._find_rows` fighting the new markdown page in both directions, and both
  are fixed: the `**宿**：` line was not `|`-prefixed, so a bookable lodging POI
  missing its official link silently passed the export gate; the new cost table's
  `|`-rows carried POI-name substrings, so a bookable POI could get a spurious "row
  missing official source link" failure even when the link was present elsewhere in
  the deliverable.
- **Photo enrichment gets an owner (`scripts/photo_adapter.py`'s CLI, `main`).**
  Dogfood measurement: five existing trips carry **78 hand-written `photo_source: google`
  media entries**, every one bypassing `license_allowed` (the adapter's own hard
  license gate), because nothing ever ran the adapter's decision logic against
  hand-authored side-files. All five deliverables were already recorded
  `distributable: false` by `export-gate` — and every one of those five reports still
  read `status: pass`, so the pipeline shipped them cheerfully. The CLI now runs
  `build_media` + `write_media_sidefile` end to end and validates its own output
  against `media.schema.json` before writing, closing the exact "self-check passes
  because nothing checked the right schema" shape this release exists to close
  elsewhere.
- **Exactly which half of `_DEPS` is live.** `scripts/orchestration.py`'s `_DEPS` table
  (which artifact each skill's Stage Contract declares as Input) and its drift guard
  are **live and mechanically enforced**: `tests/test_deps_table.py` re-parses all 11
  producing skills' Input rows and fails the moment the table and the documentation
  disagree, in both directions (verified by live mutation). The **content predicate
  `deps_stale` is built, unit-tested, and deliberately NOT wired into the router** —
  `scripts/next_stage.py` imports six names from `scripts/orchestration.py`
  (`ADVISORY_PROJECTION`, `GATE_INPUTS`, `EXPORT_GATE_INPUTS`, `candidates_stale`,
  `input_fingerprint`, `route_gate_failures`) and `deps_stale`/`_DEPS` are not among
  them. The measured reason is data, not machinery: **zero artifacts across all six
  corpus trips record `input_fingerprints`**, so the fail-open predicate would return
  an empty list for every edge and could not be validated against anything real. The
  producing side is NOT missing — `skills/travel-advisory/SKILL.md` already instructs
  recording `input_fingerprints["trip-brief.yaml"]`, `schemas/advisory.schema.json`
  already declares the field, and rule 11 in `scripts/next_stage.py` already performs
  `deps_stale`'s comparison inline for that one edge, over the same
  `ADVISORY_PROJECTION`. So `deps_stale` is the general form of a check the router
  already runs in one hand-rolled place; 0.34.0 should unify the two rather than grow a
  second copy (a note in `scripts/orchestration.py` says so beside the function).
  `skills/orchestrator/SKILL.md` already
  describes it as "consumed by future stages"; that framing is accurate and this
  release does not change it. What ships live and enforced is the **report tier**:
  rules 13 and 15 (`scripts/next_stage.py`) now compare `gate-report.yaml` /
  `export-gate-report.yaml` against **every** artifact the corresponding CLI actually
  opens (previously a narrower, hand-maintained list), so a report can no longer look
  fresh while one of its real inputs changed underneath it.

### The three items 0.32.0 published as "Deliberately still open"

- **Gate 2c's optional trigger — CLOSED.** Omitting `geocode.geocode_source` is now an
  outright refusal (`unverified`), not a silent skip. Measured: 19 of 127 real POIs
  omitted the field; **none of the 19 was `verified`**, so closing this demotes no
  existing artifact.
- **Lodging — Gates 2b and 2c CLOSED; Gate 0 stays open, deferred to 0.34.0.**
  `itinerary-gate` now re-derives every `accommodations.yaml` candidate's
  `verify_status` for name-match and geocode-source provenance, so a gate-report
  failure naming a hotel is new output this release. Gate 0 (operating status) is
  **not** closed for lodging: `accommodations.schema.json` has no `business_status`
  field at all, and adding one means redoing TW-063's design for hotels rather than
  reusing it — that is 0.34.0's work. The measured defect this closure did find in
  delivered data: `2026-07-sun-moon-lake` candidate `d2-6` is a district centroid with
  **no existence proof**, and is recorded `verified`. Gates 3a/3b (region match /
  conflict detection) are not re-derivable for lodging at all today — the artifact
  records neither `in_claimed_region` nor `conflict_detected`.
- **`classify_hop`'s `km`/`mode` omission — CLOSED at the artifact layer.** A hop
  recording no `mode`, or an endpoint with no resolvable cluster centroid, is now a
  `verdicts_rederivable` failure that routes back to `routing-audit`. The legacy
  two-argument `classify_hop` call form stays legal at the function layer,
  deliberately — this release closes the gap where an artifact could omit the
  provenance fields, not the function's own back-compat surface.

### Migration — read this before re-gating an existing trip

- **Re-gating the four existing consumer trips reports 125 gate failures in total** —
  26 / 31 / 32 / 36 for yilan / sun-moon-lake / chiayi / northeast-coast. Measured
  through the shipped `run_gate` over all five re-derivation axes at once, not through
  a subset:

  | Axis | Examined | Failures |
  |---|---|---|
  | `verdicts_rederivable` | 103 verdict-bearing records | 94 |
  | `verdicts_match` | 47 records with complete inputs | **1** |
  | `no_ai_tone` | (not a re-derivation axis) | 30 |

  The single `verdicts_match` failure is real and is named in the lodging bullet above:
  2026-07-sun-moon-lake's candidate `d2-6`, a `cluster_fallback` centroid recorded
  `verified` with no existence proof. Everything else is **provenance that was never
  recorded, not verdicts that were wrong**, and the 94 split cleanly: 19 hops with no
  `duration_source` (they predate TW-066), 56 scheduled rows with no recorded
  `closing_status` or no `hours.close`, 18 lodging candidates with no `resolved_name`
  (the field is new in this release) and 1 with no `geocode_source`.

  An earlier draft of this section quoted **19 failures on 29 records**. That figure was
  measured before the closing and lodging axes existed — it is `rederive_legs` +
  `rederive_hops` + `rederive_cost` in isolation — and describing the shipped five-axis
  gate with it understated the migration by a factor of five. `tests/test_corpus_gate.py`
  now pins every number above against a real `run_gate` report, per trip and per failure
  class, so the document and the mechanism cannot drift apart again.
- **A timed `slot: lodging` row is not subject to the closing-buffer check.** The gate
  folds each stop's chosen lodging into the POI pool (P4), which briefly put check-in and
  checkout rows in `rederive_closing`'s scope and demanded `hours.close` from them —
  unsatisfiable, because `schemas/accommodations.schema.json` forbids `hours` on a
  candidate. The lodging arrival check is a separate mechanism on a field that schema DOES
  declare (`scripts/facilities.py::reception_ok` against `reception.close`, owned by
  accommodation-research); re-deriving it is deferred to 0.34.0. Seven corpus rows moved
  out of scope, which is why the closing figures above read 56 rather than 63.
- **Rule 13.5 routes the missing-hours class to `tripwork:source-verify`.** `hours` lives
  in `verified-pois.yaml` and only source-verify writes it, but the failure previously
  fell through to `tripwork:itinerary-synthesis`, which cannot write the field — so the
  feedback loop could not terminate. Granting each routed stage its best possible fix,
  all four trips now drain to `pass` in 4-5 rounds. With the route removed, the three
  trips that HAVE missing-hours rows stall on exactly those rows and never pass — yilan
  at 5, sun-moon-lake at 12, northeast-coast at 10. 2026-08-chiayi has none, so it is
  the one clean trip that drains either way; it is not evidence for this change.
  `tests/test_corpus_gate.py` runs the drain on all four and the route-removed
  counterfactual on yilan.
- **The gate now FAILS when `legs.yaml`, `routing.yaml` or `cost.yaml` is absent**,
  where it previously passed silently. An absent artifact means the pipeline ran out
  of order, and the gate says so now instead of shrugging. This affects every existing
  trip directory that predates this release, not only ones already known to be dirty.
- **A POI must record `geocode.geocode_source`.** Omitting it used to skip Gate 2c
  silently; it is now a refusal. 19 real POIs currently omit it, none of them
  currently `verified` (see above).

### Residual, stated rather than fixed here

- `gate.py`'s thirteen legacy checks (the pre-0.33.0 ones) still derive `passed` by
  substring-scanning a single merged failures list rather than carrying their own
  explicit pass/fail. `no_ai_tone`'s failure messages are the first to embed
  **arbitrary trip text** — an AI-tone snippet — into that shared list. The realistic
  collision surface is narrow (the markers are English literals, the corpus is
  Chinese prose) but the coupling itself is unfixed; converting every check to an
  explicit per-check failure list is a wider refactor than this release.

### Deferred to 0.34.0

- **R5 (`lead_time_missed`) and R6 (`in_peak`) re-derivation.** R5 needs a wall-clock
  read (`today_iso`) that no schema field records; naively substituting today's date
  risks a calendar-driven non-terminating loop (a `False` recorded at synthesis time
  flips to `True` purely from elapsed days, `verdicts_match` fails, rule 13.5 routes
  back to synthesis, synthesis rewrites the same itinerary, it fails again) — needs its
  own freshness-rule design, not naive re-derivation. R6 is vacuously satisfied on 2 of
  4 valid corpus trips today (`in_peak` returns `False` for every input when
  `peak_windows` is empty, so the recorded and re-derived values agree on a premise
  that was never actually true); needs a `no_peak_windows` legitimacy declaration and a
  narrowed scope before it means anything.
- **TW-062's `verified-pois.schema.json` `allOf` constraint** (a `cluster_fallback`
  geocode source paired with `verify_status: verified` must carry an existence-proof
  source). Deferred so that existing trips carrying this shape (chiayi has 8) get a
  routed, fixable gate failure rather than a hard `validate_artifact` exit 1 — tightening
  the schema before the corpus migrates would be strictly worse than the gate-level
  enforcement this release already ships.
- Lodging Gate 0 (needs `accommodations.schema.json` `business_status`).
- **Re-deriving `reception_ok`** — the lodging counterpart of the closing-buffer check.
  `slot: lodging` rows are out of `rederive_closing`'s scope because `hours` is a
  verified-pois field a lodging candidate cannot carry; the arrival-vs-reception verdict
  lives on `reception.close`, which the lodging schema DOES declare, and
  `scripts/facilities.py::reception_ok` already computes it. What is missing is the
  artifact-level re-derivation: 3 of 5 chosen lodgings in the corpus record `reception`
  at all, and only 1 records a `close`, so the axis would be almost entirely a
  rederivable gap today.
- Wiring `deps_stale` into the router. The producing side is not missing —
  `skills/travel-advisory/SKILL.md` instructs recording `input_fingerprints`,
  `schemas/advisory.schema.json` declares it, and rule 11 already runs the same
  comparison inline for that edge. What is missing is DATA: no corpus artifact records
  the field yet, so a wired predicate could not be validated against anything real.
  The wiring pass should replace rule 11's inline copy, not sit beside it.
- `gate.py`'s thirteen-legacy-check substring coupling (see Residual above).

### End-to-end consumer-fixture closure

`tests/test_e2e_v033_closure.py` builds ONE fixture trip carrying all eleven of this
release's exit-criterion defects at once and drives it through both real CLIs from a
cwd outside the repo, with an absolute script path. It exists because the eleven do
not all live at the same layer: `scripts/gate.py` consumes the `verify_status`
already recorded in `verified-pois.yaml` and never re-runs `verify_poi`, so the three
write-time defects (a `cluster_fallback` POI with no existence proof, a POI whose
`geocode` records no `geocode_source`, a bare-string `business_status`) are closed by
`scripts/source_verify_run.py` → `verify_poi` as the artifact is WRITTEN, and the
other eight by `gate.py` as the finished artifact is GATED. A closure that ran only
the gate would have reported all eleven green while proving nothing about the first
three. The layer boundary is asserted in both directions rather than described: the
fixture schedules a POI carrying the missing-`geocode_source` defect and pins that
the gate says nothing about it while `verify_poi` refuses it. The run is network-free
without `--offline` (the per-trip geocode cache is pre-seeded, and a cached miss is
what makes the `cluster_fallback` branch deterministic) — `--offline` could not be
used, because it returns before any geocode is built and so can produce neither a
`cluster_fallback` coordinate nor any coordinate at all.

Tests: 874 → 999, zero skipped or xfailed throughout.

## 0.32.0 — provenance at write time: six dogfood defects, gates that can now fail

A consumer 3D2N dogfood run finished with `gate-report.yaml` 13/13 green and
`export-gate-report.yaml` 17 of 19 (the other two are the deliberate
non-distributable labels) — and the user still caught errors by eye. Every
defect landed on one axis: **a gate that consumes a value the agent asserted about
itself cannot fail, and a check that cannot fail is indistinguishable from a check
that passed.** This release closes six instances of that axis at the moment a value
is written.

**Read the scope note at the bottom before assuming it closes more than it does.**

- **Operating status needs a source and a date (TW-063).** `business_status` was a
  bare enum — no `as_of`, no `source_url` — while `hours.as_of` and `rating_source`
  already existed in the same repo. In the dogfood run 17 of 17 verified POIs carried
  a hand-typed `OPERATIONAL`; the user caught a temporarily-closed restaurant on
  Google Maps that Gate 0 did not. It is now the object form
  `{status, source_url, as_of}` with a 90-day ceiling, and a bare string is treated
  as self-attested (`unverified`, not a silent pass).
  Both acquisition routes the SKILL used to name were measured dead: a fetched Google
  Maps card carries no `businessStatus` (client-side render), and "official-site 404"
  does not apply to venues whose only web presence is a social page. The skill now
  names the routes that work — Places API, a dated official/social statement, or a
  phone confirmation recorded as `tel:` — and says plainly that leaving a POI
  `unverified` with a pre-departure call on the checklist is the honest outcome, not
  a defect.
- **A district centroid is not a geocode (TW-062).** `cluster_fallback` lived in the
  global `geocode_source` enum but only `accommodation-research` ever authorised it,
  and `verify_poi` never read the field (`grep -rn geocode_source scripts/` returned
  nothing). So a POI carrying a neighbouring cluster's centroid passed Gate 2, skipped
  Gate 2b (no `resolved_name` meant `name_match` defaulted `True`), and satisfied
  Gate 3b by construction. The incentive inverted: a POI the geocoder could NOT
  resolve was easier to verify than one it resolved to a different name. Dogfood: 8
  of 17 verified POIs took this path, and 7 of those 8 share a verbatim-identical
  coordinate with a sibling (one group of three, two groups of two). Four were bound
  to a schedule slot at some point during the run; one survived into the shipped
  itinerary as a meal. A centroid now keeps a POI `verified` only with an existence
  proof independent of the coordinate.
  The same commit closes the twin one gate over: omitting `resolved_name` used to
  skip Gate 2b silently. Callers now pass the resolved name or the explicit
  `NO_RESOLVED_NAME` sentinel — silence is no longer a pass.
- **A re-estimated hop must say where the estimate came from (TW-066).**
  `classify_hop` compared numbers only, and the skill offered "re-estimate the hop or
  cite a timetable" — the first branch needs no evidence. Dogfood: two hops judged
  `implausible` were re-typed as 30 and 20 minutes and the gate went green with no
  source and no trace. Root cause the defect report missed: `routing.schema.json`
  constrained `flag` to `[ok, far]`, so honestly recording `implausible` produced an
  invalid artifact — raising the guess was the only schema-legal move. The enum now
  carries `implausible` and `unsourced`, hops record `duration_source` (+ `source_url`,
  required when the source is not an agent estimate), and the verdict precedence is
  **implausible > far > unsourced > ok** so the user-facing `far` halt can never be
  swallowed by a provenance verdict.
- **The iron rule binds to provenance, not to a vendor tool (TW-064).** "No search,
  no fact" halted on `WebSearch` being unavailable. Nine skills named that tool and
  `WebFetch` appeared nowhere, so on a model group without `web_search_20250305` every
  research stage halted and the plugin was unusable — a dogfood run hit exactly that
  API error and the agent invented its own WebFetch route, correctly, with nothing in
  the plugin to record it. Renamed **No unsourced fact** and rewritten as a three-rung
  source ladder; HALT fires only when every rung is unavailable. The four alt-platform
  mirrors (`GEMINI.md`, `.kimi-plugin`, `.opencode`, `.pi`) were re-synced and are now
  guarded — they had each kept the old single-tool framing.
- **The drive home is a leg, with an owner (TW-065).** `inter-stop-legs` told a
  single-base trip to write `legs: []` and return, so the home↔base drive belonged to
  no stage: `cost-rollup`'s only transport source is `legs.yaml`'s `fare`, and
  `drive_too_long` never saw what is usually the longest drive of the trip. Three real
  trips produced three incompatible shapes — one hand-wrote 1,300 into `cost.yaml` (a
  line item carries no `sources` requirement and never reaches `classify_leg`), one
  added three home legs totalling 445 min / NT$2,200 with the return split across two
  rows through a non-overnight waypoint, one broke the SKILL and got the right answer.
  `legs[].kind: inter_stop|home` plus `trip-brief.home_origin`/`home_return`, both
  optional.
- **Advisory staleness anchors on content, not on file mtime (TW-067).** Rule 11
  compared whole-file mtimes while its own comment named destination/dates/airline as
  the anchor, so editing `must_do` invalidated the advisory and the only way to clear
  the oracle was to rewrite a byte-identical file. Dogfood did it three times; the
  final `advisory.yaml` is 277 bytes of `items: []`. The damage is not the wasted run
  — it teaches an agent to satisfy an oracle by touching a file, and rules 13 and 15
  have mtimes that ARE load-bearing. Now a normalised content fingerprint, with mtime
  as the fallback when none is recorded (rule 11 is the gate that surfaces a `banned`
  regulation, so it fails closed).
- **Known schema inconsistency, not fixed here.** `candidates.schema.json`'s
  `business_status` is still the bare-string enum — only `verified-pois` gained the
  sourced object form. Nothing exercises the gap today (`destination-research` never
  writes the field; only `source-verify` does), but the two schemas now disagree.
- **Gate reports can record how many records a check examined.** `checks[]` accepts an
  optional `examined` integer. Nothing emits it yet — see the scope note.

### Migration — read this before re-running an existing trip

- **Re-running `source-verify` will empty an existing trip.** Measured against the four
  schema-clean consumer trips: **100 of 100 currently-`verified` POIs become
  `unverified`** — three trips because `business_status` is a bare string, one because
  45 POIs have no `business_status` at all. `itinerary-synthesis` reads only `verified`,
  so the next synthesis produces an empty itinerary until the operating signals are
  re-sourced. This is the intended consequence of the fix, not a regression.
- **Artifacts already on disk are untouched.** `gate.py` consumes the `verify_status`
  recorded in the artifact; nothing re-runs `verify_poi` over a finished trip. So this
  release closes the self-attestation defect **at write time only**. Closing it for
  existing artifacts requires re-deriving recorded verdicts from recorded inputs, which
  is 0.33.0's work.
- New artifact fields are **optional in schema and required by the gate**, so every
  existing artifact still passes `validate_artifact` (verified: 60/60 files across the
  four clean trips) and a stale one gets a routed gate failure rather than a hard
  validation error.

### Deliberately still open

- **Lodging does not reach the new gates.** `accommodation-research` calls
  `classify_candidate` directly, so `operating`, `name_match` and `geocode_source` all
  take permissive defaults. 14 of 18 real lodging candidates are `cluster_fallback`
  with no `business_status`. TW-062 and TW-063 do not apply to hotels yet.
- **Gate 2c can be skipped by omission.** It keys on `geocode_source`, which is
  optional; a POI that simply omits the field never reaches the check. 19 real POIs
  already omit it.
- `classify_hop`'s floor and provenance checks both sit behind `km`/`mode`, which are
  optional — omitting them skips both.
- `examined` has no producer, so gate reports still cannot say how many records they
  inspected.
- `legs[].kind: home` has no renderer: `itinerary-synthesis` renders a leg only on a
  day that moves between overnight stops, so a home leg feeds cost and feasibility but
  may never reach the deliverable.

### Scope

TW-068 (a batch driver for `source-verify`) and TW-069 (a page-level markdown render
entry plus a `contingency` container) are **not** in this release, along with verdict
re-derivation, the mechanical AI-tone gate, the `_DEPS` staleness table, and
photo-enrichment ownership. All are 0.33.0.

Tests: 813 → 874, zero skipped or xfailed.

## 0.31.0 — Codex hook 127: hooks-codex.json anchors on CLAUDE_PLUGIN_ROOT

- **`hooks/hooks-codex.json` 相對路徑必爆 127**（下游 consumer 實爆，paperwork 7.98.0 / chipwork 0.54.0 同批）：command 原為 `bash ./hooks/run-hook.cmd session-start`，但 Codex 執行 plugin hook 時 cwd 是 session workspace 而非 plugin root（`codex-rs/hooks/src/engine/command_runner.rs` — `$SHELL -lc` + `current_dir(cwd)`），SessionStart 在每一個真實 Codex 安裝上都 exit 127。Codex 對 hook process 注入 `CLAUDE_PLUGIN_ROOT`/`PLUGIN_ROOT` env（`discovery.rs` OOTB compat），故 command 改為與 `hooks.json` 相同的 `"${CLAUDE_PLUGIN_ROOT}/hooks/run-hook.cmd" session-start`。
- 測試：`tests/test_manifests_present.py` 新增 plugin-root 錨定斷言＋e2e closure（`bash -lc`、foreign cwd、僅注入 `CLAUDE_PLUGIN_ROOT` — 斷言 rc=0 且輸出 SessionStart JSON）。修復前雙 RED（127 重現），修復後 GREEN。
- 同根因掃描：`hooks.json`（Claude）不受影響；`hooks-cursor.json` 相對路徑列 follow-up（Cursor cwd 語意未驗證、無消費者回報）。

## 0.30.0 — lodging name_zh: kana-hotel gate gap closed

- **accommodations `name_zh` (product-gap closure)** — `accommodations.schema.json`
  candidates gain an optional `name_zh` (Chinese gloss) plus the same kana→required
  `allOf` if/then guard as verified-pois (0.21.0): a `verified` candidate whose
  `name_display` carries kana must carry a non-empty `name_zh`. This closes the gap
  where a kana-named hotel (ホテルXX) could NEVER pass `itinerary-gate` — the gate's
  `kana_name_without_gloss` check requires the field the schema previously forbade
  (`additionalProperties: false`). Renderers and gate logic unchanged (already
  generic over `name_zh`); `accommodation-research` now captures the gloss during
  verification. e2e fixture reverted to a kana-named hotel so the path is exercised
  end-to-end.
- **next_stage scalar-report hardening (v0.29.0 backlog)** — a report file that
  parses as a bare YAML scalar (truncated to e.g. `status`) now degrades to the
  unreadable/invalid-report branch (re-run the producing gate) instead of crashing
  with an AttributeError.

## 0.29.0 — mechanized gate invocation + early advisory

- **validate_artifact CLI (D1)** — `python scripts/validate_artifact.py <artifact.yaml>`:
  runtime schema validation for every pipeline artifact (exit 0/1/2); every stage
  SKILL's "validate against the schema" now cites this command instead of ad-hoc glue.
- **gate CLIs (D2)** — `python scripts/gate.py <trip-dir>` and
  `python scripts/export_gate.py <trip-dir>` load artifacts, fold chosen lodgings,
  apply the media overlay (export side), run the existing gate functions unchanged,
  and write their reports. Kills the hand-written merged-pois glue defect class.
- **next_stage oracle (D3)** — `python scripts/next_stage.py <trip-dir> --work-dir <dir>`
  implements orchestrator rules 0–16 (tests: tests/test_next_stage.py); the pipeline
  marker for synthesis is now the canonical `itinerary.yaml` (was the derived `.md`).
- **travel-advisory runs early (D4)** — moved to rule 1.5 (right after trip-brief) so a
  `banned` regulation surfaces before any research is spent; rule 11 is now a
  staleness re-check anchored on trip-brief mtime.
- **description hygiene (D5)** — calendar-check / seasonal-advisory triggers now cite
  their real data dependencies; test_description_hygiene enforces trigger ⊆ Stage
  Contract Input for `.yaml`-suffixed citations.

## 0.28.0 — body trim (redundant restatements)

- Compress the heaviest skill bodies by removing `Common Mistakes` / `Red Flags`
  rows and downstream-contract restatements that duplicate content already pinned
  in each skill's `Gates` / `Rules` / `Method` / `Output` / `Capture` sections;
  compress the orchestrator `Inputs` roster and the `using-tripwork` script-detail
  iron-rule rows. On-invocation preload only.
- No behaviour change: every content invariant guarded by
  `tests/test_skills_structure.py` (~60 assertions) stays green; no skill renamed,
  no stage moved, README §2/§4 unchanged.

## 0.27.0 — Tier-1 routing pointer at session-start

- `hooks/session-start` now injects a ~80-token Tier-1 routing pointer via
  `additionalContext`: every session carries the "enter
  workspace-shape-preflight → orchestrator, never plan/verify/draft from model
  memory (Source-Verified-First), re-enter orchestrator on resume" imperative.
  This closes the standalone-install routing-discipline gap (no global
  skill-first mandate) without preloading the full `using-tripwork` body — that
  stays lazy-loaded on invoke.
- New `test_session_start_pointer.py` executes the hook and asserts the parsed
  `additionalContext` carries the imperative and stays Tier-1 (not the full
  body). Guards against accidental removal or full-body regression.

## 0.26.0 — preload trim (descriptions + using-tripwork roster)

- Strip what-it-does tails from skill descriptions (13 of 18 trimmed; 5 were
  already clean); add `test_description_hygiene.py` capping every one of the 18
  descriptions at 210 chars with a `Use when` prefix (always-on preload
  regrowth guard).
- Remove the duplicate Quick Reference roster from `using-tripwork` (the
  Pipeline tree already carries the stage roster + output artifacts); add
  `test_using_tripwork_no_qr_roster.py`. Also shrinks the Gemini per-session
  `@import` body for free.
- No behaviour change: no skill renamed, no stage moved, README §2/§4 unchanged.

## 0.25.1 — maps-link gate now catches the percent-encoded (%3A) dead form

0.25.0's `maps_link_resolvable_form` was blind to the **real** dead form. 0.23.0 built
the dead link as `quote("place_id:<id>", safe="")`, which percent-encodes the colon —
the actual URL (and the 76 real consumer dead links) is `…/maps/place/?q=place_id%3A…`,
not the literal-colon `…place_id:…`. The check matched `_MAPS_DEAD = "/maps/place/?q=place_id:"`
against the raw target with no `unquote`, so `%3A` slipped past and 0.25.0 shipped green
on the exact links it was meant to block. The 0.25.0 fixtures used a literal colon, so
the unit + e2e tests were falsely green.

- **Fix:** the dead-form test now runs against `unquote(t)`, so `place_id%3A` decodes to
  `place_id:` and is caught. A resolvable `/maps/place/<name>/@` share link never decodes
  to `/maps/place/?q=place_id:`, so the 0.25.0 false-positive guard is unaffected.
- **Fixtures corrected** to the exact 0.23.0 output via `quote("place_id:<id>", safe="")`
  (real `%3A` form), and a new e2e asserts a `%3A`-form deliverable fails the gate. These
  fixtures are RED against 0.25.0 and GREEN after the `unquote`.
- `maps_url` regression lock also asserts the `%3A`-encoded twin never appears.

## 0.25.0 — export-gate now blocks dead Google Maps links (D2)

The export-gate and html-gate `links_well_formed` check was scheme-only (`^https?://`),
so the 0.23.0 dead `maps/place/?q=place_id:<id>` deep-link form — which Google does not
resolve — passed both gates green while shipping 38 dead POI links in a real deliverable
(hokkaido-7d, 2026-07-01). `maps_url` itself was already fixed in 0.24.0, but nothing
mechanically enforced the ban, so any regression to a dead-but-`https://` form shipped
unnoticed. This adds a mechanical `maps_link_resolvable_form` check to both gates.

- **New gate check `maps_link_resolvable_form`** in `run_export_gate` (over every
  markdown link target) and `run_html_gate` (over every href). It rejects a
  `www.google.com/maps` link only when it is *provably* dead/unresolvable:
  - the D1 `maps/place/?q=place_id:` deep-link form, or
  - a `/maps/search` link with an empty / whitespace-only `query=` (e.g. a nameless POI).
- **Precise blocklist, not a canonical allow-list.** "Is an arbitrary Google Maps URL
  resolvable?" is not regex-decidable — Google has many valid shapes
  (`/maps/place/<name>/@lat,lng` share links, `/maps/@`, path-style dir). An allow-list
  false-positives on those: a POI whose official-source URL is a real, resolvable
  `/maps/place/<name>/@` share link renders as `[官網](…)` and would wrongly fail the
  gate, blocking a valid export. The blocklist leaves every resolvable maps form
  untouched while still catching the dead forms.
- **`&amp;` normalisation** so an html-escaped href in a real rendered page
  (`?api=1&amp;query=`) is matched correctly and not false-failed.
- A dead maps link is **render-fixable** (re-render under the fixed `maps_url`), so it
  stays `retryable: true` — the orchestrator re-exports rather than halting.
- **Regression lock** in `tests/test_render_gmaps.py`: `maps_url` never returns the
  dead `maps/place/?q=place_id:` form and always carries `query_place_id=` when a
  place-id is present, so a future edit cannot silently reintroduce D1.
- **Coverage confirmed** (adversarial audit): the two maps-emitting adapters
  (`markdown.py` → `<slug>-itinerary.md`, `html_page.py` → `<slug>-itinerary.html`) are
  the only export paths carrying `www.google.com/maps` links, and both run through the
  new check; LINE short-text emits no maps links; Notion reuses the gated markdown.
- README §2 export-gate row updated to state Google Maps links are checked to open.

## 0.24.0 — multi-agent runtime support (Cursor / Codex / Kimi / Gemini / OpenCode / Pi)

tripwork now installs and self-bootstraps on six additional AI agent runtimes
besides Claude Code. No skill / script / schema logic changed — this is purely
the packaging, version-sync, tool-mapping, and session-start bootstrap layer,
mirrored from the sibling chipwork plugin.

- **Per-agent manifests** — `.cursor-plugin/`, `.codex-plugin/`, `.kimi-plugin/`,
  `gemini-extension.json`, `package.json` (npm). Each carries tripwork metadata and
  a tool-mapping that translates tripwork's neutral verbs to that agent's native
  tools, including the Source-Verified-First rule: map `WebSearch` to the agent's
  web search, or HALT ("No search, no fact") if it has none.
- **Version-sync** — `.version-bump.json` + `scripts/bump_version.py` keep all 8
  version-bearing manifests (json + pyproject toml) in lockstep; `--check` /
  `--audit` run in CI.
- **Bootstrap** — session-start injection of `using-tripwork` on every runtime:
  shell hooks (Claude / Cursor / Codex), in-process injectors
  (`.opencode/plugins/tripwork.js`, `.pi/extensions/tripwork.ts`), and a Gemini
  `@`-include (`GEMINI.md`). `AGENTS.md` symlinks `CLAUDE.md`.
- **Gates** — `test_version_consistency` (8-manifest), `test_bump_version`,
  `test_version_bump_manifest_lists_all`, `test_alt_platform_descriptors`,
  `test_run_hook_invariants`, `test_agent_context_files`.

## 0.23.1 — fix dead place_id maps link (consumer regression)

The 0.23.0 P9 change rewrote `maps_url`'s place_id branch to the single-param
`maps/place/?q=place_id:<id>` form. Google does **not** resolve that form — every
place_id-bearing POI rendered a dead link, hit during Sun-Moon-Lake dogfood.

- **`scripts/render/gmaps_links.py`** — restored the Maps URLs API form: the visible
  `query=<name district>` (or `query=lat,lng` under `pin_exact`) is kept and a
  `&query_place_id=<id>` refinement is appended, so Maps resolves the exact place while
  the link stays a well-formed `/maps/search/?api=1&query=…` URL. place_id now REFINES
  the query (as it did pre-0.23.0) instead of replacing it. Removed the unused
  `PLACE_BASE` constant; updated the P9 docstring to flag the dead form as not-to-reintroduce.
- **Tests** — migrated all green-locked place_id assertions (in `test_render_gmaps.py`,
  `test_defects_2026_06_21.py`, `test_e2e_defects_all9.py`, `test_e2e_photo_enrichment.py`)
  from the dead `maps/place/?q=place_id` form to `/maps/search/?api=1&query=…&query_place_id=<id>`,
  including the e2e href check asserting the dead form never reappears in a rendered deliverable.
- **`skills/source-verify/SKILL.md`** — P9 prose realigned: place_id feeds a
  `&query_place_id` refinement of the search link, not a `maps/place/?q=place_id:` deep-link.

## 0.23.0 — matrix follow-ups (twins of the v0.22.0 defects)

Three same-root-cause twins surfaced by the v0.22.0 cross-axis matrix audit, fixed via
TDD red→green (`tests/test_followups_0_23_0.py`).

- **F1 (P7-twin) — export-gate `retryable` flag.** `photo_has_attribution` and
  `bookable_has_official_source` were still on the binary fail channel that
  `orchestrator` rule 15 loops on — but they are upstream DATA defects re-rendering can
  never fix, so they looped export-artifact forever (the same infinite-loop class P7
  fixed for google photos). `run_export_gate` / `run_html_gate` now emit `retryable`:
  on `status: fail`, `retryable: false` means every failure is a data defect → the
  orchestrator **stops and asks the user to fix the data** instead of re-rendering;
  `retryable: true` means a render-fixable defect remains → re-render. A fail with both
  stays retryable until the render defect clears, then halts. New optional `retryable`
  field on `gate-report` schema; orchestrator rule 15 + stop-on-confirmation updated.
- **F2 (P6-twin) — `pass_break_even(travellers=)` head-count scaling.** Fares and the
  pass are both per-person, so a multi-traveller trip under-counted the pass cost line.
  The new `travellers` arg (default 1, back-compat) scales both sides → correct group
  `individual_total` / `pass_price` / `saving`; the `use_pass` decision is unchanged
  (head-count-invariant). cost-rollup passes `len(trip-brief.members)`.
- **F3 (P9 coverage) — capture `gmaps_place_id` during the P1 Google check.** `maps_url`'s
  canonical place-id deep-link only fires when `gmaps_place_id` is present. Rather than
  make the field required (which would force a Google dependency on every POI and break
  the no-key design), source-verify now records it **while the agent already has the POI's
  Google Maps card open for the P1 `business_status` check** — zero extra cost, maximising
  canonical-link coverage. Contract change only (source-verify SKILL); no code behaviour.

## 0.22.0 — fix 9 consumer-discovered defects (Sun-Moon-Lake dogfood)

Nine defects hit end-to-end while a consumer ran the full pipeline for a 3D2N
Sun Moon Lake self-drive trip. Each is fixed with a TDD red→green cycle; a single
e2e fixture (`tests/test_e2e_defects_all9.py`) exercises all nine simultaneously,
including the cross-defect gate run where P1/P2 filter the POIs, P4 folds the chosen
lodging, and P5 covers the thematic must_do in one pass.

- **P1 — operating status (Gate 0) is now enforced, not defaulted.** A permanently/
  temporarily closed venue used to sail through as `verified` because `operating`
  defaulted to `True` and nothing fetched a signal. `scripts/verify.py::verify_poi` now
  reads a sourced `business_status` (Google Places vocabulary `OPERATIONAL` /
  `CLOSED_TEMPORARILY` / `CLOSED_PERMANENTLY`) off the POI: CLOSED → `rejected` before
  geocode; an **absent / unknown signal → `unverified` (never a silent `verified`)**.
  New optional `business_status` field on `verified-pois` + `candidates` schemas;
  `operating_from_status` maps the vocabulary. `classify_candidate`'s low-level
  `operating` default is unchanged.
- **P2 — renamed-neighbour / name-drift false match caught.** `scripts/geocode.py::
  name_matches` confirms the resolved place corresponds to the queried venue (conservative
  CJK containment on the venue token); a mismatch (querying 星月大地 but Nominatim returns
  星月驛站) → `conflicting` ('name mismatch'), not `verified`. `verify_poi(resolved_name=…)`
  / `classify_candidate(name_match=…)` wire it in.
- **P3 — famous CJK landmarks resolve first-pass.** `resolve_place(name_roman=…)` adds an
  English-name attempt and a bare-core-name free-text attempt after the street-slot
  structured query and the combined query miss, so 日月潭文武廟 / 九族文化村 / 向山遊客中心 …
  resolve without a manual English-retry pass.
- **P4 — chosen lodging resolvable by gate AND export.** `scripts/gate.py::
  chosen_lodging_pois(accommodations)` yields each stop's chosen lodging as a POI-shaped
  dict; `run_gate` folds it into the reference pool and `itinerary-synthesis` /
  `export-artifact` build `poi_map` the same way, so a `day.lodging` hotel id resolves
  natively — without polluting canonical `verified-pois.yaml`.
- **P5 — `must_do` is thematic, gate verifies coverage.** `trip-brief.must_do` entries are
  free-text themes (e.g. `日月潭遊湖賞景`). `itinerary.must_do_coverage` (theme → covering
  POI ids) lets `run_gate` check each theme has ≥1 scheduled covering POI. A scheduled POI
  id still self-covers (id-based back-compat).
- **P6 — rooms multiply + budget scope.** `accommodations.cost.rooms` + `scripts/cost.py
  ::lodging_line_amount(cost, nights, rooms)` cost a multi-room stop as per-room × rooms ×
  nights. `trip-brief.budget` is documented as the whole-trip total (lodging + transport +
  incidentals) that `cost-rollup` already compares against.
- **P7 — non-distributable deliverable has a terminal state.** A personal HTML variant with
  `photo_source: google` no longer fails `export-gate` (which made `orchestrator` re-export
  loop forever). `run_export_gate` / `run_html_gate` emit `distributable: false` (a clean
  terminal "personal variant complete" — status stays `pass`); a genuine render defect still
  fails and loops. New optional `distributable` field on `gate-report` schema; orchestrator
  rules 15/16 recognise the terminal.
- **P8 — media side-file present but 0 photos is caught.** `run_html_gate(media_count=N)`
  fails when a media side-file was loaded but the rendered HTML has 0 `<img>` — catching a
  dropped (non-mutating) `apply_media` return. `apply_media`'s docstring + `export-artifact`
  now mandate capturing the return.
- **P9 — Maps links use the canonical place_id form.** `maps_url` returns
  `maps/place/?q=place_id:<id>` when `gmaps_place_id` is present (exact single place; wins
  over `pin_exact`), falling back to name-search otherwise. Google deprecated the official
  URL shortener, so true short links are not API-mintable — place_id canonical is the
  cleanest stable form with no new dependency.

Next-version follow-ups surfaced by the cross-axis matrix (same root-cause twins, out of
scope here): `conflict_detected` default (P1 twin), `photo_adapter` name+region image match
(P2/P3 twin), `export_gate._find_rows` name-substring matcher (P4 twin), `line_short` has no
lodging line (P4 twin), `cost.pass_break_even` no head-count multiplier (P6 twin),
`photo_has_attribution` / `bookable_has_official_source` on the binary loop channel (P7
twins), `apply_media` ignores typo'd media keys (P8 twin), `dir_url` place_id deep-link (P9
twin), and making `gmaps_place_id` non-optional (P9 depends on it).

## 0.21.0 — require name_zh for kana-named verified POIs (gloss-at-source guard)

A verified POI whose `name_display` contains kana renders its maps-link label as
`name_display（name_zh）`; without `name_zh` the label is bare kana a Chinese reader can't
read. `name_zh` was optional. This adds a forward data-quality guard so a kana-named POI
cannot be scheduled without its Chinese gloss. **Forward guard only — the dogfood data
already complies (0 verified violations; the 9 bare-kana POIs are all `unverified` and never
render).**

- **Rule:** a `verify_status: verified` POI whose **rendered name** (`name_display`, else
  `name_local`) matches kana (`[぀-ヿ]`) must carry a non-empty `name_zh`. Pure-Han names
  (五稜郭, 函館駅) are exempt (readable); non-verified POIs are exempt (never rendered).
  `name_display` is now also `minLength: 1` (an empty display name fell back to a possibly-kana
  `name_local`, slipping the guard — caught by adversarial review).
- **`scripts/gate.py::run_gate` (runtime guard):** the referenced-POI loop adds
  `referenced_pois_glossed` — a scheduled verified kana-named POI lacking `name_zh` fails the
  gate, naming the POI id. This is the load-bearing enforcement (verified-pois.yaml is not
  runtime-schema-validated). Predicate `text_hygiene.kana_name_without_gloss(poi)`.
- **`schemas/verified-pois.schema.json` (declarative contract):** a third `allOf` if/then —
  `verified` + kana `name_display` ⇒ `name_zh` required, `minLength: 1`.
- **`source-verify` SKILL:** `name_zh` is no longer "optional" — it is REQUIRED when the name
  contains kana.

No consumer migration (real data already compliant). The kana-gloss check on free *prose*
stays per-line best-effort and is a separate, abandoned concern (string-heuristic precision
on Chinese-prose-with-Japanese-names is not viable — see that work item).

## 0.20.0 — canonical content-hygiene gate (protects every renderer) + Notion de-adapted

0.19.0 added the `no_internal_jargon` check to the md + html export gates but left
`line_short.py` un-gated and `run_html_gate` without a kana-gloss check — a cross-axis gap
(the same content checks lived per-renderer and were missed for two of three text
deliverables). This release moves the **format-agnostic** content checks to the canonical
layer so a leak is blocked at the source, before any renderer runs.

- **Canonical content hygiene (`scripts/gate.py::run_gate`).** `no_internal_jargon` +
  `japanese_glossed` now run (always-on) over `_itinerary_text`, which is a **superset of
  every authored free-text field a renderer surfaces** — `title` + each day `label` +
  `checklist` + each row `text` + each move row's `from`/`to` endpoints (all unescaped).
  Blocking a leak here keeps **every** renderer clean by construction — md, html,
  line-short.txt (which has no gate of its own and renders the title + labels verbatim), and
  a Notion page pasted from the md — and future renderers too. This is the PRIMARY guard;
  the `export-gate` md/html copies stay as render-layer defense-in-depth. (An adversarial
  review caught that an earlier draft scanned only `checklist` + row `text`, so a leak in
  the title/label/endpoints would have shipped to line-short ungated — now closed.)
- **Shared `scripts/text_hygiene.py`.** `jargon_failures(text, pois)` + `kana_gloss_failures
  (text)` lifted into one module imported by both `gate.py` and `export_gate.py` (imports
  only `re` → no cycle); single implementation, no drift. Behaviour identical (messages
  unchanged); the jargon scan keeps the backslash-stripped probe so md-escaped leaks
  (`must\_do`, `(hak-yam\_yakei)`) are still caught render-side.
- **`line_short.py` gap closed at the source.** It keeps its deterministic
  `chunk_line_messages` (LINE 5000-char cap, day-boundary split) + no-URL discipline and
  needs no gate of its own — the canonical guard guarantees its input is clean. (Resolves
  the v0.19.0 "line_short follow-up".)
- **Notion de-adapted.** `export-artifact` no longer documents a Notion write-back adapter /
  graceful-skip / page-id bookkeeping. To put the itinerary in Notion, paste the gated
  `exports/<slug>-itinerary.md` via the consumer's Notion MCP — content = md = already
  validated. No code referenced a Notion path (it was always skill-only).

Scope notes (deliberately deferred to separate future items, not bundled here):
- `run_html_gate` still has no `bookable_has_official_source` check — the HTML renderer emits
  no official-source links to check (only maps chips), so gating it would require adding
  official-link *rendering* to the one-pager (a different check family — link-completeness,
  not content-hygiene; md already enforces it).
- The kana-gloss check is per-LINE, not per-RUN: a line that already carries one `（…）`
  paren (a glossed term, or a rendered maps-link target) masks a *second* ungloss kana run
  on the same line. Tightening it to per-run is a kana-heuristic redesign with its own
  false-positive edge cases (kana nested inside a gloss paren; bare-kana POI link labels for
  the ~9 dogfood POIs that lack `name_zh`) and consumer re-gloss impact, so it is tracked
  separately rather than rushed into this release.

Migration note: the canonical kana check is stricter than the old md-only check (which a
POI-link's `（gloss）` on the same line could mask), so an existing `itinerary.yaml` with
ungloss kana in a **checklist** item or row `text` will now fail `itinerary-gate` until the
synthesis author adds the （中文）gloss — the documented gloss discipline, now enforced at
the source. (e.g. the dogfood `hokkaido-7d` checklist `かに将軍` / `ラビスタ函館ベイ` need glossing.)

## 0.19.0 — 3-col grid itinerary layout + move directions links + content-hygiene gate

The native HTML/markdown renderer adopts the consumer's hand-built one-pager layout
(G1–G5), adds structured move-row directions links (G2), and grows a mechanical gate that
stops internal jargon from reaching user-facing deliverables (G6). Verified to reproduce
the visual baseline (`trips/hokkaido-7d/exports/hokkaido-7d-itinerary.html`) structurally
on real data. Backward-compatible: trips without `from`/`to` render exactly as before.

- **G1 — 3-column grid (`_STYLE`, `_row_html`, `_photo_html`).** Rows render as a CSS grid
  `48px 1fr 64px` (時間 | 說明 | 縮圖) with an always-present reserved `.thcol` thumb cell,
  so photo-less rows still column-align. The separate `.emo` column is gone (the slot emoji
  folds into the 說明 cell); the thumb lives in `.thcol` / `.lodge` instead of a
  `margin-left:auto` flex sibling.
- **G2 — move directions chip + chip-at-start (`gmaps_links.dir_url`, `_row_chip_body`,
  `markdown._move_cell`).** New optional `row.from`/`row.to` schema fields
  (`additionalProperties:false` intact, keyword-safe via `row.get()`); `dir_url` builds
  `maps/dir/?api=1&origin=…&destination=…` with **no** `&travelmode` (user picks
  car/transit). The maps chip moves to the START of the 說明 cell with the slot emoji
  (dropping the literal 🗺️); a move row with endpoints leads with an A→B directions chip in
  both HTML and markdown. A move row without `from`/`to` is unchanged (no fabricated link).
  A move row that *also* carries a `poi_id` keeps the POI maps link + official source after
  the directions chip (so a bookable POI on a move row still satisfies the export-gate
  bookable-official-source check) and suppresses the now-mismatched thumbnail. The
  `itinerary-synthesis` SKILL output contract documents the `from`/`to` row fields so the
  synthesis author actually populates them.
- **G3 — 備案 as in-cell `.altbox` (`_STYLE`, `_row_html`).** A `▸` 備案 row is a full-width
  orange `.altbox` INSIDE the 說明 cell with an empty time cell and an empty thumb cell
  (never a thumbnail, even when its POI carries a photo) — superseding 0.18.4's whole-row
  `li.row.alt` box.
- **G4 — look-ahead dashed grouping (`_day_html`).** The dashed row separator is opt-in per
  `dashed = (not last) and not next_is_alt`: real→alt none, alt→alt none, alt→real dashed,
  real→real dashed, *→last none. This carries 0.18.4's 備案-binds-to-slot intent forward
  (the `↳` attach connector + `_attached_flags` + `.row.alt.attached` are removed).
- **G5 — lodging box (`_STYLE`).** The `.lodge` line is a light-blue rounded card
  (`background:#f0f9fb`); its thumb is right-aligned via `.lodge .thumb{margin-left:auto}`.
- **G6 — `no_internal_jargon` gate (`export_gate._jargon_failures`, `itinerary-synthesis`
  SKILL).** `run_export_gate` (md) and `run_html_gate` (html) hard-fail on a leaked internal
  `(poi-id)` token or the literal `must_do`, keyed off the authoritative POI id set (literal
  `(<id>)` match → zero false positive on legitimate romaji parentheticals). The scan runs
  over a backslash-stripped probe so a markdown-escaped leak (`must\_do`, `(hak-yam\_yakei)`)
  is still caught. Authoring rule documented in the synthesis skill.

Known follow-up (out of scope): `scripts/render/line_short.py` has no gate, so a `must_do` /
`(poi-id)` leak in `line-short.txt` still ships — closing it needs a new `run_line_gate`
(`run_export_gate` is md/html-only).

## 0.18.4 — D11 slot-level 備案 visually bound to the slot it replaces

Pure CSS/markup polish (`scripts/render/html_page.py`); no gate or schema change.

A `▸` alternative (備案) row used to render as a standalone orange box separated by the
same dashed border as every other row, so it was unclear which slot it replaced. Now a
**mid-day** alt-run is attached to the slot above it.

- **Attach rule (`_attached_flags` + `_day_html`).** A maximal run of consecutive alt
  rows is *attached* iff it is sandwiched between a real row **both before and after**
  (a fallback for the preceding slot). The attached alt gets `class="row alt attached"`
  and the real row above gets `has-alt`; a **trailing** run (day-tail 本日備案, e.g.
  「備案(乃の風訂不到)」) or a **leading** run stays an independent box. Consecutive alts
  bind to the same parent.
- **Connector styling (`_STYLE`).** `.row.alt.attached` drops its top border + top
  radius, indents to the `.bd` column (`margin-left:62px`), and shows a `↳` `::before`
  connector; the parent real row drops its dashed separator (`.row.has-alt`) so the pair
  reads as “↳ if … then …”.

Note: the slot-vs-day distinction is positional only — a mid-itinerary day-level note
(e.g. a luggage-transfer line) still attaches to the row above it; cleanly separating
those would need a synthesis-level day-scope marker (out of this render-only scope).

## 0.18.3 — D10 lodging thumbnail alignment

Pure CSS/markup polish (`scripts/render/html_page.py`); no gate or schema change.

- **Lodging thumbnail right-aligned, consistent with row thumbs.** `_day_html` previously
  emitted the lodging `_photo_html` as a sibling **after** the `.lodge` `</div>`, landing
  in the non-flex `.day-card` where `.ph{margin-left:auto}` was a no-op — so the lodging
  thumb hung at the left while every row thumb sat at the right. The photo is now nested
  **inside** the `.lodge` div, and `.lodge` is a flex row
  (`display:flex;align-items:center;flex-wrap:wrap;gap:6px`), so its thumb pins to the
  right edge like the rest.

## 0.18.2 — D9 photo caption layout: thumb-title attribution + centred lightbox caption

Pure CSS/markup polish on the photo caption (`scripts/render/html_page.py`); no gate
or schema change.

- **Row caption removed.** `_photo_html` no longer emits a `<span class="phcap">` under
  the thumbnail. The duplicate caption (already shown in the lightbox) was stretching
  the 60px thumb's column to ~170px. Attribution now rides on the thumbnail's **`title`
  attribute** (visible on hover, plain-text `📷 author / license`, `_html_escape`'d) plus
  the lightbox caption — so CC attribution stays reachable without occupying the row.
- **Lightbox caption centred.** `.lbbox` is now a vertical flex column
  (`display:flex;flex-direction:column;align-items:center`) and `.lbimg` is
  `display:block`, so `.lbcap` sits centred directly under the image. Previously
  `text-align:center` on an inline image/caption pushed a landscape image's caption to
  the right.

## 0.18.1 — D8 photo polish: right-aligned thumbnail + gate-on-merged-pois

Visual + correctness polish on the 0.18.0 photo enrichment.

- **🖼️ Right-aligned thumbnail (`scripts/render/html_page.py`).** The POI photo was a
  168×120 block stacked under each row's text. It is now a **60×60 square thumbnail
  (`object-fit:cover`) pinned to the right edge of the row**: `_row_html` emits the
  `.ph` block as the last flex child of `<li class="row">` (a sibling **after** `.bd`,
  not nested inside it) and `.ph`/`.thumbwrap` carry `margin-left:auto`. The pure-CSS
  checkbox lightbox and the mandatory attribution caption are unchanged.
- **🚦 Export-gate runs on the MERGED pois (`skills/export-gate/SKILL.md`).** The gate's
  `photo_has_attribution` + `no_nondistributable_photo_source` checks only see a
  `photo`/`photo_source` on the side-file-merged pois. The Stage Contract previously fed
  the gate the canonical `verified-pois.yaml` (which never carries photos, by design),
  so those checks spun against nothing. The contract now requires overlaying
  `verified-pois-media.yaml` via `scripts/media_merge.py::apply_media` (the same overlay
  `export-artifact` applies before render) before invoking the gate; the photo checks
  and the `<img src>` whitelist are now documented in the Checks list.

## 0.18.0 — opt-in CC photo enrichment + place_id deep-link + img-src/attribution gate

Adds **optional, license-clean, attributed POI photos** to the HTML one-pager (plus
a Google-Maps `place_id` deep-link upgrade), behind a pluggable photo adapter whose
**default backend is `none`** — nothing changes for existing trips. Photos are
provenanced, CC-whitelisted, durable across re-verify (stored in a side-file, never
in the wholesale-rewritten canonical yaml), and gate-enforced. Delivered as a delta
on 0.17.0 under the 8-step pre-ship gate (TDD red→green, full pytest green, a single
cross-defect e2e fixture, an 8-agent adversarial matrix re-review).

**Boundary principle (ToS safety):** the *mechanism* (adapter dispatch, license
whitelist, base64 encode, gate) ships in-plugin and is generic; the *data* (a
licensed image, an API key) is supplied at runtime by the operator who owns the ToS
relationship. `backend=none` ships enabled; `backend=wiki` is CC-only and safe to
distribute; `backend=google` is BLOCKED (no display-surface ToS clearance / no
personal-cache exception) **and** its output is marked non-distributable by the gate.

- **🗺️ Maps `place_id` deep-link.** `scripts/render/gmaps_links.py::maps_url` appends
  `&query_place_id=<id>` (fully percent-encoded, `safe=''`) when a POI carries the new
  optional `gmaps_place_id`, in both the name-search and `pin_exact` branches — the
  visible `query` (name or coords) is left intact. Both markdown + HTML adapters inherit
  it from the shared builder.
- **🖼️ Photo schema fields.** `schemas/verified-pois.schema.json` gains optional
  `gmaps_place_id`, `photo` (`{url|data, width?, height?, thumb?}`; `url` pinned
  `^https://`, `data` pinned `^data:image/`), `photo_attribution`
  (`{author, license, source_url}`, all required + non-empty when present), and
  `photo_source` (enum `{wikimedia, openverse, google}`). A new `allOf` conditional
  enforces **photo ⇒ photo_attribution**. None are added to `required`; the line-330
  POI seal still rejects typo keys.
- **🗄️ Durable side-file + render-time merge.** A new
  `schemas/verified-pois-media.schema.json` governs `trips/<slug>/verified-pois-media.yaml`
  (keyed by `poi_id`, own `additionalProperties:false` seal). `scripts/media_merge.py`
  overlays it onto the poi_map at export (`apply_media` is a pure, non-mutating, key-
  whitelisted overlay; `load_media` degrades to `{}` on absent/corrupt/non-dict). Media
  is **never** written into canonical `verified-pois.yaml` (source-verify rewrites it
  wholesale). `export-artifact` SKILL prose wires the overlay in before render.
- **📷 Photo render: thumb + pure-CSS lightbox + mandatory caption.**
  `scripts/render/html_page.py` renders a `data:`/`https` thumbnail, a **pure-CSS
  checkbox-hack lightbox** (no `<script>`, no `href`/`#anchor` toggle), and a
  **mandatory, `_html_escape`'d attribution caption** (author / license + source link).
  Checkbox ids are unique per call site (a POI can be both a row and the day's lodging).
- **🚦 Export-gate hardening (`scripts/export_gate.py`).** `run_html_gate` adds an
  `<img src>` whitelist (`data:image/` or `https://` only — the gate was previously
  `href`-only and structurally blind to `src=`). Both gates add **photo ⇒ non-empty
  (stripped) attribution** and **`photo_source=google` ⇒ non-distributable** checks
  (`img_src_safe`, `photo_has_attribution`, `no_nondistributable_photo_source`), so
  the distributability guard ships even though no google backend exists yet.
- **🧩 Pluggable CC photo adapter (`scripts/photo_adapter.py`, `backend=wiki`).**
  Wikimedia Commons + Openverse client; **hard license whitelist** `{CC0, PD, CC-BY,
  CC-BY-SA}` rejecting NC/ND; 2-size base64 (thumb + full); descriptive User-Agent on
  every request; caller-supplied per-source `RateLimiter` (mirrors the Nominatim
  ≤1 req/s discipline); per-trip cache; `name_local`-first query + geocode location-
  match; landmark-only. CC-BY-SA is kept (share-alike binds the image, not the MIT
  plugin code; the rendered caption + source link satisfy its terms).
- **Adversarial-review hardening (step 8).** Stripped whitespace-only attribution
  before the gate truthiness test; `load_media` now guards non-dict YAML + broadens
  its `except` to `OSError`/`UnicodeDecodeError` (mirroring `geocode_cache`);
  `apply_media` ignores a non-dict media entry.

README: §3 deliverables gains a plain-language photo bullet; the §2 step-table
`export-artifact` row notes the optional photo overlay; the 開發者資訊 `<details>`
documents the adapter/side-file/schema/gate. No new pipeline stage → §2 mermaid
unchanged (render-time, in-stage feature).

## 0.17.0 — card-style HTML one-pager + mobile RWD fail-safe + XSS hardening

The `html` export adapter (`scripts/render/html_page.py`) is rewritten from a
plain card list into a magazine-style one-pager, modelled on the hokkaido-7d
dogfood deliverable. Everything new is derived strictly from `itinerary.yaml`
fields — nothing is fabricated (Source-Verified-First): the advisory `warn`
box from the hand-authored reference is intentionally omitted because that data
is not in the itinerary dict.

- **🎨 Card-style layout.** Gradient hero with a date-span (from `days[].date`)
  and a 🏨 lodging-flow line (distinct consecutive overnight stays with ×count,
  resolved from per-day `lodging`); a per-day overview table (日 / 行程 / 住宿);
  an emoji legend; rounded shadowed `.day-card`s with a day-number badge and a
  lodging maps link; per-slot row colouring (meal / visit / activity / move /
  lodging); and orange-bordered inline 備案 rows (a row whose `text` starts `▸`).
  The `lodging` field — previously ignored by every renderer — is now surfaced
  as a maps-linked line and in the overview/hero (HTML adapter only).
- **📱 Mobile RWD fail-safe.** Flex rows default to `min-width:auto` and will not
  shrink, so a long Japanese map label forced a horizontal page overflow on
  phones. Fixed with `html,body{overflow-x:hidden}` (backstop),
  `.bd{min-width:0;overflow-wrap:anywhere}`, an `a.map` that wraps
  (`word-break:break-word;max-width:100%`, no more `white-space:nowrap`), and
  `word-break:break-word` on overview table cells (the one long-content element
  outside the flex fix).
- **🔒 XSS hardening.** `_date_span` was the sole interpolation point left
  unescaped; a crafted `day.date` (e.g. `<img src=x onerror=…>`) reached the
  hero verbatim **and passed `run_html_gate`**, whose only markup guard is a
  literal `<script>` substring check. `_date_span` now escapes, matching the
  discipline applied to every other field. (Surfaced by an adversarial review.)
- **Gate compatibility unchanged.** Every emitted `href` is an https Maps URL
  (href-first attribute order) and exactly one `class="day-card"` is emitted per
  day, so `export-gate` / `run_html_gate` still pass; the markdown / gmaps /
  line / Notion adapters are untouched. README §3 deliverable copy updated.

## 0.16.0 — hokkaido-7d dogfood defects (D1-D4)

Four defects surfaced by a real Hokkaido 7-day dogfood run, plus a cross-cutting
audit of the false-pass shape that produced two of them.

- **D1 🔴 Google Maps links — name-search-first.** `maps_url` now returns
  `query=<name_local> <district>` so Google resolves a labelled place card,
  reversing the TW-048 coord-first default that produced unnamed pins for area
  POIs (onsen districts, parks, markets). Coordinate pinning is now opt-in via
  `geocode.pin_exact: true`. Source-verify gained `normalize_and_validate_poi`,
  which normalises legacy `lon`/`long` geocode keys to `lng` and **rejects**
  `name_local == district` (the `cluster_fallback` town-name bug, where a POI's
  name was silently overwritten by its area).
- **D2 🟠 itinerary-gate false-pass — overnight lodging floor.** New always-on
  `overnight_days_have_lodging` check derived from `itinerary.yaml`: every
  non-final day must resolve lodging (a `lodging` field or a `slot:"lodging"`
  row), independent of whether `accommodations.yaml` was passed. Previously the
  lodging check was gated behind the optional `accommodations` arg, so an
  itinerary with no overnight rows passed silently.
- **D3 🟡 Japanese gloss.** New optional `name_zh` schema field and render label
  `name_display（name_zh）`; new hard-fail export-gate `japanese_glossed` — any
  line carrying kana (hiragana/katakana) without a `（中文）` gloss fails
  (Han is excluded to avoid ZH/JP false-positives). Itinerary-synthesis must
  author inline Japanese terms as `日文（中文）`.
- **D4 🟡 HTML export adapter.** New `scripts/render/html_page.py` renders a
  self-contained, offline, elder-friendly one-page `exports/<slug>-itinerary.html`
  (inline CSS, mobile RWD, Maps links inheriting the D1 name-search fix),
  validated by the new `run_html_gate`.
- **D2-class advisory fix 🔴 itinerary-gate — advisory presence enforced.** New
  always-on `advisory_present` safety floor: `advisory` is now a **mandatory**
  gate input. An absent advisory **fails the gate** ("advisory absent — …")
  instead of silently skipping the banned/restricted surfacing check. Unlike the
  D2 lodging floor (derivable from `itinerary.yaml`), the banned/restricted list
  lives *only* inside `advisory.yaml`, so absence cannot be reconstructed — the
  only safe response is failure. An advisory that ran but flagged nothing passes
  as `{"items": []}`. The per-item `advisory_items_surfaced` loop is unchanged
  and now runs only once `advisory_present` confirms an advisory exists. This
  closes the D2-class false-pass hole for the 🔴 safety gate.
- **Cross-cutting audit.** The "optional-input → skipped-check" false-pass shape
  (root of D1+D2) was swept across `scripts/`. The advisory sibling is fixed
  above; the remaining two out-of-scope instances in `gate.py` — the **calendar
  and must_do** checks, each gated behind their optional arg — are flagged for
  **v0.17.0 follow-up**, NOT fixed here.

## 0.15.0 — 2026-06-11

Research discipline + script robustness + adapter fidelity (Wave 4, final wave of the
2026-06-11 agentic-robustness audit) — 25 defects closed.

- **Script edge-cases:** `cost.sum_costs` raises on a non-numeric `amount` (no silent
  zero); `hours.to_minutes` rejects a non-`HH:MM` value (no crash deep in scheduling)
  and `closing_status` handles overnight (past-midnight) windows; `legs.misses_last_service`
  handles a small-hours last service; `geocode.resolve_place` rejects an empty name;
  `season.approx_sunset` accepts `lng`+`utc_offset_hours` for a civil-time correction.
  (TW-014, TW-020, TW-047, TW-021, TW-045, TW-050)
- **Cache integrity:** `geocode_cache.load_cache` tolerates a corrupt/non-dict file
  (renames to `.corrupt`, returns `{}`), `save_cache` is atomic (temp + `os.replace`),
  and `resolve_place` validates a cache hit's shape/source before trusting it. (TW-046,
  TW-019)
- **Export-adapter fidelity:** link labels escape `]`/`|`/`$`, source URLs percent-encode
  `)`; Google-Maps links are coordinate-pinned (or district-disambiguated); export-gate's
  bookable check scans table rows (not a heading) across all of a POI's rows; LINE output
  chunks at day boundaries under the 5000-char cap. (TW-022, TW-048, TW-044, TW-049)
- **Research discipline:** source independence is by distinct domain (`verify.py`);
  "no search, no fact" halts a research stage when WebSearch is unavailable; conflict and
  independence are defined operationally; hours carry an `as_of` recency; calendar requires
  trip-year coverage (`provisional` field); hotel centroid-fallback needs an existence
  proof; Gate 3 resolves the claimed-district centroid; negative-cache entries are
  invalidated on manual re-verify; Notion write-back runs only post-gate. (TW-023, TW-024,
  TW-032, TW-033, TW-052, TW-051, TW-058, TW-057, TW-025, TW-039, TW-061)
- **Tests:** a cross-stage closure fixture (verify→gate→render→export-gate) and README
  mermaid stage-coverage/order guards. (TW-059, TW-060)

## 0.14.0 — 2026-06-11

Flow + skill-contract hardening (Wave 3 of the 2026-06-11 agentic-robustness audit) —
12 defects closed. Makes the orchestrator's routing predicates explicit and gives
every halt condition an owning, testable stage.

- **Orchestrator routing made explicit:** `stale` (rule 3) and `ready` are now defined
  predicates (`scripts/orchestration.py::candidates_stale`); stage names are
  `tripwork:`-namespaced (no paperwork collision); a fail-routing rule (13.5) maps
  gate failure classes to owning stages; rule 13 re-runs the gate when itinerary is
  newer; a terminal rule declares the pipeline complete on export-gate pass. (TW-053,
  TW-054, TW-029)
- **Slug binding (rule 0.5):** a new trip allocates an unused `<slug>`; a resume names
  one existing `trips/<slug>/`; file-existence rules never apply across trips.
  trip-brief derives `<yyyy-mm>-<destination>` and stops on collision. (TW-027)
- **Halt list synced with what stages emit:** adds reception-after-close (no late
  check-in), scopes the regulation halt to `banned` only, and adds a stage-state
  read-back rule so a recorded decision is not re-asked. (TW-031, TW-055)
- **stage-state.yaml schema** (`schemas/stage-state.schema.json`) — decisions are now a
  validated, re-readable record. (TW-055)
- **Owned halts:** `booking lead-time missed` is owned by itinerary-synthesis via
  `scripts/booking.py::lead_time_missed`; `missed_last_service` is re-checked at
  synthesis once the departure is known (no longer suppressed). (TW-030, TW-026)
- **Hop plausibility floor:** `scripts/distance.py::min_plausible_mins` flags an
  `implausible` hop estimate below a physical speed floor (urban transit ≈ 15 km/h);
  routing-audit re-estimates rather than trusting a too-fast guess. (TW-056)
- **travel-advisory standalone mode** must not overwrite the pipeline `advisory.yaml`
  (writes `work/<slug>/advisory-adhoc.yaml`); orchestrator rule 11 treats a stale
  advisory as re-runnable. (TW-035)
- **trip-brief** is orchestrator-routed, guards on the preflight stamp before writing,
  and **using-tripwork** regenerates the full 17-stage pipeline tree. (TW-036, TW-037)

## 0.13.0 — 2026-06-11

Schema strictness (Wave 2 of the 2026-06-11 agentic-robustness audit) — 10 defects
closed. Tightens every artifact schema so a hallucinating agent's malformed output
is rejected at validation instead of flowing downstream silently.

- **`additionalProperties: false`** on every object schema across the 13 files — a
  typo'd key (e.g. `close_days` for `closed_days`) is now rejected instead of
  silently vanishing. (TW-013)
- **Source URLs** must match `^https?://` everywhere a `url` field appears; a bare
  token like `"airline"` no longer validates. (TW-008)
- **Coordinates** bounded: `lat ∈ [-90, 90]`, `lng ∈ [-180, 180]` in verified-pois /
  accommodations / routing — swapped or placeholder coordinates rejected. (TW-043)
- **ISO date pattern** (`^\d{4}-\d{2}-\d{2}$`) on calendar / trip-brief / seasonal
  date fields, so non-ISO dates can't silently disable date-equality logic. (TW-007)
- **advisory** requires `risk` and ≥2 sources; **calendar** holiday requires `impact`
  with `crowds`/`closures`; **cost** requires `as_of` + `estimate_note` (adds
  `fx_as_of`/`fx_source`); **legs** `fare`/`pass.price` require `amount`+`currency`;
  **transit** walks/peak_windows require sources (walk requires `station`). (TW-006,
  TW-040, TW-041, TW-042)
- **legs.mode** constrained to `drive|rail|bus|flight|ferry`; a `drive` leg requires
  `duration_mins` (schema if/then) and `scripts/legs.py::classify_leg` raises instead
  of defaulting an unmeasured drive to feasible. (TW-010)
- **trip-brief** requires a `destination` object (`country`/`city`/`local_lang`) and
  an optional `airline`, consumed by source-verify and travel-advisory. (TW-011)

## 0.12.0 — 2026-06-11

Iron-rule mechanization (Wave 1 of the 2026-06-11 agentic-robustness audit) — 14
defects closed. The itinerary becomes a canonical structured artifact so the gate
validates an artifact instead of an LLM-reconstructed dict, and travel-advisory
moves before synthesis so banned/restricted regulations shape the plan.

- **Keystone — canonical `itinerary.yaml`** (`schemas/itinerary.schema.json`, new).
  `itinerary-synthesis` now emits `itinerary.yaml` (`days[].rows[]` with `poi_id`,
  `slot`, `time`, `text` + optional `checklist`) as the single source of truth;
  `itinerary.md`, LINE and Maps exports all render from it. `scripts/gate.py::run_gate`
  consumes the structured itinerary, not a reconstructed days list. (TW-003, TW-017)
- **itinerary-gate now checks verification status.** A `conflicting`/`unverified`
  POI with a geocode no longer passes; `geocode: null` is caught. New checks:
  `referenced_pois_verified`, `no_closed_day_violation`, `must_do_covered`,
  `advisory_items_surfaced`. (TW-002, TW-018, TW-038, TW-034)
- **travel-advisory runs before itinerary-synthesis.** advisory.yaml now feeds the
  synthesis checklist and the gate; banned/restricted items must be surfaced.
  README §2 mermaid + step table reordered. (TW-028, TW-034)
- **source-verify Gate 0 (operating status).** A permanently/temporarily closed
  (defunct) POI is `rejected` instead of passing as `verified`. (TW-005)
- **Schema strictness:** `verified-pois` requires `geocode` + ≥2 sources only when
  `verify_status: verified` (non-verified require a non-empty `status_reason`);
  `closed_days` constrained to canonical weekday / ISO-date / `public_holiday`
  tokens, normalized in `poi_closed_on`; `gate-report` rejects `status: pass` with
  failures or empty checks. (TW-012, TW-001, TW-009)
- **export-gate** fails an empty or too-few-days deliverable; the `official` source
  flag is now authored by source-verify so the bookable-link check is enforceable.
  (TW-015, TW-016)

## 0.11.2 — 2026-06-09

Docs — wrap README pipeline mermaid node labels to stop GitHub CJK clipping.

- `README.md` §2 flowchart: the 0.11.1 `htmlLabels` directive did not stop the
  clip on GitHub (GitHub measures CJK glyph advance too narrow at render time,
  sizing node boxes by the Latin skill-name line while the wider CJK detail line
  overflows and the trailing characters are clipped). Re-flow every node's detail
  into shorter `<br/>`-separated lines so no single CJK line exceeds the box
  width. All label text preserved verbatim — only line breaks added.

## 0.11.1 — 2026-06-09

Docs — fix README pipeline mermaid clipping CJK node labels on GitHub.

- `README.md` §2 flowchart: add `%%{init: {'flowchart':{'htmlLabels':true}}}%%`
  directive so node labels render via foreignObject (browser box-model layout)
  instead of SVG `<text>` width estimation. GitHub's client-side width measure
  undercounts CJK glyph advance (treats them as Latin half-width before the web
  font loads), sizing node boxes too narrow and clipping trailing characters.
  No label text changed — every character preserved.

## 0.11.0 — 2026-06-06

Transit polish — intra-city comfort for elderly / luggage trips.

- New `transit-detail` stage (`skills/transit-detail/`): researches the destination's
  commuter **peak windows**, an **IC-card** advisory (Suica / ICOCA / T-money / …), and
  per-POI **station-to-POI walk** notes into `transit.yaml`
  (`schemas/transit.schema.json`). Wired as orchestrator stage 9. All advisory — no
  stop-on-confirmation, no `itinerary-gate` change.
- `scripts/transit.py`: pure `in_peak` (is a move in a rush-hour window?) + `walk_too_far`
  (is a station-to-POI walk over the comfortable max?).
- `trip-brief` schema gains `routing.max_walk_mins` (default 15).
- `itinerary-synthesis` consumes `transit.yaml`: off-peak advice for groups with elders /
  children, a taxi/flag for long walks, and the IC-card + walk notes into the checklist.
  No-key research, same model as calendar / seasonal.

## 0.10.0 — 2026-06-06

Geocode cache (faster re-runs, less Nominatim load).

- New `scripts/geocode_cache.py`: a per-trip on-disk cache (`cache_key`, `cache_get`,
  `cache_put`, `load_cache`, `save_cache`). `cache_get` returns `(hit, value)` so a cached
  miss (`None`, negative caching) short-circuits the network.
- `scripts/geocode.py::resolve_place` gains an optional `cache=None` param: a hit (including
  a cached miss) returns without touching Nominatim; otherwise the result (or `None`) is
  stored. `cache=None` preserves the original behaviour.
- `source-verify` and `accommodation-research` pass a per-trip cache
  (`work/<slug>/geocode-cache/geocode.json`) so re-runs skip already-resolved and known-miss
  lookups. No pipeline / schema / orchestrator change.

## 0.9.0 — 2026-06-05

Trip-cost rollup (big-ticket estimate + budget compare).

- New `cost-rollup` stage (`skills/cost-rollup/`): sums accommodation + inter-city
  transport + rail pass + a daily-incidental allowance into `cost.yaml`
  (`schemas/cost.schema.json`), computes a precise rail-pass break-even, and compares the
  total to `trip-brief.budget` (over → stop-on-confirmation). Wired as orchestrator
  stage 9 (B3). Everything is a no-key estimate with an `as_of` date.
- `scripts/cost.py`: pure aggregation — `sum_costs`, `incidental_total`,
  `pass_break_even`, `over_budget`.
- Numeric cost recorded upstream: `accommodations` candidates gain `cost`
  (amount/currency/basis); `legs` gain per-leg `fare` + a trip-level `pass` option;
  `trip-brief` gains `budget` / `daily_incidental` / `home_currency`.
- `itinerary-synthesis` renders a cost-summary block (breakdown, total, budget status,
  pass recommendation, FX note). No `itinerary-gate` change. Cross-currency uses a
  researched approximate rate (no FX API); per-meal/per-POI pricing stays out of scope.

## 0.8.0 — 2026-06-05

Mode-aware inter-stop legs (transit + self-drive parity).

- New `inter-stop-legs` stage (`skills/inter-stop-legs/`): one mode-aware leg per pair of
  consecutive overnight stops, researched from official sources into `legs.yaml`
  (`schemas/legs.schema.json`). Transit legs carry `service` / `reserved` / `transfers` /
  `last_service` / `pass_advice`; drive legs carry `duration_mins`. Wired as orchestrator
  stage 6 (B1).
- `scripts/legs.py`: pure feasibility — `drive_too_long`, `misses_last_service`,
  `classify_leg`. A single-day drive over `routing.max_single_drive_mins` (default 300) or
  a planned same-day departure past the last service → stop-on-confirmation, like a
  routing `far` hop. No `itinerary-gate` change.
- `trip-brief` schema: `overnight_stops[].leg_mode` (per-leg mode override of the
  trip-level `transport`) + `routing.max_single_drive_mins`.
- `itinerary-synthesis` renders the inter-city move per travel day and pushes reserved /
  pass / last-service notes into the checklist. Single-base trips have an empty `legs`
  list (no behaviour change). Precise rail-pass break-even is deferred to B3.

## 0.7.0 — 2026-06-05

Seasonal/weather advisory + no-key daylight.

- New `seasonal-advisory` stage (`skills/seasonal-advisory/`): no-key seasonal/weather
  hazard research (official sources: road authority / met service / parks) into
  `seasonal.yaml` (`schemas/seasonal.schema.json`). Two-tier severity — `blocking`
  stops on confirmation (closed pass), `advisory`/`info` flow to the synthesis checklist
  (chains, gear, short daylight). Wired as orchestrator stage 7 (B2).
- `scripts/season.py`: no-key solar-geometry daylight — `daylight_hours`,
  `approx_sunset`, `after_dark`. Per overnight stop's sunset is computed and, for
  `self_drive` trips, after-dark driving legs are flagged for an earlier start.
- `trip-brief` schema gains optional `transport` (e.g. `self_drive`).
- `itinerary-synthesis` consumes `seasonal.yaml` (advisories + daylight into the
  checklist). No `itinerary-gate` change — `blocking` stops at the stage, like
  `travel-advisory` `banned`.

## 0.6.0 — 2026-06-05

Accommodation layer + no-key geocode resilience.

- New `accommodation-research` stage (`skills/accommodation-research/`): per overnight
  stop, verify a user-provided hotel or recommend N=3 verified candidates (stop-to-pick).
  Produces `accommodations.yaml` (`schemas/accommodations.schema.json`). Wired as
  orchestrator stage 5 (D1).
- `trip-brief` schema: `overnight_stops` (ordered, per-stop optional `lodging`) +
  `facility_needs` (`required` hard / `periodic` soft). `base` retained, coexists (D1).
- D7 no-key geocode: `scripts/geocode.py::resolve_place` (structured Nominatim query
  then free-text), `cluster_centroid`; a real place Nominatim cannot pin degrades to
  `unverified` (`scripts/verify.py`) instead of `rejected`; accommodations fall back to
  the stop's cluster centroid (`geocode_source: cluster_fallback`) and stay verified.
  `verified-pois`/`routing` schemas gain `geocode_source` / cluster `centroid`.
- Facilities (`scripts/facilities.py`): `stop_meets_required`, `coverage_gaps`
  (periodic cadence, advisory), `reception_ok` (late-arrival lock-out, reuses
  `hours.py`). `itinerary-gate` adds `overnight_stops_have_lodging` +
  `required_facilities_met`; lodging rows reuse the v0.5.0 renderer + export-gate.

## 0.5.0 — 2026-06-04

Export integrity — the rendered deliverable is now contract-checked.

- `scripts/render/markdown.py`: `md_escape` backslash-escapes `\ $ _ * | < ` `` ` `` in all free
  text (prices like `\$120` no longer trigger KaTeX math mode and break previews,
  D4); each POI row appends a primary `官網` source link (D2); the POI name remains
  the maps link (D5).
- `verified-pois` schema: `sources[]` gains optional `official` (marks the
  official-site source for the deliverable link, D2).
- New `export-gate` stage (`scripts/export_gate.py` + `skills/export-gate/`): a
  mechanical post-export gate on `exports/<slug>-itinerary.md` checking
  `no_naked_dollar`, `links_well_formed`, `poi_name_is_link`,
  `bookable_has_official_source`. Reuses `gate-report.schema.json`. Wired as
  orchestrator stage 10; `fail` returns to `export-artifact` (D6).
- `export-artifact`: deliverable renamed `exports/<slug>-itinerary.md` (no longer
  clashes with the synthesis intermediate, D3); day tables must go through
  `render_day_table`.

## 0.4.0 — 2026-06-04

Closing-buffer awareness (intra-day scheduling safety).

- `scripts/hours.py`: `closing_status(start, close, last_call, need_mins)`
  classifies a scheduled arrival as `ok` / `tight` / `after_last_call` /
  `closed` against a POI's closing window.
- `verified-pois` schema gains per-POI `hours` (`close` / `last_order` /
  `last_entry` / `typical_visit_mins`), recorded by `source-verify`.
- `trip-brief` schema gains optional `scheduling`
  (`min_buffer_mins` default 30, `default_visit_mins` default 60).
- `itinerary-synthesis` never schedules a slot past last order/entry, flags
  thin buffers, and stops if a `must_do` cannot fit before close on any slot.
- day-granularity calendar closure (v0.3.0) now complemented by time-of-day
  buffer — a place open on the chosen day can still be reached too late.

## 0.3.0 — 2026-06-04

Calendar-awareness feature + geocode-query hardening.

- new `calendar-check` stage → `calendar.yaml`: destination public holidays
  (incl. substitute days) overlapping the trip range, each with crowds/closures
  impact and ≥1 official source (schema: `schemas/calendar.schema.json`).
- `verified-pois` schema gains per-POI `closed_days` (weekday / ISO date /
  `public_holiday` token), recorded by `source-verify` from the hours check.
- `scripts/calendar.py`: `weekday_of` / `holiday_on` / `is_high_crowd` /
  `poi_closed_on` decision logic.
- `itinerary-synthesis` hard-avoids scheduling a POI on a closed day (must_do
  closed on every feasible day → stop-and-ask) and flags holiday/weekend
  crowd days with earlier-start / off-peak advice.
- pipeline reordered: `routing-audit → calendar-check → itinerary-synthesis`.
- `source-verify` Gate 2 geocodes by `name_local` (English descriptor
  suffixes mis-resolve on live Nominatim, e.g. "Togetsukyo Bridge" → none).
- README rewritten in Traditional Chinese for non-engineer users (install
  flow, plain-language pipeline, holiday-awareness, dogfood examples).
- `CLAUDE.md` repo conventions (paperwork-style): mandatory README-freshness
  contract + writing convention + per-PR README check.
- `tests/test_readme_freshness.py` mechanical guard: every flow skill mentioned,
  `calendar-check` present in the workflow diagram, no obsolete names.
- `.github/workflows/ci.yml`: full hermetic pytest on every push/PR.
- `tests/test_version_consistency.py`: plugin.json / marketplace.json / CHANGELOG
  versions must agree (release-flow split-version guard).

## 0.2.0 — 2026-06-03

Hardening release: 5 known-issue fixes + workspace-shape-preflight entry-gate skill.

- advisory schema requires ≥1 official source (M1)
- candidates schema requires name_local + sources (M2)
- itinerary-gate checks meals + activities + visits POI references (M4)
- configurable region radius via trip-brief.routing.region_radius_km (M5)
- e2e must-do verification-failure closure test (M3)
- workspace-shape-preflight entry-gate skill (P1)

## 0.1.0 — 2026-06-03

Initial release.

- Orchestrator-driven staged pipeline (10 skills).
- Iron rule: Source-Verified-First (multi-source + geocode + region match).
- source-verify three-gate classification; routing-audit cross-region flags.
- itinerary-synthesis with contingency + pre-trip checklist sections.
- travel-advisory for entry/customs/battery regulations.
- itinerary-gate mechanical structure check.
- export adapters: markdown, Google Maps links, LINE short, Notion (graceful skip).
- Geocoding via OSM Nominatim.
