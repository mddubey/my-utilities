# Findings log

Analysis conclusions and narrative decisions that never changed a single code
parameter, so they had nowhere to live under the "comment next to the code" policy
(see `README.md`'s Current status section). Anything that DID change a parameter is
documented as a comment at that parameter instead — this file doesn't duplicate that.

## Swing side

**Chase a big-momentum entry, or wait for a pullback? (2026-09-01)** — checked
against 924 real trades (v27), bucketed by the entry day's own price move size, and
separately by RSI-at-entry for VCP (which has no RSI ceiling to artificially cap it):

| entry-day move | win | median | conc | RSI at entry (VCP) | win | median | conc |
|---|---|---|---|---|---|---|---|
| ≤1% | 58.7% | +1.89% | 105.4% | ≤55 | 58.3% | +1.55% | 219.8% |
| 1-2% | 59.8% | +2.93% | 331.7% | 55-60 | 57.9% | +2.83% | 156.1% |
| 2-3% | 62.2% | +2.18% | 128.2% | 60-65 | 60.0% | +2.41% | 61.5% |
| 3-4% | 66.7% | +3.03% | 50.6% | 65-68 | 63.1% | +2.63% | 154.2% |
| >4% | 64.1% | +3.94% | 25.5% | 68-72 | 58.5% | +2.26% | 81.9% |
| | | | | 72-100 | 66.8% | +3.72% | 43.0% |

Result is the opposite of "never chase a green candle" — bigger/more extended moves
perform BETTER, not worse, and it's not a thin/outlier effect (concentration is lowest,
i.e. best, in the most-extended bucket both ways). **Conclusion: don't wait for a
pullback on this scanner's signals.** Independently validated by outside review with
a real AUROPHARMA chart: "you asked wait for pullback? It never came."

Outside review's caveat, worth respecting: this may not hold the same way for a
GAP-UP that opens extended and goes flat all day (possible exhaustion gap) vs a
candle that builds the move gradually through the session (institutional
accumulation signature, matches this scanner's existing EMA/RS/volume/breakout
filters). Not yet tested separately — real, open follow-up.

**Why big-momentum days USED TO skew toward Coiled Spring, not Breakout Continuation
(2026-09-01, now resolved)** — real case: a watchlist was 5 Coiled Spring vs 1 Breakout
Continuation. Traced each ticker's exact blocking condition (not one bug, one
structural asymmetry): Breakout Continuation had an RSI ceiling (55-68) that Coiled
Spring/VCP simply doesn't have. On a day with a genuinely large move, RSI routinely
clears 68, structurally routing big movers toward VCP even when everything else about
the Breakout Cont setup (fresh high, volume, trend) was fine.

**Correction on the above, from outside review — the first fix attempt was an
overgeneralization.** The chase-vs-pullback table above showed VCP entries with
RSI>72 as the single best bucket, which tempted the conclusion "so Breakout
Continuation's RSI≤68 ceiling is probably cutting off its own best zone too." That's
selection bias — VCP and Breakout Cont at the same RSI number mean different things.
A VCP stock at RSI 75 typically spent WEEKS tightening in a quiet base and is elevated
only because today is breakout day (RSI is a symptom of the breakout, not
pre-existing extension). A Breakout Continuation stock at RSI 75 may have already run
5-6 consecutive days before today — a genuinely different, more extended situation,
even at the same RSI number.

**Done properly (2026-09-01): swept Breakout Continuation's OWN RSI ceiling in
isolation** (55-68/72/75/80/85/100-no-real-cap) on v28 data, not inferred from VCP's
data at all. This time it held up: win rate ~67-69% throughout, median flat-to-better,
concentration drops monotonically 52.2%→16.4% and flattens right at 80 — same
real-then-plateau shape as the other v27/v28 parameter sweeps. **Adopted `signals.RSI_MAX=80`.**
Also checked, before trusting it, whether this was just relabeling VCP's own good
trades as Breakout Cont instead of adding real new ones: only ~90 of VCP's 713→663
drop are same-day overlaps; the two exact-match subgroups checked out clean (see
`signals.py`'s own comment for the full numbers, including one real case — PAYTM
2024-11-08 — where the same entry flipped outcome between patterns for a fully
legitimate reason: VCP's stop is Minervini's published structural-base-low stop,
Breakout Cont's is the published Chandelier Exit's 3×ATR trail; two different, real,
sourced stop philosophies, not an inconsistency).

