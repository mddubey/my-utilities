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

**Promising untested lead: SMA50, not just SMA200/ADX, for the market-level gate.**
`market_regime.py` already computes and caches `sma50` for Nifty but `market_trending()`
never uses it. Quick check (2026-09-01): a `Close > SMA50` filter would have closed
the gate in October 2024 itself (100%→14% open that month) instead of December/
January under the current SMA200-based gate; an `SMA50 rising` (5-day lookback, same
convention as the existing ADX_RISING test) filter closes it by mid-November
(→0%). Both are meaningfully faster than the current gate's 62-100%-open readings
through the same window. **Not yet backtested as an actual filter** — two structurally
similar-looking ideas already failed on this exact question (`TEST_ADX_RISING` halved
the sample for no real gain; `TEST_ADX_UPTREND`/+DI-DI cut the sample 37% and didn't
discriminate the VCP patch at all) — "closes the gate faster during the bad patch" is
necessary but not sufficient; the real test is a full backtest re-run (n/win/median/
concentration) with the SMA50 filter added, not just eyeballing the Nifty-level days.

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

**Survival analysis / capital-efficiency metric** — real, done findings (see the
critique-response threads for full derivation): eventual stop-outs take ~2x longer to
resolve than resistance wins across both the swing and options layers; the resulting
options-layer asymmetry (bigger losses on trades held longer) is a stock-duration
effect, not options-specific theta bleed, since implied leverage stays symmetric
(~9.4x losers vs ~9.9x winners). Real leverage across all 4 contract-selection
variants is flat (9.5-11.5x) — ITM's moneyness offset barely reduces leverage despite
costing 1.5-2x the capital per lot, so whatever case exists for ITM rests on
liquidity/theta characteristics, not risk reduction. Computed on the pre-v27 options
sample; not yet re-run on the bigger v27-derived set.

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
