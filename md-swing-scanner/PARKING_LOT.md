# Parking Lot

Deferred research/implementation items with enough context to pick up
cold, whenever there's time. Different from FINDINGS.md (an append-only
research log of what's already been done) — this file is for what's
**intentionally not done yet**, kept current (edit/remove entries as they
get picked up or superseded, don't just append). Checked automatically by
`/swing-resume` at the start of a session.

Each entry: what it is, why it's parked (not urgent, not blocked, or
explicitly sequenced after something else), and the concrete next step —
not a vague "look into this sometime."

---

## 1. VCP Exit-Architecture Audit

**What**: VCP's entry detector (Trend Template + multi-contraction base)
is trusted, but VCP still runs entirely on the legacy exit engine
(`resistance_target()` pivot target, SMA21 trail) — never migrated to or
audited against the Primed Gate framework (ATR0 stop, ZigZag+R_FLOOR
target, K=2 swing-low trail, RQ-68/69-audited) that Breakout Continuation
now uses in production.

**Why parked**: standing user instruction — "VCP we don't touch unless
asked for." VCP is low-frequency (~496 trades/5yr vs. BC's 6,000+), so
this was explicitly deprioritized relative to BC/options work, not
forgotten.

**Next step, exact sequencing (do not skip ahead)**:
1. **Phase 0 (diagnostic only, no production change)** — run VCP entries
   through the existing RQ-68 (exit-efficiency)/RQ-69 (stop-geometry)
   audit framework as-is.
2. **Phase 1 (controlled replay)** — identical VCP entries under BOTH the
   legacy and Primed Gate exit mechanisms, to isolate how much of VCP's
   performance is entry vs. exit, before touching production.
3. **Phase 2 (migration decision)** — only after Phase 0/1 give a real
   answer; migration becomes an engineering decision, not a guess.

**Guardrails**: per Research Integrity Rule #9 (Entry/Exit Architecture
Confound), any BC-vs-VCP performance comparison under different exit
engines is descriptive only, never an entry-quality verdict, until this
audit is done. Don't rank BC vs. VCP entry quality off raw performance
numbers in the meantime.

**Full detail**: FINDINGS.md, "Known Architectural Gaps" section
(2026-09-21).

---

## 2. O'Neil Benchmark v1.0

**What**: build a faithful, standalone reconstruction of O'Neil's actual
system (entry: 40-day/~8wk pivot + SMA200 + volume ≥1.5x normal; exit:
flat 7.5% stop + one-time 15% raise, no continuous trail) as an
independent artifact — not another feature bolted onto BC — then compare
organism-vs-organism against current BC/Primed Gate.

**Why parked**: explicitly deferred to weekend-scale work (2026-09-21,
"O'Neil Benchmark Research Week 1" closed with this as the sole carried-
forward implementation task). Doing it piecemeal during the week risks
unconsciously tuning v31 toward an incomplete O'Neil implementation.

**Two validated inputs already in hand, ready to use**:
- **ON-01 (Extension)**: don't buy >5-10% past the pivot. Strongest
  finding of the week — confirmed 4 separate times in O'Neil's own text,
  monotonic across win rate/stop-out rate/holding period/concentration on
  the faithful replica (n=2,423).
- **ON-14 (Base Tightness)**: tighter base (lower High-Low range over the
  40-day base window, as % of median Close) = better outcome. Real,
  independent of Extension (additive, not multiplicative — see the 2x3
  interaction table in FINDINGS.md).

**Design discipline, critic-specified, don't skip**:
1. Write the **Spec** first (entry rules, exit rules, market filter,
   out-of-scope items, acceptance tests) as its own document — this never
   changes once written, prevents accidental tuning toward a predetermined
   answer.
2. **Then** run experiments (Benchmark O'Neil, Benchmark BC v31, same
   metrics, delta report — what explains the differences).
3. Fidelity Rule: if O'Neil doesn't specify something clearly, don't
   invent it — tag it "not implemented (qualitative)" rather than
   approximate. The benchmark should occasionally feel "dumber" than v31.
   Already-known qualitative/out-of-scope items: climax-top exit,
   distribution days (as a counted rule), C/A/I fundamentals.