**"Dec'24-May'25" VCP losing patch is understated — it's really Oct'24 onward, patchy
through Feb'26, not a closed 6-month window (2026-09-01)**. Year-by-year v27 slice
found 2025 is a net LOSER on a mean basis (-0.6% mean, though median stays +1.1%) and
it's entirely a Coiled Spring/VCP problem — Breakout Continuation had a fine 2025
(72.7% win, +3.3% median, all year). Month-by-month VCP breakdown shows the weak
patch actually starts **Oct 2024** (32.1% win, -6.7% median), not Dec, and never
fully resolves through Feb 2026 — just gets punctuated by occasional strong months
(May'25 73.3%/+4.2%, Jan'26 71.4%/+4.6%) between weak stretches (Jul-Oct'25, Feb'26).
Two obvious hypotheses (Nifty direction, weak relative strength during the patch)
both refuted directly. Outside review calls this "the biggest unresolved mystery... I
wouldn't change the strategy until I know why" and suggests testing, in priority
order: sector concentration (pharma/IT/metals), volatility regime (was ATR unusually
high), market breadth (weak breadth despite index-level trend), earnings-season
clustering, and election/macro period effects.

**New evidence (2026-09-01): the regime gate was OPEN through most of the worst leg
of the decline.** Checked Nifty ADX/SMA200 directly against `data_cache/_NIFTY.csv`
for Oct-Dec 2024, the exact window where VCP's win rate first collapsed:

| month | Nifty close (start→end) | ADX range | gate-on % of days |
|---|---|---|---|
| 2024-10 | 25797→24205 | 24-32 | 100% |
| 2024-11 | 24304→24131 | 30-42 | 79% |
| 2024-12 | 24276→23645 | 20-33 | 62% |
| 2025-01 | 23743→23508 | 31-37 | 9% |
| 2025-02 | 23482→22125 | 22-30 | 0% |

This is the same mechanism already flagged in `market_regime.py`'s own comment on
`_compute_adx()` (ADX measures trend STRENGTH, not direction — a real correction can
read as "trending" and get waved through) plus SMA200's inherent lag (a 200-day
average takes ~2-3 months of a correction before it catches up and actually closes
the gate). Caveat already on record: a `+DI/-DI` directional filter was tried
specifically to catch this and was REJECTED — per-trade, down-days weren't actually
worse than up-days for VCP in this window (31.25% vs 37.5% win, no real difference).
So "gate stayed open during a down-move" is a confirmed temporal correlation, not
proof that a naive direction filter fixes it at the trade level.

**SMA50 gate lead — tested and REJECTED (2026-09-01).** `market_regime.py` already
computed and cached `sma50` for Nifty but `market_trending()` never used it. A
Nifty-level check first looked promising: a `Close > SMA50` filter would have closed
the gate in October 2024 itself (100%→14% open that month) instead of December/
January under the current SMA200-based gate, meaningfully faster than the gate's
actual 62-100%-open readings through that window. Added `require_above_sma50` /
`require_sma50_rising` to `market_trending()` and full-backtest-tested both (plus
combined) — **backwards result**: isolated exactly which VCP trades each filter
removes from the Oct'24-Feb'26 weak window, and they're the BETTER half. The 98
trades `TEST_SMA50_ABOVE` removes (Nifty below/falling its 50-SMA) ran 55.1% win /
+1.83% median; the 100 it keeps (Nifty above/rising) ran 38.1% win / -3.99% median.
Cut VCP's sample 25-37% while making the targeted window's own concentration worse
(22.0%→27-29%), not better. **Nifty's own medium-term trend strength is not what's
driving this weak window** — third market-level gate idea rejected, after
`TEST_ADX_RISING` and `TEST_ADX_UPTREND`. All three "tighten the shared regime gate"
ideas have now failed; the remaining investigation moves to the critique's original
list (sector concentration, volatility regime, market breadth) since this doesn't
look like a gate problem at all. See `backtest.py`'s `TEST_SMA50_ABOVE`/
`TEST_SMA50_RISING` comments and `market_regime.py`'s `market_trending()` docstring
for the full numbers.

**OR-based SMA50 "recovery" gate — tested, INCONCLUSIVE, not adopted (2026-09-01).**
Structurally different from the rejected idea above: an OR on `require_above_sma200`
(`allow_sma50_recovery`), not an AND — lets a trade through if SMA200 fails but
Nifty's SMA50 has risen over the last N trading days, so it can only ADD trades the
gate currently blocks, never remove any (unlike the AND version, which could only
remove). Swept N=10/15/20 — pooled effect is tiny either way (n 1430→1433-1457, win
65.0%→64.7-65.0%, concentration flat ~10.3%), since the recovery window rarely comes
up across 5 years. Isolated the actual added trades (n=17 at N=15): dominated by one
real cluster in mid-June 2026 (15 of 17, 60% win, +2.42% median — close to baseline
quality but two large losers, IFCI -16.4% and ANGELONE -11.3%, pull the mean
negative) plus 2 older isolated losers (2022, 2025). Too thin (one cluster) to trust
either way — not backwards like the AND version, just unproven. **Directly live and
consequential right now**: as of 2026-08-31 (latest cached data), the recovery
condition is ACTUALLY TRUE — Nifty's still below its SMA200 but its SMA50 has been
rising for 15 trading days — so adopting this today would immediately reopen the
regime-gate drought that's been running since 2026-02-26. Given the thin evidence,
**not adopted** (`TEST_SMA50_RECOVERY=False` stays the default) — kept as a
documented, disabled option (`market_regime.py`'s `allow_sma50_recovery` param,
`backtest.py`'s `TEST_SMA50_RECOVERY`/`TEST_SMA50_RECOVERY_LOOKBACK`). Worth
revisiting as a live natural experiment: if Nifty's SMA50 keeps rising and price
genuinely recovers over the coming weeks, that's more real evidence accumulating for
free, without having gated real trades on an unproven signal today.

**Does a stock qualifying for BOTH patterns on the same day mean higher confidence?
Checked, and no — not yet, on this sample (2026-09-01).** `detect_entry()` itself
short-circuits (Breakout Cont checked first, first match wins, VCP's own check never
runs if BC already fired), so `daily_scan.py` now re-checks the OTHER pattern's raw
condition independently, purely for display (`[BOTH]` tag). Validated against all
1430 v28 trades before shipping it: only 40 (2.8%) are dual-qualified, and it only
ever happens on the Breakout Cont side (no VCP trade ever also independently clears
BC's stricter same-day checklist). Win rate is IDENTICAL either way — 65.0% dual vs
65.0% single-pattern. Median looks higher for the dual set (+4.07% vs +2.86%) but
rides on a lumpy distribution (concentration 131% on n=40 — top 10 winners alone sum
to +139%, e.g. HAL +21.2%, KFINTECH +19.8%, RECLTD +18.9%, while the other 30 trades
net to -32.9%), not proof of a real edge. Not the same thing as "likely to fail"
though — the losers in that group aren't unusually frequent (14/40, same ballpark as
everywhere else), they're just sized enough (several -7% to -14%) to offset the
smaller wins outside the top 10. Shipped as a purely informational tag, explicitly
NOT a ranking signal, until there's a much bigger sample (rare event, ~3% of trades)
to actually trust the median difference either way.

## Options side

**Conclusion evolution (all real, all previously reported, kept here as the timeline
since the number changed meaning several times)**: original small sample (n=30-36)
said ATM+next-month; `portfolio.py`'s capital-pooling bug fix flipped this to
ITM+next-month (the earlier "ITM is unaffordable" read was itself the bug); extending
`options_cache/` back to 2022-06 confirmed it on a bigger sample (n=89-93); re-running
on v27's bigger swing-entry set strengthened it further (n=131-137, concentration
first time under the 100% comfort line at 77.1%, and ITM-next turned out to be the
MOST capital-efficient variant too — 87% participation even at ₹1L, directly
contradicting the original "unaffordable" read). **Current standing conclusion: ITM +
next-month expiry.** Outside review's real, unaudited caveat: no transaction costs,
STT, slippage, or bid-ask spread are modeled anywhere in this layer — the ±800%
portfolio-level number should be read as an upper bound pending that audit, not a
real-money expectation.