**Full detail**: FINDINGS.md's O'Neil sections (search "ON-01" through
"ON-14", "RQ-ONeil-Naive", "O'Neil Benchmark Research — Week 1 formally
closed").

---

## 3. RQ-77 — Momentum Failure Recognition (Type-B), still open

**What**: this project's own "central unresolved research question"
(2026-09-19 reframe) — ~49% of all BC trades exit via `max_hold_cap`
("breakout never became momentum, watched it decay for two weeks"), and
there is still **no working detector** for this failure mode. Three prior
stall detectors (3-day-stall, Energy Stall, Efficiency-trigger) were built
and shelved pre-this-weekend. The SMA20 post-breakout signal (real,
non-circular deterioration marker, reproduces on real VCP too) was tested
as a candidate detector and **failed its own diagnostic** (2026-09-21):
damage-avoided only +0.41pp median, false-exit-risk 44.2% of the time,
opportunity-cost +5.89pp median/85.9%-to-loss on eventual winners.

**Why parked**: not blocked, just no promising candidate survived testing
yet. Standing mandate: no new rule design without a diagnostic pass first
(same 4 questions every candidate must answer — when does it fire, damage
avoided, false-exit risk, opportunity cost on winners).

**Next step**: no specific candidate queued. If a new Type-B candidate
signal emerges (from reading, from the O'Neil benchmark's delta report, or
elsewhere), run it through the RQ-77 diagnostic protocol before any rule
design — don't invent Stall v4 without a real reason to expect a
different outcome than the three that already failed.

---

## 4. RQ-BC-Taxonomy — descriptive characterization (cheap, not started)

**What**: purely descriptive (no PnL, no gate implications) — classify all
~6,200 real BC trades into three buckets based only on pre-entry price
behavior:
- **Fresh High**: no touch of the trigger level within the last 20 days.
- **Resistance Grind**: ≥1 touch near trigger in that window.
- **Gap Breakout**: opened above trigger.

Then report: what % of BC trades is each type, and (optionally) which
sectors/years generate each type more.

**Why this matters**: TA-02's finding today (2026-09-21) that only 22.3%
of BC trades ever touched the trigger in the prior 20 days suggests BC is
mostly "continuation through fresh highs," not "compression under
resistance" — a different mental model than the VCP-style pressure-
building intuition this project kept testing against (and which kept
coming back null). This taxonomy would confirm/quantify that directly.

**Why parked**: cheap (a few hours), but genuinely lower priority than the
Benchmark v1.0 build — deferred, not blocked.

**Next step**: straightforward to build directly from the existing
canonical BC population + daily bars; no new research design needed.

---

## 5. A genuinely new exit construction (not another R-multiple retune)

**What**: this project has tuned the SAME exit family repeatedly this
year (structural stop width, `TRAIL_ENGAGE_PCT`, Fixed-R variants, SMA21
trail, K=2 swing-low trail) — all variations on "stop + trail + target,"
never a structurally different exit mechanism. Noted as an open item
after the RQ-68/69 exit-efficiency/stop-geometry audits closed
(2026-09-20): "if returned to, a genuinely new exit construction rather
than another R-multiple retune."

**Why parked**: no concrete design proposed yet — this is a placeholder
for "if a genuinely different idea shows up," not a queued task with a
defined next step.

**Next step**: none defined. Revisit only if a real, structurally
different exit idea surfaces (e.g., from the O'Neil benchmark's own exit
philosophy comparison, or elsewhere) — not a scheduled task.

---

## 6. RQ-91C / RQ-91D — status genuinely uncertain, verify before resuming

**What**: from the pre-O'Neil RQ-90→95 options-derivatives arc
(2026-09-19/20). RQ-91C = IV percentile/expansion/crush as a signal.
RQ-91D = combine breach quality + derivatives confirmation. Last recorded
status (2026-09-19): "not yet started." The critic's later "closed the
whole arc" statement (2026-09-20) named RQ-90/91A/91B/93/95/95A/96
explicitly but did NOT explicitly mention RQ-91C/91D — so it's genuinely
unclear whether they were implicitly closed along with the rest, silently
dropped, or are still real open items.

**Correction, worth remembering**: the critic repeatedly called "RQ-91B"
a "P0, highest expected value" priority during today's (2026-09-21) O'Neil
conversation. **RQ-91B is actually already CLOSED** (2026-09-20) — this
was a stale/incorrect reference on the critic's part, not a real open
item. Don't resume RQ-91B based on that framing.

**Why parked**: status ambiguity itself, not a deliberate deprioritization
— needs a 10-minute FINDINGS.md re-read (search "RQ-91C", "RQ-91D",
"IV percentile") before deciding whether to resume, close, or drop these.

**Next step**: verify actual status first, don't assume either way.

---

## 7. Options-strategy rethink — day+1-open metric may not be the right proxy anymore

**What**: 2026-09-24 filter-validation work (the corrected RQ-P1 arc) found
that the R2-proximity filter — real, R-negative on swing (n=183, cumR=
-5.51, worst drawdown of any bucket) — is completely flat on
`day1_open_ret` (71.2%->71.0% win, +0.385%->+0.384% median). A filter with
a real, verified swing effect produces no visible signal on the current
options proxy, raising the question of whether `day1_open_ret` is
discriminating anything real for filter-validation purposes, or is too
noisy/wrong a proxy to trust going forward.

**User's proposed alternative framing (captured, not built)**: stop trying
to reconstruct/measure the option's own day+1-open price directly — this
already has a known, permanent problem (entry is always priced off day-0
Close, never the real intraday breach price; OX1 reconstruction explicitly
does not model executable fills). Instead, use the underlying STOCK's own
spot price move from entry to a fixed later checkpoint the next day
(candidates mentioned: 9:30, 11:30) as a rougher, explicitly-imperfect
signal — e.g. spot up ~1% by that checkpoint => expect an option win,
otherwise not. User's own framing: "with a pinch of salt that it's not
real" — a directional proxy, not a precision metric.

**Why parked**: not a today task, explicitly "note this down, come back to
it later." Needs real design thought (which checkpoint, what threshold,
how it interacts with OX1's already-validated "reconstruction preserves
relative ranking, not absolute price" capability) before building
anything.

**Next step**: none defined yet. When revisited: (1) decide whether this
replaces or supplements `day1_open_ret`/OX1 for filter-validation
purposes specifically (not necessarily the whole options research line);
(2) if built, validate it the same way OX1 was — against real option
price data (Dhan exports), not just assumed; (3) reconcile with OX1's
existing relative-ranking-only finding, since this proposal is
conceptually similar (a spot-price-based proxy for option outcome) but
even coarser (binary threshold vs. continuous reconstruction).

**Related, not yet resolved**: RQ-P1B (options economic relevance for the
pivot-friction filter specifically) was already flagged as "genuinely
unresolved" — this item is a broader version of the same underlying
doubt (is `day1_open_ret` trustworthy at all), not limited to one filter.

**Full detail**: FINDINGS.md, "RQ-P1 CORRECTED" section (2026-09-24) — the
specific trigger for this doubt.

---

## 8. Intraday-derived, tighter decision-time-safe stop (swing_qs) — revisit only when intraday tests are in scope

**What**: S1 (breakout day's own low, Kullamägi's literal stop) makes 2R/3R much more
reachable within a realistic window (median day to 3R = 5, vs 7-8 under S1b) but isn't
decision-time-safe from daily bars alone — the day is still in progress at the moment of
entry. S1b (prior day's low, the current standing QS stop) fixes the decision-time
problem but is ~1.6x wider, making the literature's round-number thresholds (2-3R, 3-5
days) meaningfully harder to hit than in Kullamägi's own numbers.

**Idea, explicitly deferred**: once intraday data is in scope for this line, revisit
whether a stop based on the actual intraday low observed strictly BEFORE or AT the
moment of breach (not the full day's eventual low, which isn't known until close) could
be both decision-time-safe (uses only information available up to and including the
breach moment) AND tighter than S1b — without falling back on the not-yet-happened
rest-of-day low that made plain S1 impractical.

**Why parked**: user explicit — "I am not sure if we should jump to that." This needs
intraday tests to even be meaningful, which is a larger scope decision (data
availability, likely a heavier parallelized build per this project's own conventions),
not something to reach for opportunistically mid-thread.

**Next step**: none scheduled. Revisit only when/if intraday-data work for swing_qs is
explicitly taken up.

**Full detail**: `swing_qs/FINDINGS.md`, "S1 vs S1b — how much of the 2R/3R reachability
gap is stop-width, not weak price action" section (2026-09-27).

---

## 9. RQ-QS-04B onward — Post-Breakout Consolidation Anatomy — 04B RUN, answer is NO, awaiting critic's close/continue call

**Status update 2026-09-29 (afternoon)**: step 1 (04B) is done — `swing_qs_bpc/08_rq04b_anatomy.py`,
full writeup in `swing_qs_bpc/FINDINGS.md` "RQ-QS-04B". The data says the 8,403 subset is
NOT a recognizable tight continuation structure: 61% pause for at most 2 bars, median
close-to-close range 0.48%, no volume dry-up, longer pauses are wider not tighter, and B
closes above the consolidation high only 45.6% of the time. Step 2 vocabulary from the
data: "impulse rest", not consolidation/base/VCP. Per the pre-declared decision tree the
branch should close; steps 3-6 below are NOT to be started unless the critic explicitly
overrides with a pre-declared cell. Hand-checks (IRB/IREDA/IDEA/HINDUNILVR) all matched.
04C (20-vs-20 replay, run at user's direction 2026-09-29) agrees: B is a late entry (median 2 ATR above A), 12/20 stopped by D5, 6/20 D5-positive, dominant archetype poke-and-fade; pre-B pause low equals the S1b stop in 14/20 pairs (no multi-bar structure to anchor a distinct stop). A-side of that replay is future-conditioned, not comparable. Recommend closing; steps 4-6 not started.
One methodological note carried forward: 04A's consolidation_low includes B's own bar,
which must be redefined (pause bars before B only) before any structural-stop work.

Original entry, kept for the record:


**What**: `swing_qs_bpc/` found a real, distinct 8,403-event subset (A's whose
post-breakout pause holds its low ABOVE A's own entry price — 18.0% of 46,776 A's,
median 2-day duration, ~1.36x ATR range, 90.7% resolve rate). Full detail:
`swing_qs_bpc/FINDINGS.md`, "RQ-QS-04A" section (2026-09-29). **Not yet established**
whether this 8,403 population is actually a recognizable tight-continuation structure
(the thing the user remembers from Strike's algo curriculum/VCP) or just a 1-2 day
pause followed by another new high — that is exactly tomorrow's first question.

**Why parked**: session closed for the night, critic explicitly sequenced the next
steps — not urgency-deprioritized, just the natural stopping point after finding the
population and before characterizing it.

**Next step, critic's exact sequencing (do not skip ahead, do not reorder)**:

1. **04B — anatomy of the 8,403 population only** (no returns, no expectancy, no
   filtering for winners). Compute: consolidation duration P25/50/75/90; range
   width % same percentiles; range width/ATR same percentiles; whether B actually
   breaks the established consolidation high; consolidation low relative to A entry
   % and to ATR; volume vs A's breakout day and vs prior 10D avg; a duration ×
   range-width descriptive matrix; how often the consolidation stays entirely above
   A vs. merely ends above A. Question to answer: is this a recognizable tight
   continuation structure, or merely noise?
2. **Decide the structural vocabulary from the data** — generic consolidation,
   continuation pause, tightening, VCP-like contraction, or something else. The
   literature (Minervini/O'Neil/Strike, already verified this session) is a PRIOR,
   not a label to force onto whatever 04B shows.
3. **04C — 20-vs-20 trajectory replay** — ONLY if 04B confirms the structure is
   genuinely distinct. Same discipline as the D3 replay: deterministic stratified
   sampling, A↔B linkage preserved, no cherry-picking, no returns/expectancy yet.
   Look specifically at: does B represent genuinely renewed expansion, a merely
   marginal new high, or an already-late/exhausted move; does the structural low
   give a coherent invalidation; does B actually look cleaner than A.
4. **Structural-stop comparison** — only after the replay. Compare conceptually
   (not by optimizing performance yet): S1b, retest-low, full-consolidation-low,
   final-contraction-low. Question: which price structure actually represents the
   thesis being traded?
5. **QS product-fit check** — if the structure survives the replay: time from A→B,
   structural risk %, consolidation duration, B's distance from A, whether this
   stays plausibly quick-swing rather than positional (this is where the user's
   original "is this just another positional trade" concern gets answered directly).
6. **Only then, performance test** — freeze the structure definition, the B entry,
   and the structural SL first; establish a clean risk unit; only then test
   returns/1R/2R/time-to-resolution. No parameter optimization before all of the
   above are frozen.

**Explicitly NOT next** (per critic, do not reach for any of these opportunistically):
D1/D2/D4 BPC variants, reopening BPC, VCP threshold hunting, volume-threshold
hunting, EMA filters, stop optimization, options modelling, expectancy fishing,
selecting the 90.7%-resolved subset in isolation, or another giant replay before the
structure itself is defined.

**Decision tree**: 04B anatomy → is this genuinely a distinct structure? No → close
the branch. Yes → 04C 20×20 replay → does it produce visibly better/cleaner
continuation behavior? No → close the branch. Yes → freeze structure + structural
stop → performance test.

**Full detail**: `swing_qs_bpc/FINDINGS.md`, "RQ-QS-04A" section.

---

## Explicitly NOT in this parking lot (deliberately deprioritized, different from "parked")

- **Paper Trading Calibration Log + Rule Break Log** — explicitly
  deprioritized (not "pick up when there's time"), per standing project
  memory.
- **Base Count / historical multi-year base counting** — CLOSED (no
  objective/reproducible definition possible), not parked. Don't reopen
  without genuinely new evidence.
- **Supply exhaustion, breakout-candle-geometry family, prior-advance
  proxy, base-duration sensitivity, breakout-day volume magnitude** — all
  CLOSED-negative (2026-09-21), not parked. Don't reopen without new
  evidence.

## 10. fetch_prices.py — silent partial-batch failure, needs chunking + honest "current" bucket

**What happened (2026-09-29)**: a full-universe refresh left 198 of ~700 tickers stuck
2-13 days behind (last cached 09-16/09-17 while 501 others reached 09-28), discovered
only because JUSTDIAL/GOCLCORP were being hand-checked for the swing_qs_bpc chart work
and their dates didn't match the rest. `fetch_all()`'s own summary print gave no signal
of this — the 198 were silently folded into the `current` bucket, indistinguishable
from tickers that genuinely had no new trading day.

**Root cause**: `fetch_all()` makes ONE `yf.download(..., threads=True)` call across the
whole `existing_tickers` batch (up to ~700 names). When Yahoo throttles/drops a subset
of tickers within that single batched, multi-threaded request, that sub-ticker's slice
of the response comes back empty — `new_df.empty` is True — which the code currently
treats as "nothing new since last fetch" (`result["current"]`), not as "the fetch for
this ticker failed." There is no per-ticker success signal distinguishing a real
no-new-trading-day case from a silently-dropped request. Confirmed the fix: re-running
`fetch_all()` on just the 198 stragglers, in sequential chunks of 25 with a 2s pause
between chunks, cleared 100% of them in one pass (0 empty, 0 still-current) — this is
exactly the same class of failure this project already hit once before with
`intraday_cache.py` (concurrent yfinance fetches rate-limited 224/500 tickers, fixed by
running sequentially) — README already documents that incident but `fetch_prices.py`'s
own main batch call was never hardened the same way.

**Why parked**: user explicit, "we need to fix our refresh mechanism later" — fix now
was the narrow unblock (retry the 198 stragglers), not the mechanism itself.

**Next step**: harden `fetch_all()`'s existing-tickers branch to chunk instead of one
big batched call (the 25-per-chunk/2s-pause shape that worked today is a reasonable
starting point, not necessarily final), AND make `current` stop being a catch-all —
distinguish "last_cached_date already == safe_today or one trading day prior" (genuinely
current) from "still behind safe_today by more than a normal trading gap after a fetch
attempt" (silently failed, should be retried automatically before the script exits, not
just reported). Should reuse this same session's retry script as a starting point
(ran directly against `fetch_all`, not a rewrite) rather than redesigning from scratch.