**Scheduler-fragility methodology finding (2026-09-01), general and reusable**: tested
whether an adaptive expiry-selection rule (roll to next month only if the current
contract has <20 trading days left, vs the blunt "always skip exactly one listed
month") beats the existing rule. Raw %-metrics slightly favored the adaptive version.
Portfolio-level results favored the blunt rule instead. Traced the discrepancy to
source: only 12 of 131 trades actually differ in expiry choice between the two rules,
and on those 12 the adaptive rule was BETTER. The portfolio-level gap came entirely
from 29 unrelated trades getting bumped in or out of `portfolio.py`'s fixed 3-slot
scheduler due to a timing cascade (a handful of trades settling a few weeks earlier or
later shifts what capital/slots are available for every later trade in sequence) —
worth a net ₹274,000 swing that has nothing to do with contract-selection quality.
Same underlying fragility as an earlier single-trade case (KOTAKBANK, non-monotonic
capital-level returns) — now confirmed as a repeatable pattern, not a one-off.
**Standing rule: portfolio-level P&L rankings between similar-quality variants are NOT
reliable on their own — trace which specific trades actually drive a gap (or compare
per-trade paired differences directly, per outside review's independent
formalization: `Portfolio(A) > Portfolio(B)` does not imply `Trade_i(A) > Trade_i(B)`)
before trusting the ranking.**

**Survival analysis / capital-efficiency metric — re-run on v28's bigger FO-scoped
set (2026-09-01, was only computed on the pre-v27 sample).** 838 v28 trades are on
FO-eligible tickers; ITM+next (the standing pick) simulates to n=562 (up from
131-137) and **gets healthier on the bigger sample**: win 61.6% (was 62.6%), median
+18.63% (was +15.35%), concentration **32.6%** (was 77.1%). Both original findings
hold:
- Survival: stop-outs take **1.6-1.75x** longer to resolve than resistance wins on
  this bigger sample (median stock hold 21 days vs 12; mean 23.4 vs 15.0) — a bit
  less dramatic than the "~2x" first quoted, same direction and still real. Option
  holding time tracks the stock's almost exactly (median 21 vs 14, mean 22.9 vs 16.7).
- Leverage stays roughly symmetric between winners and losers on ITM+next
  (median 9.7x winners vs 8.6x losers) — no options-specific theta-bleed
  disproportionately punishing the longer-held losers, confirming it's a
  stock-duration effect as originally concluded. **Use MEDIAN here, not mean** — same
  caveat as signals.py's own filter-ablation comment: a few trades where the stock's
  own pnl landed near zero (division near-zero) produce leverage ratios in the
  hundreds either direction (e.g. one real case: stock +0.04%, option -59% ->
  reported "leverage" of -1452x, meaningless) and corrupt the mean badly (it reads
  4.0x for losers vs the real 8.6x median).
- Checked leverage across all 4 contract variants too (median, same fix applied):
  still flat, 9.3-11.5x — ITM+next specifically shows the TIGHTEST winner/loser
  symmetry (9.7x/8.6x) of any variant, the strongest version of this finding for the
  config actually in use.
- New, minor finding from this re-run: 54 of 562 trades (9.6%) have the option's P&L
  land in the OPPOSITE direction from the stock's own recorded outcome (e.g. stock
  exits at a resistance win, but the option — often carried to expiry, illiquid along
  the way — ends up negative because the stock gave back the move before the option's
  own exit actually settled). Not a bug, a real known mechanism (`simulate_option_trade`'s
  own comments already document walking forward to the next liquid day or settling at
  expiry) — just not previously quantified. Worth knowing before assuming "the stock
  won, so the option trade must have won too."

## Outside critique review history

Five rounds of an external ChatGPT-based review, each fed this project's own session
summaries (originating from `Options stoploss management.pdf`).

- **Round 1** (8.5/10): praised the swing/options separation, VCP fidelity, and
  regime filter design.
- **Round 2 & 3**: proposed breadth-based regime gate, gate-isolation test, and
  neutral-zone/SMA50-stack alternatives — all tested, all rejected as drought fixes
  (candidate-scarcity, not a gate problem). One correction sent back: the critic
  hypothesized the options gap was a holding-period mismatch between patterns; checked
  directly and found VCP's median hold is actually SHORTER than Breakout
  Continuation's, opposite of the theory — their top-level conclusion (Breakout
  Continuation is the real options pattern) was right, their reasoning wasn't.
- **Round 4**: independently recommended freezing the swing engine and narrowing
  options to ATM+next-month — both matched this project's own conclusion at the time,
  arrived at independently, and both were later superseded by this session's own
  further work (swing side un-frozen at v27; options side flipped to ITM+next-month).
  Proposed survival analysis and a capital-efficiency metric (both done, see above);
  flagged the capital-efficiency formula as backwards before it was even built (a
  leverage formula that was actually premium/spot, corrected before use).
- **Round 5** (2026-09-01): approved v27 as "a huge leap... the signature of real
  improvement rather than curve fitting," singled out the concentration drop
  (30.7%→16.1%) as the most important single metric. Two corrections owed back (both
  captured above): the RSI-ceiling overgeneralization, and genuine skepticism of the
  ITM-next +812% portfolio number pending a transaction-cost audit. Independently
  reformalized the scheduler-fragility finding. New, unaddressed ask: proper
  walk-forward validation (freeze parameters through 2023, test untouched on each
  subsequent year, never retune) — everything validated so far is one long in-sample
  backtest, not proven to generalize forward. Recommended shifting effort from further
  backtest refinement to paper trading the swing signal (confidence 9/10) while
  auditing the options layer's execution assumptions (confidence 6.5/10 contract
  selection, 5/10 portfolio P&L, 4/10 real-money-ready for options specifically).

## Other ideas worth considering (source: feedback/2026-09-01_05-57-04_IST_veteran_trader_review.md)

Notes from that file, sorted into what's already covered vs genuinely new — logged
here so they can feed into whatever gets tested or submitted next, attributed to
where they came from rather than presented as this project's own original thinking.

**Already addressed, or independently confirms our own prior work:**
- Breakout Continuation RSI ceiling swept in isolation (68/72/75/80) — their exact
  suggested values, word for word. We'd already done this the same day (item 2, this
  session) and adopted RSI_MAX=80. Strong independent confirmation of both the
  question and roughly where the answer landed.
- Gap-up exhaustion vs intraday accumulation, as a diagnostic not a hard gate — we'd
  already run this split (item 3, this session): 81% of trades are grind-dominated
  and healthy (12.5% concentration), the gap-dominated cohort is real but too thin to
  trust (n=75, 78.5% concentration). Matches their own caution ("do not make it a
  hard gate until tested").
- Portfolio-level fragility from the fixed 3-slot scheduler — this is our own
  scheduler-fragility finding above, already independently confirmed by round 5.
  Third independent source landing on the same mechanism now.
- "Treat MOMENTUM_20D_MIN/EMA34_RISING_DAYS_MIN/MIN_TRADED_VALUE as candidate-list
  controls unless they prove edge" — matches our own leave-one-out ablation
  (`signals.py`'s own comment, 2026-08-30) almost exactly: those filters showed weak
  or no backtest edge but are kept anyway to keep the daily candidate list
  manageable, not for a hidden performance reason.
- Dec'24-May'25 VCP patch "by sector, breadth, volatility, and events" — this is item
  5, in progress. Window already corrected (Oct'24-Feb'26, not just Dec-May); four
  regime-gate ideas tried and rejected/inconclusive; sector/volatility/breadth
  hypotheses queued next, not yet run.
- Walk-forward validation — partially done (year-by-year consistency check, item 1)
  but NOT the full train/test-untouched-by-year version they're asking for. That's
  still explicitly deprioritized per standing user instruction (portfolio ₹ figures
  are illustrative only) — logging their ask here for the record, not reopening it
  without being told to.
- Options transaction costs (STT, stamp duty) — also still deprioritized per the same
  standing instruction. Their review adds real sourced numbers worth keeping for
  whenever that changes: NSE (Apr 2026) lists STT on option sale at 0.15% and on
  exercised options at 0.15% of intrinsic value, plus 0.003% stamp duty on the buyer
  side.
- Two real, currently-true stale-label bugs they caught by direct code reading, not
  yet fixed: `option_backtest.py`'s `__main__` still points at
  `runs/trades_v23_recent.csv` (should be `trades_v28.csv`), and `daily_scan.py`'s
  `--ignore-regime` banner and module docstring still say "v25" (should say
  whatever's current). Both confirmed still present (2026-09-01).
- `tradingview_stop_target.pine` being stale against v27 (weekly pivots, old
  version) — already known, sitting uncommitted/unresolved from earlier in the
  broader session, now independently flagged too.

**New, not yet addressed at all:**
- **Same-close entry bias (their "hard block #1", ranked top priority)**: the
  backtest enters at the signal day's own close, but daily workflow discovers signals
  after that close has already happened. Is a same-close fill actually attainable, or
  should the model be tested against next-day open / a live 14:45 cutoff price / a
  gap-size skip rule instead? We've discussed live-cutoff timing this session but
  never actually backtested an alternative entry-timing assumption against the
  current one. Real, unaddressed methodological gap, and their top-ranked item.
- **Survivorship bias**: the backtest runs the CURRENT NIFTY 500 list across the full
  2021-2026 window — delisted/merged/removed names from earlier years are entirely
  absent. Never discussed or checked this session. Doesn't invalidate the project,
  but the historical stats are probably cleaner than the real opportunity set was at
  the time.
- **Options liquidity criteria too weak**: `liquid()` in `option_backtest.py`
  currently just checks OI>0 and volume>0. Suggested real minimums: contracts traded
  in lots, premium turnover, OI in lots, excluding single-print contracts,
  liquidity-bucketed slippage.
- **R-multiple / MFE / MAE / exit-efficiency reporting** — a whole analytical
  dimension not built at all. Would answer "does this earn enough per unit of risk,"
  which win-rate/median/concentration alone don't.
- **Partial-profit-taking variant ("veteran compromise")**: take partial profit at
  1R/first pivot, move stop to breakeven, trail the remainder — instead of the
  current all-or-nothing resistance exit. Untested. Their own hedge: "full exits at
  daily pivot resistance probably leave money on the table in the best trend leaders.
  They also probably improve hit rate and median. Both can be true."
- VCP minimum base age check (could be accepting compact structures the multi-week
  spec doesn't intend) and a true volume-dry-up check near the pivot (last few days
  specifically, not just the last leg's average) — both untested refinements to
  `vcp.py`'s base detection.
- Sector-leadership tracking and earnings/event-proximity annotation — neither built.
  Sector leadership ties directly into item 5's next hypothesis.
- Options: back out approximate delta/IV instead of a fixed 5% ITM offset; a premium
  stop or time stop (-35% to -50% premium loss, or exit if the stock hasn't moved in
  3-5 sessions) as an options-specific exit distinct from the stock's own stop; using
  the actual next-tradable option price rather than an idealized same-close fill if a
  signal is discovered after the close (same root issue as the top hard block, just
  options-specific). None built.
- `oi_buildup_bullish()` sits unused in `option_backtest.py` — either integrate and
  test it or remove it, per their suggestion. Real dead code, not yet acted on.
- Epistemic caution worth keeping in mind rather than acting on directly: treat
  `VOL_ZSCORE_WINDOW=8` and `vcp.LAST_LEG_TOLERANCE=0.40` as "this general adjustment
  direction helped," not "this exact number is the true one" — both were chosen from
  in-sample sweeps, same caveat as everything else pending walk-forward validation.
