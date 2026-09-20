# Findings log

Analysis conclusions and narrative decisions that never changed a single code
parameter, so they had nowhere to live under the "comment next to the code" policy
(see `README.md`'s Current status section). Anything that DID change a parameter is
documented as a comment at that parameter instead — this file doesn't duplicate that.

## Market structure: the Closing Auction Session (CAS)

**A real, dated market-structure change (2026-09-02) this project had no visibility
into until directly investigated.** SEBI's Closing Auction Session (CAS) went live
2026-08-03, Phase 1 = F&O stocks only (`fo_universe.csv`'s exact scope). Continuous
trading for F&O names now genuinely ends at **15:15 IST**, not 15:30 — a separate
20-minute auction (15:15-15:35) sets the real official close, reference price = VWAP
of 15:00-15:15 trades, ±3% band, market/limit orders only (no stop-loss orders
allowed in that window). Confirmed directly against real intraday data (see
`intraday_cache.py`): post-CAS 5-minute bars for F&O tickers simply stop at 15:15,
nothing after — matches the mechanism exactly.

**Real, confirmed downstream consequences:**
- The earlier suggestion to push `daily_scan.py --live`'s cutoff to ~15:15-15:20
  (reasoning: "a few minutes is enough to place an order before the 15:30 close") is
  WRONG for F&O names post-CAS — 15:15 is the wall itself now, not a target with
  buffer before it. A live check should stay safely before 15:15 for F&O tickers.
- Real stop-loss ORDERS (the order type) cannot function during 15:15-15:35 for F&O
  names — a resting stop won't trigger in the auction window; managing an exit that
  would hit during that window needs a manual market/limit action instead.
- **A real, previously-unknown bug in `fetch_prices.py`, found and fixed
  (2026-09-02): yfinance returns a NULL Close for a date when that date is the LAST
  row of a wide multi-day range request, but the correct value when the same
  date/ticker is requested as a narrow single-day range on its own** — confirmed
  reproducible across 8/8 tickers checked, consistently. `fetch_all()`'s
  existing-tickers branch computes ONE shared start date (the minimum last-cached
  date across the whole batch) for every ticker in that call — so even a single
  stale ticker widens the request for everyone, meaning the existing NaN-close
  protection (`dropna(subset=["Close"])`, itself a fix from an earlier real incident)
  could silently drop the latest day's data for tickers that were otherwise fully
  current, with no visible error. Fixed with `_recover_safe_today()`: after the main
  fetch, any ticker still missing `safe_today`'s row gets one narrow single-day
  re-fetch, which reliably returns the correct value. Verified against the real,
  reproduced bug (not just a synthetic test) before considering it fixed — see
  `fetch_prices.py`'s own comments for the full mechanism and `tests/test_fetch_prices.py`
  for the regression test.
- **RESOLVED (2026-09-02): yfinance's daily Close correctly reflects the CAS-determined
  official closing price — confirmed, not just assumed.** Fetched NSE's own cash-market
  bhavcopy directly (`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_
  {ymd}_F_0000.csv.zip`, UDiFF format, same family as the F&O file `fetch_stock_options.py`
  already uses — its `ClsPric` field is NSE's own authoritative official close, and
  `SttlmPric` is the actual auction-settled price). Compared against our own cached
  `data_cache/` Close across 6 tickers x 5 post-CAS dates (29 successful comparisons,
  one date failed to fetch — likely a holiday): **29/29 exact matches**. Also notable:
  NSE's own `ClsPric` and `SttlmPric` are themselves almost always within a few paise
  of each other on ordinary days — the CAS auction typically settles very close to the
  pre-auction reference, which is also why the raw-bars check above happened to line up.
  No fix needed — the pipeline is accurate as-is. This was a one-off verification script,
  not built as permanent infrastructure (no ongoing need once confirmed).
- 60 days of real 5-minute intraday data (`intraday_cache.py`, all 500 tickers, June
  10 - Sept 1) captured and cached permanently before it ages out of yfinance's own
  rolling 60-day retention window — this is what made the above verification
  possible at all, and is available for further CAS-window analysis later.
- Checked directly (2026-09-02) whether CAS shows up as a detectable shift in this
  project's own signals: close-position-within-day's-range (pre/post-CAS median
  0.462/0.478 — noise) and raw weekly signal-firing rate (no collapse at the Aug 3
  boundary, wide variance both before and after) — **no detectable pattern in either
  check**, on ~4 weeks of post-CAS data. Doesn't rule out a real effect specifically
  inside the 15:00-15:35 window itself, which these two checks don't touch — now
  possible to investigate with the intraday cache above, not yet done.

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

**Sector leadership — ADOPTED as a ranking signal (2026-09-01), but does NOT explain
the VCP weak window (5th hypothesis tested, also ruled out).** Built `sectors.py`
(ticker→sector via yfinance, cached, 499/500 classified) and `sector_strength.py`
(sector-level relative strength, same methodology as `relative_strength.py`'s
per-stock RS but grouped by sector). Two separate results:
- **General signal, real and worth keeping**: bucketing all v28 trades by sector-RS
  percentile at entry, VCP specifically shows a clean pattern — win 56.1%/60.8%/
  55.3% in the bottom three quartiles vs **68.1%** in the top quartile (leading
  sector), and concentration drops from a lumpy 75-200% down to a healthy 30.5%.
  Leading-sector trades aren't just winning more, they're winning broadly. Adopted as
  a `daily_scan.py` annotation (`sector`, `sector_rs` fields — shown as
  "{sector} (sector RS {N})" under each candidate), **NOT a hard filter** — same
  reasoning as keeping MOMENTUM_20D_MIN/MIN_TRADED_VALUE as candidate-list controls
  rather than proven gates: helps decide which of several same-day candidates to
  prioritize, doesn't shrink the list.
- **Does not explain the Oct'24-Feb'26 weak window specifically**: sector-RS during
  that window was only mildly lower than outside it (median 63.6 vs 72.7), and
  splitting the weak-window trades themselves by sector strength doesn't discriminate
  at all — above-median-sector trades still lost (46.2% win, -1.1% median), nearly
  identical to below-median (46.9% win, -2.3% median). There IS a real compositional
  shift (Industrials' share of VCP trades dropped from 34% outside the window to 17%
  inside it, Financial Services and Basic Materials grew) but sector quality itself
  stopped mattering during this specific stretch, so the shift isn't the actual
  driver. Fifth hypothesis for the VCP collapse ruled out, same as the four
  regime-gate ideas above — remaining candidates: volatility regime, market breadth.

**Volatility regime and market breadth — 6th and 7th hypotheses tested (2026-09-01),
both ruled out, and the VCP collapse investigation is paused here.**

| metric | weak window (Oct'24-Feb'26) | outside window | gap |
|---|---|---|---|
| Nifty index ATR% (n=351 vs 884 days) | median 1.07% | median 1.10% | none |
| per-stock ATR% at VCP entry (n=198 vs 465 trades) | median 3.56% | median 3.49% | none |
| market breadth at VCP entry (n=198 vs 465 trades) | median 62.6% | median 85.6% | real, ~23pt gap |

Per-trade split within the weak window (n=198 VCP trades):

| split by | bucket | n | win% | median pnl |
|---|---|---|---|---|
| per-stock ATR% | below median | 99 | 45.5% | -3.3% |
| per-stock ATR% | above median | 99 | 47.5% | -0.4% |
| breadth | below median | 102 | 57.8% | +2.4% |
| breadth | above median | 96 | 34.4% | -5.4% |

Volatility (both index-level and per-stock) shows no gap at either the window level
or the per-trade level — ruled out cleanly. Breadth shows a real, large gap at the
window level (62.6 vs 85.6) but the sign FLIPS at the trade level — lower-breadth
days within the window actually did better (57.8% win) than higher-breadth days
(34.4% win), the same failure mode as the rejected SMA50-AND gate test: a metric
that's genuinely different across the whole bad period but backwards as a per-trade
filter within it.

**Why the investigation stops here rather than continuing to the remaining
critique-list items (earnings-season clustering, election/macro period effects):**
across all 9 hypotheses checked for this window (Nifty direction, weak RS, ADX
rising, ADX uptrend, SMA50-AND, SMA50-OR-recovery, sector concentration, volatility,
breadth), there's a consistent shape — whenever a metric shows a real difference
across the whole bad period (SMA50, breadth), it fails or reverses the moment you
look at individual trades within that period; whenever a metric shows no macro
difference at all (volatility), there's nothing to find at the trade level either.
That's not what you'd expect if an external, conditionable factor (market regime,
sector, volatility, breadth) were actually driving this — at least one should have
discriminated the real losing trades from the winning ones within the window itself.
None did. Read as pointing toward something more idiosyncratic (either genuine
variance in a still-real edge — 56% and 65% win-rate windows both happen normally in
924+ trades — or something specific to VCP's own base-detection mechanics during
that stretch, not a macro-conditions question at all), rather than a filter waiting
to be found. Given the track record, the two remaining critique-list items are lower
confidence and harder to test than what's already been tried, so this is a
deliberate stop, not an oversight — the natural next angle if this gets picked back
up is the base *shapes* of the losing trades themselves (thinner/shorter/different
than usual), not another macro filter.

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

**Does a next-day (or next-few-day) pullback to daily EMA8/EMA34 mean anything?
Checked (2026-09-02), and the "wait for the support test" instinct doesn't hold
up.** Bucketed all 1430 v28 trades by whether/how they interact with daily
EMA8/EMA34 within 3 days of entry:

| bucket | n | % of total | win% | median pnl | concentration |
|---|---|---|---|---|---|
| never touched (ran straight up) | 798 | 55.8% | 74.3% | +3.9% | 8.7% (healthy) |
| touched EMA8 only, shallow pullback | 501 | 35.0% | 59.1% | +1.8% | 199.6% (thin) |
| touched EMA34, closed above (held) | 62 | 4.3% | 50.0% | +0.1% | -434.4% (too thin) |
| touched EMA34, closed below (broke) | 69 | 4.8% | 14.5% | -7.1% | -16.8% |

Trades that never needed a pullback at all are the BEST bucket, not the riskiest —
independently reconfirms the earlier chase-vs-pullback finding from a completely
different angle (support-touch behavior instead of entry-day move size). "Touch and
hold the 34EMA" is close to a coin flip with an unreliable sample (n=62); the only
clean, trustworthy signal is at the extremes. A same-scope **hourly** cross-check
(1h EMA8/34, using the new `intraday_cache.py`, n=181, ~2.5 months of real data
only) did NOT cleanly replicate this — hourly EMAs get touched constantly by
ordinary intraday noise (bucket shares completely different: "never touched" dropped
to 8.8% of trades, "broke" jumped to 27.1%), and every bucket there is too thin
(n<105, wild concentration) to trust. The daily result stands; the hourly one is
inconclusive on the data actually available (only 60 days retained before
yfinance's window ages it out).

**Reverse framing: is closing below EMA8/34 (at ANY point during the full holding
period, not just the first 3 days) basically as good as a stop? Checked — EMA34
yes, EMA8 no.**

| level | % of trades that ever break it | win% if broken | median pnl if broken | catches real losers | falsely flags real winners |
|---|---|---|---|---|---|
| EMA8 | 62.9% | 45.2% | -1.21% | 98.6% | 43.8% |
| EMA34 | 29.3% | 18.6% | -6.92% | 68.2% | 8.4% |

EMA8 breaks are too common (63% of ALL trades, including 44% of eventual winners) —
normal noise during a healthy uptrend, not a failure signature. EMA34 breaks are
much rarer and much more meaningful: 81.4% of trades that break it end up losing,
with only an 8.4% false-positive rate against real winners. **Timing check: 98.3% of
EMA34 breaks happen strictly BEFORE the trade's actual stop-out** (median 7 days
early, mean 11) — a genuine leading indicator, not just a restatement of the
existing exit.

**Designing "breaking" properly, not just "any close below"**: tested 4 candidate
definitions (bare close-below, ≥1% below, ≥2% below, 2 consecutive closes below).
At nearly the same false-positive rate (~4.2-4.3%), the **≥1% margin** rule catches
far more real losers than the **2-consecutive-closes** rule (57.8% vs 37.0%
sensitivity) — a real break shows up as closing convincingly under the level, not
just needing an extra day to "confirm." ≥2% below is even more precise (2.2% false
positives) but starts missing too many real losers (41.6% sensitivity).

**Simulated actually adopting this as an automatic early-exit rule — net NEGATIVE at
every threshold tested, don't adopt.** Re-ran the full 1430-trade set with the
EMA34-break day (if any) replacing the original exit:

| | win% | median pnl | concentration | trades actually exited earlier |
|---|---|---|---|---|
| current (existing stop only) | 65.0% | +2.89% | 10.3% | — |
| + ≥1% EMA34 early-exit | 62.3% | +2.63% | 10.7% | 11.5% |
| + ≥2% EMA34 early-exit | 63.7% | +2.83% | 10.5% | 5.6% |

Stricter threshold = less damage (fewer trades touched, smaller drop) but NEVER a
net improvement at either threshold. By pattern, VCP takes the bigger hit both times
(≥1%: 61.7%→58.2% win, conc 22.0%→24.0%; ≥2%: 61.7%→60.2%, conc 22.0%→22.7%) than
Breakout Continuation (≥1%: 67.9%→65.8%; ≥2%: 67.9%→66.8%) — VCP's own exit design
(Minervini's structural stop) is already built to tolerate a temporary EMA dip while
holding a multi-week base, so a faster generic EMA trigger fights that design more
than it does Breakout Cont's already-faster ATR-chandelier stop. **Conclusion: this
is a genuinely good diagnostic (correctly flags most future losers, a week or more
early) but not a profitable automatic exit rule at any threshold tested** — the real
recoveries it cuts short always cost more than the early losses it saves. Best use:
a manual watch/warning signal (e.g., surfaced in `monitor_positions.py`), not
something to wire into the exit logic.

**Does immediate (day-3) follow-through strength predict real quality, and can it be
seen at entry? Checked (2026-09-02) — yes to the first, breadth is the only real
answer to the second.** Bucketed all v28 trades by actual day-3 stock return, then
looked at their REAL, patient, full eventual outcome (not cut early) per bucket:

| day-3 performance | n | real eventual win% | real median pnl | median holding days |
|---|---|---|---|---|
| down >2% by day 3 | 356 | 39.6% | -5.3% | 13 |
| down 0-2% | 313 | 58.8% | +1.8% | 16 |
| up 0-2% | 314 | 76.1% | +3.5% | 15 |
| up 2-5% | 253 | 74.3% | +3.9% | 11 |
| up >5% by day 3 | 194 | 91.8% | +8.0% | 5 (fastest) |

Real, monotonic, and doesn't contradict the "don't exit on weak early action" finding
above — 39.6% of the weakest bucket still wins if held patiently (that's exactly why
cutting them all early was net harmful), but as a QUALITY signal, strong immediate
follow-through genuinely does mean a better trade, matching the "is this a real
breakout" intuition directly.

**By pattern (2026-09-02): VCP is far more sensitive to a weak immediate start than
Breakout Continuation.** In the worst bucket (down >2% by day 3): BC still wins
51.4% of the time (median +0.2%, barely positive but real) — a weak start isn't a
strong red flag for a stock already mid-trend. VCP crashes to 27.7% win (median
-6.7%) in the same bucket — for a base-breakout pattern, no immediate follow-through
more directly suggests the base itself failed. Both patterns converge to a similarly
strong outcome at the good end (up >5% by day 3: BC 92.1% win, VCP 91.4% win) — the
asymmetry is specifically in how much a WEAK start should worry you, not in whether a
strong one is good.

Compared entry-day features between the two extremes (down>2% vs up>5%) to see if
this could be caught AT ENTRY instead of 3 days later — pattern mix, volume z-score,
RSI, entry-day move size, close-position-in-range, and ATR% were all statistically
indistinguishable between the two groups. **Market breadth was the one real
discriminator**: median 68.9% (immediate-failure group) vs 85.5% (immediate-strong
group). Tested properly as an entry-gate threshold sweep (not just the two-group
comparison) — a real, clean, MONOTONIC result, unlike every other gate idea tried
this session:

| breadth threshold | n | win% | median pnl | concentration |
|---|---|---|---|---|
| none (baseline) | 1430 | 65.0% | +2.89% | 10.3% |
| >=65% | 990 | 65.6% | +3.03% | 13.6% |
| >=70% | 835 | 67.5% | +3.21% | 13.3% |
| >=75% | 748 | 68.9% | +3.42% | 13.0% |
| >=80% | 670 | 69.3% | +3.58% | 13.6% |

Win rate and median both climb steadily as the threshold tightens, concentration
only drifts up mildly (still well within a healthy range) — genuinely different from
the ADX/SMA50 gate ideas (backwards or inconclusive). **Per direct user instruction,
NOT adopted as a hard filter** — same reasoning as sector-RS: use it as a
ranking/confidence signal, don't shrink the candidate list. Implemented as a
top-level annotation in `daily_scan.py` ("market breadth today: X%..."), since
unlike sector-RS this is one market-wide number per day, not a per-stock value, so
it reads as "how much weight to put on today's whole list" rather than a per-ticker
ranking field. `market_regime.py`'s `market_trending(min_breadth=...)` param and
`backtest.py`'s `TEST_MIN_BREADTH` exist and are tested/documented for anyone who
later wants to revisit this as an actual gate.

**By pattern (2026-09-02): VCP gets the bigger lift from breadth, consistent with it
being the more breadth-sensitive pattern overall.**

| variant | breakout_cont win/median/conc | coiled_spring win/median/conc |
|---|---|---|
| baseline | 67.9% / +2.93% / 16.4% | 61.7% / +2.88% / 22.0% |
| breadth>=70 | 69.2% / +3.18% / 22.3% | 65.5% / +3.32% / 26.3% |
| breadth>=80 | 70.7% / +3.61% / 22.1% | 67.4% / +3.45% / 27.0% |

Win rate climbs +5.7pp for VCP (61.7%→67.4%) vs +2.8pp for BC (67.9%→70.7%) going
from baseline to breadth>=80 — matches the day-3 finding above that VCP is generally
more dependent on the environment cooperating, while BC is more self-sufficient once
already trending. Concentration gets meaningfully worse for both patterns (roughly
+6pp each), a real, shared cost of the tighter sample, not specific to either one.

## Exit-strategy comparison: moving resistance vs fixed-R targets vs trail-only (2026-09-03)

Prompted by a real practical question ahead of live trading: does waiting for a bigger fixed R-multiple (2R/3R) instead of the current moving-resistance-pivot target make more money, and what does the "textbook" VCP/momentum trailing-stop-only exit actually look like on this data? All four variants share the exact same entry logic (`detect_entry`) — only the exit rule differs. Measured on the full v28-equivalent sample (not capital-constrained), using per-trade R-multiple = (exit_price − entry_price) / (entry_price − initial_stop), expectancy = win_rate × mean_win_R + loss_rate × mean_loss_R (mean, not median — median understates true expectancy under right-tail skew, same lesson as the options side's leverage metric), and concentration = top-10 trades' share of total net R (this project's standing outlier-risk check).

| Variant | n | Win % | Mean win R | Mean loss R | Expectancy | Median hold (days) | Concentration |
|---|---|---|---|---|---|---|---|
| **Baseline** (moving resistance target, current production) | 1430 | 65.0% | 0.826 | -0.897 | +0.224R | 13 | 10.6% |
| 2R fixed target | 1235 | 51.3% | 1.399 | -0.785 | +0.336R | 24 | 9.1% |
| 3R fixed target | 1204 | 50.4% | 1.524 | -0.782 | +0.380R | 26 | 11.3% |
| Trail-only (`use_resistance=False`, no target at all — pure 21-EMA/chandelier/structural-low trail + climax exit) | 1162 | 49.8% | 1.876 | -0.784 | **+0.542R** | 29 | **24.7%** |

**By raw per-trade expectancy, trail-only > 3R > 2R > baseline — a real, well-distributed effect** (not a concentration artifact at this full n=1200+ sample size; a naive first look at a capital-constrained ₹1L/~2yr slice showed 2R at 85.8%/3R-adjacent concentration and looked alarming, but that was an artifact of slicing the sample down to ~150-220 trades, not a property of the strategy — always re-check concentration on the full sample before trusting a thin slice).

**But higher expectancy does not mean "better exit rule" once you look at HOW each variant gets there — this matters more than the headline number:**

- **2R/3R**: only about half of nominal "wins" ever actually reach the stated target. Broke down the 2R set's winners by exit reason: 318 of 633 winners (50.2%) hit the actual 2R target (mean 2.37R, up to 4.34R on gap-throughs); the other 311 (49.1%) are trades that rose, dragged the trailing stop up behind them, then reversed and got stopped out **above breakeven but nowhere near 2R** (mean only 0.40R, range 0.004R–1.52R). So "2R fixed target" describes where the target sits, not what most winning trades actually book — roughly half the time the trailing stop catches the trade on the way back down long before target.
- **Trail-only**: 96.7% of ALL exits (1134/1173) are via the trailing stop; the climax/exhaustion exit fires only 38 times (3.2%) despite being specifically designed to catch a blow-off top. Median trade is a near-exact coin flip that nets to roughly zero (median pnl_pct −0.05%) — the entire +0.542R average is carried by a small number of outsized winners the trail happens to catch a long way into a big run, which is exactly why concentration jumps to 24.7% (2-2.5x every other variant). This is the classic trend-following shape (cut losses fast, rarely ride a monster winner) — real edge, but a materially harder system to stay disciplined through day-to-day than the headline expectancy number suggests, and likely why an earlier, less rigorous test of this same idea (see "Two open questions closed" in memory) was rejected — that verdict holds up, just for a different reason (lived-experience lumpiness/coin-flip win rate, not lack of edge).

**Conclusion: this is a genuine, unresolved trade-off, not a settled "switch to X."** Baseline is the cleanest/most consistent (65% win, lowest concentration, shortest holds) but leaves real per-trade expectancy on the table. 2R is a reasonable middle ground (materially better expectancy than baseline, concentration/win-rate still sane). Trail-only has the best raw number but is the least "clean" in practice — a coin-flip win rate carried by rare large winners. No change made to the production exit rule from this investigation; logged for whenever the user wants to revisit which trade-off to accept.

**Live case study reopening this (2026-09-04)**: IFCI (real pilot entry, 96.90 on 2026-09-02) hit a day High of 107.50 on 2026-09-04 (+10.9% from entry) but the model's own moving-resistance target sat at only 102.87 — a mechanical target-exit would have captured barely half the day's real move. Direct user reaction: "if I enter yesterday and exit today [on target], I will never make money" — explicit standing instruction to revisit this trade-off later using IFCI as a concrete live example, not decided yet.

## "Near-miss" ranking signal: intraday High vs closing Close (2026-09-03)

Prompted by a real live example: 4 real TradingView charts (Meesho, Texmaco Infrastructure & Holdings, Euro Pratik Sales, Belrise Industries) shared by the user, each showing a stock breaking out of a tight consolidation box. Investigated why the scanner wasn't flagging the first two.

**Texmaco**: not in the 500-ticker `nifty500_universe.csv` at all — too small-cap, the scanner never considers it. Trivial, not a bug.

**Meesho**: two independent reasons, isolated by checking each entry condition directly (same method as the earlier AUROPHARMA investigation) —
- VCP/Coiled Spring structurally cannot fire: Meesho IPO'd 2025-12-10, so as of 2026-09-02 it has only ~183 trading days of history. `stage2_trend_template()` requires a 200-day SMA and a 252-day high/low window, both genuinely undefined this early — a real methodological requirement (Minervini's trend template is designed to confirm an established uptrend), not a bug.
- Breakout Continuation missed by exactly one line: every other gate passed (trend bullish, RSI 67.8, EMA34 rising 10/10, liquidity, momentum), but `breakout_continuation()`'s own check — `Close > high10_prior` — failed (Close ₹211.60 vs prior-10-day-high ₹212.65), even though today's intraday High (₹213.95) did clear that level. The scanner requires a *closing* breakout by design, not an intraday touch.

**Tested loosening the check from Close to High** (monkeypatched variant, full 500-ticker backtest, not a scratch guess): n 1430→1468, win 65.0%→64.9%, median +2.89%→+2.87% — looks like a wash in the pool average. But per standing methodology (check the MARGINAL trades directly, never trust pooled averages alone): isolated the 46 trades this variant newly unlocks (44 breakout_cont, 2 coiled_spring via a scheduling-cascade side effect) — win 63.0%, median +2.29%, mean +1.85%. Real and tradeable, modestly below the full pool's quality, but NOT the "buying a failed breakout that already reversed" disaster the mechanism suggested. A separate 8 trades that exist under the current Close-based rule vanish under the High-based one (same cascade mechanism) and are unusually strong (87.5% win, +4.57% median) — so the trade is: gain 46 mediocre signals, lose 8 excellent ones.

**Decision: NOT adopted as the entry rule** — net is close to a wash tilted slightly negative, and per direct user instruction, going into live trading isn't the time to add a coin-flip-adjacent signal that looks like a real one. **Adopted instead as a third, explicitly low-weight `daily_scan.py` output section**: `signals.near_miss_high_breakout()` — same checklist as Breakout Continuation, swaps only the final Close-vs-High comparison, explicitly skipped if the real Close-based signal already fired (no double-listing). Wired into `daily_scan.py`'s `scan()` as a third bucket alongside "Tradable Today" and "Watchlist", printed with an explicit low-weight/informational caveat and the real backtest numbers inline. Same design pattern as the existing breadth/sector-RS annotations — a ranking hint for quiet days, never promoted to a gate without a fresh full-backtest check. Verified end-to-end: MEESHO appears in this new section with the real numbers (close ₹211.60, high ₹213.95, resistance ₹212.65). All 69 tests pass.

## Real bug found and fixed: split-adjusted spot price corrupting contract selection (2026-09-03)

Found while manually inspecting a single trade's lot cost (BEL, 2022-08-23 — the single most expensive lot in the whole ITM+next set at ₹5,28,390). Root cause: `option_backtest.py`'s `pick_contract()` compares option strikes (bhavcopy, never retroactively adjusted) against `spot_price` sourced from `data_cache` (yfinance) — but yfinance RETROACTIVELY rescales all historical prices for every stock split/bonus after the fact. Any ticker that split between its trade's entry_date and whenever `data_cache` was last fetched gets compared against the wrong spot. Confirmed directly against NSE's own historical cash-market bhavcopy: BEL's real, contemporaneous close on 2022-08-23 was ₹298.45; `data_cache` shows ₹99.48 for that same date today (a ~3.00x ratio, i.e., BEL did a 1:3 split/bonus sometime after that date). `pick_contract()` picked strike 200 (deep-deep ITM against the real ₹298.45) instead of the correct ~283.5 (a genuine 5%-ITM target).

**Scope, checked before assuming it was a one-off**: strike/spot ratio across the full 562-trade ITM+next set should sit near ~0.95 for a genuine 5%-ITM call. **91 of 562 trades (16.2%) were wildly outside that band, up to 19.76x** (NESTLEIND) — hitting most of the well-known Indian split/bonus names: BAJFINANCE, RELIANCE, HDFCBANK, KOTAKBANK, SHRIRAMFIN, WIPRO, MCX, CANBK, COFORGE, NAUKRI, HAL, PFC, and more. A second instance of the identical bug existed at the expiry-settlement step too (`stock_close()`, used to compute intrinsic value for held-to-expiry trades) — same root cause, different call site.

**Fix**: built `fetch_cash_bhav.py` — pulls NSE's real, never-adjusted historical cash-market bhavcopy (two archive formats: legacy `cm{DDMMMYYYY}bhav.csv.zip` for older dates, UDiFF `BhavCopy_NSE_CM_0_0_0_{ymd}` for newer — tried in that order, paced to avoid NSE's rate-limiting, confirmed directly: a URL that returned 200 started returning 503 after a few rapid follow-ups, then 200 again after a short pause). `option_backtest.py` now uses this real spot at both the entry (contract selection) and expiry-settlement steps, falling back to the old `data_cache`-derived price only when no cash bhavcopy is cached for that date (tracked and reported, not silent).

**Verified the fix actually worked**: re-checked strike/real-spot ratio across all 562 trades post-fix — mean 0.961, std 0.023, tightly clustered around the expected 0.95. Only 7 of 562 sit slightly outside a strict band (1.05-1.08), and those are normal strike-ladder granularity on expensive/wide-strike-spacing stocks (ULTRACEMCO, MCX), not bugs.

**Result — the core edge survives and slightly strengthens, but the number we'd already reported was measuring the wrong thing for 1 in 6 trades**:

| | n | Win % | Median | Concentration |
|---|---|---|---|---|
| Buggy (what was reported to the round-6 critic) | 562 | 61.6% | +18.63% | 32.6% |
| **Fixed** | 562 | **62.5%** | **+19.34%** | **29.0%** |

All 4 contract-selection variants regenerated on the fixed pipeline (`runs/opt_v28_{atm,itm}_{current,next}.csv`):

| Variant | n | Win % | Median | Mean | Concentration |
|---|---|---|---|---|---|
| ATM current | 572 | 46.7% | -15.91% | +2.32% | 297.1% |
| ITM current | 571 | 54.6% | +10.97% | +6.58% | 70.3% |
| ATM next | 562 | 58.4% | +15.07% | +11.18% | 44.4% |
| **ITM next (standing decision)** | 562 | **62.5%** | **+19.34%** | **+16.32%** | **29.0%** |

ITM+next remains the clear best variant and the standing decision is unchanged and, if anything, better-evidenced now. Note: only ITM+next has a clean, isolated before/after-fix comparison on the identical v28 dataset (the table above) — the other 3 variants' most recently *recorded* numbers in memory predate v28 entirely (computed on v27's swing entries), so don't diff them against those older numbers as if the delta were purely the spot-price fix; that comparison is confounded by the v27→v28 swing-side change too. ITM-current in particular looks meaningfully healthier here (54.6%/+10.97%/70.3%) than its old v27-era reputation ("near-zero, unreliable, -869% concentration") — worth a fresh, isolated look later, not concluded here.

**Separate, smaller, NOT-fixed residual**: 36 (ticker, date) pairs across 12 tickers still fall back to the old price — not the split bug, a different cause: **ticker renames/demergers** (ETERNAL=Zomato's new name, ADANIENSOL/GVT&D=Adani Energy Solutions demerger, LTF/LTM=L&T Finance-family renames, TMPV=Tata Motors Passenger Vehicles demerger, PGEL, PATANJALI, SUZLON, UNITDSPR, GMRAIRPORT, ADANIPOWER). The historical bhavcopy simply doesn't have data under the ticker's CURRENT name for dates before the rename. Would need a historical-symbol-mapping table to fix properly — flagged, not built, since it affects far fewer trades (36 lookups vs the 91-trade split bug) and isn't blocking anything right now.

**Correction owed to the round-6 outside critique**: the "562 trades, 61.6% win, +18.63% median, 32.6% concentration" number we told the critic to trust "more than any portfolio number" was itself corrupted for 91 of those 562 trades. The corrected number is close and slightly better, so the critic's underlying conclusion (trust per-trade metrics over the portfolio simulator) stands — but the exact number sent needs updating in the next round.

## Outside critique Round 7 (2026-09-03) — response to the split-bug fix + lot-cost analysis

Full submission and response in `/Users/mdubey/Documents/pet-pooja/Options stoploss management-response7.pdf` (12 pages). Key outcomes:

**Verdict upgrade**: per-trade options dataset moved from yellow to green ("trustworthy after integrity fix") on the strength of the split-adjustment bug fix — called it "the biggest bug found in the whole project," bigger than the CAS discovery. Contract selection confirmed green (ITM-next genuinely best per trade). Portfolio simulation stays yellow (research tool only), real-money options stays red (wait).

**Allocator disagreement, resolved in the critic's favor — logged as the standing approach**: pushed back directly on a lookahead/optimization-based allocator fix (which was under consideration after the slot-cap removal proved insufficient) — called it "cheating" since a lookahead allocator uses future trade information you wouldn't have live. Reframed the problem as a 0/1 knapsack and proposed ranking today's candidates by `expected_score / capital_required` (score-per-rupee), using only information available that day — no future peeking. Correctly demoted the allocator from Sprint-A priority #1 to #4: "the strategy doesn't depend on it anymore" now that per-trade data integrity is fixed — it's a portfolio-research nicety, not a correctness blocker. **Not yet built** — next concrete step if picked up.

**Convexity/premium-based options exits — confirmed dead, archive the whole branch.** Matches this project's own conclusion (EMA-trail and %-drop-from-peak both rejected, same mechanism as the earlier fixed premium-stop rejection).

**Concrete, capital-driven deployment thresholds for options** (based on our own lot-cost table, median ITM-next lot ₹48,400): ₹1L → no. ₹2L → paper/live-shadow only. ₹5L → small allocation, 5-10% of portfolio. ₹8-10L → strategy becomes practical. Reasoning: one ITM-next lot is already ~10% of a ₹5L account (manageable) vs ~50% of a ₹1L account (too concentrated in one position).

**New feature proposed, rated more valuable than allocator optimization — NOT built yet**: a "Capital Feasibility Layer." Scanner takes account size as an explicit input; for each candidate, flags feasible/large-allocation/skip based on that candidate's actual lot cost vs. the given account size. Doesn't touch the strategy itself, purely an execution-adaptation layer. Example shape: `AUROPHARMA ITM-next ₹27k → feasible at ₹1L; NAVINFLUOR ITM-next ₹51k → large allocation; OFSS ITM-next ₹1.8L → skip`.

**Walk-forward validation — now explicitly recommended** (was told to wait before this round). Proposed protocol: freeze v28's params entirely (RSI_MAX=80, VOL_ZSCORE_WINDOW=8, daily pivots, VCP tolerance, regime gate) — train on nothing, just roll the test window forward: train-until-2022→test-2023, train-until-2023→test-2024, train-until-2024→test-2025, train-until-2025→test-2026. If v28 survives unseen years without retuning, that's rated as more trustworthy evidence than another parameter sweep. **Not yet run.**

**Pushback on our own "ITM-next is strictly better than ATM-next" framing — corrected, real numbers computed same-session**: proposed metric `(median_return × win_rate) / median_lot_cost` ("edge per ₹10,000 deployed") and left it as an open question for both variants. Computed directly:
- ATM-next: (15.07% × 58.4%) / ₹32,358 × ₹10,000 = **0.0272**
- ITM-next: (19.34% × 62.5%) / ₹48,400 × ₹10,000 = **0.0250**

**ATM-next is actually ~9% MORE capital-efficient per rupee deployed**, despite being the lower-quality variant per trade. Corrected standing framing: ITM-next wins on per-trade quality (win rate, median, concentration), ATM-next wins on capital efficiency (edge per rupee). Neither is "strictly better" — which objective matters depends on whether capital or edge-per-trade is the binding constraint for the account size in question.

**Their own personal ₹1L account plan (Sep-Oct 2026), unchanged in substance from round 6 but now more confident**: trade stocks only with v28 real money at ₹1,000 max risk/trade (matches the user's actual plan); ₹0 options capital, paper-trade every ITM-next signal instead; keep an options journal (fills, spread, slippage, lot cost, expiry chosen); compare live vs backtest after 30-40 real stock trades and 30-40 shadow option trades. Still no real options money — not because the edge is doubted, but because "the execution economics for a ₹1L account still don't work... the instrument has coarse lot sizing," an instrument-structure problem, not a strategy flaw.

**Rename bug (12 tickers, 36 lookups) — classified Medium priority**, below the split bug (Critical) and CAS close-timing (High): "it affects completeness, not correctness." Consistent with our own earlier decision not to fix it yet.

**Bigger future idea, not started, own separate project**: calibrated win-probability per trade (logistic regression or gradient boosting on the existing 1,430 stock + 562 option trades) instead of a binary pass/fail scanner signal — framed as "how much confidence to place in a signal," while keeping v28's actual entry logic frozen. Explicitly NOT proposed as a filter change.

**Revised Sprint A priority order (supersedes the round-6 version)**: 1) walk-forward validation, 2) transaction cost + bid/ask spread model, 3) capital feasibility layer, 4) allocator v2 (score-per-capital, portfolio-research only, not a live-trading blocker).

## Same-day intraday confirmation trigger — a real fix for the "same-close entry bias" gap (2026-09-04)

Motivated by a live case: SOLARINDS fired a real breakout_cont pattern on 2026-09-03, but the user's `--live` scan only caught it near noon, well after the move (10:00-10:45 AM per a Twitter trader's sourced timeline) had already happened. This reopened FINDINGS' own top-ranked unresolved gap ("same-close entry bias" — the backtest enters at the signal day's own Close, but real-world discovery only happens after that close).

**Two ideas tested, one rejected, one adopted:**

1. **"Day-before" precursor score** (critic's `v29`/"Tomorrow Candidates" proposal, response-8.pdf): score primed candidates the night before on VCP tightness/volume-dryness/52wk-high-distance/etc. and predict which will break out *tomorrow*. Tested properly against history (not the critic's untested point-weights): built a 9-feature discrimination test (range compression, EMA8 distance, ATR-trend stability, narrowing-range inversion, volume-dryness ratio, distance-to-52wk-high, distance-to-actual-resistance, sector RS, RSI) comparing the day before 767 real historical breakout_cont fires against a matched "primed but nothing happened" control (n=795). Result: even the best composite score (range-compression + EMA8-distance + ATR-trend + narrowing-range) only lifts the 3-day fire rate from a 7.2% baseline to 10.5% at the top-5% tail — a real but weak ~1.4-1.5x tilt, not a usable entry trigger. **Rejected as an entry mechanism**, kept only as a watchlist-ranking aid (see below). Two features the critic weighted heaviest (volume-dryness, 52wk-high-distance) showed ~zero discrimination in our own data — sector RS, which mattered a lot for VCP trade *quality* elsewhere in this project, also showed zero discrimination for *timing* here — predicting trade quality and predicting fire-timing are different questions.

2. **Same-day intraday confirmation trigger, price margin over resistance**: instead of predicting the day before, test what *same-day* intraday signal reliably predicts the Close will hold above resistance. Checked hold-into-close rate by how far the day's High cleared `high10_prior` (n=2,158 checklist-qualified High-crosses): 0-0.5% clearance → only 27.7% hold; 0.5-1% → 80.6%; **1-2% → 97.7%; 2-3% → 98.7%; 3-5%+ → 99.8-100%**. Volume magnitude beyond the existing `vol_zscore>=1.5` gate showed no further discrimination (95-96% hold rate flat across 1.5-8+ z-score buckets). **Adopted: a same-day order/alert at `high10_prior * 1.01`** ("clear resistance by 1%") as a real, sharp, backtestable confirmation signal — a fundamentally different and much stronger result than the day-before score.

**Full validation of the +1% trigger (all corrected for a real methodology bug found mid-analysis — see below):**
- Coverage: 679 of 767 real historical breakout_cont trades (88.5%) would have triggered the order; the 88 that wouldn't (11.5%) are cases where the whole day traded in a tight band and closed just above resistance without ever spiking a full 1% — a different dimension (intraday range) than "did Close eventually confirm," not a contradiction.
- Full trade re-simulation (entry price, stop-engagement, exit — not just re-pricing the same exit) on the 679 triggered trades: **win 69.8% → 66.9% (old), median +4.01% → +3.17% (old), concentration 11.6% → 17.7% (old)** — better on every dimension, not just price. 96% of triggers happen via a smooth intraday climb (safe for an automated GTT/stop-buy order); only 4% via an opening gap (real slippage risk, priced at the actual Open in the simulation, not the theoretical trigger).
- **Bug found and fixed mid-analysis**: an initial "blind trigger, including false starts" pool showed n=1,878 with 1,199 "false starts" — wildly larger than expected. Root cause: `trades_v28.csv`'s single-position-per-ticker backtest silently skips recording a new Close-confirmed signal if that ticker already has an open trade — 1,182 of the 1,199 were actually genuine, Close-confirmed signals, just never recorded as separate trades, not false starts at all. Only 17 were genuine fades (Close never held above resistance). Corrected full pool (679 real + 17 genuine fades, n=696): **win 69.4%, median +3.97%, concentration 11.6%** — barely moved from the 679-only number, confirming the false-start cost is real but tiny at scale.
- Tested "cut immediately at EOD if the day doesn't confirm" as a risk-management alternative for the 17 fades: **worse on both mean and median** (100% loss rate, median -1.34%, vs. holding forward with the normal trailing stop: 9/17 real wins, median +2.03%, mean +0.32%). Don't add a same-day-cut rule — the existing trailing-stop discipline already handles this better than an intuitive "cut the failure" impulse would.
- Day-by-day price trajectory from the trigger price (n=696): cumulative median +1.20% (day 0) → +1.78% (day+1) → +1.62% (day+2) → +1.88% (day+3), % positive declining 83.5%→68.4%. **No cooldown/sell-off the day after** — the incremental move day+1-vs-day0 is still slightly positive (median +0.16pp, 53.9% positive); days +2/+3 are genuine coin-flips (~49% positive, near-zero median), i.e. the move stalls sideways rather than reversing.
- Base rate: of 55,001 historical "primed" ticker-days, only **17.29%** see the day's High actually reach the +1% trigger — a live watchlist name has roughly a 1-in-6 daily chance of firing, and of those that do fire, **76.9%** go on to clear a *second* 1% (2%+ total) the same day, i.e. the trigger is rarely a bare graze.

**Options behavior over this same window — real premiums pulled, not theta reasoning:**
- ATM calls: median return is flat-to-negative at literally every holding length from day+1 through day+8 (0.00% at 6 of 8 days, -1.40% in one 3-day-window cut, all with persistent 62-71% top-10 concentration) — the mean climbs steadily (5.6%→15.5%) purely because a small set of jackpot trades gets bigger with more time, not because the typical trade improves. **ATM has no repeatable multi-day edge on this signal.**
- ITM calls: meaningfully better for multi-day holds — median turns positive from day+3 onward (+1.02% → +2.44% by day+8), concentration steadily improves (58%→48%), matching the project's general "ITM tracks the underlying more directly" finding from the swing-options backtest.
- The full breakout DAY itself (yesterday's premium close → breakout day's premium close, i.e. the biggest single-day move in the whole trade): ATM median +79.58% (mean +104.71%, 99% positive, 13.0% concentration), ITM median +55.02% (mean +67.06%, 98.8% positive, **8.9%** concentration — even cleaner). This is the one clearly great options number in the whole investigation, but it requires knowing *before market open* which stock will break out that day — exactly the day-before-prediction problem already rejected above as too weak (~10% hit rate) to act on. Not achievable in practice with current tools.
- **Practical conclusion for options on this signal: same-day exit only.** ATM or ITM both work reasonably for a same-day capture; holding an ATM position into the flat day+2/day+3 period is a clear mistake (confirmed with real premiums, not assumed); ITM is the only one of the two with a defensible multi-day hold if one is wanted.
- Genuinely unresolved: whether "buy after the intraday +1% spike is already confirmed, sell same day" (the realistic version of the trade) captures a meaningful fraction of the +79.58%/+55.02% full-day number — the options bhavcopy has no intraday ticks, only daily O/H/L/C, so this can't be precisely isolated from historical data. Needs either real intraday broker option quotes or forward paper-testing to answer properly.

**Live watchlist mechanics, tested same-day (2026-09-04) against the actual current 52-name primed list**: the original 4-feature composite score (range compression, EMA8 distance, ATR-trend, narrowing-range) ranks pure setup *quality* with no regard for how far a stock currently sits below resistance — real case caught by direct user question: NAUKRI and NEULANDLAB both ranked top-5 on quality while sitting 4.3-4.5% below their own resistance, meaning a top-5 list built on quality alone can surface names that are unlikely to actually fire that specific day. **Fixed: added `dist_to_resistance` (Close/high10_prior) as a 5th equally-weighted component** — re-ranks toward names that are both good-quality AND close to actually triggering today (GLAND, 0.76% below resistance, correctly moved to #1). This is a feasibility fix, not a predictive-power fix (dist_to_resistance itself showed only a weak day-before discrimination gap in the precursor test) — it answers "will this be reachable today," a different question from "is this a good setup."

**Not yet built**: the actual daily pipeline (computing today's `high10_prior*1.01` trigger prices for the shrunk watchlist and placing them as broker GTT/stop-buy orders) — validated in full, ready to build whenever the user wants it.

## Outside critique on the +1% trigger (response-9.pdf, 2026-09-04) — confirmations + genuinely new ideas, not yet actioned

Rated the whole pivot 9.7/10 confidence ("you changed the problem from 'find tomorrow's breakout' to 'execute today's breakout early' — that's the right problem"). Independently re-derived the distance-to-resistance watchlist fix before seeing we'd already shipped it. Reacted to the actual 2026-09-04 watchlist output and agreed with our own ranking (GLAND best, NAUKRI correctly flagged too far).

**New ideas raised, NONE built yet — logging so they aren't lost:**

1. **Study the 17 genuine fades as their own dataset** — build a per-trade case file (chart, volume, sector, news, gap, ATR) to find *why* each failed (earnings? gap-fade? long upper wick? market reversal?) rather than treating them as unexplained noise.
2. **Volatility-scaled trigger instead of a flat 1%**: `Trigger = Resistance + max(0.6%, 0.35 × ATR%)` — reasoning: a flat 1% is a bigger ask for a low-ATR stock than a high-ATR one. Explicitly flagged as untested by the critic too ("test this, don't ship blindly") — **we have not tested this against the flat 1% rule at all.**
3. **Bounded-interval technique for estimating intraday option entries from EOD-only data**: since the exact intraday path isn't knowable from daily bars, compute three entry-price scenarios — optimistic (day's Low after the trigger), pessimistic (day's High after the trigger), mid ((Open+Close)/2) — and report a return *interval*, not a point estimate. Directly answers the "can we estimate buy-after-trigger-sell-EOD from EOD data" question we'd flagged as unanswerable — this is a real, usable technique, not yet applied to our own options data.
4. **Standing benchmark metrics proposed for this pipeline**: Recall@5 of tomorrow's actual top-10 movers (ex->5% news gap-ups) appearing in yesterday's candidate list, target 30-40%; Trigger precision >65%; Trade win rate after trigger ~69% (already met). Companion experiment: **"Missed Breakout Audit"** — check every day's top gainers against the prior day's candidate list across ~200 trading days, to see whether SOLARINDS-style misses are systematic or a one-off. Not built.
5. **Don't automate broker GTT/IOC placement yet** — validated trigger price, stop, and exit, but NOT live execution around the trigger itself. Recommends manually paper-trading the exact IOC workflow for 20-30 real triggers first, logging: trigger price, actual first trade above trigger, worst fill in the next minute, Close — to get a real slippage/fill-rate distribution before automating. Proposed metric: **fill rate = IOC filled / trigger actually hit**, target 90%+; if only 60-70%, consider a small buffer (trigger + 0.1%) but only after measuring, not before.
6. **Limit IOC vs. stop-market/stop-limit, independently confirmed by the critic**: IOC caps slippage at zero (fill at/better than the limit, or no fill) — the real risk becomes missed fills via a gap-through, not slippage. Ranked: Limit IOC (best) > stop-limit with a small buffer (+0.2%) > stop-market (worst, can overpay badly during fast breakouts). Proposed experiment: measure the historical "gap-through rate" (of triggered days, how often did the day's Low after the breakout stay entirely above the trigger, meaning an IOC resting at the trigger would never have filled) — not yet run precisely; we can only approximate it with the 4.0% opening-gap figure from daily bars, the more precise intraday-jump version needs 5m data we only have for the last ~3 months (June 2026 onward), too short a window against the 265-ticker/multi-year trades_v28.csv universe to get a meaningful sample (confirmed: a first attempt returned n=1, useless).
7. **On "should I capture just the intraday +1% instead of holding for days" — critic's verdict: NO, don't fold this into the main v29 strategy.** The edge was discovered on multi-day holds; our own day-by-day finding (cumulative median keeps rising through day+1 before flattening) means capturing only the first 1% leaves real edge on the table. If tested at all, treat as a fully separate, secondary strategy: IOC entry at trigger, **+1% target**, but a *tighter* stop than 1% (recommends 0.5-0.6% below entry, not below the trigger), giving ~1.7-2:1 reward:risk. Proposes testing only 3 SL values (0.4%/0.5%/0.6%) on the existing 696-trade dataset, measuring win rate/median/how often target is hit before the SL — called "very high priority," more valuable than testing many stop values. **Not tested at all yet.**
8. **Capital allocation suggestion**: 90% of risk capital to the main v29 swing strategy (hold with trailing stop), 10% (paper-trading only) to the intraday +1%-target variant for a month before real money. Don't replace the swing system until the intraday variant proves itself on both backtest AND live paper trades.
9. **ATM/ITM/expiry mental model** the critic converged on independently, matching our own data: intraday breakout → ATM (behaves like a lottery ticket / same-day convexity); 2-8 day swing breakout → ITM next-month (behaves like a leveraged stock); current-month swing → don't use options at all.

## Options side

**Options-specific time stop AND premium stop — both tested, both REJECTED at every
threshold tried (2026-09-02).** A review note suggested a stock stop isn't an option
risk stop, and floated two candidate options-native exits: a time stop ("exit if the
stock hasn't moved in favor within 3-5 sessions") and a premium stop (-35% to -50%
premium loss). Both tested properly against the full ITM+next set (n=562), not just
reasoned about.

Time stop (checked at N=3/5 sessions, threshold = stock move needed to avoid
triggering):

| N | threshold | triggered | win% | median pnl |
|---|---|---|---|---|
| — | current (no rule) | — | 61.6% | +18.63% |
| 3 | any non-positive move | 45.4% | 46.8% | -2.97% |
| 3 | down >3% | 11.4% | 58.4% | +14.40% |
| 5 | any non-positive move | 41.8% | 48.8% | -1.99% |
| 5 | down >3% | 14.9% | 57.5% | +13.58% |

Cross-checked across all 4 contract-selection variants (ATM/ITM x current/next), not
just ITM+next — same shape everywhere, including the theta-sensitive front-month/ATM
config with the least time to recover, so this isn't an ITM+next-specific artifact.

Premium stop (option's own price dropping X% from entry, checked day-by-day, only on
real liquid trading days):

| threshold | triggered | win% | median pnl | concentration |
|---|---|---|---|---|
| current (no stop) | — | 61.6% | +18.63% | 32.6% |
| -30% | 42.5% | 50.2% | +0.86% | 41.6% |
| -35% | 38.8% | 52.0% | +3.73% | 40.7% |
| -40% | 35.1% | 54.4% | +10.34% | 38.8% |
| -50% | 28.3% | 58.0% | +15.29% | 33.7% |

Same shape as the time stop: damage shrinks as the threshold loosens but never
crosses into a real improvement, even at -50% (the loosest end of the review's own
suggested range). Same underlying mechanism both times — this strategy's real edge
lives in a small number of huge convex option winners, and those winners routinely
draw down 30-50%+ before recovering; any early cut based on temporary weakness (stock
move or option premium) removes exactly the trades that make the whole thing
profitable. **Conclusion: neither mechanism works at any threshold tested — this
options layer doesn't currently have (and these two review-suggested ideas don't
provide) a working independent risk-management overlay separate from the stock's own
exit.** A real, validated negative result, not an unexplored gap anymore.

**Robustness check on the above (2026-09-02): does the premium/time-stop rejection
hold up on a liquidity-tightened trade set, or was it resting on thin/unreliable
option prints?** Correctly caught before being left as an open question — the
original test ran on the CURRENT liquidity bar (`liquid()`: OI>0 and volume>0 only),
so it was worth checking whether stricter liquidity criteria (tested next) would
change the underlying trade set enough to flip the conclusion. It doesn't: re-ran
premium-stop on the liquidity-tightened set (min 25 lots traded, min ₹1L turnover, no
single-print days, n=444) and the rejection holds up MORE strongly, not less:

| | win% | median pnl | concentration |
|---|---|---|---|
| stricter-liquidity baseline | 57.2% | +13.37% | 62.9% |
| + premium-stop -35% | 46.2% | -19.72% | 88.9% |
| + premium-stop -40% | 48.2% | -8.03% | 85.6% |
| + premium-stop -50% | 52.0% | +3.36% | 72.3% |

**Liquidity criteria tightening itself (item 2) — tested, mixed/inconclusive result,
NOT adopted as designed.** Added `MIN_LOTS_TRADED`/`MIN_PREMIUM_TURNOVER`/
`EXCLUDE_SINGLE_PRINT` to `option_backtest.py`'s `liquid()`, motivated by the same
review note ("some contracts print once and then vanish... OI>0/volume>0 doesn't
prove you could get filled"). Tested on ITM+next:

| preset | n | win% | median pnl | concentration |
|---|---|---|---|---|
| baseline (OI>0, vol>0 only) | 562 | 61.6% | +18.63% | 32.6% |
| moderate (min 10 lots, no single-print) | 497 | 60.6% | +17.35% | 49.3% |
| stricter (min 25 lots, min ₹1L turnover, no single-print) | 444 | 57.2% | +13.37% | 62.9% |

Traced exactly which 118 trades the stricter preset removes (going baseline→stricter)
before trusting the worse numbers: they are NOT disproportionately bad trades — win
61.0%/median +19.09%, actually slightly BETTER than the overall baseline, and include
some of the biggest winners (ICICIGI +300%, PFC +184%, TRENT +160%) alongside some of
the biggest losers (PIIND -100%, TRENT -100%, TORNTPHARM -95%) in roughly equal
measure. So this specific tightening doesn't cleanly separate real/executable trades
from unreliable prints — it acts more like a blunt "prefer generally bigger/more
liquid stocks" filter, and the worse headline concentration/median are mostly a
smaller-sample mechanical effect (same "fewer trades → bigger top-10 share" dynamic
seen elsewhere in this project), not evidence the original numbers were inflated by
fake data. **Not adopted as designed** — these specific thresholds aren't well
targeted; a genuinely useful version would need something that flags stale-looking
individual prints specifically, not just raw daily volume/turnover size. Left
documented (`MIN_LOTS_TRADED`/`MIN_PREMIUM_TURNOVER`/`EXCLUDE_SINGLE_PRINT`, all
default to disabled) for anyone who wants to design a better-targeted version later.

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
- Sector-leadership tracking — DONE (2026-09-01), see the "Sector leadership" entry
  in the "Swing side" section above. Earnings/event-proximity annotation — still not
  built.
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

## Exit-timing / "capital rotation" investigation (2026-09-05) — a real, modest early-exit edge found; several adjacent ideas tested and rejected along the way

Prompted by two live positions (IFCI, GLAND) and a direct question: entries have gotten a lot of attention this session (the +1% trigger), but exits haven't — is there a principled signal for "this stock's run has stalled, lock in the gain and rotate into the next fresh setup" instead of waiting out the full trailing-stop/target cycle? All work below is on the `breakout_cont` pattern, trigger-based entries (n=679, the same population as the +1% trigger validation), not the old close-based entry — an early version of this test was mistakenly built on the close-based entry and had to be redone (see below).

**1. First version (built on close-based entry by mistake, corrected)**: a rule armed once the trade reaches 1R (R = `ATR_TRAIL_MULT`×ATR14 at entry, the same distance the stock's own stop uses), then exits after 2 consecutive days of below-average volume (`vol_zscore<0`) with no fresh high. First build used `trades_v28.csv`'s own recorded (Close-based) entry price — caught and rebuilt on the trigger-based entry price instead, since that's the strategy actually in use. On the corrected trigger-entry population: fires on 51 of 679 trades (7.5%). On just those 51: win rate 94.1%→98.0%, median pnl +9.74%→+8.30%, median holding 27→14 days, **return/day +0.302→+0.570%/day (+89%)**. Options-side check (n=30 matched via ITM+next contracts): win 80.0%→86.7%, median +43.80%→+49.74%, days 26→14, **return/day +1.572→+3.216%/day** — the options leg benefits even more than the stock leg, consistent with theta decay compounding the cost of sitting through a stall.

**2. Maximum Favorable Excursion (MFE) study — chasing the theoretical peak is not a free lunch, and overturns the "quiet volume" assumption**: for all 679 trades, found each trade's actual best-possible (hindsight) exit point. Peak median return is 4.6x the current rule's (+18.84% vs +4.07%), but takes 5.8x as many days (58 vs 10) — **return/day is essentially identical** (+0.432 vs +0.416%/day). So holding longer buys more total return at the same rate of capital efficiency, not a better rate — a real preference trade-off, not a strictly better outcome. **Drawdown check confirms it's a worse ride, though**: median max drawdown along the way to the peak is −9.26pp vs only −4.01pp to the current rule's actual exit — more than double the pain for the same return/day. Separately, **the indicator signature at the peak contradicts the "quiet volume" theory**: mean vol_zscore in the 3 days into the peak is +1.13 (vs −0.12 in a mid-trade control window), and the peak day itself is a fresh high 75.7% of the time with mean vol_zscore +1.72. Most peaks are strong, high-volume, fresh-high days that simply aren't followed by another one — not a slow fade. This is also why the existing `climax` exit (fresh high + heaviest volume of the whole run + weak close) almost never fires (0.0% of exits) — it's designed for a dramatic reversal candle, but most real peaks here are just "a good day that doesn't repeat," with no visible tell in real time.

**3. Re-entry-after-early-exit check**: of the 51 trades exited via the momentum-exhaustion rule, 56.9% (29) get a fresh, valid `detect_entry()` signal on the same ticker within 150 trading days (median 35 days later). But split by whether the re-entry fires before or after the trade's own normal exit would have happened anyway: 62.1% (18/29) are genuinely independent setups the standard backtest would record on its own regardless of the early-exit rule; 37.9% (11/29) fire *before* the normal exit would have — under the standard single-position-per-ticker backtest these are just the *same underlying move* the early exit stepped out of, not a new opportunity (same masking mechanism as the false-start bug found earlier this session). Initial second-trade-quality read looked weak (win 48.3%, median −0.26%, n=29) and was provisionally blamed on a "later-stage base is weaker" theory — **that theory was tested properly at full scale (grouping all 767 trades by per-ticker occurrence number: 1st/2nd/3rd/4th+) and rejected**: win/median do NOT decay with occurrence number (65.3%/2.75% → 62.2%/2.16% → 70.1%/3.18% → 75.8%/3.43%) — 3rd and 4th+ occurrences are if anything better than the 1st. The weak n=29 re-entry number was almost certainly small-sample noise, not a real effect — a repeat signal on a previously-traded ticker should be treated like any other trade.

**4. Exit-signal bake-off — several alternative "give it back" rules tested uniformly on all 679 trades** (not narrow fired-subsets): percentage giveback from peak (3%/5%), ATR-multiple giveback from peak (1x/1.5x), and plain stall (N days with no fresh high, no volume condition) at 3 and 4 days. All fire on only 2-7% of trades (most trades already exit via the existing target/stop/climax mechanism first) and give small, similar improvements (+0.42 to +0.55%/day vs baseline's +0.416%/day). **The volume condition adds nothing measurable** — a plain 3-day stall (no volume check at all) matched or beat the original volume-conditioned version.

**5. Arm-threshold sweep — the real find of this investigation**: the original 1R arming threshold was chosen somewhat arbitrarily and turns out to be well past the optimum. R itself (3xATR14) is a wide distance, so waiting for a full 1R before ever checking for a stall means most trades resolve via the normal exit before the rule gets a chance to fire (only 7.2%). Swept 0.1R-1.0R (plain 3-day-stall, no volume): removing the arming gate entirely is a real regression (fires 76%, win 64.9%, ret/day +0.361%/day — *worse* than doing nothing, cuts good trades before they've developed). But arming at a fraction of R is a clear, broad, smooth improvement — a plateau from ~0.45R to 0.7R all cluster around +0.52 to +0.55%/day (vs +0.475%/day at 1R, +0.416%/day baseline), win rate mid-to-high 70s throughout that plateau (vs 70.5% at 1R). Smooth/broad, not a single spike — good evidence this isn't a lucky single-point overfit. **Re-checked the volume condition across this whole arm range too** (not just the old 1R point): at every arm level from 0.4R to 1.0R, the volume-free version matches or beats the volume-conditioned one and always fires on more trades (volume is a strictly more restrictive filter, so it can only shrink the sample); only 0.3R showed the opposite, likely noise given every other row disagrees.

**Adopted finding**: once a trade reaches ~0.5-0.6R (deliberately mid-plateau, not the single best point, to avoid reading noise as signal), exit after 3 consecutive trading days without a fresh high above the running peak since entry (no volume condition needed) — "3-day stall." Real, modest, broad-based improvement over the current trailing-stop-only exit (+0.544 to +0.548%/day vs baseline +0.416%/day, win rate ~74-75% vs 70.0%), amplified further on the options leg. **Not yet wired into `check_exit()`/production code** — a validated backtest finding, not yet implemented. Caveats: tested on `breakout_cont` only, not `coiled_spring`/VCP; MFE/drawdown study capped at a 90-trading-day horizon (a small number of very long trades could be truncated); this is a genuinely new rule layered on top of the existing exit logic, not a replacement for the resistance-target/stop/climax mechanism, and interacts with the still-open, separately-deferred exit-strategy question (baseline vs. 2R/3R fixed target vs. trail-only, see the "Exit-strategy comparison" section above) — that question is about *where the target sits*, this one is about *cutting a stalled trade early regardless of target*; the two haven't been tested together yet.

**6. Re-checked all 4 options contract-selection variants (ATM/ITM × current/next) under the new stall exit** — real premiums, n≈440-452 per variant, same 679-trade population, comparing the old (trades_v28-style normal exit) vs. the new stall-rule exit for each:

| Variant | Policy | Win | Median | Days | Return/day |
|---|---|---|---|---|---|
| ATM+current | baseline → new | 46.3%→48.7% | −17.17%→**−8.43%** | 13→10 | −1.154→**−0.615%/day** |
| ITM+current | baseline → new | 54.4%→56.0% | +10.52%→**+12.94%** | 13→10 | +0.633→**+0.913%/day** |
| ATM+next | baseline → new | 57.3%→59.4% | +14.84%→+13.91% | 15→13 | +1.131→+1.040%/day |
| ITM+next (standing pick) | baseline → new | 61.6%→62.8% | +20.86%→+18.68% | 16→14 | +1.412→+1.374%/day |

The stall exit is a large, genuine help for the current/front-month variants (ATM+current's loss nearly halves; ITM+current improves on every metric, +44% return/day) but a wash-to-mild-negative for the next-month variants. Mechanism: "next month" was originally adopted specifically to buy runway against theta/expiry risk over a long hold — an early, disciplined exit removes most of that risk on its own, so current-month's main weakness matters much less once you're not holding as long, while next-month's extra runway has less left to protect against.

**Then checked capital cost directly (user pushback: ITM is the costliest contract, and lower-convexity/"slower" per rupee — both correct)**: median lot cost is real and substantial — ATM+current ₹22,906, ITM+current ₹45,257, ATM+next ₹33,600, ITM+next ₹48,825 (ITM runs 1.5-2x ATM's cost at the same expiry). Computing "edge per ₹10k deployed per day" (same formula the round-7 outside critique used pre-session: `median_pnl × win_rate / median_lot_cost`, now divided by median days too) **flips the ranking**: ATM+next is the most capital-efficient (+0.0019/₹10k/day) — not ITM+next (+0.0017), despite ITM+next's better raw win rate/median. This reconfirms (rather than contradicts) the round-7 finding that ATM-next was ~9% more capital-efficient per rupee than ITM-next — the new stall exit didn't change that underlying ranking, it just makes the case sharper now that holding periods are shorter (ATM's extra convexity/leverage per rupee is wasted on a long patient hold, but is exactly the right tool for a quick capture-and-rotate strategy; ITM's steadier 1:1 tracking is the reverse trade-off). **Practical read: ITM+next remains the pick for steadier, more reliable per-trade quality; ATM+next is the better pick if the actual goal is capital-rotation efficiency** — not yet reconciled into a single standing recommendation, a real either/or depending on which objective governs.

## Intraday +1%-target secondary strategy (response-9.pdf item 7) — tested and REJECTED, daily-bar backtest was dangerously overoptimistic (2026-09-05)

Critic's own top-priority idea: instead of holding for days, IOC entry at the trigger, fixed +1% target, tight stop (0.4%/0.5%/0.6% below entry, not below the trigger). First pass on the 679-trade population using daily bars (day-0 resolved via Close only, to avoid counting a pre-entry Low as a post-entry stop-out; day+1 onward via full daily High/Low) looked very strong: win 72.6-89.1% depending on stop width and how same-day ambiguous cases (target and stop both touched, unresolvable from daily bars) are broken — median resolution 1 day, matching the already-known base rate that 76.9% of trigger days clear a second 1% same day.

**That daily-bar number was wrong, and dangerously optimistic — checked against real 5-min intraday data before trusting it.** `trades_v28.csv` predates the intraday cache entirely (last entry 2026-02-11, matching the known regime drought), so scanned the full 500-ticker universe's real daily data for genuine trigger-fire events in the intraday-cache window (2026-06-10 to 2026-09-04, regime gate ignored since it's irrelevant to whether the pattern itself fires) — 289 real events. Resolved each one using actual 5-min bars from the moment of trigger-crossing onward:

| SL | R:R | Real 5-min win rate | Daily-bar approximation had said |
|---|---|---|---|
| 0.4% | 2.5:1 | 17.3-31.1% (bounded) | 72.6-88.1% |
| 0.5% | 2.0:1 | 26.0-37.7% (bounded) | 74.7-88.7% |
| 0.6% | 1.67:1 | 31.5-42.2% (bounded) | 76.4-89.1% |

**Root cause of the gap, confirmed directly**: 178 of 180 stop-hits at SL=0.5% (98.9%) happen on the *same day* as entry, not later. The daily-bar test's day-0-via-Close-only rule (a deliberate choice to avoid counting pre-entry lows) also blinded it to genuine, ordinary same-day chop — the stock routinely dips 0.4-0.6% from the trigger-entry point sometime that day, often recovering later and closing fine, but a real stop order that tight would already have been triggered and taken you out before any recovery. A tight stop this size doesn't survive normal post-breakout retest noise.

**Corrected per-trade expectancy (% terms), full bounded interval**: SL=0.4% −0.158% (pessimistic) to +0.036% (optimistic); SL=0.5% −0.111% to +0.066%; SL=0.6% −0.096% to +0.075%. Every stop width is a coin-flip-to-negative strategy at real resolution, not the clean edge the daily-bar test showed.

**Verdict: REJECTED as specified.** The critic's underlying idea (capture the same-day spike instead of holding for days) isn't necessarily dead, but 0.4-0.6% is too tight to survive ordinary intraday chop — any real version would need either a much wider stop or genuine forward paper-testing, not a daily-bar backtest, which is exactly the caution the critic themselves flagged ("test this, don't ship blindly") and turned out to be justified. **Standing methodology lesson, worth remembering broadly**: a same-day, tight-stop strategy cannot be honestly backtested on daily bars alone — day-0 resolution is structurally blind to intraday path, and any test that quietly resolves day-0 via Close (to dodge the pre-entry-contamination problem) will systematically overstate win rate for exactly this kind of strategy. Real 5-min data, even a short and unrelated-population window, is worth checking before trusting a tight-stop daily-bar result.

## Entry-clearance re-optimization — ADOPTED: 0.5% (was 1.0%) (2026-09-05)

Follow-up question prompted directly by the pullback/liquidity-cluster discussion above: is the original flat 1% clearance actually the right number, or was it chosen for a narrower reason than what matters for the full trade? Swept clearance 0.0%-2.0% on the full 7,209-row primed universe, full trade re-simulation (entry at trigger/Open-on-gap, normal `check_exit` management), plus the stall-exit overlay from earlier in this session:

| Clearance | n | Stop-rate | Stall-rate | Normal win/median | Fast win/median | Fast return/day |
|---|---|---|---|---|---|---|
| 0.0% | 5,465 | 42.2% | 16.5% | 61.8%/+2.54% | 65.8%/+3.00% | +0.346%/day |
| 0.3% | 5,196 | 42.3% | 16.2% | 61.4%/+2.45% | 65.5%/+2.88% | +0.331%/day |
| **0.5%** | 4,993 | 42.6% | 16.1% | 60.9%/+2.40% | 65.0%/+2.83% | +0.321%/day |
| 1.0% (previous) | 4,392 | 43.3% | 16.0% | 60.0%/+2.23% | 63.8%/+2.74% | +0.302%/day |
| 1.5% | 3,806 | 44.0% | 15.8% | 58.4%/+2.01% | 62.2%/+2.64% | +0.269%/day |
| 2.0% | 3,231 | 43.5% | 15.7% | 58.4%/+2.16% | 61.9%/+2.75% | +0.272%/day |

**Reconciled against the ORIGINAL clearance-bucket finding that motivated 1% in the first place** (0-0.5% clearance → only 27.7% hold-into-close) — that finding is real but answers a narrower question (does *that specific day's* close hold above the level), not whether the *full, multi-week-managed trade* eventually works. The reason full-trade stop-rate stays flat (42.2%-44.0%) across the whole 0-2% range: the exit stop is `peak_close − 3×ATR14`, an absolute distance from the stock's own volatility, median ≈9% initially (real distribution checked: 25th pct 7.26%, 75th pct 11.58%) — this is 5-10x wider than the entire 0-2% clearance range under test, so within that range the stop simply never differentiates between a 0% and a 2% entry. It only tightens to the 21-EMA once a trade is up 3% (`TRAIL_ENGAGE_PCT`); realized median loss on real stop-outs is only −5.96% (checked directly on the 276 real stop-exits in `trades_v28.csv`), well under the ~9% initial worst case, though the tail is real (10th percentile −11.1%). **General rule found here, worth keeping**: entry-clearance buffer only matters for reliability when the stop is comparably tight to the buffer (exactly why the 0.4-0.6% intraday-target test above failed) — with a wide stop already in place, the buffer mostly just sets your cost basis, not your odds.

**Also checked and rejected**: the stall-exit rate does NOT meaningfully change with clearance either (15.7%-16.5%, noise-level) — whether a trade stalls is driven by what happens after entry, not by how much clearance was demanded before it. A hypothesis that a tighter (lower-clearance) entry would land you in a "consolidate just above resistance" zone more often was tested directly and found no support.

**One real, non-backtested reason not to go all the way to the 0% floor**: buying exactly at resistance means resting an order in the densest part of the liquidity cluster other breakout traders' stop/buy orders also sit at — the most likely spot for a brief liquidity-driven overshoot-and-reverse before it's clear whether the move is real (this is the same underlying mechanism as the pullback-to-resistance finding, and the same reason the tight-stop test failed). A small buffer (0.3-0.5%) buys just past that initial cluster while still capturing nearly all of the measured gain (0% vs 0.5% differs by only ~0.025%/day of the ~0.044%/day total gain over the old 1% number).

**ADOPTED: move the live entry-clearance trigger from 1.0% to somewhere in 0.3-0.6%** (`trigger = high10_prior * 1.005`, was `* 1.01`) — **but 0.5% itself is NOT a data-derived optimum, worth stating plainly rather than dressing up as one.** The four candidates in this range are statistically indistinguishable: 0.3% n=5196/fast median+2.88%/ret+0.331%/day; 0.4% n=5097/+2.84%/+0.325%/day; 0.5% n=4993/+2.83%/+0.321%/day; 0.6% n=4881/+2.84%/+0.323%/day — 0.3% is if anything the marginally best of the four on this exact metric, not 0.5%. 0.5% was picked as a clean round number sitting comfortably off the 0% floor, not because the data pointed there specifically. **Not yet wired into `tomorrow_candidates.py`/`daily_scan.py`** — per standing instruction, holding all of today's changes (stall-exit, this threshold change, the ATM/next capital-efficiency read) for outside critical review before touching production code, and this specific pick-within-a-flat-plateau question is now explicitly one of the things being asked of the critic (is there a principled reason to prefer one exact value here, or is the honest answer "anywhere in 0.3-0.6% is equally defensible, stop pretending to more precision than the data supports").

**Explicit overfitting caveat, worth being honest about rather than burying**: today's session tested a lot of adjacent parameters on overlapping populations in sequence — stall-exit arm threshold (0.1R-1.0R), stall-days (3 vs 4), entry-clearance (0.0%-2.0%), tight-stop widths (0.4/0.5/0.6%), all against variations of the same ~7,000-row primed universe. Each individual result showed a broad, smooth plateau rather than a sharp single-point spike (real evidence against overfitting *within* each test), and the daily-bar-vs-real-5-min-data check for the intraday-target idea shows this session is willing to reject its own optimistic results under scrutiny, not just confirm them. But the sheer number of knobs turned in one sitting, several against the same underlying data, is a legitimate multiple-comparisons concern that deserves a genuinely critical (not confirmatory) outside read before any of it goes live — explicitly what's being requested from the next critic round.

## Closing out three more response-9 items (2026-09-05)

**Item 1, 17 genuine fades case-file study — done, but on an honestly-rescoped population.** The exact original 17 came from a narrower population that can't be reproduced (the scratch script that found them wasn't saved, and even restricting to `trades_v28`'s own exact ticker/date range still gives 591, not 17 — some additional filter is lost). Ran the archetype analysis on this 591-fade set instead (same universe/date range as the real backtest, so still an honest comparison, just broader than the original count). Real archetypes found: **51.4% show a "weak close"** (bottom 30% of the day's range) — the classic rejection/long-upper-wick pattern; **33.0% show climax-like volume** (vol_zscore>4, an "effort vs. result" divergence, same Wyckoff pattern the exit-timing research found independently on the exit side); **21.0% gapped up >2% at the open** (already-extended before the session even started). Genuinely encouraging: **50.6% recover within 3 days anyway** — about half of what looks like a same-day "fade" is a delayed confirmation, not a lasting failure. Could not check earnings/news proximity — no data source for that in this project. Note: the 591 is itself a small slice (~13.5%) of the roughly 4,392 total trigger-fires at the 1% clearance level — this is a within-failure-population breakdown, not an overall failure rate; don't read "51.4%" as "half of all trades fail."

**Item 3 (critic's numbering), bounded-interval option-entry estimate — done, and better than proposed, since the option bhavcopy has real OHLC (Open/High/Low/Close), not just Close.** Applied directly to the option's own day range rather than approximating from the stock's. On the 679-trade trigger-fired population (ITM/ATM+next, n=442 matched each): pessimistic (bought at day's High) is a trivial ≤0% floor by construction (Close can never exceed High) — not a real finding, just definitional. The informative numbers: **mid ((Open+Close)/2) — ATM 79.9% win/+10.21% median; ITM 74.4% win/+9.65% median.** This directly answers the previously-flagged-unanswerable question ("does buy-after-confirmed-spike-sell-EOD capture a meaningful fraction of the +79.58%/+55.02% full-day number") — yes, a real and solid same-day trade, but only **~13% (ATM) to ~18% (ITM)** of the full-day figure, since the full-day number requires impossible before-open foresight. Practical caveat surfaced by the user: this can't be operationalized as a pre-set IOC the way the stock trigger is — option premium isn't a static formula from yesterday's data, so this requires actually watching the live quote at execution time, not a queue-and-forget order. Connects to the still-not-built delta/IV-backout item (see priority queue) as a partial (not complete) fix — scoped at ~1-2 hours for a rough realized-vol-proxy version, ~half-day to a day for a proper IV-backed-out version — explicitly deferred, not started.

**Item 4 (critic's numbering), benchmark metrics / Missed Breakout Audit — done, real and somewhat sobering result.** Retroactively re-ran the actual watchlist scoring logic (no lookahead) across 150 historical trading days (2026-01-30 to 2026-09-03) and checked the next day's real >5% movers against each day's top-5. **Recall@5 = 9.6%**, well below the critic's 30-40% target (only 14 of 146 mover-days had that mover in the top-5). **But coverage is much better: 68.5% of the time the mover was somewhere in the broader candidate pool, just not top-5-ranked.** So detection is reasonably good; ranking specifically is what fails. **This is systematic, not a one-off SOLARINDS fluke — and it's not a new problem, it's the same conclusion the day-before predictive-score investigation already reached** (best composite score only lifted 3-day fire rate 7.2%→10.5%) via a cleaner, more direct methodology. Trigger precision (the third proposed metric) is already satisfied by the existing validated win rate (69.4% > the 65% target) — no new work needed there.

## Item 5 (exit-target × stall interaction) and the stall/expiry-choice synthesis (2026-09-05)

**Exit-target × stall interaction, tested directly** (trigger-based entry, breakout_cont, n=679): baseline (moving resistance) + stall is the best combination found (75.4% win/+4.02% median/7d/+0.538%/day), clearly ahead of 2R/3R/trail-only + stall (all converge to identical numbers, 70.5%/+3.71%/10-11d/+0.338%/day, since the stall usually fires before a 2R/3R/no-target trade ever gets the chance to reach those much wider levels). **This is a different population from the 2026-09-03 exit-strategy comparison** (that one used close-based entry across both patterns; this one uses trigger-based entry, breakout_cont only) — the two tables aren't contradictory, they're measuring different things, but this result does newly inform (not settle in general) the previously-parked baseline-vs-2R/3R question for this specific population: widening the target and adding the stall-exit are in tension, not complementary, since the stall already does the job a wider target was trying to do.

**Real-money portfolio check (not just per-trade averages) — the stall-exit's benefit is conditional on capital scarcity, a real correction to the earlier crude percentage-sum version of this test.** Built a proper cash-only, compounding, ₹1,000-max-risk-per-trade simulation (the earlier attempt just summed raw % returns with no rupee sizing or compounding — a crude proxy, corrected here) across the same 679 real historical signals, chronological order:

| Starting capital | Baseline-only return | Baseline+stall return |
|---|---|---|
| ₹1,00,000 | +168.04% | **+175.27%** (stall wins) |
| ₹2,00,000 | **+122.58%** | +116.72% (stall loses) |
| ₹5,00,000 (no cash constraint at all) | **+55.34%** | +50.45% (stall loses) |

Stall only wins when genuinely capital-constrained (₹1L, where baseline-only skips 223 of 667 signals for lack of cash). At ₹2L and ₹5L it loses despite taking the same or more trades, because **it reduces the mean return per trade** (+4.06%→+3.79% from the earlier full-economics table) even though median and win rate both improve — it clips the right-tail winners that drive compounded growth, the same mechanism the MFE study already flagged. **Caveat on this simulation, raised directly by the user and worth keeping**: the scheduler is pure first-come-first-served by date with no quality selection — captured vs. skipped trades are not "good vs. bad," just whichever happened to be next in the timing queue, so this shows an expectation-level mechanism, not a guaranteed real-world outcome, and doesn't model a real trader's active judgment about which signal to prioritize when capital is tight (which should make the real-world case better than simulated here, not worse, though unquantified).

**Standing decision, given the above and the user's own capital situation: no stall on the stock/swing leg (keep baseline moving-resistance, let it run) — stall on the options leg specifically.**

**Re-checked whether front-month + stall could now beat next-month + stall for the options leg, given stall shortens holds — no, next-month still wins on both raw return and capital-efficiency-per-rupee**, even with stall applied to both:

| Variant (with stall) | Win | Median | Return/day | Edge per ₹10k/day |
|---|---|---|---|---|
| ATM+current | 48.7% | −8.43% | −0.615%/day | −0.0018 |
| ITM+current | 56.0% | +12.94% | +0.913%/day | +0.0016 |
| **ATM+next** | 59.4% | +13.91% | +1.040%/day | **+0.0019** |
| **ITM+next** | **62.8%** | **+18.68%** | **+1.374%/day** | +0.0017 |

Reason: theta decay is a per-day *rate* that accelerates near expiry, not just a function of total days held — a front-month contract bleeds faster per day even over a shortened stall-exit window, so cutting the hold short doesn't close the structural gap.

**But the user then raised a real, separate point (already partially in the ATM/ITM/expiry mental model from response-9, item 9) — next-month should respond more sluggishly to a same-day spike specifically (lower gamma, more time value) — checked directly, and it's a large, confirmed effect, not a marginal one:**

| | Same-day mid-capture win | Median |
|---|---|---|
| ATM+current | 98.3% | **+27.44%** |
| ATM+next | 79.9% | +10.21% |
| ITM+current | 96.3% | **+20.91%** |
| ITM+next | 74.4% | +9.65% |

Current-month captures the same-day spike roughly 2-2.7x better than next-month on both win rate and median. **Resolution: expiry choice depends on intended holding period, not one universal answer** — current-month for the same-day capture trade (item 2/3 above), next-month for the multi-day stall-managed swing. This is a fresh, concrete confirmation of the response-9 mental model (intraday → ATM/current, multi-day swing → ITM/next), not a new finding in tension with it.

## Response-10 outside critique (2026-09-05) — four items actioned same session

Full critique read in full (28-page chat export). Overall verdict 9.3/10, ship the 0.3-0.6% trigger band and ATM-current/ITM-next split, keep the 3-day stall as a hypothesis (not adopted), reject any capital-level portfolio conclusion at face value. Four of their specific asks tested directly:

**1. Trailing-stop/EMA intraday mirror-bug audit (their "highest-quality result... asks whether this blind spot exists elsewhere").** The Chandelier/21-EMA trailing stop is evaluated on daily Close — a live stop order would trigger on an intraday Low even if price recovers by close, the mirror image of the original intraday-target bug. Checked directly on the 289 real trigger-fire events (June-Sept 2026 intraday window): of 2,947 "held per daily-close backtest" trade-days, **110 (3.7%) had a real intraday Low that breached the stop level** — real, but well under the critic's 5-10% guess. Full-trade impact: **37.4% of trades (108/289) are affected on at least one day**; aggregate win rate 58.5%→56.4%, median +1.21%→+0.86%, mean +1.21%→+1.09% once corrected to a live-stop rule. Important nuance: the 108 affected trades were already net losers on average even under the generous backtest treatment (median −3.72%) — this mostly catches already-bad trades a little earlier and a little worse, not converting winners into losers. Confirmed real, modest impact — nowhere near the scale of the original intraday-stop-loss bug, but a genuine correction worth carrying forward.

**2. DTE × stall heatmap (critic's single highest-priority ask, hypothesis: stall benefit should increase smoothly as DTE shrinks toward expiry).** Tested on ITM+current, n=300 option-matched trades, bucketed by DTE at entry:

| DTE bucket | n | Baseline median | Stall median | Benefit (pp) |
|---|---|---|---|---|
| <10 | 46 | +40.76% | +37.15% | −3.61 |
| 10-15 | 58 | −18.99% | −2.33% | +16.66 |
| 15-20 | 97 | +30.67% | +29.29% | −1.39 |
| 20-25 | 75 | +21.21% | +18.62% | −2.59 |
| 25+ | 24 | +20.86% | +30.40% | +9.54 |

**No monotonic pattern — the hypothesis is NOT supported.** If anything the opposite at the low end (stall *hurts* at <10 DTE, where accelerating theta should have made it help most). The one clearly positive bucket (10-15 DTE) is sandwiched between negative/mixed results either side — no coherent accelerating-toward-expiry shape. Sample sizes per bucket (24-97) are real but modest, so this isn't an airtight rejection, but there's no evidence here to promote stall-for-options from "hypothesis" to "economically-grounded expiry-aware rule."

**3. VCP LAST_LEG_TOLERANCE full sweep re-verification (critic: "why 40%, not 35% or 55% — you stopped because it looked good, that's a danger sign").** Full backtest sweep, 0%-100% in 10% increments, full 500-ticker universe:

| Tolerance | n | Win | Median | Concentration |
|---|---|---|---|---|
| 0% | 551 | 61.9% | +2.89% | 36.8% |
| 10% | 591 | 61.3% | +2.86% | 37.2% |
| 20% | 615 | 61.8% | +2.88% | 37.1% |
| 30% | 644 | 61.5% | +2.84% | 37.6% |
| **40% (adopted)** | 663 | 61.7% | +2.88% | 37.4% |
| 50% | 674 | 61.9% | +2.90% | 37.1% |
| 60% | 683 | 61.9% | +2.90% | 37.0% |
| 70% | 687 | 62.0% | +2.90% | 36.8% |
| 80% | 692 | 62.3% | +2.93% | 36.9% |
| 90% | 697 | 62.7% | +3.00% | 36.6% |
| 100% | 699 | 62.7% | +3.00% | 36.6% |

**No spike at 40% — genuinely flat across the entire range** (win 61.3-62.7%, median +2.84-+3.00%, concentration 36.6-37.6%, all within ~1-1.5pp of each other end to end). Directly answers the critic's concern: this is a real plateau, not an isolated overfit peak. **Honest addendum, same shape as the entry-clearance finding**: the curve drifts mildly, monotonically better toward looser tolerance (90-100%, i.e., no real tightening requirement between the base's contraction legs at all) rather than peaking and declining at 40% — so there's no strong data-driven reason to prefer 40% specifically over something looser either. Worth flagging to the critic rather than claiming 40% is uniquely justified, same honesty standard as the 0.3-0.6% trigger band.

**4. Recall@N curve, extending the Missed Breakout Audit (critic suggested "improve candidate pruning, not ranking score").** Computed Recall@N for N=5/10/15/20/25/30/full-pool on the same 150-day retroactive test:

| N | Recall |
|---|---|
| 5 | 9.6% |
| 10 | 19.9% |
| 15 | 24.0% |
| 20 | 30.1% |
| 25 | 37.0% |
| 30 | 42.5% |
| Full pool (median 73) | 68.5% |

**Recall climbs almost linearly with N, tracking roughly N/pool-size the whole way — the signature of a ranking with close to zero real discriminating power for next-day movement**, not merely "imperfect." This sharpens rather than just confirms the critic's own read. It also means "improve candidate pruning instead of ranking" runs into the same wall: pruning only helps if the pruning criteria have real next-day predictive power, which is exactly what the day-before predictive-score investigation (earlier this session) already tested and found weak (~1.4-1.5x lift at best, rejected). No obvious quick fix here — either accept the candidate list for what it demonstrably does well (feasibility/quality ranking among already-qualifying names, e.g. the GLAND-over-NAUKRI call), or this needs a genuinely different signal (news, options flow, sector rotation), not a harder cut of already-tested-weak features.

## Round-12 exploration and reverse-engineering entry timing — ADOPTED: same-day distance-to-trigger checkpoint, a real, strong finding (2026-09-05)

**Three new-information-source ideas from response-11, tested — two rejected, one modest positive:**
- **Options flow** (`oi_buildup_bullish()`, already-existing but unused futures-OI-based confirmation): tested on 679 trades — OI buildup present shows *worse* outcomes (62.3% win/+4.20% median, n=61) than absent (70.3%/+4.57%, n=219), the opposite of the function's design intent. Also a real coverage gap: 399/679 trades (58.8%) have no futures data at all. **Rejected.**

**Re-checked directly against options P&L specifically (2026-09-06), not just the stock-level result above — the natural follow-up question ("even if it fails as a stock confirmation, could it still help pick options") answered with real data rather than assumed.** Since options P&L is a leveraged/convex function of the same underlying move, it's a genuinely distinct question, not automatically the same conclusion. Computed `oi_buildup_bullish()` directly against the real options P&L for both standing recipes:

| Variant | Buildup present | Buildup absent |
|---|---|---|
| ITM+next-month | win=51.4%, median=+1.30% (n=74) | win=64.1%, median=+21.15% (n=488) |
| ATM+current-month | win=34.6%, median=−71.45% (n=81) | win=48.7%, median=−7.48% (n=491) |

**Even more decisively backwards than the stock-level result** — a ~20pp median gap on ITM+next vs the stock-level ~4pp gap, and a dramatic −71.45% median for ATM+current specifically. Consistent with leverage amplifying whatever weakness the "buildup" signal was quietly flagging on the stock side. Fully closes the door on this idea in any form — not a case of "wrong context," it gets worse, not better, the more leveraged the instrument. `oi_buildup_bullish()` deleted from `option_backtest.py` (2026-09-06) — zero callers anywhere in the codebase, and this finding plus the original stock-level one are both preserved here, so nothing is lost.

**Before trusting the rejection above, checked whether it was a real economic finding or a data artifact (2026-09-06) — a real, serious data issue was found, but the rejection survives it.** Direct challenge: "a backtest can tell you a signal doesn't work because of data issues, not because the signal is actually bad" — worth taking seriously rather than accepting "rejected" at face value.

**The data issue was real**: `oi_buildup_bullish()`'s original code treated ANY missing futures data as `return False` (buildup absent) — no distinction from a genuinely-checked-and-confirmed-absent case. Worse, the re-check's own test code added a blanket `except: b=False` around it, which silently caught real crashes too. Isolated the crash: pre-2024 futures bhavcopy files (from `fetch_stock_options_pre2024.py`'s normalization) carry ONLY options rows (`FinInstrmTp=='STO'`) — no futures OI data columns (`PrvsClsgPric`, `ChngInOpnIntrst`) exist in that schema at all. Checking properly (catching the exact `KeyError`, not swallowing broadly): **342 of 562 ITM+next trades (60.9%) and 339 of 572 ATM+current trades (59.3%)** were silently misclassified as "buildup absent" when the honest answer was "no data available" — almost entirely 2022-2023 dates (79+258 and 83+250 respectively), matching the known pre-2024 coverage gap exactly.

**But separating the contamination out, the original rejection holds up on the clean data**:

| Status | ITM+next win/median | ATM+current win/median |
|---|---|---|
| Confirmed absent (real data, checked) | 60.3% / +18.65% | 50.7% / +7.51% |
| Confirmed present (real data, checked) | **51.4% / +1.30%** | **34.6% / −71.45%** |
| (no-data, previously miscounted as absent) | 65.8% / +22.65% | 47.8% / −9.09% |

Still clearly backwards comparing only clean, real, checked cases — this isn't a data-artifact false rejection. Confirmed further by checking the **raw stock return** on this same clean subset (before any options leverage): mean +1.69%/median +2.76% (confirmed absent) vs mean −0.09%/median +1.44% (confirmed present) — the weakness shows up at the stock level directly, not just amplified by options leverage or an artifact of which era each bucket happens to sample.

**Likely real mechanism, not noise**: futures OI building up alongside a rising price plausibly signals a more crowded, later-stage move — by the time enough participants have visibly piled into futures, the "fresh conviction just arriving" phase the function was designed to detect may already be behind it, closer to exhaustion than confirmation. The opposite of the function's original design assumption, but a coherent, sensible story. One honest residual caveat: confirmed-present trades skew slightly more toward 2024 than confirmed-absent (62% vs 35% of each group respectively) — a small remaining era-mix confound can't be fully ruled out, though it's unlikely to be the whole story given the divergence already appears in the raw, unleveraged stock move.

**Went further, per direct instruction — don't just accept a plausible-sounding replacement story, work out WHY the original logic specifically fails.** The original theory (OI-up + price-up = fresh conviction = should predict continuation; OI-flat + price-up = short covering = weaker) is a real, standard heuristic, not a naive one — but it likely fails here for three specific, checkable reasons, not just "markets are sometimes contrarian":
1. **Wrong market for the heuristic.** The theory is standard practice for INDEX/commodity futures, where OI changes reflect large directional bets by sophisticated participants. Indian single-stock futures are a much thinner, more retail/arbitrage-heavy market — a lot of the OI there comes from cash-futures arbitrage and hedging flows, not directional conviction. The heuristic was built for a different market structure than the one it was applied to.
2. **Redundant, not independent, information.** This project's own stock-level entry signal already requires a volume/momentum spike to fire — that's structurally what a breakout is. If futures OI *also* builds in the same 3-day window, it's mostly re-detecting the same move via a second instrument, not adding independent new information.
3. **The redundancy itself is the problem.** A move loud enough to also attract fresh futures positioning within 3 days is, by construction, no longer quiet or early — it's already drawing outside attention. A crowded, already-attention-grabbing setup has fewer new buyers left to extend it and is more exposed to profit-taking the moment it stalls. The theory assumed "more participants building in = more fuel ahead"; the more likely mechanism is "more participants already in = less fuel left."

**Reframed conclusion**: not "the theory is unsound," but a domain mismatch — a real heuristic, sound in its usual context (index-level conviction-vs-covering), that doesn't transfer to a thin, single-stock, already-signal-confirmed swing setup.
- **Sector rotation** ("sector breaks out before the stock," not the existing backward-looking sector RS): tested both same-day and 3-day cumulative sector momentum against next-day movers across 146 real historical days — 27.1% and 25.3% of movers respectively come from a "hot" (top-quartile) sector, essentially identical to the ~25% pure-chance baseline. **Rejected**, directly contradicting the critic's own PHARMA/AUROPHARMA anecdote.
- **Energy Stall** (`Energy = (ATR3/ATR20) × (Volume3/Volume20)`, exit only on low-ATR+high-volume "distribution"): real, modest positive — win 70.0%→71.4%, median +4.07%→+4.17%, return/day +0.416→+0.455%/day, but fires on only 7.2% of trades (much less often than the calendar-based 3-day stall's 28.6%) since the joint condition is stricter. Untuned first pass — thresholds (ATR ratio<1.0, volume ratio>1.2) not swept.

**First-15-minute momentum ranking — initially looked dramatic (Recall@5=83.0% vs. night-before's 9.6%), but the comparison was circular and the honest version is a clean negative.** The "full-day return ≥5%" target *includes* the first-15-min return as part of it — a stock already up sharply at 9:30 gets counted as both "strong early" and "a mover," which isn't a real prediction. Corrected test: correlation between first-15-min return and the *remaining* day's return (non-overlapping) is −0.007, essentially zero, and swept across every window from 15 to 45 minutes the result stays flat with a small, consistent **mean-reversion** tilt (strongest-start bucket underperforms the weakest-start bucket by ~0.2-0.3pp at every window length). **Rejected**: chasing the biggest early mover in the watchlist doesn't help pick the day's winner, and mildly hurts.

**Reverse-engineered ignition timing instead — a real, strong, actionable pattern.** For 289 real trigger-fire events (June-Sept 2026 intraday window), found the exact 5-min bar each one first crossed its trigger:
- **52.2% of all real fires happen in the first 30 minutes (09:15-09:45)** — a strong front-loaded cluster, not spread evenly through the day. Cumulative miss rate if you can only check once: 31.1% already gone by 09:20, 39.4% by 09:30, 52.2% by 09:45.
- Of the fires within the very first 5-min bar specifically (n=90): only 32.2% are genuine gaps (Open already at/above trigger); **67.8% open below the trigger and cross it within that same first candle** — even the fastest fires mostly build in real trading, not overnight gaps. (Could not get a reliable volume read for this subgroup — the feed's very-first-bar Volume is often 0, a known data quirk, not a real signal.)
- Volume-at-ignition is modest and stable through the morning (~2-2.8x the day's own pace so far) but spikes dramatically in the rare afternoon ignitions (7-21x) — small samples (4-10 events per afternoon bucket), suggestive only.

**The real, validated, actionable finding: rank the still-live candidate pool by same-day distance-to-trigger at a single checkpoint.** Among candidates that haven't fired yet, "how close is the current price to its own trigger" predicts "fires later that day" with a clean, monotonic gradient — and this is NOT circular (distance-at-checkpoint and fires-after-checkpoint are sequential, non-overlapping facts). Tested as bucketed hit rate (checkpoint 09:20/09:30/09:45, closest-20% bucket): 35.2%/32.0%/26.6% vs. a base rate of 11.0%/9.6%/7.9% and a farthest-20% rate of 0.5%/0.3%/0.0%. **Computed as Recall@K to directly compare against the night-before ranking** (checkpoint 10:00, n=59 days with a real available fire):

| Ranking | Recall@1 | Recall@2 | Recall@5 |
|---|---|---|---|
| Night-before quality+dist_to_resistance score (existing) | — | — | 9.6% |
| **Same-day distance-to-trigger at 10:00** | **64.4%** | **76.3%** | **88.1%** |

**Robust to the entry-clearance choice** — re-ran at 0.3%/0.5%/0.6%/1.0% clearance, all give similarly strong results (Recall@1 60.7-68.9%, Recall@2 76.3-83.6%, Recall@5 88.1-96.7%), so this isn't an artifact of the specific trigger level tested first.

**Decomposed why this works, per direct user question ("by 10am the stock might have already moved, isn't that the real signal, not distance"): both the static night-before position and today's real movement carry independent signal, but netting them together (same-day distance) is far sharper than either alone** — bucket hit-rate spread low-to-high: night-before distance alone 0.7%→16.5% (~23x), today's-gain-alone 2.4%→17.1% (~7x), same-day distance (the two netted together) 0.1%→24.6% (~246x). Same-day distance is the sufficient statistic — "how much further is actually left" — not double-counting, just collapsing two partially-informative signals into the one that matters.

**Volume tested as a secondary signal on top of distance — makes it worse, not better.** Blended ranking (70% distance-rank + 30% volume-rank) vs. distance alone, same population (0.5% clearance, 10:00 checkpoint, n=61 days): Recall@1 drops 60.7%→44.3%, Recall@2 drops 77.0%→59.0%. Distance-to-trigger is already close to a direct measure of the outcome itself; blending in a noisier signal only adds noise. **Rejected as a refinement.**

**ADOPTED: built `live_checkpoint.py`** — a real, runnable script (`python3 live_checkpoint.py [HH:MM]`), reusing `daily_scan.py`'s existing `shortlist_primed()`/`fetch_live_bars()` two-pass infrastructure. Splits output into "already triggered" (act now) and "closest to trigger, not yet fired" (ranked, this is the validated list). Uses the 0.3-0.6% clearance band directly (a ticker "fires" at the 0.3% low edge, matching the limit-order-ceiling framing from the entry-clearance work — ceiling at 0.6%, never pay more). Verified end-to-end against live data.

**Practical synthesis for a capital- and attention-constrained workflow (1-2 IOC slots, can't watch continuously)**: don't spend scarce capital on the night-before top pick (9.6% Recall@5, close to a lottery ticket) — accept that the 09:15-checkpoint window is genuinely unwatchable and its ~50%+ of the day's fires are unavoidably missed, then deploy the 1-2 slots at whatever single checkpoint is actually reachable (e.g., 10:00 after a commute), ranked by same-day distance-to-trigger via `live_checkpoint.py`. That is a real, ~6-8x improvement over the night-before pick for the same scarce capital.

## Round-13: critic's three "break this" validation tests (all passed) + Checkpoint Walk-Forward + two follow-up questions (2026-09-05)

**Response-12 asked for the harshest possible read on the same-day distance-to-trigger finding, offering an explicit bar: "if it survives all three, I'd upgrade confidence to 95%." All three tested, all three passed.**

**1. Survivorship/removal conditioning** (critic: the "still watching" pool shrinks all day as names fire — does ranking against a shrinking population bias Recall?). Fix tested: freeze the ranking ONCE at a fixed checkpoint, never remove/re-rank as the day progresses, check Recall against that frozen snapshot for the rest of the day. Result — even STRONGER than the dynamic-removal version: frozen at 09:20 → Recall@1=67.2%, Recall@2=88.5%, Recall@5=98.4%; frozen at 09:25 → 65.6%/80.3%/95.1%; frozen at 09:30 → 65.6%/78.7%/93.4%. All well above the critic's own 95%-confidence bar.

**2. "Distance is secretly momentum, not proximity"** (critic: decompose Distance into Gap + IntradayMove + Residual — does a residual beyond pure momentum still predict firing?). Gap alone (open vs. yesterday's close): flat, ~1.2x spread (8.1%→9.8%) — essentially no signal, the overnight gap carries nothing. IntradayMove alone (open→checkpoint): real, ~5.7x spread (2.8%→16.0%). **Conclusion: the signal is genuine post-open trading activity, not overnight positioning re-labeled as "distance"** — combining starting position with intraday movement (the already-established ~246x combined spread) is a real interaction effect, not a tautological restatement of momentum.

**3. "Base rate changes every minute" (shrinking population inflates raw Recall@K)**: already answered by the existing bucket analysis (closest-20%/farthest-20% hit rates at multiple checkpoints) — that IS the percentile-normalized, population-size-invariant measure the critic was asking for, just computed earlier in the investigation under a different name.

**Checkpoint Walk-Forward simulation, run honestly on the only available data (critic asked for "Jan 2024 onward" — real intraday data only goes back to 2026-06-10, ~62 trading days; ran the full methodology over that entire window rather than faking a longer period with daily-bar approximations, which would repeat the exact mistake already caught once this session).** For every historical day: run yesterday's scanner, freeze the candidate pool, simulate 09:20 prices only, rank by same-day distance-to-trigger, place simulated IOC orders (top-2/day) at the trigger, walk forward with the real exit logic, no lookahead. Result (0.5% clearance, 09:20 freeze): 122 total picks, **fill rate 65.6%** (34.4% never fire and are skipped), **win rate (filled only) 61.3%**, **median return (filled only) +1.07%**, exit reasons {resistance 57.5%, stop 22.5%, open-still 17.5%, stall 2.5%}, false-alert rate (filled then immediately stopped out) 22.5%.

**Honestly weaker than the main backtest's headline (69.4% win / +3.97% median) — two real, identified reasons, not swept under the rug:**
- **Right-censoring**: 17.5% of simulated trades are still open when the ~62-day data window runs out, cut short mid-trade rather than at a real exit — likely understates true win rate/median given trades in the main backtest keep improving for many days after entry (matches the MFE research elsewhere in this log).
- **Distance-ranking optimizes for timing, not quality** — a genuinely different objective than the night-before quality score. This walk-forward answers "does the checkpoint mechanism itself work end-to-end," not "is this as good a trade as the average backtest trade" — those are different questions and shouldn't be expected to produce the same number.

**Follow-up 1 — why not weight quality and distance together instead of distance alone?** Tested three selection modes on the same 62-day walk-forward population (0.5% clearance, 09:20 freeze, top-2 picks/day):

| Mode | n picks | Fill rate | Win (filled) | Median (filled) | Fill×Win ("successful pick rate") |
|---|---|---|---|---|---|
| distance_only (current) | 122 | 65.6% | 61.3% | +1.07% | **40.2%** |
| quality_gate_then_distance (keep ≥median quality, then rank by distance) | 122 | 47.5% | 63.8% | +1.64% | 30.3% |
| combo_70_30 (70% distance-rank + 30% quality-rank blend) | 122 | 43.4% | 64.2% | +1.65% | 27.9% |

Quality-weighting genuinely improves per-trade quality (win +2.5-2.9pp, median +0.57-0.58pp) but at a large fill-rate cost (65.6%→43.5-47.5%) — since idle capital has a real cost (established earlier via the real-money portfolio simulation), **distance_only wins on total successful-pick rate** (40.2% vs. 27.9-30.3%) despite lower per-trade quality. **Not adopted as a change** — logged as the honest trade-off: quality-gating is the right call only if the actual goal shifts from "deploy scarce capital efficiently" to "fewer but better trades" as a distinct, legitimate alternative preference, not a strict improvement either way.

**Follow-up 2 — a very close top-1 pick might fire before there's realistic time to react ("filled at gap-up itself, can't trade it") — quantified rather than assumed.** For each day's top-1 pick specifically (fastest-firing subset, not top-2), minutes elapsed between the 09:20 checkpoint and actual fill (n=41 of 61 days with a top-1 pick that eventually fills): mean 44.4 min, median only 10 min, 25th percentile 5 min (the very next 5-min bar) — **46.3% fill within 5 minutes (effectively zero reaction time), 56.1% within 10 minutes.**

Quantified the real cost of this rather than just flagging it exists: for the n=43 fastest fires, computed slippage from a realistic ~10-minute-late reaction (price 10 min after the fill signal vs. the trigger price itself): **median slippage −0.10%, mean −0.05%** (typically a wash or slightly favorable — the same mean-reversion-after-initial-pop pattern as the rejected first-15-min momentum test), 76.7% of the time within an extra 0.3% of trigger, 88.4% within an extra 0.6% (i.e., still inside the existing band), only **7% of the time >1% slippage** (tail risk, max seen 2.25%). **Conclusion: no new mechanism needed.** A realistic human reaction delay doesn't typically blow through the band — the existing 0.3-0.6% band already absorbs ordinary latency. The one operational discipline this confirms: treat `trigger_high` (the 0.6% ceiling) as a hard skip line — if price is already past trigger_low+~1% total by the time you can act, don't chase; that's exactly the ~7% tail this data flags, and it's what the IOC-with-ceiling design was already built for.

## Response-13 outside critique — three quick tests actioned, one big strategic question (freeze/deploy) still open (2026-09-05)

Full critique read (13 rounds reviewed, 9.2/10 research discipline / 7.5/10 deployability verdict). Confidence table for high-confidence findings acknowledged, no action needed there. Three concrete, bounded asks tested directly on a rebuilt version of the checkpoint walk-forward population (62-day real window, 0.5% clearance, 09:20/09:30 freeze). **Rebuild note**: the original walk-forward script was ephemeral (scratchpad, not committed) and had to be reconstructed — this time using the pool's own night-before pattern classification (`on_vcp_path`/`base_filters_pass` from `build_pool`, matching `live_checkpoint.py`'s actual operational definition of "fired") rather than re-running `detect_entry()` on the fire day itself, which turned out to be a materially stricter, non-operational bar (re-checking full `detect_entry()`, including the Nifty regime gate, on the synthetic fire-day bar collapsed 533 real fires down to 0-2 — first because `require_regime=True` correctly reflects that the regime gate has been shut essentially the whole test window per the standing drought, and second because `detect_entry`'s stricter RSI/volume/trend-template re-check doesn't match what `live_checkpoint.py` itself actually validates before treating a name as "fired"). Numbers below use the corrected, operationally-consistent definition, and differ somewhat in scale from last round's first-pass walk-forward (122 picks) as a result — same direction, cleaner denominator (533 real fires across the same 62 days once the pool isn't artificially gated).

**1. Expected Profit@K / Regret vs. Oracle (the critic's "biggest critique" — Recall@K rewards being in the list, not being the best pick) — confirmed, and sharper than the critique anticipated.** Computed per-day Profit@1 (rank-1 alone), Profit@2 (equal-weight rank-1+2, 0 pnl on no-fire days), and Oracle (best-performing candidate that actually fired that day, perfect hindsight):

| Metric | Mean | Median |
|---|---|---|
| Profit@1 | −0.41% | 0.00% |
| Profit@2 | +0.19% | 0.00% |
| Oracle | +8.88% | +7.54% |
| Regret (Oracle − Profit@2) | +8.70% | +7.64% |

Only 3.3% of days did the top-2 picks actually capture that day's best-performing fire. **Broken down by rank specifically — a real, concrete instance of exactly what the critic warned about:**

| Pick | Fill rate | Win (filled) | Median (filled) |
|---|---|---|---|
| Rank-1 (closest) | 70.5% | 44.2% | **−0.46%** |
| Rank-2 | 63.9% | 71.8% | **+2.39%** |

Rank-1 fires most reliably (as validated all along) but performs *worse* once filled than rank-2 — real, if thin (n≈43 vs 39 fired), signal that the single closest candidate is often the most "used up" (least room left before a stall/reversal), consistent with the mean-reversion-after-fast-move pattern already found in the rejected first-15-min-momentum test. **Conclusion: distance-to-trigger genuinely optimizes for "who fires soonest," not "who performs best once filled" — these are different objectives, and the ranking should not be assumed to also be quality-optimal.** Not yet acted on (no ranking change made) — flagging for further work given the thin per-rank sample.

**2. Kaplan-Meier-style conditional-survival fix for the walk-forward's right-censored trades — passed, confirms the walk-forward was understating itself.** Used the full v28 backtest's completed trades (n=1430) as a survival-conditioned reference population: for each censored (still-open at data-cutoff) walk-forward trade, instead of marking it at whatever price the 62-day window happened to end on, looked at same-pattern completed trades that had already survived at least as many holding days and took their eventual median outcome.

| | Win rate | Median |
|---|---|---|
| Raw mark-to-market for censored trades (104 of 533, 19.5%) | — | −2.05% |
| Survival-adjusted expected outcome | — | **+1.77%** |
| Full population (533), raw-censored included | 56.3% | +1.04% |
| Full population (533), survival-adjusted | **71.5%** | **+1.77%** |
| Original approach: exclude censored entirely (429) | 64.6% | +1.75% |

Confirms directly what was flagged as a likely explanation last round: right-censoring was making the walk-forward look artificially worse than reality. The survival-adjusted win rate (71.5%) lands *above* the naive exclude-censored version, closing most of the remaining gap to the main backtest headline (69.4%/+3.97%) — the walk-forward mechanism is healthier than the raw censored-inclusive number suggested.

**3. Trigger Velocity (rate of distance-closing between 09:20→09:30 checkpoints) as a secondary ranking signal — a real, novel improvement, unlike volume.** Tested the same 70/30 blend structure that failed for volume last round:

| Ranking | Recall@1 | Recall@2 | Recall@5 |
|---|---|---|---|
| distance-only (baseline, at 09:30 checkpoint) | 55.7% | 80.3% | 95.1% |
| velocity-only | 16.4% | 39.3% | 62.3% |
| **combo (70% distance + 30% velocity)** | **65.6%** | **85.2%** | **98.4%** |

Velocity alone is weak (consistent with distance being close to a direct measure of the outcome, same reason volume-alone also failed) but blended with distance genuinely improves the ranking — Recall@1 +9.9pp, Recall@2 +4.9pp, Recall@5 +3.3pp over distance-only. Bucket check confirms it's not noise: among the closest 40% by distance, fire rate climbs from ~23-24% (slowest-closing/moving-away quintiles) to **38.4%** (fastest-closing quintile) — a real gradient among otherwise similarly-close candidates. **Real, promising lead — not yet wired into `live_checkpoint.py`**, needs the two-checkpoint (09:20 + 09:30) data flow built before it can be operational, and should go through the critic's same break-testing standard before being trusted at the same confidence level as the distance-only finding.

**Not actioned this round (informational or awaiting a strategic decision, not a testable claim)**: the confidence/deployment-readiness table (matches this project's own existing green/yellow/red reads — 3-day stall and sector/OI filters already independently flagged not-ready here); options-as-leverage-tiers reframe (a mental-model simplification, not a test); Energy Stall reframed as a resume-vs-distribute classification question (reasonable, same data already available, not yet re-cut); microstructure feature family (gap-fill%, ORB, VWAP distance, relative first-15-min volume — legitimate next direction, bigger lift, not started); the proposed 30-day feature-freeze-and-forward-paper-trade protocol (`Version 30`) — a real strategic call, explicitly left to the user rather than adopted unilaterally.

## `live_checkpoint.py` redesign: tiered by settledness, not flat distance-only ranking (2026-09-06)

Prompted by a direct question about the earlier `rank1_vs_rank2` finding above: user pointed out the wall-clock-anchored version of the pullback/no-pullback test conflated "how long since it fired" with "what hour it is" — a real confound (a stock that fired at 10:45 and hasn't pulled back by 11:00 just hasn't had time to, that's not the same state as one that fired at 09:20 and still hasn't pulled back 100 minutes later). Rebuilt anchored to bars-since-fire instead of wall-clock time (1470 real fire events, checked at fixed 30-min/60-min offsets from each fire, not fixed times of day):

| Tier (bars-since-fire anchored) | 30 min after fire | | 60 min after fire | |
|---|---|---|---|---|
| | Win | Median | Win | Median |
| Kept going, extended (ran well past band) | 59.4% | +1.40% | 58.3% | +1.39% |
| Kept going, still near breach | 57.2% | +0.99% | 62.6% | +1.53% |
| Pulled back near the level | 57.5% | +1.14% | 55.1% | +0.92% |

Confirmed: most of the originally-reported wall-clock gap (54.9%-66.2% spread) was the confound — properly controlled, the spread compresses to 55.1-62.6%, with no consistent, strong quality edge for any one state over another. **This connects directly to the existing day-3 follow-through finding** (immediate strength predicts eventual quality, tested at a multi-day scale, monotonic 39.6%→91.8% win spread) — same question, intraday timescale — but the intraday echo is far weaker, plausibly because 30-60 minutes isn't enough time for real signal to separate from noise the way 3 days is.

**Given win-rate differences between tiers are small/inconsistent, the redesign is justified on a different, stronger basis: removing the timing race entirely, not proving a quality edge.** A candidate that has ALREADY fired has a known, settled price whenever you happen to check — no 5-minute race to catch it (the real problem quantified earlier: 46.3% of top-1 picks fill within 5 minutes of a checkpoint). Rebuilt `live_checkpoint.py` around three actionable tiers instead of one flat distance-sorted list:

1. **Pulled back** — fired, retraced ≥0.5% off its high-so-far, still within 2% of trigger. Best average price (~0.2-0.35% below trigger in live-data spot checks), fully settled.
2. **Kept going, still near trigger** — fired, hasn't pulled back or run away, within 2% of trigger. Also settled, slightly worse average price.
3. **Watching, not yet fired** — the original, unchanged mechanism (same-day distance-to-trigger ranking, Recall@1 60.7-68.9%/Recall@2 76.3-83.6%/Recall@5 88.1-96.7% across the 0.3-1.0% clearance band).

A fourth state (fired, ran well past the band, still moving) is deliberately NOT surfaced as actionable — logged as **MISSED** per direct instruction (2026-09-06): the price is stale/uncertain by the time an order could be placed, and if it settles back into tier 1/2 on a later run it naturally reappears there, no special-casing needed since every run is a fresh, stateless snapshot.

**Quality annotations added per direct request, reusing only already-validated signals** (deliberately nothing new invented): `quality_score` (the same 4-feature night-before composite `tomorrow_candidates.py` already uses — range compression, EMA8 distance, ATR trend, narrowing-range — percentile-ranked against the same run's primed pool) and `sector`/`sector_rs` (the adopted 2026-09-01 sector-leadership signal, VCP top-quartile-RS sector wins 68.1% vs 55-61% bottom three). These are shown as reference context for choosing between same-tier candidates, not re-validated as tier-ranking signals in their own right.

**Verified end-to-end against real live data (2026-09-06)**: correctly bucketed IFCI (pulled back, now trading below its own trigger_low after a full round-trip — a real, valid case the win-rate numbers above already account for, not a bug), GLAND (pulled back), RBLBANK (kept-going-near, current price already above `trigger_high` — the band is reference-only for fired tiers, not an executable ceiling the way it is for tier 3), and NIACL (correctly flagged MISSED, +12% past its band). Added an explicit runtime note clarifying that for tiers 1/2/missed, the tradeable price is the `price` column, not bounded by the printed band.

**Trigger Velocity hardened and wired in (2026-09-06).** Round-13's velocity result was a single blend ratio (70/30) at a single checkpoint pair (09:20→09:30) — swept the blend ratio 0-100% at three separate checkpoint pairs before trusting it:

| Pair | Baseline R@1/R@2/R@5 | Best in the 70-90% dist / 10-30% vel zone |
|---|---|---|
| 09:20→09:30 | 55.7% / 80.3% / 95.1% | 65.6% / 88.5% / 98.4% (80/20) |
| 09:30→09:40 | 62.3% / 82.0% / 96.7% | 65.6% / 86.9% / 96.7% (90/10) |
| 09:25→09:35 | 63.9% / 83.6% / 95.1% | 75.4% / 83.6% / 96.7% (70/30) |

No single ratio is uniformly best across all three pairs (a real plateau, same honesty standard as the entry-clearance band and VCP tolerance — not a pinned-down optimum), but **80% distance / 20% velocity never lost and usually won** across all three — adopted as the standard blend.

**Wired into `live_checkpoint.py`**: since the live tool only took one snapshot per run, velocity needed a second data point — solved by calling `fetch_live_bars()` twice per run, once at the requested cutoff and once 10 minutes earlier (`_minus_minutes()`), both drawn from the same day's already-cached intraday data, no state persistence between runs needed. Tier 3 (watching, not yet fired) candidates now rank by `0.8×dist_rank + 0.2×vel_rank` (percentile ranks; candidates too early in the day for a prior snapshot fall back to a neutral 0.5 vel-rank rather than being penalized). Verified end-to-end against real live data — reordered the tier-3 list sensibly relative to pure distance (e.g. a candidate closing fast moved up, one drifting slightly away moved down), each row now prints `vel=+X.XX%/10min`.

**Caveat, checked directly and worth being honest about: the 10-minute lookback window itself was never validated, only inherited.** It was simply the gap size in the first checkpoint pairs tested above. Swept the lookback duration (5/10/15/20/25 min) at three separate fixed evaluation checkpoints (09:30, 09:40, 09:45), holding the 80/20 blend ratio fixed:

| Eval checkpoint (baseline R@1) | 5-min | 10-min | 15-min | 20-min | 25-min |
|---|---|---|---|---|---|
| 09:30 (55.7%) | 70.5% | 65.6% | — | — | — |
| 09:40 (62.3%) | 65.6% | 65.6% | 77.0% | 63.9% | — |
| 09:45 (67.2%) | 54.1% | 63.9% | 63.9% | 67.2% | 60.7% |

Unlike the blend ratio (a genuine, repeatable 70-90% "good zone" across all three checkpoint pairs), **the lookback duration has no consistent optimum** — the best window bounces between 5, 15, and 20 minutes depending on which specific checkpoint is evaluated, and a too-short 5-minute lookback is actively worse than plain distance-only at the 09:45 anchor (54.1% vs 67.2%). With only 62 days of real intraday data, this likely isn't pinnable down more precisely right now. **Conclusion: the direction (blend in some closing-speed signal) is real; the specific 10-minute window is an arbitrary, reasonable middle choice, not a validated optimum** — same honesty standard already applied to the 0.5% entry-clearance pick. Not changed from 10 minutes given the instability offers no confident alternative to switch to.

## `trader_dashboard.py` — one entry point tying the daily workflow together (2026-09-06)

Per the critic's Round-13 suggestion ("stop writing more scripts, build one dashboard"). Deliberately a thin orchestrator, not a fourth independent copy of any logic — `evening` wraps `tomorrow_candidates.py`'s `build_candidates()` (adds a stop level via `daily_scan.py`'s own `_initial_stop()`, not re-derived), `morning` wraps `live_checkpoint.py`'s `classify_candidates()` unchanged, `journal` is the one genuinely new piece (a lightweight, append-only `trade_journal.csv` for logging which tier/price a trade actually came from — separate from `open_positions.csv`, whose exact schema `monitor_positions.py`'s exit-logic replay depends on and which is deliberately left untouched).

**Two real, pre-existing gaps surfaced while verifying all three modes against live data — both fixed same-day on direct user go-ahead:**
- `tomorrow_candidates.py`'s `trigger_price` still used the old 1% clearance, not the validated 0.3-0.6% band — confirmed directly (GLAND: evening view showed `TRIGGER=2977.48`, morning view showed band `[2956.84, 2965.69]`, same night, same ticker). **Fixed**: `tomorrow_candidates.py` now imports `TRIGGER_CLEARANCE_LOW`/`TRIGGER_CLEARANCE_HIGH` directly from `live_checkpoint.py` (single source of truth, not a second copy of the same constant) and outputs `trigger_low`/`trigger_high` instead of one `trigger_price`. Re-verified: GLAND now shows the identical `[2956.84, 2965.69]` band in both tools. All 69 existing tests still pass.
- `open_positions.csv` was empty (header row only) despite two real, live positions (IFCI, GLAND) — so the dashboard's "already holding" cross-check had nothing to check against. **Fixed**: verified each ticker's actual pattern classification directly rather than assuming (IFCI qualifies for both breakout_cont and VCP on its entry day, 2026-09-02 — same-day-dual-qualified case, breakout_cont wins per `detect_entry`'s first-match-wins order, matching the real memory note "IFCI breakout_cont"; GLAND's entry (2026-09-04) was driven by the intraday trigger off the prior night's `base_filters_pass` classification, not a same-day `detect_entry` fire, so checked the night-before date 2026-09-03 instead — breakout_cont, not VCP). Both logged: `IFCI,2026-09-02,96.90,breakout_cont` and `GLAND,2026-09-04,2925,breakout_cont`. Verified via `monitor_positions.py` — resolves cleanly, reports current stop (₹86.83 / ₹2657.39) and target (₹104.52 / ₹2954.73) for both. Re-ran `trader_dashboard.py morning` — GLAND now correctly shows `[ALREADY HOLDING]`.

**Added a fourth mode, `night`, per a direct follow-up question ("why isn't this part of the dashboard too") — there was no good reason it wasn't.** Wraps `monitor_positions.py`'s existing `monitor()` function unchanged (same reasoning as the other three modes — no new logic, just wiring). Verified output is identical to running `monitor_positions.py` directly for both IFCI and GLAND. All 69 tests still pass. The dashboard is now a complete daily loop: `evening` → `morning [HH:MM]` (place trades, then `journal add` + a manual `open_positions.csv` row) → `night`.

## Distance Calibration Curve — turns Recall@K into a real, usable probability (2026-09-06)

Prompted by outside critique (response-14): instead of "is the real mover in my top-K," directly compute P(fires later today | distance-to-trigger at a checkpoint) — a smooth calibration curve, not a ranking comparison. Pooled every (checkpoint, distance, fires-after) triple across all six tested checkpoints (09:20-09:45, n=21,273 candidate-checkpoint pairs, 62-day real intraday window):

| Distance bucket | n | Fire rate |
|---|---|---|
| 0.1-0.2% | 25 | 88.0% |
| 0.2-0.3% | 48 | 81.3% |
| 0.3-0.4% | 81 | 77.8% |
| 0.4-0.5% | 122 | 68.0% |
| 0.5-0.6% | 146 | 71.9% |
| 0.6-0.8% | 487 | 56.7% |
| 0.8-1.0% | 577 | 48.0% |
| 1.0-1.5% | 1764 | 32.9% |
| 1.5-2.0% | 2032 | 22.3% |
| 2.0-3.0% | 3796 | 11.7% |
| 3.0-5.0% | 5962 | 3.8% |
| 5.0%+ | 6233 | 0.5% |

Genuinely, smoothly monotonic (a small 0.4-0.5%/0.5-0.6% wobble is sampling noise at n~120-150, not a break in the trend). **Checked robustness — the curve looks the same whether measured at 09:20 or 09:40 specifically** (both checkpoints independently show the same monotonic decline at comparable magnitudes), confirming this is a real distance-to-probability relationship, not a time-of-day artifact. **Wired directly into `live_checkpoint.py`**: each tier-3 (watching) candidate's row now shows a `fire_pct≈X%` field alongside its raw distance, using this exact lookup table — turns an abstract rank into a concrete, historically-grounded probability read at the moment of deciding whether to commit capital. Verified end-to-end against real live data; all 69 tests still pass.

## Two more response-14 items checked before market open — one rejected, one shipped (2026-09-06)

**Rank-aggregation instead of a weighted blend for Trigger Velocity — tested directly, does NOT hold up.** Critic's proposal: `Score = DistanceRank + VelocityRank`, no weights, on the reasoning that weights imply false precision. Tested against the same three checkpoint pairs as the original blend-ratio sweep:

| Pair | Distance-only R@1/R@2 | 80/20 weighted R@1/R@2 | Rank-aggregation R@1/R@2 |
|---|---|---|---|
| 09:20→30 | 55.7% / 80.3% | 65.6% / 88.5% | 62.3% / 77.0% |
| 09:30→40 | 62.3% / 82.0% | 65.6% / 83.6% | 67.2% / 77.0% |
| 09:25→35 | 63.9% / 83.6% | 73.8% / 82.0% | 67.2% / 78.7% |

Consistently worse at R@2 (5-11pp) across all three pairs — not the "<1% change" the critic guessed. **Precise reason**: summing two ranks already on the same 1..n scale is not weight-free — it's mathematically the 50/50 point on the exact same weighting spectrum already swept in the original blend-ratio test, where 50/50 was already known to underperform 80/20 at every pair. The "no weights, more honest" framing was a specific (and worse) weight choice in disguise, not an escape from the weighting question. **Not adopted** — kept the existing 80/20 weighted blend.

**Breadth line added to `trader_dashboard.py morning`** — trivial, reuses `breadth.breadth_pct()` unchanged (the same real, adopted signal `daily_scan.py` already surfaces), just wasn't wired into the newer tool. Verified working against live data (`market breadth today: 56%...`). All 69 tests still pass.

## SMA200 regime-TYPE split (critic's highest-priority re-audit, 10/10) — attempted, data genuinely can't answer it (2026-09-06)

Critic's ask: the earlier regime-gate investigation only ever compared "gate on" vs "gate off" against the CURRENT drought — never split by regime *type* (Bull/Recovery/Correction/Bear) across the fuller history, so it's possible Breakout Continuation survives fine in a Recovery regime specifically even if it doesn't in whatever specific flavor of "gate off" the current drought represents.

**Real methodological wrinkle discovered first**: `trades_v28.csv` can't answer this at all — every trade in it required `require_regime=True` at entry (Nifty above its 200-SMA is baked into `detect_entry`'s gate), so literally 100% of v28 trades classify as "Bull" by construction. Had to generate a fresh gate-off backtest (`require_regime=False`, full 500-ticker universe, n=3149) to get any trades outside a Bull regime at all.

Classified each trade's entry date into Bull (Nifty > SMA200) / Recovery (below SMA200, SMA50 rising over the prior 10 trading days) / Bear (below SMA200, SMA50 falling), using `market_regime.py`'s own cached SMA200/SMA50. First look was a real, striking, counterintuitive result — Recovery came out *worst* for both patterns, Bear *best* (opposite of naive intuition: breakout_cont Bear 67.8% win/+3.01% median vs Recovery 55.6%/+1.30%; coiled_spring Bear 58.0%/+2.39% vs Recovery 48.6%/−0.04%).

**Checked before trusting it, per our own standing discipline, and it doesn't survive**: top-10 trade concentration for Bear (n=199) is 67.5%; for Recovery (n=133) it's **167%** — meaning the top 10 trades' P&L exceeds the bucket's entire total, so the other 123 trades net *negative* overall. Real red flag. Worse: 69% of the "Bear" bucket's trades and 89% of the "Recovery" bucket's trades have entry dates in 2026 specifically. **Root cause: Nifty closed above its own 200-SMA continuously from 2022 through Feb 2026 — the entire available history contains essentially ONE non-Bull episode (the current, still-ongoing drought), not multiple independent bull/bear/recovery cycles.** "Bear" and "Recovery" here aren't different market TYPES being compared — they're just two sub-phases (SMA50-falling weeks vs. SMA50-rising weeks) of the same single continuous episode.

**Conclusion: this specific re-audit can't be answered with the data available, not due to a bug or a small sample specifically, but because the real world has only produced one non-Bull episode in the whole window this project has data for.** Answering the critic's actual question (does the pattern generalize across genuinely different regime types) would need either a much longer/older data history containing prior independent bear-market episodes, or waiting for the current drought to resolve and a future one to occur — not something re-slicing the existing data can produce. Logged honestly as "data insufficient to answer," not reported as a real finding despite the first-look number looking dramatic.

## VCP weak-window (Oct'24-Feb'26): detector-quality audit — 10th hypothesis, mostly rejected, one real nuance found (2026-09-06)

Critic's 2nd-highest-priority re-audit: every prior hypothesis for the weak window tested a FILTER (regime, sector, volatility, breadth) — none ever questioned the VCP detector's own output quality (base duration, leg count, volume-decay slope, distance from 52-week high). Extracted these four features directly from `vcp.py`'s own zigzag/leg-detection internals (`_find_swings`/`_legs`) for all 663 real coiled_spring trades in v28.

**Macro-level comparison (weak window vs. outside) — no difference on any of the four features, same shape as every prior rejected hypothesis:**

| Feature | Weak window (n=198) | Outside (n=465) |
|---|---|---|
| Base duration | median 51d | median 51d |
| Number of legs | median 10 | median 11 |
| Volume decay ratio | median 0.46 | median 0.47 |
| Distance from 52-week high | median 0.957 | median 0.970 |

Base quality itself is not measurably different during the weak window — the 10th hypothesis tested for this investigation, and the 10th to show no macro-level gap (joining Nifty direction, weak RS, ADX rising, ADX uptrend, SMA50-AND, SMA50-OR-recovery, sector, volatility, breadth).

**But a real, non-outlier-driven split showed up WITHIN the weak window specifically**: splitting at the median base duration (51 days), short bases did meaningfully worse (win 38.9%, median −3.31%, mean −2.25%) than long bases (win 53.4%, median +1.21%, mean −0.06%) — a genuine 14.5pp win-rate gap, mean and median telling the same consistent story (no single-trade distortion; a naive concentration-ratio check broke down here only because the "long bases" group's total P&L nets to near-zero, not because of real outlier concentration). The other three features (leg count, volume decay, 52-week-high distance) showed no comparable split within the weak window.

**Checked whether this generalizes beyond the weak window — it does NOT.** Same median split applied outside the weak window: 69.8% win (short) vs 66.7% win (long) — flat to mildly reversed. Across ALL 663 trades: 60.6% vs 62.7%, a real but much milder tilt. **Conclusion: base duration doesn't explain why the whole period was weak (it isn't different during that period), but it IS a real, useful quality filter specifically when conditions are already unhelpful** — a sensible mechanism: in a strong tape even a hastily-formed base can work because the broader market carries it, but in an indifferent/weak tape, only a base that actually completed genuine institutional accumulation (longer, more thoroughly tested) succeeds. Not adopted as a change (single-window evidence, and the general effect outside the window is much weaker) — logged as a real, mechanistically-explained nuance, not a root cause for the weak window itself.

One measurement caveat, disclosed rather than hidden: `base_duration` as computed here is capped by `BASE_LOOKBACK=60` trading days (the zigzag lookback window itself), so it cannot exceed that — a truly free/uncapped duration measure wasn't attempted here.

## DTE × moneyness × expiry heatmap (critic re-audit #3, 8/10) — the moneyness split reveals a real pattern the ITM-only test hid (2026-09-06)

Critic's methodological complaint: the earlier DTE×stall heatmap (`ITM+current` only, "no monotonic pattern, hypothesis not supported") never checked whether the shape differs across moneyness/expiry combos — theta acceleration genuinely depends on moneyness too, not DTE alone. Reused already-computed stall-vs-baseline options results from earlier this session (`stall_options_results.pkl`, all 4 combos) and bucketed each by DTE-at-entry:

| DTE bucket | ATM+current Δ (stall − baseline median) | ITM+current Δ |
|---|---|---|
| <10 | +5.42pp | −4.74pp |
| 10-15 | +16.33pp | −7.88pp |
| 15-20 | +29.55pp | +10.01pp |
| 20-25 | +16.95pp | +5.89pp |
| 25+ | −3.96pp | −6.56pp |

**ATM+current shows a real, sensible shape the ITM-only test completely hid**: stall helps at every bucket except the longest, fading from a large benefit at short/medium DTE down to slightly negative at 25+ — broadly matching the critic's theta-acceleration hypothesis (not strictly monotonic — 15-20 shows the single biggest benefit, not <10 — but the overall "helps when DTE is tight, doesn't when it isn't" direction is real and coherent, unlike ITM+current's incoherent up-down-up-down pattern). **ATM+next and ITM+next have only one DTE bucket at all** (25+, since next-month expiry is always 25+ days by construction) — no gradient exists to test for either, and both show stall mildly hurting (−0.93pp, −2.18pp), consistent with the already-established "stall doesn't help next-month" finding.

**Conclusion: the critic's methodological point was correct — checking DTE decay without controlling for moneyness averaged away a real signal.** For ATM+current specifically (the "same-day spike capture" recipe this project already recommends), stall's benefit is genuinely DTE-dependent in a sensible way; for ITM+current it isn't. Not yet turned into a code change (would mean making the stall exit's use conditional on moneyness+DTE rather than a flat rule) — logged as a real refinement worth adopting if/when the options-side stall logic gets revisited, not acted on unilaterally given it touches the options exit mechanism directly.

## Energy Stall redefinition (critic re-audit #4, 7/10) — a genuine improvement over the original formulation (2026-09-06)

Critic's complaint: the original Energy Stall (`Energy = (ATR3/ATR20) × (Volume3/Volume20)`, exit in the low-ATR/high-volume "distribution" quadrant) uses ATR ratios as a proxy for "result," but ATR measures volatility, not the stock's actual net directional progress — the real Wyckoff "effort vs. result" concept is better measured directly. Redefined and tested: **Efficiency trigger = |3-day net return%| < threshold AND (Volume3/Volume20) > 1.2** — heavy relative volume with little actual net price progress over the same window, on the same 679-trade breakout_cont pool as the original test:

| Return threshold | Fires | Baseline win/median/ret-per-day | Efficiency-stall win/median/ret-per-day |
|---|---|---|---|
| 0.5% | 6.0% | 70.0% / +4.07% / +0.416%/day | 71.3% / +4.16% / +0.461%/day |
| 1.0% | 12.7% | (same) | 72.9% / +4.33% / +0.516%/day |
| 1.5% | 17.5% | (same) | 73.8% / +4.16% / +0.570%/day |
| 2.0% | 22.2% | (same) | **75.1% / +4.20% / +0.623%/day** |

**Monotonically improves as the threshold loosens — a real, robust shape, not a single lucky point** — and beats the original Energy Stall's own result (fires 7.2%, win 70.0%→71.4%, ret/day →+0.455%/day) at every threshold, even at a comparable fire rate. Checked concentration on the strongest configuration (2.0% threshold, n=151 fired) before trusting it: **top-10 concentration only 14.2%** (healthy, well-distributed — nowhere near the >100% red flag seen elsewhere this session), worst fired trade barely negative (−0.05%), median +5.17%. A genuinely clean, robust result.

**Conclusion: the critic's reframing is a real improvement, not just a different way of describing the same thing** — measuring the actual price-progress shortfall directly (rather than inferring it from an ATR ratio) produces a stronger, more monotonic, better-distributed signal. Not yet adopted into the live exit logic — this is still a validated backtest finding, same standing rule as everything else pending outside review before being wired into production — but a clear, real upgrade candidate over the original Energy Stall concept, best among all four of this round's re-audits in terms of concrete, unambiguous improvement.

## Energy Stall "immortal time bias" audit (critic pushback, response to Round 15) — a real, sharper problem than the concentration/data checks alone would have caught (2026-09-06)

Critic's specific concern, not just "verify this isn't a data artifact" (already done) but something sharper: the efficiency condition only ever gets evaluated on trades that have already survived to arm (reach 0.5R) — comparing "fires" vs "doesn't fire" could be comparing populations conditioned on survival in a way that makes the improvement look more causal/actionable than it is. Requested test: compare cumulative expectancy trajectory, from the point of arming, for trades where the condition eventually fires vs never fires — using each trade's FULL, uncut natural continuation (ignore the stall exit entirely), not the shortened outcome.

Built exactly this (449 of 679 trades arm, 66.1%): split into "fires at some point" (n=158) vs "never fires" (n=291), tracked cumulative pnl at day+3/+5/+8 since arming AND the final natural (uncut) outcome for both groups:

| | Final natural outcome | Day+3 median | Day+5 median | Day+8 median |
|---|---|---|---|---|
| Never fires | win 93.5%, median +7.01% | +4.93% | +4.48% | +4.96% |
| Fires at some point | win 76.6%, median +6.50% | +4.69% | **+4.91%** | **+5.22%** |

**The final-outcome gap is real** (fires trades do end up somewhat behind never-fires trades over the full horizon) — but **at the actual decision point (day+3/5/8, where the real exit rule would trigger), the two groups look nearly identical, and "fires" is even slightly ahead at day+5 and day+8.** The divergence only emerges much later than the point where the stall rule would have already cut the trade.

**This sharpens, with real evidence, exactly the concern the critic raised conceptually**: the signal correlates with modestly weaker trades in aggregate, but doesn't show visible, actionable weakness at the moment it actually fires — it isn't "catching an imminent reversal" the Wyckoff effort-without-result framing implied, it's closer to "this subgroup tends to underperform slightly for reasons invisible at the actual exit point." That's a materially weaker mechanistic claim than originally reported. **Conclusion: matches the critic's "do not ship" verdict, now with concrete supporting evidence rather than just the a priori concern** — the earlier win-rate improvement (70.0%→75.1%) is real as a population-level correlation, but the case for it being a well-timed, causally-understood exit signal is weaker than it looked before this audit. Kept as research, not adopted, not elevated toward shipping.

**Same audit run on the ORIGINAL, already-adopted 3-day-stall rule (no fresh high in 3 days once armed) — for comparison, per a direct follow-up question ("does the rule that's actually live have the same problem?").** Same population (679 breakout_cont trades, 449 armed), same day+3/5/8-since-arming trajectory methodology, condition = 3 consecutive days with no fresh High above the running peak since entry:

| | Final natural outcome | Day+3 median (n) | Day+5 median (n) | Day+8 median (n) |
|---|---|---|---|---|
| Never stalls | 97.3% win, +7.67% | +7.85% (n=44) | +7.27% (n=16) | +6.22% (n=4) |
| Stalls at some point | 74.2% win, +5.16% | **+4.40%** (n=189) | +4.53% (n=176) | +5.02% (n=132) |

**Materially different result from Energy Stall — the divergence is already large and visible at Day+3** (+7.85% vs +4.40%, a real ~3.5pp gap on reasonable sample sizes, 44 vs 189), not something that only emerges much later. (One caveat: "never stalls" trades tend to hit their resistance target and exit quickly, so that bucket's sample collapses fast — 44→16→4 — making the Day+8 comparison specifically too thin to trust; the Day+3 comparison, where both groups still have real sample sizes, is the one to rely on.) **Conclusion: the original, simpler, already-live 3-day-stall rule does not show the same immortal-time-bias problem Energy Stall did** — the weakness in trades that eventually stall is visible close to real-time, near the point the rule would actually act, not just in hindsight long after. Reassuring, not just "no gap left by not shipping Energy Stall" but genuine evidence the rule already doing this job for options is on more solid footing than the newer, more sophisticated attempt to replace it.

## Fixed-N-days-after-arming exit — a genuinely strong new candidate, found by directly testing a "why not just cut it there" hunch (2026-09-06)

Prompted by a direct observation on the Day+3-since-arming numbers above ("both groups already look decent at Day+3 — why not just exit everyone there?"). Tested rather than assumed: an **unconditional** rule — once armed (0.5-0.6R), exit exactly N trading days later no matter what (unlike the reactive "wait for 3 consecutive no-fresh-high days" rule, this needs no streak-tracking at all).

**Stock-side sweep** (679 breakout_cont trades): N=3 is the best of three tested, and decays sensibly as N grows (a real shape, not a lucky single point):

| Rule | Win | Median | Return/day |
|---|---|---|---|
| Baseline (no early exit at all) | 70.0% | +4.07% | +0.416%/day |
| Fixed exit 3 days after arming | 75.7% | +3.94% | **+0.582%/day** |
| Fixed exit 5 days after arming | 74.4% | +4.16% | +0.495%/day |
| Fixed exit 8 days after arming | 72.9% | +4.24% | +0.469%/day |

Fixed-3 slightly beats even the existing reactive 3-day-stall's own return/day (+0.582%/day vs the existing rule's +0.544-0.548%/day) — genuinely competitive, and simpler to implement. Real, honest tradeoff disclosed: for the 213 trades where this rule actually changes the exit, the natural (uncut) median for those same trades is +6.61%, vs +4.64% under the forced exit — real upside given up in exchange for the win-rate/turnover-speed gain. Stock-side concentration on the changed subset: healthy, 13.8%.

**Options-side test, all 4 variants — this is where it gets genuinely strong.** Re-simulated real option prices for both the baseline (natural) and fixed-3-day exit dates, using the existing `simulate_option_trade()`:

| Variant | Baseline win/median/ret-day (days) | Fixed-3-after-arm win/median/ret-day (days) |
|---|---|---|
| ATM+current | 46.3% / −17.17% / −1.154%/day (13d) | 49.0% / −5.38% / −0.340%/day (9d) |
| ITM+current | 54.4% / +10.52% / +0.633%/day (13d) | 56.7% / +14.89% / +1.250%/day (9d) |
| ATM+next | 57.3% / +14.84% / +1.131%/day (15d) | 60.3% / +14.71% / +1.245%/day (11d) |
| ITM+next | 61.6% / +20.86% / +1.412%/day (16d) | 64.6% / +20.31% / +1.472%/day (13d) |

**Improves win rate and return/day in every single variant**, with the largest gain in ATM+current (the most theta-sensitive, most convex contract — exactly where a faster-turnover rule should help most) and, notably, a real (if smaller) improvement even for **ATM+next/ITM+next** — variants where the *existing* reactive 3-day-stall rule showed no benefit ("a wash for next-month variants," per the earlier options re-check). This fixed rule reaches further than what's currently adopted.

**Concentration checked before trusting the dramatic ATM+current number — real caveat, but not a new one.** ATM+current's concentration under the new rule is 230.8% (extremely skewed — a handful of huge winners rescue an otherwise-negative population), but checking the SAME variant's baseline concentration shows 169.7% — this skew is inherent to ATM+current itself (already this project's roughest, most fat-tailed variant), not something the new rule introduced; the rule still improves the underlying number a lot, but neither the before nor after number for ATM+current should be over-trusted given the inherent skew. **ITM+next — the standing, most-trusted recipe — shows a healthy 32.2% concentration**, and its improvement (61.6%→64.6% win, +1.412→+1.472%/day) is real and well-distributed, not concentration-driven.

**Status: a genuine, promising new candidate — not yet adopted.** Same standing rule as everything else this session: validated backtest finding, pending outside review before being wired into production. Notably stronger evidence base than Energy Stall got (tested directly on options P&L across all 4 variants, not just stock), and arrived at by directly testing a hunch rather than assuming it — the exact "greedy but test it" instinct this whole audit thread has been encouraging.

**Outside critique on this finding — sharp, and confirmed correct by a proper follow-up test.** Reviewed the aggregate per-trade stats above and pushed back hard: (1) the day+3/5/8 trajectory chart mixes a shifting, survivor-biased population at each checkpoint rather than tracking a single fixed cohort — a real methodology gap, not just the sample-size caveat already flagged; (2) return/day is not the same thing as trade expectancy — it only matters if freed-up capital is genuinely redeployed into another edge, and ignores real-world frictions (slippage, missed entries); (3) for ITM+current specifically, total rupee P&L across the trade population was nearly unchanged between baseline and the new rule — meaning any "improvement" is a capital-rotation effect, not a real per-trade edge, which is a portfolio-allocation question, not an exit-rule question. Proposed the correct test: compare CAGR under real capital constraints via a proper sequential portfolio simulation, the same rigor already used to settle the original 3-day-stall's stock-vs-options question.

**Ran exactly that test on ITM+next (reusing `portfolio.py`'s existing cash-only event-driven simulator) — the rule does NOT hold up.**

| Starting capital | Baseline CAGR (taken/440) | Fixed-3-after-arm CAGR (taken/441) |
|---|---|---|
| ₹3L | 106.4% (341) | 91.8% (306) |
| ₹4L | 93.8% (368) | 80.1% (316) |
| ₹5L | 82.4% (374) | 78.5% (387) |
| ₹7.5L | 68.4% (412) | 64.8% (432) |
| ₹10L | 58.8% (433) | 54.5% (440) |

**Baseline (natural exit) beats the fixed-3-day rule at every capital level from ₹3L to ₹10L** — a real, consistent 4-15pp CAGR gap, the opposite direction of what the per-trade aggregate stats suggested. (Below ₹3L — ₹50k/1L/2L — results are noise either way: a tiny number of early trades can lock up nearly the whole pool for weeks at low capital, a real, previously-documented "scheduling fragility" artifact of the fixed-1-lot sequential allocator, not a signal about either exit rule; first attempt at ₹50k-2L showed one rule taking 10x fewer trades than the other, which looked like a bug and was traced directly to this mechanism before being correctly set aside as unreliable rather than reported.)

**Conclusion: do not adopt.** The critic's skepticism was correct and is now a decisive result, not just an argument — the per-trade win-rate/return-per-day improvement does not survive a real, sequential, capital-constrained simulation. Natural exits compound better. Matches the critic's final verdict exactly (keep as a research branch, do not replace the current exit).

**Checked the same capital-constrained test on the stock leg too, not just options — fails there as well, though far less dramatically.**

| Capital | Stock baseline CAGR | Stock fixed-3-after-arm CAGR |
|---|---|---|
| ₹3L | 36.2% | 38.6% |
| ₹5L | 32.3% | 31.5% |
| ₹7.5L | 28.7% | 28.9% |
| ₹10L | 25.5% | 24.3% |
| ₹20L (uncapped, both take all 679 trades) | 15.6% | 14.2% |

Much closer to a coin flip than options (max ~2.5pp gap either direction at intermediate capital, vs options' consistent 4-15pp loss) — but at the uncapped level, where capital constraints stop mattering entirely, baseline is still slightly ahead, consistent with the already-disclosed fact that fixed-3's raw median (+3.94%) sits slightly below baseline's (+4.07%). **No capital level or leg shows a real benefit for this rule** — a clean, complete "do not adopt," not just for options.

## Standing methodology caveat (2026-09-20, retroactive): `portfolio.py`/`simulate_lots()` assumes perfect chronological capture of every affordable candidate, with no realistic visibility/execution constraint — every capital-constrained CAGR conclusion built on it should be treated as provisional, not decisive

Surfaced revisiting whether "Opportunity Cost Exit" (below) should be trusted enough to extend to swing/EMA34=2. `simulate_lots()` (used for the fixed-3-days-after-arming rejection immediately above, and for the original reactive-3-day-stall re-check right after this note) sorts every candidate trade by `entry_date` and admits it purely on cash-affordability — it has no ranking mechanism and assumes the trader is simultaneously aware of and can act on every single affordable candidate the moment it appears, with no missed signals, no execution failures, no "I wasn't watching" real-world risk. This exact limitation was independently found and named while building RQ-57 (2026-09-18, months later) — `simulate_lots()` "has no ranking mechanism at all... no connection to the Primed-Gate/EMA34 candidate-generation logic," leading RQ-57 to abandon `portfolio.py` entirely in favor of the real intraday cache + live 9:20 Top-5 ranking mechanism — but that conclusion was never generalized into a standing rule at the time, so the fixed-3-day-exit rejection immediately above (and the reactive-3-day-stall re-check below), both from 2026-09-06, predate that fix and rest on the same unrealistic assumption.

**A sharper, related point raised directly by the user, more fundamental than the ranking-mechanism gap**: even a "realistic" Top-5-ranking-based simulation still assumes the trader successfully allocates to the ranked-good trade every time it's available — real life doesn't guarantee that (not watching at the right moment, execution failure, any real-world reason a good signal gets missed while a bad one gets taken instead). No portfolio-level simulation, however realistic its candidate-selection model, can fully eliminate this irreducible execution/luck risk, because it's about the trader's own real-time reliability, not which signals exist. **This is the actual theoretical justification for asymmetric risk:reward (e.g., 1:3 R-multiples) as a design philosophy, separate from whatever a capital-constrained CAGR backtest says**: instead of trying to guarantee you correctly catch the best available trade at the right time (which no simulation can promise reflects reality), size wins to be big enough relative to losses that the system stays profitable even under realistic execution variance — you don't need to always get the "right" trade, you need whichever trades you do get to be safely asymmetric. Worth deciding explicitly: is a proposed exit/rotation rule being evaluated on raw backtest CAGR (vulnerable to this whole class of unrealistic-capture assumptions), or on distributional robustness (win/loss size ratio, tail risk) — these are different criteria and can disagree.

**Practical implication for tonight's abandoned line of work**: do not reuse `portfolio.py` to test "Opportunity Cost Exit" on swing/EMA34=2 — it would inherit the same flaw. If a capital-constrained answer is wanted, it needs RQ-57's real approach (intraday cache + live 9:20 ranking), not a portfolio allocator. The fixed-R-multiple test run earlier tonight (1R/2R/3R vs baseline, EMA34=2, real `detect_entry()`/`check_exit()`) showed mean expectancy rising while win rate and median both fell (baseline 64.2%win/+1.720%exp/+2.421%median → 3R 56.3%win/+2.232%exp/+1.345%median) — flagged in the moment as needing a concentration/outlier check before trusting the higher mean, **still unresolved, not yet checked**.

## Same capital-constrained test run on the ORIGINAL, already-live reactive 3-day-stall — mixed, and worth flagging since it questions something already in production (2026-09-06)

Direct follow-up question: if the fixed-N-day rule's per-trade improvement didn't survive a real capital-constrained test, does the rule *actually currently live* for options survive it? This had never been checked — the original stall was only ever validated on per-trade aggregate stats (win/median/ret-per-day), never run through a real sequential portfolio simulation. Reused the existing `stall_pool.csv` (baseline vs reactive-stall stock exits, 679 trades, 181 changed), re-simulated both ATM+current and ITM+next option prices, ran through `portfolio.py`'s simulator at the same capital levels — using only ₹7.5L-10L as trustworthy (lower levels showed the same scheduling-fragility noise as before, with meaningfully different trade counts taken between the two rules):

| Variant | ₹7.5L Baseline / Stall | ₹10L Baseline / Stall |
|---|---|---|
| ATM+current | 24.2% / 25.6% | 22.5% / 23.2% |
| ITM+next | 68.4% / 65.4% | 58.8% / 55.2% |

**Mixed result, not a clean pass or fail**: ATM+current's stall rule genuinely wins, even at the clean uncapped level — this one holds up under proper scrutiny. **ITM+next does not** — baseline wins by a real ~3-3.6pp margin at the reliable capital levels, the same pattern that just killed the fixed-N-day rule. **This means the rule already live in production for ITM+next may not survive the same capital-constrained test that's supposed to justify it** — a real, actionable finding since it questions something already adopted, not just a candidate. Not yet resolved into a code change — flagging for outside review given the significance, same as everything else pending before touching production.

**Direct pushback on the portfolio-scheduler test itself — well-founded, and confirmed independently with a cleaner method.** Trusting a scheduled selection (which trades happen to get "taken" at a given capital level) as the primary evidence is exactly the kind of scheduling-fragility artifact this project has been burned by before — the ₹50k-2L results earlier in this thread looked like an outright bug for precisely this reason. Rather than trace which specific trades the ₹7.5L-10L comparison selects, ran a completely selection-free alternative: for the 181 stock-level trades where the reactive stall rule actually changes the exit, matched pairs (same trade, same entry, only the exit differs) directly, no portfolio scheduler involved at all.

| ITM+next, matched pairs (n=117) | Win rate | Median | Mean | Median hold |
|---|---|---|---|---|
| Baseline (natural exit) | 59.8% | +25.18% | +29.53% | 23 days |
| Stall (cuts early) | 65.0% | +11.73% | +22.09% | 13 days |

**Stall only beats baseline on 50 of 117 trades (under half) — per-trade median difference exactly 0.0.** Essentially a coin flip, with a real, substantial cost: median return roughly halves (+25.18%→+11.73%) for a modest win-rate bump. This reaches the same conclusion as the portfolio test (ITM+next's stall rule doesn't clearly help) but via a method with zero selection/scheduling bias — a same-trade, matched comparison, not a population-selection one. **This matched-pair result should be treated as the primary evidence for ITM+next going forward, not the portfolio CAGR numbers** — it answers the actual question (does cutting early help on the trades it affects) directly, without the scheduler's known fragility in the mix.

## What "final outcome" hides: the option's path during the hold, not just entry-vs-exit (2026-09-06)

Direct challenge: the matched-pair comparison above only looks at entry-vs-exit P&L for each rule — it says nothing about what the option's value actually does *between* the stall-trigger point and the eventual natural exit if you don't cut. That's the real, felt cost of "sitting in a stalled option" (theta bleed + adverse moves along the way), independent of whether freed capital gets redeployed anywhere.

Measured directly: for each matched ITM+next trade, the option's price at the stall-trigger point vs. the minimum price it reaches at any point between there and the eventual natural exit (same contract, real intraday-cache-independent option data, day-by-day via `option_row()`):

| ITM+next (n=114) | |
|---|---|
| Median further drawdown from the stall-trigger price | **−16.4%** |
| Trades with a real (>10%) further dip before any recovery | 61 of 114 (53.5%) |
| Trades with a severe (>30%) further dip | 38 of 114 (33.3%) |
| Trades that never dip below the stall-trigger price at all | 38 of 114 (33.3%) |

**This directly confirms the "stalled option = real pain" worry the stall rule was designed to avoid** — holding through means sitting through a real, often severe, further loss in option value a majority of the time, even though the position frequently (not always) recovers to a good final number. The final-P&L comparison completely hides this. **Reframes the tradeoff**: it's not "the stall rule doesn't help, hold through it" — it's a genuine risk/reward tradeoff where cutting early avoids real pain most of the time, at the cost of giving up upside in the minority of cases that do recover. Neither side is free.

**Follow-up hypothesis, tested directly: if ITM+current suffers WORSE interim pain than ITM+next (faster theta, less runway to recover), does a fast-exit discipline actually pay off there — unlike ITM+next?** Ran the identical matched-pair and drawdown-path methodology on ITM+current (same 181 changed trades, contracts resolved to current-month instead):

| | ITM+current baseline | ITM+current stall | ITM+next baseline | ITM+next stall |
|---|---|---|---|---|
| Win rate | 55.9% | **64.0%** | 59.8% | 65.0% |
| Median | +5.66% | **+10.47%** | +25.18% | +11.73% |
| Mean | +16.46% | **+19.41%** | +29.53% | +22.09% |
| Median hold | 18 days | **10 days** | 23 days | 13 days |

| Drawdown-if-you-don't-cut | ITM+current (n=94) | ITM+next (n=114) |
|---|---|---|
| Median further drawdown | **−19.2%** (worse) | −16.4% |
| % with real (>10%) further pain | **62.8%** (more often) | 53.5% |
| % with severe (>30%) further pain | **40.4%** (more often) | 33.3% |

**Confirmed — and it reframes the whole finding.** ITM+current punishes holding through a stall harder (worse, more frequent drawdowns, consistent with faster theta decay and less time for the underlying to recover before expiry pressure), and precisely because of that, cutting early on ITM+current genuinely improves win rate, median, AND mean — the opposite of ITM+next, where the position usually has enough runway that holding through wins on net despite the real interim pain. Concentration checked before trusting this: 66.3% top-10 (elevated but not disqualifying — consistent with current-month options generally being more fat-tailed than next-month, not something specific to the stall rule).

**Practical implication: the fast-exit discipline's real home may be ITM+current, not ITM+next where it's currently applied.** ITM+current alone (natural exit) was previously seen as a weak, unreliable variant — but paired with an early-exit rule, it looks like a real, capital-efficient alternative (shorter 10-day median hold, better aggregate stats across the board). Not yet adopted — needs the same outside review as everything else before touching production, and this specific combination (ITM+current + fast exit) hasn't been through the capital-constrained portfolio test the other variants got. Real, promising, and a genuinely new angle rather than just a rejection.

## Two small UX ships, per critic response to Round 15 (2026-09-06)

**Calibration tiers instead of a raw percentage.** Critic's point: a person makes better decisions off a small number of named buckets than off two numbers that only differ by a point or two ("63.2% vs 64.7%"). Added `FIRE_TIERS`/`fire_tier()` to `live_checkpoint.py` — `[HIGH]` ≥70%, `[WATCH]` ≥50%, `[WEAK]` ≥25%, `[IGNORE]` <25%, directly off the Distance Calibration Curve. The raw number is still shown alongside the tier, not hidden, per the "critic's ask, not blind compliance" standard — e.g. `[WEAK] ~33%`.

**Raw distance shown alongside velocity, not just the blended rank.** Critic's explainability point: showing only the combined score hides *why* something ranked where it did. Every tier-3 row in both `live_checkpoint.py` and `trader_dashboard.py morning` now prints `dist=+X.XX%` next to `vel=+X.XX%/10min`, so the two raw inputs to the ranking are both visible, not just the output.

Verified against real live data in both tools, all 69 tests still pass.

## "Opportunity Cost Exit" (critic's response-14 proposal) — cut AND redeploy, not cut-to-cash — the strongest new idea from this whole thread (2026-09-06)

Critic's idea: instead of a calendar/streak trigger deciding *whether* to exit, use the already-validated Distance Calibration Curve to decide whether a real, currently-available alternative is worth rotating into — "would I rather own today's top checkpoint candidate than this current position?" Tested the core mechanism directly rather than the exact scoring proposal: at the moment a stall condition (either mechanism — reactive 3-day-stall or fixed-3-days-after-arm) would cut a position, check whether a real, independent signal fired on that *same calendar day* elsewhere in the full trade history, and compare three arms for the same trades — hold, cut-to-cash, and cut-then-rotate (crystallize the cut-point P&L, then compound with the real alternative's own full realized outcome, averaged unbiased across all same-day alternatives when more than one existed, never cherry-picked).

**Stock-side, both cut mechanisms — clean, consistent, real:**

| Cut mechanism | n (with a real alt available) | Baseline win/median/conc | Cut-to-cash win/median/conc | Rotate win/median/conc |
|---|---|---|---|---|
| Reactive 3-day-stall | 124 of 181 | 71.0% / +4.46% / 33.5% | 94.4% / +4.20% / 21.3% | **89.5% / +8.17% / 20.1%** |
| Fixed-3-days-after-arm | 155 of 213 | 77.4% / +6.35% / 26.0% | 96.1% / +4.63% / 17.7% | **89.7% / +7.81% / 17.3%** |

Rotate nearly doubles cut-to-cash's median/mean **both times**, with the best (lowest) concentration of all three arms both times — a genuinely robust result, not sensitive to which cut mechanism triggers it. Real alternatives were available most of the time the cut fired (median 3, up to 11 same-day candidates) — not a thin, contrived sample.

**Options-side, all 4 combinations tested (2 cut mechanisms × 2 moneyness variants):**

| | ITM+next, reactive | ITM+next, fixed-3 | ITM+current, reactive | ITM+current, fixed-3 |
|---|---|---|---|---|
| Rotate win/median/mean | 70.6% / +41.68% / +46.05% | 73.5% / +38.35% / +47.16% | 63.5% / +23.34% / +37.24% | 66.7% / +33.82% / +51.45% |
| Rotate concentration | 63.8% | **50.2%** | **99.3% ⚠** | 64.7% |
| Beats cut-to-cash on win rate too? | Yes | Yes | No | No |

**ITM+next + rotate is the clear, consistent winner** — beats both hold and cut-to-cash on every metric, both cut mechanisms, with the best concentration of any result in this entire session's exit-side work (50.2% with the fixed-3 trigger). **ITM+current + rotate is real but less trustworthy** — good median/mean both times, but win rate lags cut-to-cash both times, and concentration swings from a real red flag (99.3%, reactive-stall cut) to reasonable (64.7%, fixed-3 cut) depending on which trigger is used — needs a larger sample before trusting at the same confidence level as ITM+next.

**Conclusion: this is the strongest validated new idea from the whole stall-exit thread, and it directly confirms the critic's proposal — the value was never in "cut vs. hold," it's in "cut and redeploy into something real," which sitting in cash the whole time was leaving on the table.** Not yet adopted — same standing rule as everything else, needs outside review and a real scoring mechanism (the critic's original proposal used the Distance Calibration Curve to rank alternatives, which this test approximated with an unbiased same-day average rather than the actual scoring rule) before being wired into anything live.

## Data-quality bug found in ITM+next contract selection — some "ITM" trades are secretly OTM (2026-09-06)

Triggered by a sanity check on personal holding preference (short, fast-cut momentum trades, ≤10 days): compared ITM+current vs ITM+next head-to-head under the fast-cut regime, and the cost gap looked wrong — next-month contracts only cost ~8.7% more than current-month for ~24 extra days of runway. Too small to be believable, and it was right to distrust it.

**Root cause**: `pick_contract()` (`option_backtest.py:131-165`) selects the strike closest to the target (`spot*(1-ITM_PCT)`) independently per expiry, filtered to whatever passes `liquid()` that day. Front-month (current) liquidity is reliably deep near the target, but next-month liquidity is often thin at exactly the ITM strikes — so the picker frequently snaps to whatever's actually tradeable, which drifts away from the intended target.

**Scope, measured precisely (n=442, full stall-rule pool):**
- 56.1% of trades pick a *different* strike for current vs next (not itself alarming — see below).
- Of all ITM+next selections, only **7.5%** drift more than 5% of spot from the true ITM target (a real moneyness-bucket change) — median drift is 0.84% of spot, mostly harmless adjacent-strike noise from differing strike grids.
- But **6.6% of all ITM+next selections (29 of 442) are secretly OTM, not ITM at all** — the picked strike is *above* spot (zero intrinsic value) for a call. Two concrete examples: ICICIGI (2024-02-06, spot 1590.95, target 1511.40, current correctly picked 1510 ITM — next picked **1720, above spot**, entry premium ₹16, exit ₹64, **+300%** on a 12.2% stock move); ESCORTS (2022-08-29, spot 1943.35, target 1846.18, current correctly 1840 ITM — next picked **2000, above spot**, +260% on an 11.1% stock move). Both are pure leveraged OTM convexity plays wearing an "ITM" label — the opposite of what ITM was chosen for (less theta/vega sensitivity, ~1:1 tracking).
- Checked overlap with reported results directly (the "verify outliers" standard): 2 of the top-10 winning trades driving the ITM+next baseline result (30.8% concentration) are in this flipped-OTM bucket — ICICIGI and ESCORTS, both listed above.

**What this invalidates vs. what survives:**
- **Invalidated / needs correction**: any direct cross-comparison of ITM+next vs ITM+current or ATM ("next is better/worse than current") — both sides weren't measuring the same moneyness. Corrected version, restricted to the 189 trades (of 442) where `pick_contract` naturally landed on the *same*, real, liquid strike for both current and next: next genuinely costs **+12.6%** more for ~16 extra days (a sane number). But head-to-head, **current wins the same trade 72% of the time** — next's better aggregate median/mean (+25.00% vs +20.41%) comes from a smaller number of much larger wins (top-10 concentration 49.3% vs current's 62.5%), not from generally winning more often. Under a fast-cut, short-hold discipline (no interest in capturing that rare fat tail), this reopens the case for current-month over next-month specifically — the opposite of what the uncorrected comparison suggested. The DTE×moneyness×expiry heatmap (earlier this week) makes the same kind of cross-comparison and needs the same re-check.
- **Not invalidated**: every result that stayed *within* ITM+next — same selected contract on both arms of the comparison, only the exit date differs (the reactive-stall matched-pairs test, the capital-constrained CAGR test, the drawdown-path measurement, the Opportunity Cost Exit/rotation numbers for ITM+next). A drifted or flipped-OTM contract affects both arms identically and cancels out of an internal comparison — these conclusions stand as reported above.

**Fixed (2026-09-06).** `pick_contract()` now hard-constrains the "itm" search to strikes below spot (`strikes[strikes.StrkPric < spot_price]`) before picking nearest-to-target, returning `None` (skip the trade) rather than silently falling back to an OTM strike when no liquid ITM strike exists for that expiry. All 69 tests still pass (none of them exercised this path).

**Re-ran the core ITM+next backtest on the real production trade file (`runs/trades_v28_fo.csv`) post-fix — every metric improved, not just shrank:**

| | Pre-fix (n=562) | Post-fix (n=523) |
|---|---|---|
| Win rate | 61.6% | **63.7%** |
| Median | +18.63% | **+21.13%** |
| Mean | +17.89% (comparable) | +17.89% |
| Concentration | 32.6% | **27.3%** |

The ~7% of trades removed (secretly-OTM, matching the 6.6% found earlier) weren't just noise sitting neutrally in the sample — they were injecting occasional huge, unrepresentative convexity wins (ICICIGI +300%, ESCORTS +260%, both gone now) that inflated concentration without helping the typical-case numbers. Cleaner sample, better numbers across the board.

**Checked whether the DTE×moneyness×expiry heatmap (below) needs re-running — it doesn't.** Verified directly: ITM+current (used in that heatmap's core table) was NEVER affected by this bug at all — 0 of 463 ITM+current picks ever flipped OTM under the old logic (front-month liquidity is reliably deep enough near the ITM target; the bug is exclusively a next-month liquidity problem). The heatmap's one-line ITM+next/ATM+next mentions are within-variant deltas (same contract on both the stall and baseline arm), already established as bug-immune regardless. Retracting the earlier "needs re-check" flag on that heatmap — it stands as originally reported.

**Direct follow-up challenge on the fix itself: does `strike < spot_price` actually guarantee ITM, given `spot_price` itself can be wrong?** Yes — this project already found and fixed one version of exactly this risk (2026-09-03, see `option_backtest.py:8-21`): `data_cache` (yfinance) retroactively rescales prices for stock splits/bonuses, so `_real_spot()` prefers the real, never-adjusted NSE cash bhavcopy and only falls back to `data_cache` when that date's cash bhavcopy is missing (tracked via `_MISSING_CASH_BHAV`, never silent). Checked how often that fallback actually happens and whether it contaminates the post-fix ITM+next result: **37 of the trades attempted hit the fallback path, but all 37 are renamed/demerged tickers (ETERNAL/Zomato, TMPV/Tata Motors PV demerger, GVT&D, LTF, LTM, GMRAIRPORT, etc.) whose options chain also has zero rows under the current ticker name on that historical date** — `pick_contract()`'s own `chain.empty` check returns `None` before the fallback spot is ever used to pick a strike. Verified directly, trade-by-trade: **0 of the 523 simulated ITM+next trades in the reported result ever used a fallback spot price.** The residual-risk path exists in the code but empirically doesn't reach any reported trade in this dataset — the fix's guarantee holds for the numbers actually being reported, not just in theory.

## Critic's three pre-trust asks on ITM+current+fast-exit — all three run (2026-09-06)

Critic flagged ITM+current+fast-exit as "not yet real" (5.5/10) pending a year-split, a volatility-regime check, and a sector-neutrality check. Ran all three directly on the matched-pair changed-trade sets (both cut mechanisms).

**1. Year-split (2022-2026):** cut wins on median in 3 of 4 usable years (2022, 2024, 2025 both mechanisms), loses only in 2023 (2026 is a partial year, n=5-7, too thin to trust). Not random — 2023 was already independently established elsewhere in this project as an exceptionally strong bull year (carries the swing-side's own headline number too); a strong year is exactly when letting a position run naturally should beat cutting early. 2025 shows the opposite and biggest swing — baseline was actually negative (−3.32%) that year, cut turns it solidly positive (+10.90% to +35.53%), consistent with a choppier year rewarding an early exit. A coherent, explainable regime-dependence, not noise flipping sign.

**2. Volatility regime** — no real IV column exists in this dataset (would need a Black-Scholes back-out), so used each stock's own ATR% at entry (from `backtest.load()`) as a realized-volatility proxy, split into tertiles. **Cut wins in all 3 tertiles, both cut mechanisms (6/6)** — LOW-vol: baseline already strong (73.0%/+17.85%), cut adds modestly (70.3%/+21.95%); MID/HIGH-vol: baseline flat-to-negative, cut turns solidly positive (e.g. HIGH-vol reactive: −3.32%→+7.23%). Clean pass, with a coherent shape — cutting matters most exactly when volatility (theta/gamma risk) is elevated.

**3. Sector-neutrality** — used `sectors.py`'s ticker→sector map. No single sector dominates the sample (top sector, Financial Services, is 26-30%; removing it entirely, cut still wins on median both mechanisms: +3.98%→+7.31% and +11.75%→+15.63%). Cut wins in 4 of 6 sectors with enough data (n≥8) both mechanisms (Basic Materials, Consumer Cyclical, Energy, Financial Services). **Technology is a real, consistent exception, not a fluke — cut LOSES in Technology both mechanisms** (reactive: win 60.0%→30.0%, median +8.03%→−14.43%, n=10; fixed-3: win 64.3%→35.7%, median +14.51%→−8.88%, n=14). Industrials is a mild wash on the fixed-3 variant only (+17.45% vs +15.75%). Not swept under the rug: this is genuinely useful evidence that the discipline isn't perfectly sector-neutral — plausible mechanism (tech options in this universe may see thinner liquidity or more explosive/sustained continuation moves that a fast cut kills prematurely) but unconfirmed at this sample size, and worth a specific tech-sector exclusion if this candidate is ever adopted.

**Overall: 2 of 3 checks pass clean (volatility, sector-concentration-robustness); the year-split and the Technology sector both surface real, explainable exceptions rather than random noise.** This is stronger, more honest evidence than a blanket "it works everywhere" result would have been — ITM+current+fast-exit looks like a real effect with two known boundary conditions (strong bull years, tech sector specifically), not a universal rule. Still not adopted — same standing rule as everything else, pending outside review.

## CORRECTION to update-16: the "current wins head-to-head 72%" claim was a methodology bug, reversed on the clean sample (2026-09-06)

Update-16 (already sent to the critic) reported: "current-month wins the same trade head-to-head 72% of the time" on n=189 same-strike-matched ITM current-vs-next pairs. **This number is wrong and reverses on correct methodology.** Two stacked problems, both verified directly against the real trade file (`runs/trades_v28_fo.csv`):

1. `pick_contract(expiry_choice="current")` auto-rolls to the next-month expiry when front-month has <5 trading days of runway at entry (`option_backtest.py:150-151`, by-design behavior, not itself a bug). When that rollover fires, "current" and "next" resolve to the **literal same contract** — same expiry, same strike, identical P&L. Of 236 same-strike-matched pairs, **116 (49%) were these collisions**, not genuine current-vs-next comparisons.
2. The original head-to-head comparison used `>=` instead of `>`. Since collision pairs are exact ties, `>=` silently counted every one of those 116 ties as a "current win" — reproduced exactly: re-running with `>=` and collisions included gives 171/236 = **72.5%**, matching the reported figure precisely.

**Corrected methodology** (strict `>`, rollover collisions excluded, n=120 genuine distinct-expiry pairs):

| Metric | ITM Current | ITM Next |
|---|---|---|
| Head-to-head win | 45.8% (55/120) | **54.2% (65/120)** |
| Win rate (own trades) | 50.8% | **58.3%** |
| Avg win / avg loss | 58.4% / −59.9% | 55.3% / −56.4% |
| Expectancy (≈ expected return per ₹10k premium) | 0.21% (₹21) | **8.76% (₹876)** |
| Expected max drawdown (mean/median) | −44.0% / −38.5% | **−32.7% / −25.6%** |
| Median holding days | 7 | 11 |

Next wins on every metric — head-to-head, win rate, expectancy, and drawdown — not just the aggregate median/mean the original (correct part of the) writeup already noted. **Retracting the "reopens the case for current-month" conclusion from update-16 section 3.** This directly answers the critic's own Q2 pushback (their response-16: "head-to-head win rate is the wrong metric without an expectancy table") — with the bug fixed, the expectancy table doesn't just refine the picture, it reverses it in the same direction their skepticism pointed.

Annualized CAGR was also computed (584.5% for next, 7.9% for current) but is flagged as illustrative only — mechanically annualizing an expectancy computed over a 7-11 day median hold isn't a real compounding number and shouldn't be quoted to the critic as if it were.

## MAE (Maximum Adverse Excursion) curve, ITM+current baseline vs fast-exit (2026-09-06)

Critic's ask (response-16): does the fast-exit rule reduce max drawdown-before-exit, not just improve final P&L — "psychologically more attractive," their words. Measured directly: for every matched trade (`stall_pool.csv`/`fixed3_pool.csv`, `changed==True` only — where the fast-exit rule actually fired earlier than the natural exit), walked the ITM+current option's daily closing price from entry to (a) the natural/full-hold exit date and (b) the earlier fast-exit trigger date, and recorded the worst drawdown from entry price reached along each path.

| Percentile | Baseline MAE (10/25/50/75/90) | Fast-exit MAE (10/25/50/75/90) |
|---|---|---|
| Reactive 3-day-stall (n=122) | −66.9 / −50.4 / −23.4 / −4.7 / 0.0 | **−46.4 / −25.9 / −10.4 / 0.0 / 0.0** |
| Fixed-3-after-arm (n=146) | −66.1 / −47.7 / −19.6 / −0.1 / 0.0 | **−46.1 / −23.1 / −7.5 / 0.0 / 0.0** |

Fast-exit roughly halves median MAE in both mechanisms and cuts mean MAE by ~40%, consistent across both trigger mechanisms — not an artifact of one. Confirms the critic's framing directly: cutting early doesn't just help the final number, it genuinely spares the position from the worst of the drawdown path most of the time.

## Trend-persistence test on the Technology exception — critic's hypothesis tested and REJECTED (2026-09-06)

Critic's response-16 proposed that the Technology-sector exception found in the sector-neutrality check (cut loses in Technology, both mechanisms) isn't really about sector — it's about trend persistence (`DaysAboveEMA21 / Last30Days`), which happens to cluster in Tech names in this sample. Proposed this as a better, more general exclusion rule than a sector-specific one.

Tested directly on the same matched-pair pools used for the original sector check. **Result: rejected, not confirmed.** Persistence buckets alone show cut helping in every tercile (low/mid/high), both mechanisms — no threshold separates cut-wins from cut-loses. The decisive crosstab:

| | Reactive | Fixed-3 |
|---|---|---|
| Non-Tech, LOW persistence | n=50, 42.0% beat-rate | n=62, 35.5% beat-rate |
| **Non-Tech, HIGH persistence** | n=51, 52.9% beat-rate, baseline −3.15%→cut +8.50% | n=59, 57.6% beat-rate, baseline −0.58%→cut +16.86% |
| Tech, LOW persistence | n=7, 42.9% beat-rate, both negative | n=9, 44.4% beat-rate, both negative |
| Tech, HIGH persistence | n=3, 33.3% beat-rate | n=5, 20.0% beat-rate |

The critic's exact prediction — high-persistence (trending) names get hurt by cutting — is contradicted by the largest, most trustworthy subgroup here: non-Tech high-persistence trades (n=51/59) show cut helping strongly (baseline flat-to-negative, cut solidly positive), the opposite of the predicted direction. Tech trades lose to cut regardless of their own persistence score (both Tech sub-splits are thin, n=3-9, but point the same direction as the original all-Tech result). **Sector-based Tech exclusion remains the better-supported rule; persistence is not a valid substitute for it.**

## Trigger-breach follow-through: how far does price run past the 0.3-0.6% entry, and a real next-day exit-timing edge for options (2026-09-06)

Triggered by a direct observation ("breakout day itself is a high, then another high, then a red candle — profit booking") and a question about whether the 0.3-0.6% entry-clearance band (adopted 2026-09-05) leaves any real room, or eats the whole known "+1% from pivot" edge. All of this is scoped to **Breakout Continuation only** (the pattern with a `high10_prior`-based trigger; VCP doesn't use this mechanism), using `runs/trades_v28.csv` filtered to `pattern=="breakout_cont"` (n=767).

**Real trigger-fill reconstruction, not Close-based approximation.** The live entry mechanism (`live_checkpoint.py`'s `TRIGGER_CLEARANCE_LOW/HIGH` = 0.3%/0.6% above `high10_prior`, a limit order) was reconstructed from each day's actual Open/High rather than using the backtest's Close-based `entry_price` (which is provably biased — Close on a strong day is often well past the real trigger band, systematically understating true remaining room). Fill logic: `Open > trigger_high` → gapped-through miss, excluded (41/767, 5.3% — these never actually fill under the real limit-order mechanism); `Open` already inside the band → fill at Open (14 trades); `Open` below the band but day's `High` reaches it → fill approximated at `trigger_low` (710 trades, the dominant case — exact intraday fill point isn't recoverable from daily bars, but this is a defensible best-case-within-band approximation, much less biased than Close). 2 trades never reached the band that day at all, excluded. **Final n=724.**

**MFE (Maximum Favorable Excursion) from the real fill price:**

| Horizon | Median MFE | ≥1.0% | ≥2.0% |
|---|---|---|---|
| Day0 (breach day itself, same-day) | +2.38% | 82.9% | 58.7% |
| +1 day | +3.76% | 91.0% | 75.3% |
| +3 days | +4.87% | 95.0% | 84.8% |
| +10 days | +7.15% | 97.7% | 92.5% |
| Ever (to actual exit) | +7.48% | 98.6% | 94.3% |

**Verdict: substantial real room exists beyond the clearance band — the earlier "0.4-0.7% remaining edge" guess badly undersold it.** Day0 alone (same-day continuation after the breach) is methodologically safe to measure this way — unlike the earlier-established Close-based day0 flaw (Close is fixed at day's END, so day-High-vs-Close ordering is ambiguous), fill_price here is anchored at the START of the price path (Open, or the first upward crossing of `trigger_low` from a lower Open), so by simple continuity the day's High can only occur at or after the fill — no lookahead ambiguity.

**Day+1 behavior — the "another high, then red candle" pattern, confirmed directly and precisely (n=724):**

| | % of trades |
|---|---|
| Gaps up next day (Open1 > Close0) | 71.3% (median gap +0.58%) |
| Makes a NEW high beyond day0's own high | 77.5% |
| Closes RED on day+1 | 56.1% |
| Closes BELOW day0's close (net given back) | 47.9% |
| Gaps up AND still fades to close red (single most common outcome) | **41.2%** |
| Makes a new high intraday, then reverses to close red | 36.0% |
| Gaps up and stays green (real continuation) | 30.1% |

Median day+1 High is +0.87% above day0's High, but median day+1 Close is only +0.08% above day0's Close — essentially flat. The gap-up and the intraday new high are real and common; keeping them by day+1's own close is not.

**Options-side test: buy ITM/ATM at the trigger-confirmed entry, exit at day+1's option price.** Reused `option_backtest.py`'s `pick_contract`/`option_row` (entry = day0 `ClsPric`, same convention as the rest of this project's options work — options data is daily bhavcopy only, no intraday option ticks exist historically, so this is a known, already-flagged approximation; see caveat below). Contract-availability dropout is real: of 724×2 attempts, 171 (ITM) / 170 (ATM) had no valid liquid contract that day — final n=466 (ITM) / 497 (ATM) for the unconditional test.

| | Next-day OPEN exit | Next-day CLOSE exit | Day+3 CLOSE exit |
|---|---|---|---|
| ITM | 52.8% win / +0.57% median / conc 63% | 49.1% / −0.21% / 66% | 48.1% / −2.28% / **185%** (untrustworthy) |
| ATM | **66.0% win / +2.85% median / conc 33%** | 41.6% / −4.68% / 149% | 42.8% / −7.84% / 208% |

ATM's next-day-open exit is the one genuinely trustworthy cell here (sub-100% concentration; the close-based exits are dominated by a handful of outsized trades). **Gap-conditional split makes it sharper still** — this isn't a blanket rule, it's conditional on the gap:

| | ITM (n≈329) | ATM (n≈356) |
|---|---|---|
| Gapped up → exit at day+1 open | 61.5-61.1% win / +2.45-2.46% median | **81.9-82.0% win / +5.03% median** |
| No gap/gapped down → exit at day+1 open | 33.3% win / −2.33% median | 28.4% win / −2.18% median |

**For the no-gap subset, holding longer only compounds the loss — no recovery pattern at all.** Walked the same no-gap trades forward: ATM median goes from −2.18% (day+1 open) → −9.71% (day+1 close) → −20.24% (day+3) → −31.11% (day+5) → **−37.29% (day+10)**; ITM shows the same monotonic direction, milder. Root cause, diagnosed directly: median DTE at entry is 15 trading days (range 5-28), so by day+10 the median position has only ~5 DTE left — the steepest part of the theta curve — while the underlying **stock's own median move stays small and flat the whole time** (−0.4% to −1.3%, never trending down hard). The option bleeding out while the stock does nothing bad is a theta signature, not a delta one. (The gap between stock mean −9% and median −1% shows a real minority of trades do crash hard — those get hit by theta AND delta together, which is why the option's mean loss is worse than its already-bad median.)

**Tested whether a mid-hold "roll to next month if DTE<5" rule fixes the no-gap decay — it doesn't, it only softens it.** Simulated rolling (sell current contract, buy a fresh same-moneyness contract in the next expiry) the moment DTE drops below 5 during a hold, for the no-gap subset held to day+10: win rate is **completely unchanged** (ITM 42.0%→42.0%, ATM 29.8%→29.8%) — rolling never flips a losing trade into a winner, it only reduces severity for the subset that actually triggers it (of 15 ITM / 22 ATM trades that hit the threshold within 10 days, median loss softens from −61.61%→−46.41% (ITM) and −93.81%→−81.01% (ATM), still deeply negative). Makes sense: rolling resets the theta clock but does nothing about delta — if the stock isn't cooperating, a fresh contract still won't make money. Damage control, not a fix, and doesn't change the standing recommendation below.

**Tested whether "wait through the gap-up with a trailing stop" beats exiting immediately at day+1 open — it doesn't, decisively, for any stop width tried (10/15/20/25/30%).** Every trailing-SL variant collapsed win rate (ATM 82.0%→~30%) and turned the median deeply negative (ATM +5.03%→as low as −30.56%), and even head-to-head, waiting-with-SL only beat the immediate-open-exit 27-32% of the time. **But this is NOT because the extra room doesn't exist** — checked directly: 88.4% (ITM) / 75.6% (ATM) of gap-up trades DO eventually reach a materially higher peak later (median peak gain +45.39% ITM / +78.15% ATM, vs the open-exit's median +1.43%/+4.92%), typically around day 6-7. The room is real and large; a flat % trailing stop on the option's own noisy daily price just isn't the right tool to hold through the (non-monotonic, choppy) path to get there — it gets whipsawed out well before the real peak. A smarter mechanism (this project's own validated stock-side stall/fixed-3-day exit logic, rather than a raw option-price stop) is the natural next candidate here, not yet built.

**Restricting to day+1 only (Open vs intraday High vs Close, gap-up subset) makes the same point most sharply:**

| | Open | High (same day) | Close |
|---|---|---|---|
| ITM | 61.1% win / +2.45% median | 84.5% win / **+13.36%** median | 53.8% win / +1.82% median |
| ATM | 82.0% win / +5.03% median | 97.8% win / **+20.74%** median | 45.5% win / **−2.59%** median |

Enormous room exists *within day+1 itself* — but it's gone by that same day's close (ATM median goes from +5.03% at open to −2.59% at close). The open isn't the ceiling, it's a safe floor; the real opportunity is intraday on day+1, not a multi-day hold.

## Equity-side exit shape: winner convexity refuted, a real partial-exit improvement found, and a deterministic Risk-of-Ruin table (2026-09-07)

Triggered by a critic question about the win:loss R-shape (production system is ~0.92:1, not the "1:3" ideal) and their response — three pieces, all on the equity swing side (both patterns combined, full v28 production population).

**Winner R-histogram — refutes the critic's "hidden convexity" hypothesis.** They guessed 40% of winners below 1R, 15% above 2R, 5% "monsters." Actual (n=930 winners): 70.5% below 1R, only 4.8% above 2R, only 1.1% monsters (3R+). Top-10 winners are just 4.4% of total winner R — no meaningful convexity exists to protect. Root cause found directly: 93.4% of all wins exit via the resistance target, and `resistance_target()` has zero minimum-distance floor — it fires the instant Close reaches the nearest daily pivot above price, however close. The system is mechanically incapable of producing convexity; it caps almost every winner at the first pivot touch. Median payoff ratio (0.670R/1.018R = 0.659) is worse than the mean-based one (0.921) — the typical trade's shape is worse than the average implies, not rescued by a hidden tail.

**Minimum-R gate on the resistance exit — 0.5R is a real, clean improvement; 1R+ is the same "chase the tail" trap as everything else this session.** Required price to clear a minimum R before the resistance exit is allowed to fire (skip the touch otherwise, keep trailing):

| Gate | Win rate | Median | Mean | Winners→losers |
|---|---|---|---|---|
| Baseline (0R) | 65.5%* | +2.93%* | +1.86%* | — |
| **0.5R** | 59.5% | **+3.85%** | +2.03% | 9.1% (85/930), gave up +2.40% median for −3.82% |
| 1.0R | 53.4% | +0.71% | +2.50% | 18.5% |
| 2.0R | 51.3% | +0.17% | +3.08% | 21.8% |
| 3.0R | 51.2% | +0.15% | +3.64% | 21.9% (plateaus — most trades reaching 1R don't reach 3R) |

*(re-simulated for this test, minor variance from the checked-in 65.0%/+2.89% baseline — re-simulation noise, not a discrepancy.)* 0.5R genuinely improves median AND mean together at a bounded, real cost. 1R+ collapses median toward zero while mean keeps climbing — propped up by a shrinking number of bigger winners, the same shape already rejected this session for Energy Stall, trailing stops, and the fixed-3-day exit.

**"Close back below entry pivot = failed breakout" early-exit — tested, REJECTED.** Fires on 35-49% of ALL trades (not rare), and even requiring 2 consecutive closes below pivot (not just 1) still catches 30-48% of what would have been real winners, converting them to guaranteed small losses (mechanically: falling back to the pivot means price is at/near entry, so this rule can never itself produce a win). Root cause: retesting the exact breakout level before continuing is completely normal behavior in genuine winners, not a failure signal — this rule can't distinguish the two. **However**, isolated specifically to trades that were ALREADY going to lose under baseline: the rule roughly halves the loss 87-96% of the time (Breakout Cont: median −7.82%→−3.85%, worst −21.54%→−13.27%; VCP: −7.17%→−3.75%, worst −13.66%→−7.75%) — a real, useful loss-containment property on its own terms, just not a net-positive rule once winners-cut-short are included. Net aggregate pnl_pct sum across all trades: worse both patterns (BC: 1604→1024; VCP: 1051→987).

**Dynamic partial exit (critic's Part-8 ask) — the strongest result of this thread.** Sell 50% at first resistance touch (their literal spec, unconditional), trail the remaining 50% with the same stop:

| | Win rate | Median | Mean | Concentration |
|---|---|---|---|---|
| Baseline (100% at resistance) | 65.0% | +2.89% | +1.86% | ~8-10% |
| Partial exit, critic's literal spec (50/50, any touch) | 60.5% | +1.97% | +3.27% | 6.8% |
| **Partial exit + 0.5R gate on the trigger (own extension, beyond the "one backtest" instruction)** | 58.7% | **+2.20%** | **+3.36%** | **6.5%** |

Nearly doubles the mean vs baseline, concentration stays excellent (broadly distributed, not lumpy) — real convexity created where none existed before, at a modest bounded cost (7.6-10.3% of baseline winners become small losses). The 0.5R-gated version beats the critic's own literal spec on every metric simultaneously — best combined result found this session.

**Deterministic Risk-of-Ruin table (critic's Part-7 ask) — real methodology snags found and fixed before trusting it.** A naive `entry_date`-sorted sequential streak (matching the critic's own L-L-W-W-W illustration) is invalid here: **95.3% of all trades share their entry date with at least one other trade** (up to 23/day) — this is a multi-ticker scanner, not one-position-at-a-time, so chronological sort order doesn't represent a real sequential experience. A first "worst streak" number was contaminated by this; a second attempt had a genuine bug (`pandas.idxmax()` on a grouped streak-length column returns the group's FIRST row, not its last, silently producing a window straddling two different streaks) — caught before reporting, fixed, and the final version verified with an explicit assertion (every value in the reported window is genuinely ≤0).

**Resolved with an explicit max-5-concurrent-positions cap** (deterministic, capital-agnostic — no rupee/position-sizing model needed, avoids reopening the already-distrusted portfolio-simulation question): admit a new signal only if fewer than 5 positions are open, skip otherwise.
- 244 of 1430 signals admitted (1186 skipped) — this scanner generates ~6x more candidates than a 5-position book can act on.
- Final cumulative result: +64.56R (~₹64,560 at ₹1,000/R) over ~4 years.
- Max drawdown: −6.96R (~₹6,963), near the end of the dataset (Oct 2025), not yet recovered but only 15 trades of runway remained after it — inconclusive, not a red flag.
- **Worst genuine consecutive losing streak: 6 trades** (2024-12-13 to 2025-01-02), R-multiples [−1.07, −1.13, −1.36, −1.15, −0.43, −1.06], totaling −6.20R (~₹6,198) — nearly the entire max drawdown by itself. Real, bounded answer to the original "capital wipeout from an unlucky start" concern: worst historical case was ~₹6,200, not a wipeout.

Nothing here adopted yet — same standing rule as everything else, pending outside review. Full submission compiled and sent as update-19.

**Not pursued tonight, deliberately deferred to forward/live experience rather than more backtesting**: a "check price after the first 30 minutes, then set a stop" refinement. Checked feasibility first — real intraday data only exists for a trailing ~90-day window (`intraday_cache.py`, 2026-06-10 to 2026-09-04), and **zero of the 516 gap-up trades in the historical population fall inside that window** (same "backtest population predates the intraday cache" gap already documented for the earlier intraday +1% test). A real test would need a fresh universe rescan inside the live window, PLUS a Black-Scholes option-pricing layer (no intraday option data exists at all, only intraday stock data) — two real builds, not attempted here. Explicit user call: learn this specific piece live rather than backtest it.

**Standing caveat, honestly stated**: every options number above uses day0's option `ClsPric` as entry price (options data is daily bhavcopy only). Given the established day0/day+1 continuation pattern, the option's Close is almost certainly higher than its true price at the actual breach instant — meaning these backtested returns are likely a **conservative underestimate** of what a real trigger-moment entry would achieve, not an overstatement. A Black-Scholes IV-backout could tighten this if pursued later; not necessary for the qualitative conclusion below.

**Practical rule this produces, ready for paper-trading**: buy ITM/ATM at the live 0.3-0.6% trigger breach (real broker quote, not backtested). Next trading day: check the gap. Gapped up (71% of the time) → exit near the open, don't hold for the close (82% win / +5.03% median, ATM) — the real intraday-high opportunity (median +20.74%) is worth watching for live, but the close gives most of it back regardless. Didn't gap up → exit immediately too, don't hold and hope — there's no recovery pattern, only compounding theta bleed with no offsetting stock move. Not yet adopted into any code — paper-trade candidate only, per standing rule.

## Live volume checks built and a re-test of the volume-as-ranking-signal rejection (2026-09-07, live trading day)

Triggered by a real live mistake: claimed NIACL's volume was "183% elevated" (vs a 20-day trailing average) when a candidate first fired — wrong. The 20-day average was itself contaminated by including NIACL's own 66.9M-share breakout day (2026-09-04), making a merely-average follow-through day look artificially elevated. Compared directly against the user's own chart: today's volume was actually only ~20-25% of the breakout day's — a weak continuation, the opposite conclusion.

**Fixed with two new live checks, built and wired into `live_checkpoint.py`/`trader_dashboard.py`**: `vol_vs_normal_pct` (live volume-so-far vs the median of the last 25 cached days, EXCLUDING any day already inside an extension run, scaled by elapsed session-time fraction — always computable) and `vol_vs_breakout_pct` (for `extension_days>=1` tickers only: live volume-so-far vs the actual breakout day's own volume, same elapsed-time scaling — the check that actually caught NIACL's real, weak continuation: 47% of the breakout day's pace).

**Re-tested whether this properly-constructed volume metric changes an earlier rejection** (`FINDINGS.md`'s "Round-12" section: blending a raw volume-rank into the validated same-day distance-to-trigger ranking dropped Recall@1 60.7%→44.3%, "distance is already close to a direct measure of the outcome, blending in noise only hurts"). Reconstructed the same Recall@K methodology (62 real trading days, full `intraday_cache.py` window, 10:00 checkpoint, 0.5% clearance) with `vol_vs_normal_pct` blended in instead of the old crude volume-rank:

| Weight (distance/volume) | Recall@1 | Recall@2 | Recall@5 |
|---|---|---|---|
| distance_only (baseline) | 67.7% | 83.9% | 91.9% |
| 90/10 | 56.5% | 80.6% | 93.5% |
| 80/20 | 56.5% | 79.0% | 93.5% |
| 70/30 | 62.9% | 75.8% | 90.3% |

**The original rejection mostly holds — Recall@1/@2 still degrade at every weight** — confirming distance really is close to a direct measure of the outcome, not just an artifact of the old, cruder volume metric. Milder degradation than before (worst case 56.5% vs the original 44.3%), and Recall@5 improves slightly (91.9%→93.5%) at the lighter weights.

**But a bucket check reveals a real, narrower use volume DOES have**: within just the closest 20% by distance (n=772, candidates already similarly close to firing), fire rate by `vol_vs_normal_pct` quartile — Q1 (low volume) 18.7% → Q4 (high volume) **41.9%**, more than double, a real monotonic-ish gradient. Volume carries genuine independent information; a global rank-blend just doesn't exploit it correctly, because it reshuffles which single candidate lands at rank 1 rather than using volume as a **tiebreaker among already-similar-distance candidates**. That's a distinct, narrower mechanism from both the original rejected test and this re-test — not yet built or tested as its own thing. Directly validated against a real live case the same day: MOTILALOFS and IDEA were both close-distance AND high-`vol_vs_normal` simultaneously, matching exactly the combination this bucket check says should matter.

Not adopted into the ranking yet — real, promising lead for a future "volume as tiebreaker within a tight distance band" test, distinct from what's been tried so far.

## The live gate is broader than every backtest tested so far, a real Freshness Score + RVOL@Trigger fix wired in, and entry-timing delay (streak/acceptance confirmation) shown to erase its own edge (2026-09-13)

**Discovery: `live_checkpoint.py` never calls `checklist_pass()`/`breakout_continuation()`'s Close-based confirmation.** It only calls `base_filters_pass()` (multi-day trend/RSI/liquidity setup) plus an intraday price cross of the trigger band. Every backtest win-rate number produced up to this point (all built on the `checklist_pass`-gated population, ~1,600-1,646 trades) was therefore measured on a hindsight-narrowed, unrealistically strong subset. The honest live-equivalent population is far larger — **~10,764-14,225 real breaches**, baseline win **53.5-55.1%**, median **+0.13-0.16%** (day+1 options metric) — essentially a coin-flip, not the confident edge every prior number implied.

**Freshness Score built and wired in** — a continuous replacement for the old boolean RSI-OR-momentum filter: `0.5 × RSI14_percentile + 0.5 × momentum20d_percentile` (lower = fresher/less extended), percentiles computed against fixed empirical breakpoints from the full 14,225-trade population (not a live cross-sectional rank, so it's stable candidate-to-candidate). Strictly beats the boolean OR at matched population sizes: **65.0% win / +0.52% median** vs the OR's **62.4% / +0.43%** at similar/larger n. Wired into `live_checkpoint.py` (`_fresh_setup`, `_freshness_score`, printed in `_print_tier` as `freshness=NN%`).

**RVOL@Trigger fixed** — the old `_elapsed_session_fraction` assumed volume accrues linearly through the session (uniform intraday distribution), which is wrong; real volume is front/back-loaded. Replaced with `_clock_time_volume_fraction`: a real clock-time-matched median of how much of a full day's volume has historically traded by this exact time, computed from `intraday_cache`, falling back to the old linear assumption when insufficient intraday history exists. Wired into `classify_candidates`.

**ATR-extension tested as a third orthogonal axis, rejected** — hypothesized it would capture something RSI/momentum miss (how far price has run vs its own volatility). Correlation with RSI: **0.806** — not orthogonal, redundant. Not added.

**The core finding of the day: acceptance/streak-based entry confirmation is a genuinely good SELECTION signal but cannot be used as an ENTRY-TIMING signal — waiting to observe it costs exactly the edge it identifies.** Tested requiring N consecutive 5-min closes above the trigger (retry allowed after a broken streak) before firing, per the critic's "Acceptance Delay" proposal.

Filter-only (hindsight) view, entry priced at the ORIGINAL trigger but only keeping trades that eventually satisfy the streak (n=934 pool) — looked excellent: baseline win 57.3%/median 0.25% → streak≥3 (74.1% kept) win 71.1%/median 0.74% → streak≥5 (67.7% kept) win 74.1%/median 0.86%, concentration sane throughout (13-17%), rejected trades win only 13-22%. **This is hindsight bias** — you don't know a stock will satisfy the streak until it does, and by then price has moved. Rebuilt with the REAL entry price (the close of the bar where the streak first completes): win collapses to **57.5%/median 0.20%** (streak≥3, n=692) — barely above the 57.3% baseline — and **55.9%/median 0.17%** at streak≥5, actually below baseline. Median premium already paid by the time of firing: 0.44% (streak≥3), 0.60% (streak≥5).

Mechanism, quantified directly: day+1's exit price is fixed regardless of entry timing, so every trade's return shifts down by the premium paid to wait. **94 of 692 trades (13.6%) flip from win to loss** on a median premium of 0.90% (vs 0.44% overall); of "thin winners" (0-1% hindsight gain), **38.4% flip** on a median premium of just 0.31%. Tried shorter waits too (1/2/3/5 bars = 5/10/15/25 min) — all underperform zero-wait; even one 5-min bar of delay costs more than it buys.

**Confirmed on the real swing exit too, not just the day+1 options metric** — turned options off, tested against `check_exit()` (3×ATR trail + resistance target), same matched population (n=692, all three entry ideas available): (A) day0 raw trigger immediate — win 63.5%/median 2.06%/hold 10d; (B) day0 streak-confirmed real price — 62.1%/1.58%/10d; (C) day1 open, the project's original "wait for close, confirm next day" idea — 60.4%/1.51%/9d. Immediate entry wins on median under either exit regime; this isn't an options-only artifact.

**Fair-comparison correction applied**: an earlier version of this test forced ideas A/B/C onto the SAME artificially-filtered population (only trades achieving streak≥3), which meant C was never actually filtered by its own natural EOD-confirmation criterion, and right-censored ("still open") trades were silently dropped from win-rate/median without disclosure (12-13% of the population, skewed negative — e.g. idea A's closed-only win rate 63.5% dropped to a blended 59.8% once opens were included at their current mark). Rebuilt so each idea uses its own natural population (A: full 14,225; C: EOD-confirmed n=3,256; freshness-only n=3,554; streak-only n=692) and reports blended (not closed-only) stats.

**Pullback anatomy after real streak-confirmed acceptance** (n=690, streak≥3): 78.8% pull back near the trigger later the same day, 68.0% actually break back below the trigger, 41.6% go all the way back to the raw pivot (`high10_prior`). Only **21.2% "run away" without ever pulling back — and this group is the best-quality trade population found all session (98.6% options win rate, 64.4% swing win rate)**. Any retest/pullback-requiring entry rule systematically filters out the best trades, not the worst ones.

**Practical framing — "take all breaches" vs "only act on visible pullbacks"** (the realistic live choice, since fast run-away moves are easy to miss when not watching live): restricting to pullback-only removes almost no bad trades but forfeits most of the edge —

| | n | losing trades | total loss | total gain (winners) | net |
|---|---|---|---|---|---|
| All breaches — options | 690 | 199 (28.8%) | -233.5% | +995.3% | +761.8% |
| Pullback-only — options | 544 | 197 (36.2%) | -231.3% | +476.7% | +245.4% |
| All breaches — swing | 690 | 277 (40.1%) | -1648.2% | +2266.2% | +618.1% |
| Pullback-only — swing | 544 | 225 (41.4%) | -1414.6% | +1555.7% | +141.1% |

Of the 146 trades dropped by requiring a pullback, 144 were winners and only 2 were losers (options) — the run-away group isn't noise to safely skip, it's the best trades, and there's no way to identify them ex-ante from post-trigger price action without giving up the edge to the premium paid.

**Consolidation-days signal validated separately** — count of days (20-day lookback) where Close sat within 3% below `high10_prior` before the breach. Correlation with formal VCP-base detection: **-0.038**, i.e. genuinely not redundant with the existing VCP detector. Full integer sweep (0-15 days) shows smooth improvement to ~10-12 days, then a concentration explosion (noise, not signal) beyond day 13. ≥3 has the best median/lowest concentration/largest sample; ≥8-10 shows better expectancy but on a smaller, noisier sample. No single clearly-best cutoff — ≥3 is the defensible, conservative choice; ≥8-10 is a real but less certain alternative.

**Best realistic combined swing filter found this session: streak + freshness together, 62.0% blended win rate, n=187** over the available window — checked for practical clustering (66 trading days, 18.2% of days produce zero candidates) rather than assumed tradeable.

**Standing framing correction, made explicit after user pushback**: none of today's filters "beat" the 14,225-trade unfiltered baseline in a simple win-rate sense, but that comparison is not meaningful — it is not operationally possible to take 14,000 trades. The real, actionable framing is **capital efficiency**: freshness/streak/consolidation filters achieve similar-or-better per-trade quality on 4-25% of the trade count, which is the actual lever available (fewer, better-chosen positions), not a race against an infeasible "take everything" baseline.

**Where this leaves us, unresolved**: confirmation/acceptance is real as a selection signal but unusable as an entry-timing signal — every delay variant tested (1/2/3/5-bar streak, day+1-open) underperforms immediate entry at the raw trigger. Two live options, neither built yet: (1) find a pre-breach or breach-candle predictor of "will run away cleanly" that doesn't require waiting to observe it (five separate volume-based attempts at a real-time discriminator failed this session — see the four rejections above and in the 2026-09-07 section); or (2) stop gating entry on confirmation at all — enter unconditionally at the raw trigger (wins on win-rate and median under both exit regimes), and use acceptance/non-acceptance in the following bars only for position sizing or stop-tightening, never as a go/no-go gate. Posed to the critic as update-27, not yet resolved.

**Critic follow-up: built the "predict Runaway vs Pullback at breach time" test they proposed instead of predicting acceptance — the headline new feature looked strong, then failed the real check.** Population: n=690 (same real streak-confirmed set). Two new features built: Breakout Body Expansion (`|Close-Open|/ATR14` on the breach bar) and RVOL@Trigger (implied full-day volume pace vs the 20-day trailing average, clock-time-scaled). Against the `ran_away` label (never revisits trigger intraday) itself, body_atr looked like a genuinely strong, clean signal — rank-corr **0.223**, quartile spread **14.5% → 37.6%** runaway rate (2.6x) — the strongest of every feature tested including freshness (-0.082, weak).

**But checked against actual win rate — the metric that matters — body_atr collapsed to the weakest, noisiest feature in the set** (corr 0.032, non-monotonic: 71.7%/68.0%/69.2%/75.7%), while freshness stayed dominant (corr **-0.194**, quartile spread **84.4% → 61.8%**). Freshness × body_atr on real win rate: within the Fresh bucket, body_atr moved win rate only 78.1%→77.8% (a wash) — freshness alone did all the work the interaction had appeared to show on the runaway label.

**Root cause, decomposed rather than left as "data says no"**: `ran_away` is close to a perfect win proxy on its own (98.6% win when true, 63.8% when false), so a real runaway-predictor should transfer to win rate — it didn't, because within EITHER species (ran_away vs pulled-back), win rate stayed flat regardless of body_atr (pullback-subset win rate actually drifted slightly down, 67.6%→61.1%, as body_atr rose). Body_atr's only lever was nudging what fraction of trades land in each species (12-38%, non-monotonic at the quartile level) — a small, noisy effect. Freshness, by contrast, moved the **pullback subset's own win rate by 24 points** (79.2%→55.4%) — it predicts quality *within* the 79%-majority species, which is where nearly all the real win/loss variance lives, since the runaway subset is already win-saturated either way. Conclusion: body_atr (and close_pos, weakly) describe *how* a trade wins — the shape of the path — not *whether* it wins; freshness (and consolidation_days/dist_to_trigger_pct, more mildly) predict quality regardless of path shape, which is the actual lever. "Predict runaway" was the wrong target — species membership and trade quality are close to orthogonal here.

RVOL@Trigger left genuinely inconclusive, not rejected: only 364/690 trades have enough intraday history to compute it, and the quartile pattern is non-monotonic (Q3 peaks at 83.5% win/+1.18% median — the best cell in the whole table — then Q4 drops to 69.2%), which could be a real u-shape or could be noise at n=91/bucket. Not resolved either way; posed to the critic as update-28.

**Options vs swing reconciliation on the runaway-prediction feature set (added, matching the standing rule to always report both exit regimes)**: every feature above was only tested against the options day+1 metric. Added the real swing exit for the same n=690 population — freshness is the only feature that survives on both sides (swing corr -0.068, quartile spread 63.6%→53.8%, real but ~1/3 the size of the options effect), everything else (consolidation_days, dist_to_trigger_pct, close_pos, body_atr, rvol_at_trigger) goes to flat/noisy or mildly negative on swing. Cross-checking consolidation_days specifically against its own earlier validated finding (`swing_outcome_by_filter.py`, full unfiltered population) resolved what looked like a contradiction: it's a real population effect, not a bug — consolidation_days shows a genuine ~5pp swing lift on the broad population (58.9%→63.6% win, 0-2 vs 6+ days) but the lift disappears/reverses once streak-confirmation is already applied (58.2%→55.8% on the n=690 streak-confirmed subset) — streak-confirmation and consolidation_days are redundant proxies for the same underlying "genuine breakout" quality, not independent/stacking filters.

**Critic follow-up, all five outstanding items from their update-28 recommendation list tested (2026-09-13, continued)**:

1. **Premium Tolerance / Fragility reframe** (win/loss → continuous magnitude + a fragility label: would this winner flip to a loss on the real 0.44% median premium found in the acceptance-delay work?). Freshness dominates continuous magnitude even more than it dominated win rate (Pearson -0.228 options / -0.119 swing; swing's worst quartile mean goes negative, -0.44%, which the win-rate view alone didn't surface). **Body/ATR, dead on win rate, is the second-strongest predictor of fragility** (rank-corr -0.133, fragile rate 25.2%→11.4% top-to-bottom quartile among winners) — checked for outlier inflation (top-10 concentration in its best magnitude quartile: 32.1%, elevated but under the 40% danger threshold, median holds without the tail) — real, not just a few big trades. Body/ATR's actual home turned out to be fragility, not win-rate or runaway-shape.

2. **Freshness × Distance and Freshness × Consolidation interactions**: both tested with an explicit additive-model check (actual cell mean vs. what pure addition of each margin would predict). Cross-terms in both cases were near zero (-0.21 to +0.22 percentage points) — **both interactions are purely additive, no real synergy**. A linear combination model is sufficient; no special-cased interaction logic needed.

3. **Velocity backfilled into historical research for the first time** (`velocity_pct`, closing speed toward the trigger over the 10 minutes before the breach bar — exists live in `live_checkpoint.py`, never in a research population before; only 377/690 trades have enough pre-breach intraday history to compute it). Standalone: weak, non-monotonic/U-shaped (Pearson +0.101 options, -0.008 swing). Freshness × Velocity: the one consistent pattern is that fast-approaching breakouts do slightly worse on swing in both freshness buckets (~6pp) — modest, directionally consistent, not strong enough to call validated, flagged as a weak lead only.

4. **Incremental/combined model** (OLS on rank-transformed features, cumulative R² against continuous pnl, n=377 matched population): Freshness alone → R²=0.0587 (options); + Distance → 0.0694; + Velocity → 0.0730; + Consolidation → 0.0778. Freshness alone captures 75% of the full 4-feature model's explained variance on options; the other three each add small, similar-sized increments (0.4-1.1pp of R²). On swing, total explained variance across all four features tops out at 0.0218 — essentially nothing; the continuous swing outcome is dominated by noise/path-dependence these entry-side features don't capture, far more than options.

5. **Acceptance as an execution-state variable — tested literally, REJECTED.** The critic's state-machine proposal: leave entry at the raw trigger (unchanged, already validated as optimal), but tighten the trailing stop (`ATR_TRAIL_MULT` 3.0→1.5) specifically for trades that never reach streak-confirmed acceptance the same day (state = Rejected), leave accepted trades at the normal stop. Tested on n=934 (all raw-trigger entries, not streak-pre-filtered): baseline (normal stop for everyone) wins 58.5%/+1.24% median/+0.47% mean; the rejected subset alone at the normal stop is already worse (54.5%/+0.70%/-0.73% mean) than accepted (59.8%/+1.48%/+0.89%) — a real quality gap exists. But **tightening the stop on rejected trades makes them meaningfully worse, not better** (54.5%→42.1% win, +0.70%→-2.03% median), and the full state-dependent combined rule underperforms the do-nothing baseline on every metric (55.2% vs 58.5% win). Same failure mode already found and rejected earlier this project (2026-09-07, "close back below entry pivot = failed breakout" early exit): retests/non-acceptance are normal behavior even in eventual real winners, and a tighter stop whipsaws out the ones that would have come back, converting recoverable trades into locked losses.

**Backlog closeout (2026-09-13, continued): RVOL@Trigger's final audit, plus three items from the critic's original response-21 track list that had never been done at all.**

**RVOL@Trigger final audit — CORRECTED (2026-09-13, later same day): the "real, options-only" verdict below does not survive using the actual production denominator, reverts to inconclusive/rejected.** First pass (larger population, n=522, real decile sweep) used `vol_mean20_prior` (a plain 20-day mean, no exclusion) as the "normal volume" denominator and found what looked like a clean, near-monotonic options win-rate climb (43.4%→69.2% across D1-D8). But `live_checkpoint.py`'s actual production baseline (`_normal_day_volume_baseline()`) is the **median** of the trailing 25 days, **excluding any day already inside a breakout run** — specifically built that way to stop a recent volume spike from inflating what counts as "normal." Re-ran the identical decile audit with the correct production formula: the clean climb disappears entirely (deciles bounce 50.0%-63.5% with no trend, Pearson corr drops from the earlier +0.126 rank-corr to +0.096). Checked whether that residual spread is even real: at n≈52/decile, the standard error alone is ±6.9 percentage points (95% CI ±13.5 points) — and the full observed spread across all 10 deciles (13.5 points) is exactly that noise width. **Corrected verdict: RVOL@Trigger shows no usable signal on the production-correct baseline — reverts to inconclusive/rejected, not promoted.** The earlier "real" read was an artifact of a denominator that let recent breakout-day volume spikes inflate the "normal" baseline for exactly the stocks most likely to be firing again — the precise bug the production formula was built to avoid. Flagged as a correction to the critic (update-31's claim was premature).

~~RVOL@Trigger final audit — flips from "inconclusive" to real, options-only.~~ *(superseded by the correction above)* Larger population (n=522, up from the earlier n=364) and a real decile sweep instead of quartiles. Options win rate climbs 43.4%→69.2% across D1-D8 (7 increases, 2 decreases across 9 steps — essentially monotonic, one likely-noise dip at D9, n=52/decile). Swing stays noise (rank-corr -0.044). Checked for outlier inflation: bottom-30% vs top-30% shows a real win-rate/median lift (47.1%→63.1% win, -0.15%→+0.43% median, not outlier-dependent) but the mean-based lift has 65.5% top-10 concentration — above the 40% danger threshold, tail-driven.

**Missed Winner Audit (response-21, never done before today) — quantifies the false-negative cost of each filter.** Of all big winners (top quartile of pnl, fixed absolute bar) in the full ~14,215-trade population: freshness-filtering (fresh half vs extended half) misses **43.3%** of them (1,540 of 3,554) — a real, meaningful cost of an otherwise-validated average-quality filter. Streak/acceptance-filtering misses only **0.4%** (1 of 241, on the n=961 subset with intraday coverage) — the rejected-by-streak group's total pnl is -342.6%, essentially all losers. Streak/acceptance is close to a perfect real-time separator of genuine winners; freshness is a much leakier, probabilistic one. Sharpens the existing update-27 finding (acceptance is a great selection signal, unusable as an entry-timing signal) — it identifies winners almost losslessly, but by the time it's observable the entry premium has already erased the edge.

**Winners-vs-fakeouts streak-length experiment (the critic's literal response-23 proposal, run for the first time)** — 50 biggest options winners vs 50 worst fakeouts (n=934 pool), measuring only the max consecutive-close streak reached before breaking. Winners: median max streak 74 (out of ~75 five-minute bars in a session) — 100% reached streak≥3, 100% reached streak≥5. Fakeouts: median max streak 1 — only 28.0% ever reached streak≥3, only 18.0% reached streak≥5. The critic's specific prediction checked directly: 60.0% of the worst fakeouts have a max streak ≤1 bar; 0.0% of the biggest winners do. Same conclusion as the Missed Winner Audit, from a completely different angle (extremes by realized pnl rather than a threshold split) — equally stark.

**Portfolio-constrained ranking (response-21, never done for these filters — only ever done for the older 2026-09-07 stall rule) — genuinely inconclusive, not a clean result either way.** Chronological greedy admission, max 5 concurrent positions, freshness-ranked tie-break vs. a ticker-alphabetical no-ranking control, full population, real `check_exit()` outcomes. First attempt had a real bug (both arms accidentally shared the same pre-sorted order, producing identical output — caught before reporting, fixed). Corrected: freshness-ranked (n=555) wins 60.2%/+1.84% median/+1.15% mean; no-ranking (n=530) wins 63.2%/+2.55% median/+1.03% mean — the un-ranked control actually looks *better* on win-rate/median. Not trusted either way: both admitted portfolios sit above the 40% concentration danger threshold (47.2%/51.9%), and the two admission orders share only 93 of ~550 trades (~17% overlap) — a single early tie-break cascades into an almost entirely different portfolio under this greedy mechanism. A trustworthy version of this test would need something like a Monte Carlo over tie-break orders, not built here.

Nothing from today beyond the two `live_checkpoint.py` wire-ins (Freshness Score, RVOL@Trigger *fraction* fix — the clock-time volume fraction is still a real, correct fix and stays wired in; only the *predictive* RVOL@Trigger feature itself is what got re-rejected above) is adopted into production. Standing rejections as of today: acceptance-delay/streak-confirmation as an entry gate; runaway-vs-pullback prediction as a target; acceptance as an execution-state stop-tightening trigger; RVOL@Trigger as a predictive feature (corrected verdict, see above — inconclusive/rejected, not promoted). Standing "real but not yet actionable" findings: body_atr as a fragility signal (not win-rate, not runaway-shape); velocity as a weak swing-side lead. Portfolio-constrained ranking is unresolved/inconclusive pending a more robust test. Freshness Score remains the only signal validated across every population, every exit regime, and every metric (win rate, magnitude, fragility) tested so far. **[2026-09-17 correction — see "Freshness, precise definition" near the end of this file: this statement is imprecise. Freshness's edge is real and large on the Primed-Gate population, but near-zero on the Entry-Gate population once EOD confirmation is already known — it isn't universal across every population, and the reason why is now understood.]**

**Standing methodology lesson from this correction**: when re-implementing a production formula for offline research, verify against the actual source (`grep`/`Read` the real function), don't reconstruct it from memory or a "close enough" existing column — a plain 20-day mean vs. a 25-day median-excluding-extension-days looks like a trivial difference but changed a "promote" verdict into a "no signal" one.

## RVOL@Trigger — RETIRED (2026-09-13, final). RQ-37 — CLOSED/ARCHIVED.

**RVOL@Trigger.** The underlying full-day `vol_zscore` signal is real and large (a ~25-point win-rate gap on the honest live-equivalent population, bigger than freshness's own effect) — never in question. RVOL@Trigger, the real-time proxy for that end-of-day event, is also genuinely time-gated (correlation with the real event grows from +0.118 at <30min elapsed to +0.58 at 2-3hr, confirmed not a U-shape/curve-tracking artifact but simple cumulative-data reliability). But across every way it was actually tested as a *decision* tool this session, it never converted into a usable edge:
1. Win-rate quartile cut on the raw metric — no signal (update-28/31, corrected in the RVOL baseline fix above).
2. Hindsight proxy-chain (does high RVOL reliably flag the real event, does that translate to win rate) — the event-detection step works (10.7%→53.6% hit rate by quartile) but doesn't chain through to a clean win-rate effect at available sample sizes (2hr+ subset, n=222, rank-corr -0.001).
3. **Capital-allocation/portfolio-ranking test (the critic's own proposed final experiment, with a pre-declared retirement rule)**: for every day with multiple already-fired candidates (66 days in the intraday-covered window, up to 32 simultaneous fires), ranked Freshness-only vs. Freshness+RVOL vs. Freshness+Distance vs. all three, capped at 2 or 3 positions:

| Cap | Freshness only | Freshness + RVOL |
|---|---|---|
| 2 | 65.0% win / +0.60% med / +0.88% mean | 59.2% / +0.35% / +0.64% |
| 3 | 62.4% / +0.39% / +0.66% | 57.3% / +0.20% / +0.54% |

Freshness+RVOL underperforms Freshness-only at both caps, on every metric, not close (n=522, the full available intraday-covered sample, not a cherry-pick). **Per the critic's own pre-declared rule ("if Freshness+RVOL does not outperform Freshness-only, RVOL leaves the production roadmap completely, no more maybe") — RVOL@Trigger is retired.**

**Rejected item: RVOL@Trigger.** Reason: predicts end-of-day volume correctly, but does not improve entry filtering, portfolio ranking, or D+1 expectancy over Freshness, across three independent tests. Not to be revisited unless a genuinely new decision mechanism is proposed (not another win-rate cut or hindsight chain). The underlying `_clock_time_volume_fraction` fix in `live_checkpoint.py` stays wired in as a correct, standalone fix (real intraday volume is front/back-loaded, not linear) — only the *predictive* RVOL@Trigger feature built on top of it is retired.

**RQ-37 (acceptance as an execution-state variable for stop management) — closed, archived.** Three independent tests, three independent failures, same underlying mechanism each time:
- Wait for acceptance before entering (update-27) → loses the edge (premium paid erases it).
- Tighten the stop on non-acceptance after entering (update-30) → loses the edge (54.5%→42.1% win on the rejected subset; whipsaws out recoverable trades).
- Pullback/retest confirmation as a quality filter (pullback-after-streak work) → loses the edge (filters out the best trades — the 21.2% "runaway" group — not the worst ones).

**Do not revisit "acceptance-based stop tightening" or "wait for confirmation" in any form.** If acceptance/streak state comes back as a research thread, it must be for a genuinely different purpose (e.g., a passive confidence display, never gating entry or modifying an open position's risk).

**Standing methodology note, now a permanent project principle**: measurement correctness is different from decision usefulness. Checklist Pass, Acceptance Streak, RVOL, and Body/ATR were all measured *correctly* at some point in this project's history — none of the four turned out to be useful for a live decision (entry gate, portfolio rank, or stop management) once tested honestly. A signal passing a correctness check is necessary, not sufficient, before it can be trusted to drive a real action.

## Multi-timeframe EMA support hypothesis (2026-09-14) — real, but options and swing need different timeframes; two variants dropped; EMA34-break exit overlay re-confirmed rejected.

**Origin**: user's own trading experience — "34EMA hourly + 8EMA daily used to be a deadly combo for intraday," and for swing the equivalent support should sit one timeframe wider (hourly→daily/weekly). Confirmed via web search this is a real, standard multi-timeframe EMA technique (8/13/21/34 "EMA ribbon"), though the common convention is same-period-across-timeframes-for-alignment or fast-EMA-entry/slow-EMA-anchor-on-one-timeframe — not the specific "34 on the short TF, 8 on the long TF" cross-swap the user recalled. Tested the literal hypothesis anyway rather than dismissing on convention alone.

**Correction to an earlier result in this same thread (a real bug, not just refinement)**: the first hourly EMA8/34 bucket table built for OPTIONS used a 3-trading-day forward window to classify "touched EMA8 only / touched EMA34 held / touched EMA34 broke," then correlated it against `day1_pnl_pct` (the day+1-open options exit). But the options position is already closed at day+1's open — so most of that 3-day window (day+1, day+2) occurs *after* the trade has already settled. Not a live-available signal, just a same-underlying-quality correlate. Recomputed on the only genuinely actionable window (same entry day only, `hourly_ema_actionable_window.py`) — the ladder inverts:

| Same-day-only bucket | n | OPTIONS win | med |
|---|---|---|---|
| never touched EMA8/34 all day | 191 (40.9%) | **87.4%** | **+1.54%** |
| touched EMA8 only | 229 (49.0%) | 52.8% | +0.10% |
| touched EMA34, held | 30 (6.4%) | 53.3% | +0.09% |
| touched EMA34, broke | 17 (3.6%) | 41.2% | -0.47% |

Read: for options, it isn't "shallow pullback to 8 fine, break of 34 bad" — it's "any same-day pullback at all is a big step down from a clean run," full stop. The earlier (wrong) 3-day-window table stays useful for SWING though, since a swing position is genuinely still open across those days — no lookahead problem there.

**Daily-level search for the best swing support (`daily_level_search.py`) — originally run on the 467-trade fresh population, corrected below to a properly-powered n=7,108. See the population-size audit section at the end of this entry** for why and what changed. Ranked by win-rate spread (never_touched − broke), final (big-population) numbers:

| Level | never_touched | held | broke | spread | n (never/held/broke) |
|---|---|---|---|---|---|
| SMA50 | 84.3%/+3.82% | 56.1%/+0.95% | 22.6%/-7.05% | +61.7pp | 3804/1142/2116 |
| EMA34 | 93.3%/+4.83% | 74.2%/+2.61% | 32.2%/-5.30% | +61.1pp | 2356/1506/3246 |
| EMA21 | 98.3%/+5.72% | 88.7%/+3.89% | 42.7%/-1.68% | +55.6pp | 1075/1577/4456 |
| EMA8 | 96.0%/+6.11% | 98.3%/+5.68% | 57.8%/+1.28% | +38.2pp | 25/597/6486 |
| SMA150 | 69.6%/+2.64% | 46.5%/-1.05% | 36.5%/-4.95% | +33.1pp | 5055/434/1189 |
| SMA200 | 68.0%/+2.50% | 54.1%/+0.46% | 42.3%/-2.75% | +25.7pp | 4954/296/1177 |

**Ranking is unchanged from the small-sample version** (SMA50 ≈ EMA34 > EMA21 > EMA8 > SMA150 > SMA200) — same conclusion, ~15x the data. EMA34/SMA50 remain the best, essentially tied (already the adopted swing signal). EMA21 remains a genuine secondary/early-warning signal, not a replacement — holding it costs little (98.3%→88.7%) but breaking it is nearly as damaging as breaking EMA34 (42.7% win). EMA8's "held"/"never touched" buckets turned out even stronger once properly sampled (n=25/597 vs the earlier unreliable n=11/40) — 98.3% win when held — but it's still the weakest *discriminator* in practice, since 91% of the population (6,486/7,108) breaks it regardless, so it rarely segments anything. SMA150/SMA200 confirmed weaker.

**Touch-bar direction (bullish vs bearish close), not "pin bar" shape, is what actually carries signal — and it's timeframe-matched to product, exactly like everything else this project has found. Numbers below are the corrected, big-population (n=7,108) version — see the audit section for what changed from the original small-sample run:**

- Hourly EMA8, same-day window, OPTIONS (genuinely intraday-dependent, can't be re-run on a bigger population — no intraday data exists before the 93-day cache): bullish close at touch 66.4%/+0.38% (n=116) vs bearish close 41.1%/-0.46% (n=158) — a real ~25pp gap, checked for outlier concentration (broad distribution, 14 separate wins from +0.17% to +1.84%, not one lucky trade). A stricter "true pin bar" (bullish + closes back above + lower wick ≥2× body) pushes to 76.5% but thins to n=17 — promising, not proven. Swing side on the same touch bucket is flat (60.3% vs 57.6%) — options-specific, as expected. This one stays on the small sample; there is no bigger population to check it against.
- Daily EMA8, 20-day window: bullish close at touch — OPTIONS 60.2%/+0.35% (n=1,959) vs bearish 60.7%/+0.37% (n=5,124), flat as expected; SWING 72.5%/+2.94% vs 56.9%/+1.17% — a real ~15.6pp gap, confirms the small-sample read (71.4% vs 57.0%) almost exactly.
- **Daily EMA34 touch-bar direction — corrected, was reported as noise, is actually real.** Small sample (n=52 vs 219) showed 44.2% vs 42.0%, called noise. Big sample (n=959 vs 3,793): SWING 55.3%/+0.73% (bullish) vs 43.0%/-1.75% (bearish) — a genuine ~12.3pp gap, and win rate is a count-based metric so this isn't a magnitude-outlier artifact (≈530 vs ≈1,631 winners, not a handful of trades). OPTIONS stays flat both times (57.9% vs 56.2%). The small sample was simply underpowered, not showing a true null — retracting the "noise" call. The n=20 thin pin-bar-off-EMA34 curiosity (85.0% options / 40.0% swing) wasn't re-tested at scale and is left as originally reported, flagged thin.

## Population-size audit on the EMA/stall thread — two corrections, two reconfirmations (2026-09-14, continued)

**The bug**: several tests above (`daily_level_search.py`, `daily_pinbar_check.py`, `ema34_exit_overlay_check.py`, `ema_combo_check.py`, and the stall-exit overlay test below) were built against the 467-trade freshness-conditioned population purely because that's what was on hand from the hourly EMA work earlier in the thread — but none of them actually need intraday data (they're pure daily-bar questions), so restricting them to the tiny 93-day intraday-cache window was an unforced, unnecessary constraint. Caught directly by the user ("why just 467? this is a swing trade, population must be bigger"). Re-ran all of them against `runs/rsi_max_sweep_80.csv`'s full live-equivalent population (`base_filters_pass()` + intraday High-cross, `breakout_cont` only, n=14,225, spanning 2021-09-28 to 2026-09-10), freshness-conditioned the same way (median split, n=7,108) — 15x the sample, same freshness logic, full history instead of 93 days.

One genuine limitation, not fixable: the `SCAN_END_TIME=13:00` cutoff needs intraday breach-hour, which only exists inside the 93-day cache. Bracketed instead of ignored — computed the stall-exit result on n=386 (freshness+cutoff, cache-window-only) alongside n=467 (freshness-only, same window) and n=7,108 (freshness-only, full history): all three move in the same direction, and the cutoff-restricted bracket (n=386) sits between the two freshness-only samples, not off on its own — reasonable evidence the freshness-only big population isn't silently missing something the cutoff would have caught for this specific swing-exit question.

**Two real corrections:**
1. Daily EMA34 touch-bar direction (noise → real), detailed inline above.
2. **3-day-stall exit overlay (reconsideration-shortlist item 3) — softened from "real cost" to "near wash."** Small-sample verdict (n=467): win rate/median up, expectancy down 18% (+1.200%→+0.985%), read as a real "chase the tail" cost. Big-population verdict (n=7,108): win 61.3%→64.3%, median +1.79%→+2.20%, expectancy +0.726%→+0.704% (**only -3%**, not -18%) — direction unchanged but magnitude much softer. On the 939 trades the overlay actually fires on (vs only 74 before): originally 75.0% win/+3.62% median/+5.352% expectancy → overlay 97.0% win/+4.44% median/+5.180% expectancy, better on 536/939 (57.1%, a real majority, not the earlier near-coin-flip 51%). Total cost across fired trades: -161.2pp on n=939 (≈-0.17pp/trade average) vs the small sample's -100.7pp on n=74 (≈-1.36pp/trade average) — an order of magnitude milder per trade. **Revised verdict: closer to a wash-to-mild-positive than a clear rejection.** Not a confident "adopt" either — expectancy still dips slightly, and this hasn't been through a capital-constrained portfolio simulation the way the 2026-09-05/06 stall-exit work was — but the small-sample "real cost" framing overstated the downside. Treat as inconclusive-leaning-neutral, not rejected.

**Two reconfirmations (no correction needed, just refreshed evidence):**
1. **EMA34-break exit overlay (item 4, already closed above) — reconfirmed, more decisively rejected at scale.** Big population (n=7,108): win 61.3%→54.4% (-6.9pp, vs the small sample's -5.2pp), expectancy +0.726%→+0.573% (-21%, same relative size as before), concentration worsens 7.8%→9.9%. On the 2,060 trades it fires on (vs 121 before): -1,092.4pp total (vs -116.9pp), same recoveries-cost-more-than-savings mechanism, now on a base 15x larger. Standing "confirmed closed" verdict holds, evidence is now much stronger.
2. **The literal combo test (34-short-TF-confirmation + 8-long-TF-support) — reconfirmed tautological at scale.** 7,108/7,108 trades above daily EMA8 at entry (100%, matching the small sample's 467/467); 6,984/6,984 of those with enough history above weekly EMA8 too. Zero variance either way, full history. No correction needed.

**Daily-level search and daily-EMA8 pin-bar direction — refreshed, not corrected**: same conclusions, both detailed inline above with the updated big-population numbers.

**Standing methodology lesson, worth keeping alongside the "verify formula against production source" one**: a test's population shouldn't inherit a scope restriction from whatever data happened to be on hand from a *different, unrelated* test earlier in the same session — check whether the actual data dependency (here: true intraday bars) is real before reusing a convenient population. Two of five re-tested findings changed as a direct result (one reversed, one softened); the other three held up, in one case much more strongly. Both outcomes are useful — this audit wasn't just error-correction, it also strengthened confidence in the findings that survived.

**Net for the original hypothesis**: partially right, mechanism different than recalled. EMA34/SMA50 tell you if the trade is structurally sound (options=hourly EMA34, swing=daily EMA34/SMA50); EMA8's touch-candle *direction* (not shape) is a secondary "still alive" tell at whichever timeframe matches the product (hourly EMA8→options, daily EMA8→swing). None of this is wired into `live_checkpoint.py` — descriptive findings only, consistent with the FILTER/RANK/LABEL discipline until an actionable decision is designed and tested.

**Two variants tested and dropped, both genuinely dead ends (not just noisy)**:
1. **The user's literal combo** (34 EMA on the short timeframe for entry confirmation + 8 EMA on the long timeframe for "overall support," e.g. daily EMA8 for options, weekly EMA8 for swing) — checked directly (`ema_combo_check.py`): 467/467 trades are above both the daily EMA8 and the weekly EMA8 at entry, zero variance. Tautological, not just weak: this scanner's breakout trigger (`high10_prior * 1.005`, a fresh 10-day-high clearance) already guarantees price is above its own fast EMA on any coarser timeframe — the condition can never be false for a candidate that reached the scanner at all.
2. **Hourly SMA50 as a "wider" intraday support level** (an attempt to find a genuinely wider support without jumping to the daily timeframe) — dropped: 227/239 trades (95%) that already broke hourly EMA34 also break hourly SMA50 same day, no differentiation (`hourly_wider_support_check.py`). Not a new information source — no overnight gap, no new session, just a slower MA on the same intraday clock as one that's already broken.

## EMA34-break as an exit-rule overlay (2026-09-14) — re-tested on the current population, confirms the 2026-09-02 rejection, still rejected.

This was reconsideration-shortlist item 4 from `critic_update_35.md` ("EMA34-break automatic early-exit," flagged there as "worth confirming, not assuming" given the noise reduction from freshness+cutoff since the original test). Tested as an **overlay** (exit at whichever fires first: the real `check_exit()` stop/target/trailing logic, or a daily Close closing below daily EMA34) — not a replacement, since the existing exit logic is not in question, only whether adding one more early-exit trigger helps (`ema34_exit_overlay_check.py`, full 467-trade population, sanity-checked the recomputed baseline exactly reproduces the original `swing_pnl_pct`, 0 mismatches).

| | win rate | median | expectancy | concentration | avg loss |
|---|---|---|---|---|---|
| current rule alone | 61.7% | +1.55% | +1.200% | 36.3% | -5.47% |
| current rule + EMA34-break overlay | 56.5% | +1.08% | +0.950% | 45.2% | -4.74% |

Overlay makes every aggregate metric worse, including concentration (45.2% vs 36.3% — the result becomes *more* outlier-dependent, not less). It fired early on 121/467 trades (25.9%). Isolating just those 121: the current rule had *already* correctly flagged them as mostly bad (19.8% win, -4.680% expectancy on the original rule) — the overlay doesn't rescue anything there, but it takes the 19.8% (~24 trades) that were going to recover into real winners and kills them at a loss before they can, dropping win rate on that subset to 0.0% and expectancy to -5.647%. Net -116.9pp across those 121 trades. Same mechanism as the original 2026-09-02 rejection ("real recoveries cost more than the early exits saved") and the RQ-37 acceptance-based stop-tightening rejection above — reproduces cleanly on the current, cleaner population rather than reversing. **Confirmed closed — do not revisit unless a materially different trigger condition (not "break of a support MA") is proposed.** (Superseded/reconfirmed at the fresh40 standard below — same conclusion.)

## Standing population discipline adopted, freshness=0.40 (2026-09-14, continued) — every test above re-run under one consistent standard

**New standing rule** (also saved to persistent memory, `feedback_population_choice_for_backtests.md`, so it applies automatically in future sessions without being re-requested): freshness cutoff = **0.40** (not a median split), and every daily-bar test gets run on **three** population variants side by side:
- **BIG** — full 2021-2026 history, `runs/pop_fresh40_big.csv`, n=5,213 (`base_filters_pass()` + intraday High-cross, `breakout_cont` only, from `runs/rsi_max_sweep_80.csv`)
- **SMALL** — 93-day intraday-cache window only, `runs/pop_fresh40_small.csv`, n=365 (needed for anything intraday, but computed for every test as a bracket)
- **SMALL+1PM cutoff** — same window restricted to real breach hour < 13:00, `runs/pop_fresh40_cutoff.csv`, n=298

Why 0.40 specifically: a full threshold sweep (0.20 to no-filter) on the big population shows **no natural knee anywhere** — options win/expectancy climbs smoothly and monotonically as the cutoff tightens (53.6%/+0.318% unfiltered → 62.5%/+0.776% at ≤0.40 → 68.7%/+1.129% at ≤0.20), swing stays nearly flat the whole range (60.6-61.5% regardless of cutoff). That's the signature of a genuine ranking signal, not a gating one — confirms freshness was correctly built as rank-only, never a hard filter. 0.40 isn't a validated optimum, just a reasonable, moderately strict, defensible reference point (n=5,213 of 14,225, ~36.6%) — same status as the 0.5% entry-clearance pick elsewhere in this project.

**Results, re-run across all three populations (`rerun_all_fresh40.py`):**

**Reconfirmed cleanly, no change from the median-split versions above:**
- Daily-level search (EMA34/SMA50 cascade): ranking holds in all 3 pops (never_touched 88-94% → held 58-76% → broke 21-33%), sharper at 0.40 than at median.
- Daily EMA8/EMA34 touch-bar direction: swing gap real and consistent everywhere (EMA8 ~15-16pp, EMA34 ~8-13pp); options flat everywhere.
- EMA34-break exit overlay: rejected in all 3 (win -5 to -7pp, expectancy -10% to -18%).
- Hourly actionable-window (options): never-touched still dramatically best (87-89%), any touch ~46%; cutoff barely moves it.
- Hourly EMA8 pin-bar (options): bullish/bearish gap even bigger at 0.40 (~29pp) than at median (~25pp); cutoff changes almost nothing here (only 1-3 trades excluded from this bucket).

**Softened, not rejected — 3-day-stall overlay.** Win/median improve in all 3 populations; expectancy dips everywhere but the size scales with statistical power: **-3%** on the reliable big population (n=5,213, +0.774%→+0.749%) vs **-16% to -17%** on the two small ones (n=365: +1.184%→+0.984%; n=298: +1.345%→+1.125%). The best-powered number should be trusted most — reads as "near wash, mild real cost," not zero cost as the single big-population number alone might have implied, but also not the sharp rejection the original small-sample-only read suggested.

**New finding — the SMA50-AND gate's two legs behave differently, and one is regime-dependent right now.** "Above SMA50" holds up in direction across all 3 populations — win rate and swing expectancy consistently favor "kept" (BIG: 62.3% vs 57.3% swing win, exp +0.908 vs +0.282; SMALL: 62.4% vs 53.7%, +1.353 vs +0.205; CUTOFF: 63.0% vs 54.5%, +1.571 vs +0.038). Options expectancy flips slightly toward "removed" in the two small samples, but against a much cleaner and more consistent swing signal, that reads as small-sample noise, not a real reversal.

**"SMA50 rising" is a different story — mildly positive on the full 5-year history, but clearly backwards on the recent period, reproducing in two independent small-population cuts:**

| | kept (rising) | removed (falling) |
|---|---|---|
| BIG (5yr): swing win/exp | 62.3% / +0.980 | 58.8% / +0.301 |
| SMALL (93-day): swing win/exp | 58.6% / +0.695 | **70.0% / +2.924** |
| CUTOFF (93-day, 1PM): swing win/exp | 59.1% / +0.809 | **71.2% / +3.226** |

Same direction, same rough magnitude, in two overlapping-but-distinct recent-period samples — not a coincidence, though concentration is elevated on the "removed" buckets (61-66%) so the exact magnitude is likely somewhat inflated; the win-rate gap itself (a count-based, artifact-free number) still agrees with the direction. This isn't just "doesn't help" — over the last ~3 months specifically, requiring Nifty's SMA50 to be rising would have actively hurt, reproducing the same backwards shape the original 2026-09-01 VCP-weak-window test found, just in a different period and pattern.

**Final verdict for reconsideration-shortlist item 5**: split the gate into its two legs, don't treat it as one unit. "Above SMA50" is a real, mild, *ranking-worthy* signal (not a gate — the removed population is still profitable in every population tested, e.g. BIG removed: 58.2% options win/+0.589% exp, still solidly tradeable — cutting it for a few points of edge repeats the "practicality over marginal edge" mistake this project has avoided elsewhere). "SMA50 rising" should stay rejected, and is actively working backwards in the current regime specifically — worth remembering as a live warning sign, not just a closed research question.

## Market breadth redundancy check (2026-09-14) — reconsideration-shortlist item 6, confirmed NOT redundant with freshness

Different question from items 3-5: breadth (`breadth.breadth_pct`, % of Nifty500 above its own 200-SMA) was already adopted as a real, monotonic RANKING signal on the raw population, never rejected, never a gate. The open question was whether it still adds independent lift on top of freshness+cutoff, or has quietly become redundant — the same overlap risk already found once this project between `consolidation_days` and streak-confirmation. Tested via `breadth_redundancy_check.py` across the standard 3-population bracket.

**BIG population (n=4,794 with breadth data, full 2021-2026 range: breadth 12.8%-95.8%)** — the population that actually has enough range to test this properly:
- Correlation(breadth_pct, freshness_score) = **-0.007**, essentially zero — genuinely independent information, same shape as the earlier consolidation_days/VCP-detection precedent (-0.038).
- Threshold cuts show a clean, smooth, monotonic climb on **both** metrics even with freshness≤0.40 already applied: options 63.0%→64.6% (≥50% to ≥75% breadth), swing 62.3%→66.2%. Quartile split confirms it too, most clearly at the top (Q4, breadth 86.6-95.8%: 65.2% options win/+0.59% med, **70.3%** swing win/+2.78% med — clearly the best cell).

**SMALL/CUTOFF (n=365/298, 93-day window)** — quartile pattern here looks messy (a Q2 spike to ~79% options win, swing actually declining Q1→Q4) but this is a range problem, not a contradicting finding: breadth in this recent window only spans **39.8%-60.1%**, a narrow band sitting near the middle of the historical range — there's no real "high" or "low" breadth extreme in this window to test against, so the quartile split is subdividing noise within a compressed band. Different situation from the SMA50-rising finding (which showed a strong, consistent, *wide-range* contrarian signal on two independent brackets) — this one lacks range, not signal, and shouldn't be read as a regime-dependence flag the way SMA50-rising was.

**Verdict**: breadth is **not redundant** with freshness — confirmed on the population with enough range to actually test it. No reversal, no regime-dependence warning like item 5's second leg. Already implemented as ranking-only (never a gate) in production — no code change needed. Closes item 6 as a reconfirmation.

**Reconsideration-shortlist status after items 3-6**: item 3 (3-day-stall) closed as near-wash/mild real cost; item 4 (EMA34-break exit) reconfirmed rejected; item 5 (SMA50-AND gate) split — "above" promoted to a ranking candidate, "rising" stays rejected and flagged as currently backwards; item 6 (breadth) reconfirmed not redundant, no change. Remaining open: items 1-2 (2R/3R fixed target, trail-only exit replay) and the theta-bleed/DTE check.

## 2R/3R fixed target and trail-only exit replay (2026-09-14) — items 1-2, sharpened from "ambiguous trade-off" to a clear reject

Replays the original 2026-09-03 "Exit-strategy comparison" (`exit_strategy_replay.py`), which found a genuine, unresolved trade-off: baseline (moving resistance, current production) had the cleanest win rate (65.0%) but left expectancy on the table; 2R/3R/trail-only had better raw expectancy but only ~50.2% of nominal "2R winners" ever reached the real target (the rest got stopped near breakeven on the way back down), and trail-only's edge was mostly a coin-flip median propped up by rare huge winners (24.7% concentration). Same entry convention as everything else this session (`trigger = high10_prior * 1.005`, `R = ATR_TRAIL_MULT(3.0) * atr14` at entry) — the fixed-target variants set `state["target"]` once at entry and call `check_exit(..., use_resistance=False)` so the resistance ratchet never overrides it; trail-only leaves `target=None` the whole trade (pure stop/climax).

**First pass, on the freshness≤0.40 population, looked like a real deterioration** — win rate for all three alternatives dropped to 46.6-50.3%, median went **negative** (-0.17% to -0.90%), and the 2R target-hit rate fell to 20.7-32.9% depending on population. Initial (wrong) explanation: freshness selects calmer, less-extended setups that don't run far enough to reach a wide target.

**That explanation didn't survive a direct check, per user pushback ("what, you are saying fresh stocks are bad or something") — correctly skeptical.** Re-ran the identical 4-variant comparison on the fully **unfiltered** population (n=14,225, no freshness cutoff at all, same breakout_cont-only, trigger-based entry):

| Variant | win rate | median | 2R target-hit rate |
|---|---|---|---|
| baseline | 60.9% | +1.77% | — |
| 2R | 45.0% | -0.89% | **36.5%** |
| 3R | 45.0% | -0.90% | 19.3% |
| trail-only | 45.0% | -0.90% | — |

Nearly identical to the freshness-conditioned result (45.0% vs 46.7% win, -0.89% vs -0.49% median, 36.5% vs 32.9% target-hit) — **freshness has essentially no effect on this question, in either direction.** The real reason today's numbers look worse than the original 2026-09-03 result (50.2% target-hit, ~50% win) is a population-scope difference: that test used `detect_entry()`, which combined both patterns (breakout_cont + VCP) and likely a different entry convention, while every test this session (and the live strategy itself) uses breakout_cont-only, trigger-based entry specifically. Not an apples-to-apples comparison, and not worth chasing further — **per direct user instruction, the project only works with trigger-based entry now**, so the old combined-pattern population is obsolete, not a baseline worth reconciling against.

**Verdict for items 1-2, on the only entry mechanism that's actually live**: baseline (moving resistance) beats all three alternatives on win rate and median, consistently, with or without freshness (win rate 60.9-61.2% vs 45.0-50.3%; median +1.77-1.78% vs -0.02% to -0.90%). The alternatives only look better on raw mean-R (+0.11-0.16R vs baseline's +0.06-0.12R), and that edge is concentration-fragile on smaller samples (SMALL/CUTOFF populations show 82-100% concentration on the alternatives — almost entirely outlier-driven there; BIG's concentration stays sane, 3.4-14.1%, so BIG is the number to trust and even there the alternatives clearly lose on win-rate/median). This sharpens the original "genuine unresolved trade-off, not a settled switch-to-X" framing into a real answer: **on the current trigger-based entry, baseline is the clear, decisive choice — not an ambiguous one.** Freshness was never the relevant variable here; closing items 1-2 as reconfirmed-reject, not reconsidered.

**Reconsideration-shortlist final status, all 6 items closed**: item 1-2 (2R/3R, trail-only) reconfirmed reject, sharpened from ambiguous to decisive; item 3 (3-day-stall) near-wash/mild cost; item 4 (EMA34-break exit) reconfirmed reject; item 5 (SMA50-AND gate) split — "above" promoted to ranking candidate, "rising" stays rejected and currently backwards; item 6 (breadth) reconfirmed not redundant. Only the theta-bleed/DTE check remains open from the original list.

## Theta-bleed / DTE check (2026-09-14) — the last open item from critic_update_35.md, real and bigger than the original hypothesis expected

**Original question**: the 2026-09-02 options premium/time-stop rejections were built on the OLD long-hold ITM+next strategy (median 21-day hold), where the mechanism was "real edge lives in convex winners that need time to recover from a 30-50% drawdown; cutting early kills them." That reasoning doesn't obviously apply to the CURRENT strategy (day+1 exit, full stop, no multi-week recovery window to protect). Proposed hypothesis: "theta bleed over a single day is a small, bounded cost unless DTE is already critically low." Tested directly rather than asserted, via real option contracts (not the stock-price day1_pnl_pct proxy used everywhere else this session — that proxy has no concept of DTE, since no contract is ever actually picked for it). `theta_bleed_check.py`: 500-trade sample from the freshness≤0.40 big population, ATM/current-month (the established recipe for a same-day/day+1 capture trade per 2026-09-06/07's findings), real `option_backtest.simulate_option_trade()`, n=346 with valid contract data.

**Result: the hypothesis was wrong in an important way — this is not a small, bounded, near-expiry-only cost.**

| DTE bucket | n | win rate | median opt return | median stock return |
|---|---|---|---|---|
| ≤5 | 18 | 33.3% | **-15.62%** | -0.10% |
| 6-10 | 77 | 39.0% | **-7.99%** | +0.61% |
| 11-15 | 72 | 29.2% | **-15.36%** | +0.20% |
| 16-20 | 105 | 45.7% | -3.46% | +0.44% |
| 21-25 | 65 | 47.7% | +0.00% | +0.59% |
| 26+ | 9 | 66.7% | +16.87% | +1.70% |

Pearson corr(DTE, opt_pnl_pct) = +0.109, rank-corr +0.155 — modest as a single number, but the bucket shape shows the real story: returns stay clearly negative through roughly DTE≈15 (the first half of a monthly cycle, not just the final days near expiry), only turning neutral-to-positive past DTE≈16-20. Checked for outliers directly (not an artifact): every bucket (18-105 trades) is a broad, well-distributed spread of individual returns, not a couple of large losers. Also checked against the existing `MIN_EXPIRY_RUNWAY_DAYS=5` protection (rolls to next-month if front-month DTE would drop below 5) — our observed DTE floor of 5 confirms that protection is already active, yet the negative effect clearly extends well past it, all the way to ~DTE 15.

**Verified this is a real option-mechanics effect, not a confound in which trades happen to fire at low DTE** (direct user challenge: "but options we are exiting in fast momentum" — a fair question, since the hold is fixed at ~1 day regardless of DTE). Checked the underlying stock's own day+1 return against the same DTE buckets: it's essentially flat (median +0.10% to +1.70%, no trend, corr(DTE, stock_pnl_pct)=**0.029**, versus the option's 0.109) — DTE has nothing to do with which trades fire or how well the stock moves. The divergence lives entirely in the option pricing, not the trade quality: an ATM option's percentage time-decay rate scales roughly like 1/DTE (standard option Greeks relationship), so the same small, ordinary stock move gets priced completely differently depending on remaining time value — a DTE≈8 contract sheds a much larger fraction of its value per day than a DTE≈25 one, even though both are held for exactly one day. A fast exit doesn't neutralize this, because it's the decay *rate*, not the number of days held, that's different.

**Practical implication, not yet tested as a live rule**: DTE-at-entry looks like a genuine candidate for a live filter or ranking signal on the options leg specifically — e.g., prefer entries with DTE≥16, or tighten `MIN_EXPIRY_RUNWAY_DAYS` well beyond its current 5-day floor for this specific (ATM, current-month, day+1-exit) combination. This is a real, new, actionable finding distinct from the old (correctly rejected) long-hold premium-stop idea — not yet built or tested as an actual gate/ranking rule.

## Reconsideration-shortlist closeout, all 7 items resolved (2026-09-14) — final synthesis

Everything raised in `critic_update_35.md`'s Part B is now closed. Summary of net changes to the standing view:

- **Confirmed unchanged (no new action)**: EMA34-break exit overlay (item 4) — rejection reconfirmed, more decisively at scale. 2R/3R/trail-only exits (items 1-2) — rejection reconfirmed and sharpened from "ambiguous trade-off" to a clear decision, once isolated to the actual live entry mechanism (trigger-based). Market breadth (item 6) — confirmed still adding real, independent lift on top of freshness, not redundant; already ranking-only in production, no change needed.
- **Softened**: 3-day-stall exit overlay (item 3) — from "real cost" down to "near wash, mild real cost that shrinks with sample size." Still not adopted, but no longer a clean rejection either.
- **New, real findings that didn't exist before this reconsideration pass**:
  - SMA50-AND gate (item 5) splits into two legs with different fates: "Nifty above its own SMA50" is a genuine, mild, *ranking-worthy* signal (never a gate, since the removed population is still solidly profitable). "Nifty SMA50 rising" stays rejected, and is *currently* working backwards in the recent-period data specifically — a live warning sign, not just closed history.
  - Theta-bleed/DTE — the single most consequential finding of this whole pass. Not "small and bounded" as hypothesized; a real, verified (not a confound), substantial effect across roughly the first half of the monthly expiry cycle. This is the one genuinely new, actionable candidate to come out of the whole reconsideration exercise — everything else either reconfirmed a prior stance or ruled something out.
- **A repeated meta-lesson, worth carrying forward past this specific list**: several of today's re-tests were initially run on an unnecessarily small, intraday-cache-limited population purely because that's what was already loaded from unrelated earlier work — caught directly by user pushback twice in this session (once on population size, once on a wrong mechanistic story for the exit-strategy replay). Both times, checking against a bigger or differently-scoped population changed the conclusion. The standing population-choice discipline adopted mid-session (`feedback_population_choice_for_backtests.md`) exists specifically because of this.

**Net for the live strategy right now**: nothing new is wired into production code from this whole pass. Everything else is either already correctly reflected in the current setup (breadth ranking, moving-resistance exit, no stall/EMA34-break gate) or stays a documented non-adoption (SMA50-rising, 2R/3R/trail-only, 3-day-stall). ~~The one candidate worth prioritizing next: a DTE-based filter or ranking signal on the options leg.~~ *(retracted — see correction directly below, found within the same session before being acted on)*

## CORRECTION to the theta-bleed/DTE finding above — real bug, not a real signal (2026-09-14, same day)

The theta-bleed result above (median swinging from -15.62% at DTE≤5 to +16.87% at DTE≥26, "verified" via a stock-return control) was built on a real methodological bug: `theta_bleed_check.py` used `option_backtest.simulate_option_trade()`'s built-in exit price, which resolves via `exit_row.ClsPric` — day+1's option **Close**, not day+1's **Open**. But the actual adopted day+1 recipe (documented 2026-09-06/07, directly above this in the file) exits near day+1's **open**, specifically because close-based day+1 exit was already found to be dramatically worse (ATM: 45.5% win/-2.59% median at close vs 82.0% win/+5.03% median at open) — "the open isn't the ceiling, it's a safe floor; the real opportunity is intraday on day+1, not a multi-day hold." I ran directly into that exact, already-documented trap myself without noticing, because `simulate_option_trade()`'s Close-to-Close convention is the right one for *other* purposes in this codebase (multi-day holds, expiry settlement) but silently wrong for this specific same-day question.

**Caught only when building the DTE<16 skip-filter test forced a direct comparison against expectations** (`theta_bleed_check_open_exit.py`, same 331-trade sample, entry_px unchanged (entry day's option Close — the already-established, flagged intraday-fill approximation) but exit_px corrected to day+1's option **Open**):

| DTE bucket | n | win rate | median |
|---|---|---|---|
| ≤5 | 16 | 75.0% | +2.87% |
| 6-10 | 74 | 59.5% | +1.91% |
| 11-15 | 69 | 56.5% | +1.26% |
| 16-20 | 99 | 51.5% | +0.26% |
| 21-25 | 64 | 62.5% | +0.99% |
| 26+ | 9 | 88.9% | +3.01% |

Correlation(DTE, opt_pnl_pct) = **-0.013** (was +0.109) — essentially zero, no monotonic pattern, and if anything the lowest-DTE bucket looks best (though thin, n=16). Skip-filter test (skip options leg when DTE<16, keep the stock/swing signal regardless): kept (DTE≥16) 57.6% win/+1.07% median vs skipped (DTE<16) 59.7% win/**+1.51%** median — **the trades this filter would remove are slightly better than the ones it keeps.** A DTE<16 filter would be actively counterproductive, not neutral.

**Corrected, final answer to the original theta-bleed question**: DTE does not meaningfully affect the day+1-open-exit strategy. The original hypothesis in `critic_update_35.md` ("theta bleed over a single day is a small, bounded cost unless DTE is already critically low") was directionally right and, once measured correctly, actually understated how negligible the effect is — there's no detectable DTE effect at all on the open-based exit, not even a small one concentrated at low DTE. **Do not build a DTE-based filter or ranking signal — closing this as a genuine null result, not a missed opportunity.**

**Standing methodology lesson, worth keeping alongside "verify formula against production source"**: a shared helper function (here, `simulate_option_trade()`) can be correct for the purpose it was originally built for and silently wrong for a different, superficially similar question — check what exit convention a reused function actually implements before trusting its output for a new question, especially when this project has *already* documented that the specific convention (close vs. open) materially changes the answer for exactly this kind of same-day trade.

## MAX_HOLD_DAYS = 15 — the swing-vs-positional identity correction, wired into production `check_exit()` (2026-09-14)

**The real finding underneath the whole stop-loss research thread**: every exit-rule test this session (the stop-family sweep, the MAE-early-exit check, the Body/ATR-conditional stop, and originally the Family C rejection) was implicitly validated against an **uncapped** baseline — the current production `check_exit()` has no day-count limit at all, and its real hold-time tail (p90=23 days, max 67-81 days on the live-equivalent population) is already a positional-trade time horizon, not a swing one. This was never questioned until a direct user challenge: "practically it will be impossible for me to leave the trade open for more than 2 weeks or at max 3." Every prior verdict in this thread ("cutting losers early always loses") was measured against an alternative (ride indefinitely) that was never actually tradeable to begin with.

**Quantified the real cost of a hard cap directly, on the standard freshness≤0.40 population bracket (daily/intraday/intraday+cutoff), before locking anything in:**

| Cap | daily win/exp | intraday win/exp | intraday+cutoff win/exp | % of trades hitting the cap |
|---|---|---|---|---|
| Uncapped | 61.2% / 0.774% | 61.1% / 1.184% | 61.7% / 1.345% | 0% |
| 25d | 60.1% / 0.759% | 60.0% / 1.197% | 60.7% / 1.349% | 7-8% |
| 20d | 59.4% / 0.775% | 59.7% / 1.234% | 60.7% / 1.392% | 15-16% |
| **15d (adopted)** | 58.5% / 0.707% | 59.7% / 1.093% | 59.7% / 1.143% | 28-32% |
| 10d | 57.3% / 0.688% | 58.6% / 1.049% | 59.1% / 1.046% | 49-55% |

A 20-day cap actually matched or slightly *beat* uncapped expectancy on the two more representative populations — the extreme tail wasn't where the edge lived. 15 days (the adopted value) costs a real but modest amount (win rate -1.4 to -2.7pp, expectancy -9% to -15% relative) and sits inside the user's stated hard ceiling (2-3 weeks) — a deliberately conservative choice within that constraint, not a data-optimized one.

**Re-tested the previously-rejected early-exit ideas (3-day-stall, fixed-days-after-arm) WITHIN this cap, not against the old uncapped baseline — and the picture changed materially.** Against a mandatory 15-day cap, every active mechanism shows a real win-rate improvement (+1.7 to +2.9pp) with only a modest expectancy cost (6-12% relative) — a genuine either/or trade-off, not the clean rejection these ideas got when tested against an effectively-unlimited alternative. Checked whether that residual expectancy cost was even real on the population that matters most (intraday+cutoff, n=298, same 298 trades under both rules): **paired mean difference (fixed-3-days-after-arm − passive) = -0.071%, SE=0.115%, 95% CI = [-0.296%, +0.155%]** — spans zero. Bootstrapped expectancy difference confirms it (95% CI [-0.318%, +0.144%]). 242 of 298 trades (81%) are literally identical outcomes under both rules; of the 56 that differ, it's close to a coin flip (30 better, 26 worse). **The apparent expectancy cost of fixed-3-days-after-arm is not statistically distinguishable from noise on the population that matters most** — only the win-rate gain and the (real, consistent) concentration improvement are trustworthy there. Revised verdict: fixed-3-days-after-arm is a legitimate, simple candidate (no streak-tracking needed, just a countdown once armed at 0.55R) — not proven better than passively riding to the cap, but not provably worse either, with a real win-rate upside.

**Wired `MAX_HOLD_DAYS = 15` directly into `check_exit()`** (`backtest.py`), not left as a research-only constraint — `state["days_held"]` is now tracked (initialized to 0 by the caller, incremented once per call), and a `hit_max_hold` condition joins resistance/climax/stop as a real exit reason (`"max_hold_cap"`), checked with lowest priority (only fires if none of the other three already did that day). Both call sites that build a `check_exit()` state dict were updated (`backtest.py`'s `simulate_ticker`, `monitor_positions.py`), plus a new `days_held`/remaining-days line added to `monitor_positions.py`'s live output so an open position's approach to the cap is visible before it fires, not just after. Verified end-to-end on real data (10-ticker sample): 13/46 trades (28%) hit `max_hold_cap`, `holding_days` showing 21-24 calendar days for the 15-trading-day cap (correct conversion, ~5 trading days/week). All 69 tests still pass.

**Standing project-identity correction, not just a parameter**: this strategy is a short-term swing system with a hard, real hold-time ceiling — that ceiling is now a first-class part of the exit logic itself, not an assumption anyone has to remember to apply manually. Any future exit-rule research should treat the 15-day-capped mechanism as the baseline to beat, not the old uncapped one.

## SMA21 trailing-exit family, Family C reconsidered, VCP Stop Geometry Audit — the critic's full post-cap priority list closed out (2026-09-14/15)

Three items, all run on the standard freshness≤0.40, 3-population bracket (daily/intraday/intraday+cutoff), all with `MAX_HOLD_DAYS=15` already baked into `check_exit()` so every comparison below is apples-to-apples with what's actually live.

### 1. SMA21 standalone trailing-exit family — real, then simplified further than expected

Kept entry and the pre-engagement initial stop untouched, only replaced the existing post-engagement floor (`max(base_stop, EMA21)`, Close-based, single-day) with four variants: (A) Close<SMA21, (B) Low<SMA21, (C) two consecutive closes<SMA21, (D) Close<SMA21−0.5×ATR.

| Variant | daily win/exp | intraday win/exp | intraday+cutoff win/exp | concentration |
|---|---|---|---|---|
| current (EMA21) | 58.5% / 0.707% | 59.7% / 1.093% | 59.7% / 1.143% | baseline |
| A: Close<SMA21 | 58.5% / 0.703% | 59.5% / 1.074% | 59.4% / 1.116% | ~same |
| B: Low<SMA21 | 58.8% / 0.679% | 59.7% / 1.059% | 59.7% / 1.115% | worse |
| **C: 2 closes<SMA21** | 59.8% / 0.758% | 61.4% / 1.150% | 61.7% / 1.214% | better, all 3 pops |
| **D: SMA21−0.5×ATR** | 59.7% / 0.737% | 61.4% / 1.172% | 61.7% / 1.243% | better, all 3 pops |

C and D both beat current on win rate, expectancy, *and* concentration, simultaneously, on all three populations — the only exit-rule result all session that wins on every axis instead of trading one for another. Checked significance on the smallest population: win-rate gain comes from a real, lopsided flip (7 trades loss→win, 1 win→loss, McNemar exact p=0.070 — just short of conventional significance on 8 discordant pairs, but the same shape holds cleanly on the two bigger populations too).

**Then asked whether ATR was doing anything in either winning variant — it wasn't.** C's `or Close<base_stop` ATR fallback never actually fired in practice; stripping it out changed nothing. D's `0.5×ATR` buffer, replaced with a plain fixed 2% buffer (no ATR anywhere), performed as well or slightly better on every population (intraday+cutoff: 62.1%/1.251% vs the ATR version's 61.7%/1.243%). Max loss stayed bounded in every no-ATR version too. **ATR was vestigial, carried over from the old formula.**

**Current best candidate for the post-engagement trailing mechanism: once up 3% from entry, exit when Close falls below SMA21 − 2%. No ATR anywhere in this stage.**

**Robustness check (critic's explicit ask before promotion, not a re-optimization)**: 3×3 grid, activation∈{2%,3%,4%} × buffer∈{1%,2%,3%}, around the found-best 3%/2% cell. Result: a genuine, broad plateau — win rate 58.9-60.4% and expectancy 0.728-0.745% across all 9 cells on daily (similarly tight ranges on the other two populations) — every single cell beats the current mechanism, none stands out as a lucky single point. Passes the robustness bar; 3%/2% sits in the middle of the plateau, not chased to an edge.

### 2. Family C (structural initial stop) × SMA21 interaction — reversed once, on a direct user challenge

First pass: paired Family C's structural-low initial stop (1.0×ATR buffer, the already-established best/representative value, no re-sweep per critic's instruction) with the new SMA21−2% trailing exit, against the current 3×ATR initial stop + same SMA21−2% trail:

| Population | 3×ATR initial + SMA21−2% | Family-C structural initial + SMA21−2% |
|---|---|---|
| daily (n=5,213) | 59.9% / 0.737% / conc 10.1% | 60.6% / **0.811%** / conc **9.2%** — real edge |
| intraday (n=365) | 61.6% / 1.172% / conc 41.3% | 61.6% / 1.148% / conc 42.1% — tied win, slightly worse |
| intraday+cutoff (n=298) | 62.1% / 1.251% / conc 46.7% | 62.1% / 1.227% / conc 47.7% — tied win, slightly worse |

Same shape seen twice before with Family C alone: real edge on the big 5-year population, ties-to-mild-negative on the smaller, more representative ones. Initially concluded (matching the critic's own pre-stated logic — "if it doesn't improve expectancy after the SMA21 change, Family C becomes redundant") that this closes Family C.

**Directly challenged ("but can it be a data gap?") before accepting that — and the challenge was right.** Isolated the trades where the two initial-stop rules actually produce a different outcome:
- On intraday+cutoff (n=298): only 31 trades differ (10.4%), and **all 31 are losers under both rules** (0% win either way) — Family C only changes the loss size here (net slightly worse, -8.69% vs -7.91% median), never rescues one into a win.
- On daily (n=5,213): 790 trades differ (15.2%). Among those, Family C **flips 38 trades from a loss into a win, and flips zero trades from a win into a loss** — a real, one-directional, downside-free rescue mechanism, not noise.

**Reconciled**: the rescue event is rare (38/5,213 ≈ 0.7% of all trades over 5 years). A 93-day window simply doesn't contain enough trades to reliably show even one occurrence — that's a genuine data-length limitation for a low-frequency effect, not evidence the effect is fake. Since the mechanism is asymmetric (only ever helps when it differs, never hurts), the long-history population is the trustworthy read here, not the short recent one — the reverse of the usual lesson this session, specifically because this question is about a rare event where sample *length* matters more than recency. **Revised, final verdict: keep Family C** — real, small, downside-free, best evidenced on the population large enough to contain it.

Checked hold-time compliance for the combined mechanism (structural initial + SMA21−2% trail): p90/max = 15/15 on every population, same hard ceiling as everything else — Family C's wider initial stop doesn't reintroduce the positional-hold problem, because `MAX_HOLD_DAYS` is enforced inside `check_exit()` itself regardless of which stop mechanism is active.

**Final recommended combination for Breakout Continuation**: structural-low initial stop (20-day lookback, 1.0×ATR buffer, no `MAX_INITIAL_RISK_PCT` cap — that cap was never part of the tested mechanism; `stop_family_research.py`'s Family C variant is uncapped, and this is what the reported numbers above reflect) → SMA21−2% trailing exit once up 3% → existing resistance target/climax exit → `MAX_HOLD_DAYS=15`.

**Wired into production (2026-09-15)**: `signals.py` (`sma21` column added to `build_indicators()`), `backtest.py` (`STRUCTURAL_LOOKBACK_BC`, `STRUCTURAL_STOP_ATR_BUFFER`, `SMA21_TRAIL_BUFFER_PCT` constants; `detect_entry()` computes BC's real structural low; `current_stop_level()` branches per pattern for the BASE stop only — BC now uses the structural−1×ATR floor pre-engagement, VCP keeps its unchanged structural-low floor — while the post-engagement floor is now the SAME SMA21−2% mechanism for both patterns (falling back to EMA21 if SMA21 is NaN); `simulate_ticker()` tracks `atr_entry`), `monitor_positions.py` (mirrors the same structural-low/atr_entry convention for live position tracking). All unit tests updated and passing. End-to-end validation — replaying the production `check_exit`/`current_stop_level` directly against the same population CSVs — reproduced the research numbers exactly: daily 60.6%/+0.811%/conc 9.2%, intraday 61.6%/+1.148%/conc 42.1%, intraday+cutoff 62.1%/+1.227%/conc 47.7%, hold p90/max=15/15 on all three.

### 3. VCP Stop Geometry Audit (RQ-43A) — production asymmetry confirmed justified, more decisively than predicted

Critic's exact question: BC's structural low (tested above) turned out much wider than 3×ATR (median ~14.8% vs ~8.7%, wider in 96% of trades) — is VCP's *existing* structural-low stop (already live in production, `current_stop_level`'s pattern-specific branch) the same kind of accidentally-positional mechanism, just never checked? Built the live-equivalent VCP population (`base_pivot()` + intraday-equivalent High cross, no vol_zscore gate, `LAST_LEG_TOLERANCE=0.40` matching production, n=3,971; n=2,048 at freshness≤0.40) and measured structural distance, the hypothetical 3×ATR distance, their ratio, and real performance with `MAX_HOLD_DAYS=15` already applied:

| | full population (n=3,971) | freshness≤0.40 (n=2,048) |
|---|---|---|
| Structural stop distance | median 4.49% | median 4.47% |
| 3×ATR distance (hypothetical) | median 10.97% | median 10.77% |
| **Ratio (structural/ATR)** | **0.44** | **0.43** |
| Structural *wider* than 3×ATR | 0.2% of trades | 0.3% of trades |
| Capped by the 8%-max-risk rule | 1.8% | 2.0% |
| Hold days (med/p90/max) | 6/15/15 | 6/14/15 |
| Win / expectancy | 66.9% / +4.972% | 59.0% / +2.404% |

**Result is the exact opposite of BC's, and stronger than the critic's own prediction** ("roughly similar to ATR" — turns out to be less than half the width, not merely similar). VCP's structural low is *tighter* than an equivalent 3×ATR stop in 99.7-99.8% of trades, median distance under half of ATR's. The 8%-max-risk hard cap (Minervini's published ceiling) almost never needs to bind (<2% of trades) because the base geometry itself is already tight. Mechanism: a VCP base is by construction a volatility-compressing consolidation, so its structural low sits close to price; BC's "structural low" (a plain 20-day rolling minimum, no compression requirement) has no such property and can sit far below price if the stock had any real range in that window. Hold-time comfortably inside the cap (p90 matches the 14-15 day ceiling by construction, median just 6 days — VCP resolves faster than BC on average).

**Verdict: the production asymmetry (BC gets ATR-based, VCP gets structural-based) is empirically justified, not an inconsistency — and VCP's version is the safer of the two, not a hidden risk. No production change needed for VCP's initial stop.**

### 4. VCP-SMA21 transfer test — one clean comparison, adopted

The gap flagged above (whether VCP should also get the SMA21−2% post-engagement floor) was closed as the critic specified: one clean comparison against the existing VCP live-equivalent population (`runs/vcp_live_equiv_tol_0.4.csv`, full n=3,971 and freshness≤0.40 n=2,048 — same population the Geometry Audit above used), no re-sweep, no re-optimization, no re-testing Family C for VCP (Family C is a BC-only initial-stop concept; VCP's initial stop was untouched here). `vcp_sma21_transfer_check.py` replicates `check_exit()`'s real logic (resistance ratchet, climax gate, `MAX_HOLD_DAYS` cap all copied verbatim) with only the post-engagement floor mechanism swapped between the two variants:

| | current (EMA21 floor) | candidate (SMA21−2% floor) |
|---|---|---|
| Full pop (n=3,971) | 66.9% / +4.972% / conc 2.5% | 65.4% / **+5.133%** / conc **2.4%** |
| Freshness≤0.40 (n=2,048) | 59.0% / +2.404% / conc 6.8% | 56.9% / **+2.473%** / conc **6.6%** |

Same trade-off shape already seen and accepted for BC: win rate down ~1.5-2pp (holds through a few more small pullbacks before exiting), but expectancy and concentration both improve on *both* populations — a real, if modest, edge, not a wash. Hold-time cap unaffected (p90/max=15/15 throughout).

**Decision (critic's rule: adopt if better-or-tied, no significance test demanded since this is a transfer decision, not a new-edge discovery): adopted.** Wired into production 2026-09-15 — `current_stop_level()`'s `coiled_spring` branch now shares the exact same SMA21−2% post-engagement mechanism as `breakout_cont` (only the pre-engagement base-stop mechanism still differs by pattern, per the Geometry Audit's justified asymmetry). End-to-end validation (production `check_exit` replayed directly against the same population) reproduced the candidate numbers exactly.

## Exit architecture — frozen (2026-09-15)

| | Breakout Continuation | VCP / Coiled Spring |
|---|---|---|
| Initial stop | `structural_low` (20-day lookback) `− 1.0×ATR` | `structural_low` (`base_pivot()`), capped at `MAX_INITIAL_RISK_PCT`=8% |
| Post-engagement floor (both, once up `TRAIL_ENGAGE_PCT`=3%) | `SMA21 × (1 − 0.02)`, falls back to EMA21 if SMA21 is NaN | *same* |
| Resistance target | moving pivot ladder, ratchets up only — unchanged | *same* |
| Climax exit | fresh-high + volume-climax + weak close gate — unchanged | *same* |
| Hard cap | `MAX_HOLD_DAYS`=15 trading days — unchanged | *same* |

Both patterns now share every exit mechanism except the initial-stop calculation, which stays genuinely different by design (BC's 20-day rolling minimum has no compression property and can sit far from price; VCP's base-pivot structural low is already volatility-compressed by construction — the Geometry Audit confirmed this asymmetry is earned, not accidental).

**Critic's remaining list, per their own explicit sequencing**: Freshness × Stop Distance interaction — now unblocked, the stop architecture is settled; this can move back up in priority. Time-without-progress stop — parked, not rejected (explicit concern: stacking a 4th temporal exit mechanism on top of the cap + fixed-days-after-arm candidate + the SMA21 trail risks losing attribution of which piece is actually creating the edge — see this project's own "keep it simple" discipline elsewhere).

## Freshness × Stop Distance interaction (2026-09-15) — mostly confirms "purely additive," one borderline swing-only lead flagged, not actionable

Same additive-model-check methodology as the earlier Freshness × Distance-to-trigger / Freshness × Consolidation interactions (`freshness_interaction_check.py`, critic update-28) — does the trade's own initial-stop width (real production formula: `structural_low − STRUCTURAL_STOP_ATR_BUFFER×atr_entry`, the exact same calculation now wired into `current_stop_level()`) interact with freshness, or are the two effects independent? Population: `runs/rsi_max_sweep_80.csv`, the full unfiltered daily Breakout Continuation set (n=14,225) — deliberately NOT pre-filtered to freshness≤0.40 here, since freshness is one of the two axes under study.

**2×2 halves check (Fresh/Extended × Near/Far stop distance)**:

| | Near (tight stop) | Far (wide stop) |
|---|---|---|
| Fresh — options | 62.8% / +0.68% | 54.9% / +0.68% |
| Fresh — swing | 61.9% / +0.61% | 59.9% / **+1.03%** |
| Extended — options | 48.7% / -0.02% | 45.7% / -0.05% |
| Extended — swing | 64.2% / +0.61% | 58.9% / +0.47% |

**Options: confirms purely additive, same as the earlier Distance/Consolidation interactions** — cross-term difference-in-differences +0.030pp, SE 0.092, |t|=0.32. No real synergy; freshness and stop distance just add.

**Swing: a real-looking but borderline asymmetry, not clearly significant** — cross-term +0.550pp, SE 0.304, |t|=1.81 (≈p=0.07, the same borderline level this session already treated cautiously for the SMA21 Family-C flip). Direction: **fresh trades benefit from a wider stop** (+0.611%→+1.028% mean, median +1.730%→+2.072%, consistent direction not just a mean shift), **extended trades get no such benefit** (+0.605%→+0.473%, flat-to-slightly-worse). Checked for outlier inflation before trusting it (standing rule): top-10 concentration in every cell is 11.0-21.8%, well under the 40% danger threshold — real, not tail-driven. The quartile-level grid (4×4) shows the same shape more granularly: mean pnl rises monotonically with stop width across the three freshest quartiles, then flattens/reverses in the most-extended quartile.

**Plausible mechanism, consistent with this session's own "MD Breakout Theorem"**: fresh/early-cycle breakouts are more likely genuine, so giving them room to survive normal adverse excursion pays off; by the time a stock is already extended, a wide adverse excursion is more often a real reversal than noise, so the same room doesn't help.

**Not promoted to a rule, for two reasons**: (1) a single borderline test (|t|=1.81, no second population to cross-check, unlike the SMA21/Family-C finding which had two independent populations pointing the same direction before being accepted) isn't enough on its own; (2) stop distance isn't a free dial here — it's *derived* from the structural low and ATR, not something choosable per trade. The only way to "act" on this would be a freshness-conditional override on stop width, which is exactly the same shape as the Body/ATR-conditional tighter-stop idea already tested and rejected earlier this session (and MAE-threshold, EMA34-break, 3-day-stall before that) — every one of those failed because a real minority of the "should be cut" subgroup recovers into a big winner, and a rule built on a borderline single-test signal is a bad place to risk repeating that failure. **Verdict: real, weak, swing-only, flagged as a lead — not validated, not actionable, no code change.**

## Pre-live-day regression check (2026-09-15) — two real crash bugs found and fixed in tools NOT covered by the unit tests

Today's `current_stop_level()` rewrite made `breakout_cont` require `state["structural_low"]` and `state["atr_entry"]` to both be real numbers (previously BC's pre-engagement stop only used `peak_close`/`atr14`, never touched `structural_low` at all). `backtest.py`/`monitor_positions.py`/`tests/test_backtest.py` were all updated together, but two other real, currently-used tools build their own ad-hoc state dicts and were missed — both would have thrown at the first BC candidate encountered:

1. **`daily_scan.py`'s `_initial_stop()`** (the `stop=₹X` column shown on every Tradable-Today/Watchlist row) — its state dict never included `atr_entry`. Fixed: added `atr_entry=row.atr14`, same convention as everywhere else.
2. **`trader_dashboard.py`'s `run_evening()`** (the "tonight's candidates" list) — passed `structural_low=None` for every `breakout_cont` candidate, harmless before today since BC never read it, fatal now. Fixed: computes a real structural low the same way `detect_entry()` does (20-day pre-entry `Low.min()`, `STRUCTURAL_LOOKBACK_BC`).

Both confirmed fixed by actually running them end-to-end on real cached data (not just re-reading the diff): `daily_scan.py` produced real stop values for two live BC watchlist candidates (PAYTM ₹1488.00, PINELABS ₹145.93); `trader_dashboard.py evening` produced real stop values for its top-5 candidates including a live BC one (KOTAKBANK ₹379.78). All 72 unit tests still pass.

**`monitor_position.py` (singular, older, pre-`monitor_positions.py` single-ticker CLI tool, superseded 10 days ago) has the same latent bug (no `atr_entry`, and a `structural_low=entry_price` placeholder that was never a real value even before today) — not fixed, since it isn't referenced anywhere and doesn't appear to be the tool actually in use (`monitor_positions.py`, plural, is what every other tool and this whole session's monitoring work wraps). Flagging its existence rather than silently leaving a dead trap; worth a decision (fix or delete) if it's ever invoked again.

**Live position check, same day**: the three real open positions in `open_positions.csv` (GRANULES, ANANDRATHI, VIJAYA — all `breakout_cont`) were re-read under the new mechanism via `monitor_positions.py`: stops recompute to ₹838.42 / ₹2048.75 / ₹1372.64 respectively, all still comfortably inside their `MAX_HOLD_DAYS=15` window (3, 4, 2 trading days held). Data freshness checked directly: cache tops out at Friday 2026-09-11's close, which is correct, not stale — Sept 12-13 were a weekend and Sept 14 a market holiday (confirmed via the trade journal's own note), and today (Tuesday Sept 15) hadn't closed yet at the time of this check. A `fetch_prices.py` run confirmed "0 new, 0 updated, 500 already current" — separately confirmed this environment's outbound yfinance calls are being rate-limited (HTTP 429, general internet egress itself is fine) rather than a real data gap.

## Same-close entry-fill bias, quantified (2026-09-15) — closes a gap flagged 2026-09-01, never investigated since

A veteran-trader review flagged this on 2026-09-01 ("is the backtest's same-day-close entry actually attainable live?") and it sat as an unaddressed open item. Direct user challenge revived it: `option_backtest.py`'s `simulate_option_trade()` (and every day+1-open variant built on it, e.g. `theta_bleed_check_open_exit.py`) prices the entry using the option's own end-of-day `ClsPric` on the entry day — but if the stock keeps running through the session after the intraday breach (this project's own "grind, not gap" finding says it usually does), that Close sits well past the price a trader acting on the real intraday breach would have paid.

There's no historical intraday *options* data anywhere in this project (`options_cache/` is one row per contract per day, not per tick), so the option side of this can't be measured directly. But `intraday_cache.py` has real 5-min *stock* bars (60-day trailing window) covering the exact same populations used throughout the SMA21/Family-C thread (`runs/pop_fresh40_small.csv` / `pop_fresh40_cutoff.csv`, both already carry a real `breach_time`). Built `entry_fill_bias_check.py`: for every trade, computed `run_pct = (entry_day_close/trigger_price - 1)*100` (how far the stock moves from the real breach level to that day's own Close) and two delta-agnostic day+1 return variants — one costed at the honest `trigger_price` (already the standing convention for every stock-side `day1_pnl_pct` elsewhere in this project), one costed at the entry-day Close (mimicking the options simulator's actual convention).

| | intraday (n=365) | intraday+cutoff (n=298) |
|---|---|---|
| Median stock run, breach→Close | +0.336% | +0.444% |
| % of days that ran further in the breakout direction | 58.4% | 60.1% |
| Day+1 return, entry=trigger price | win 68.5% / med +0.668% / mean +1.125% | win 67.8% / med +0.727% / mean +1.233% |
| Day+1 return, entry=entry-day Close | win 64.9% / med +0.227% / mean +0.290% | win 63.4% / med +0.206% / mean +0.288% |

Outlier-checked before trusting it (standing rule): top-10 `|run_pct|` concentration 17.2-18.8%, well under the 40% danger threshold — real, not a few huge movers. **The Close-based cost basis erases roughly 70-75% of the mean edge on this proxy.** Worse than a uniform haircut: splitting by eventual swing outcome, trades that became the biggest swing WINNERS ran the most during their own entry day (median run_pct +0.449%/+0.622% vs +0.179%/+0.221% for eventual losers) — so the Close-based convention shrinks the return on the best trades hardest, not evenly. Splitting by breach hour confirms the mechanism is exactly what it looks like: median run shrinks from +0.597% at a 9am breach down to ~0% (even slightly negative, small n) by 3pm — a pure "how much of the day is left to keep running" effect, not noise.

**Conclusion: every day+1 options number reported anywhere in this project has likely been conservative, not inflated** — the backtest is charging itself a worse cost basis than a trader acting on the model intraday (exactly what the `--live`/intraday-checkpoint tooling exists to support) would pay. Two honest limits on how far to take this: (1) options are leveraged with no delta/IV data anywhere in this project, so the real effect on premium is probably *larger* in % terms than this stock-level proxy shows, not smaller, but that can't be quantified further with what's cached; (2) real bid-ask spread at the volatile moment of breach isn't visible in end-of-day bhavcopy data and could eat into some of the apparent gain from buying earlier. **Not actioned as a backtest fix** — same reasoning already applied to the day+1-open refinement itself: no historical intraday options data exists to validate a corrected number, so this is deferred to live/forward experience the same way, just quantified now instead of only flagged. **User's explicit call once this was quantified: leave it as-is — a conservative-direction bias (real edge likely better than reported) is the acceptable direction to be wrong in for a real-money strategy; the risk that would actually need fixing is the opposite one (backtest inflated relative to reality).** Closed, not a standing action item.

## Real bug found live, mid-trading-day: `trader_dashboard.py` was silently missing freshness (2026-09-15)

Caught by a direct user question ("where is the freshness etc?") while checking the live morning dashboard mid-session. `live_checkpoint.py` has its own `_print_tier()` (lines ~685-713) that displays `freshness_score`, `consolidation_days`, `body_atr`, and `acceptance_state` — this project's most-validated entry-quality signals (freshness in particular: "the only signal validated across every population, every exit regime, and every metric tested," per the standing project summary). But `trader_dashboard.py` — the documented, recommended daily entry point — has its own, separately-maintained `_print_tier()` that never had these four fields added, even though `classify_candidates()` was already computing and attaching all of them to every candidate record. The two print layers had quietly drifted apart; the underlying data was never missing, only the display.

Fixed by copying live_checkpoint.py's exact field-extraction/formatting logic into trader_dashboard.py's `_print_tier()`, rather than re-deriving it independently (same reasoning this project applies to `detect_entry`/`check_exit` — one source of truth, no second copy to drift). Verified against real live data mid-session: JSWINFRA (a currently-open position) showed `freshness=6% [FRESH]`, `consol=5d`, `body/atr=0.35`, `accept=Pending`. All 72 tests still pass (display-only change, no logic touched).

**Direction check, since it's easy to get backwards**: `freshness_score` is defined lower=fresher (a percentile blend of RSI/momentum, see its own comment ~line 360-367) — 6% means the 6th percentile of extension, i.e. genuinely fresh, not extended. `fresh_setup` (the `[FRESH]` tag) is a separate boolean threshold check on the same underlying RSI/momentum inputs, independently computed — the two agreeing here (very low % *and* the boolean flag both saying fresh) is consistent, not a labeling bug. (First draft of this note got this backwards and was corrected immediately after being caught stating it wrong to the user live.)

## Live trend-strength context added to the dashboard (2026-09-16)

Grew out of a live, real-time investigation of AEGISLOG (held that day): `detect_entry()` returned `None` for it despite an intraday High well above its trigger, because Close fell back below the raw pivot by end of day. Digging into *why* it was on the primed list at all despite failing both `entry_signal()` (Close never crossed `high10_prior`) and, once checked directly, `base_filters_pass()` (fails on `ema34_rising10` persistence and 20-day momentum magnitude) revealed it had actually cleared the **VCP path** (`stage2_trend_template` + a valid `base_pivot()`), not the Breakout Continuation one — a distinction nothing in the live dashboard surfaced.

**Real gap identified**: being on the primed list only proves a candidate cleared *at least one* of the two pattern gates (`_passes_primed_checks()`'s own OR), not both — and a bare pass/fail hides the margin (e.g. AEGISLOG's RS rating turned out to be 99, near-perfect, vs. some BC-only names passing with much weaker RS). None of this was visible without manually re-running the entry functions by hand, as was done live in this thread.

**Added, reusing existing production logic rather than duplicating it**: refactored `vcp.py`'s `stage2_trend_template()` into a thin wrapper over a new `stage2_trend_breakdown()` that returns the individual sub-conditions (SMA stack, 52-week position, RS rating, etc.) — `stage2_trend_template()`'s own return value and behavior are unchanged, verified by the full test suite (72/72) passing before and after. `live_checkpoint.py`'s `classify_candidates()` now computes, per candidate: `vcp_qualified`, `bc_qualified` (which gate(s) actually cleared), `sma_stack_ok`, `rs_rating`, `pct_to_52w_high`. Both `live_checkpoint.py`'s own `_print_tier()` and `trader_dashboard.py`'s separately-maintained one were updated together this time (learned from the freshness-drift bug two days earlier) — new fields render as `gate=[VCP]`/`gate=[BC]`/`gate=[VCP+BC]`, `sma_stack=OK/no`, `rs=NN`, `52wk=NN%`.

**Verified against real live data**: AEGISLOG correctly shows `gate=[VCP] sma_stack=OK rs=99 52wk=92%`; several other same-day candidates (GESHIP, PAYTM, COALINDIA, REDINGTON, DIVISLAB, PTCIL) correctly show `gate=[BC]` only. Two names (LENSKART, MEESHO) correctly show no trend-strength fields at all — confirmed this is the NaN-guard working as designed (genuinely missing Stage-2 input columns), not a display bug.

**Explicitly scoped as a diagnostic/judgment layer, not a new validated signal**: this project already tested and rejected "dual-pattern qualification implies higher confidence" (win rate identical, 65.0% either way, on 40 real dual-qualified trades) — clearing both gates is not evidence of anything extra on its own. The value here is efficiency (seeing what would otherwise require manually re-running `detect_entry`/`stage2_trend_template`/`base_filters_pass` by hand, as happened live in this thread) and qualitative context (how much structural cushion a held position has, consistent with this project's own "MD Breakout Theorem" reasoning about tolerating normal adverse excursion) — not a new backtested ranking rule.

## RQ-47: Production Population Consistency Audit (2026-09-16/17) — 0 unexplained drift between live and backtest gates

Triggered by comparing a real third-party algo platform's trade call (StrykeX, AEGISVOPAK 2026-09-15) against our own logic: first pass said "liquidity is the only blocker" (checking `base_filters_pass()` alone), a correction then found `checklist_pass()` *also* independently fails (weak close, only 50.5% up the day's range vs. the required 70%) — but `checklist_pass()`/`reject_theta_trap()` turned out not to be part of `_passes_primed_checks()` (the actual live gate `shortlist_primed()`/`classify_candidates()` use) at all, only part of `entry_signal()` (the backtest/EOD gate). Both statements were true, just about two different, previously-undocumented gates — meaning the live dashboard and the backtest performance numbers had never been checked against each other for consistency.

**Built `population_equivalence_audit.py`**: for every real intraday breach across the full 5-year, 500-stock history (High crossing the trigger — what a live IOC would fill on), computes two independent verdicts using the real production functions (not re-derivations): **LIVE** = `daily_scan._passes_primed_checks()` on yesterday's frozen row + today's real High crossing the trigger; **BACKTEST** = `signals.entry_signal()` on today's fully-closed EOD row. Diffs them and attributes every mismatch to a specific cause.

**Result**: 72,860 breach events, 80.1% agree, 19.9% (14,487) mismatch — **every single one now attributable**, `OTHER_UNKNOWN` = 0. Getting to zero required catching two real bugs in the *audit script itself* (not production): (1) forgot to check `breakout_continuation()`'s own volume z-score condition, separate from `base_filters_pass()` — explained 5,464 of an initial 1,347+4,117 unexplained cases once added; (2) one remaining case (BEL, 2024-01-15) was an exact floating-point tie (`Close == high10_prior`) that fails `breakout_continuation()`'s strict `>` check but wasn't caught by a `<`-instead-of-`<=` label.

| Category | Count | % | Read |
|---|---|---|---|
| EOD-only telemetry (weak close never confirmed: 6,300; vol z-score gate: 5,464; `checklist_pass`: 1,320) | 13,084 | 90.3% | Expected — the live IOC genuinely fills, the EOD/audit gate correctly doesn't confirm it until the close is known. Not a bug. |
| Day-to-day indicator drift (yesterday's priming row vs. today's backtest row disagreeing on RSI/momentum/EMA34-persistence/trend, unrelated to liquidity) | 1,097 | 7.6% | Not hindsight — priming only refreshes once/day off yesterday's close, so this is a real, separate, legitimate mismatch source. |
| Liquidity floor (`MIN_TRADED_VALUE`) specifically | 497 | 3.4% | Matches the separate liquidity-ablation finding (same session) in magnitude, arrived at independently. |
| Theta trap specifically | 0 | 0% | Never the deciding condition in this dataset — `checklist_pass` is checked earlier in `entry_signal()`'s own order, so a theta-trap-only case gets attributed to checklist_pass first when both fail together. Methodology note, not a claim it never matters. |
| Freshness filter | 0 / N/A | — | Confirmed structurally zero — neither gate applies a freshness cutoff at all; freshness is a downstream research/ranking tool, never a live or backtest eligibility gate. |
| 13:00 scan cutoff | not tested | — | Honest gap — the full 5-year history has no real intraday breach-hour data outside the ~93-day `intraday_cache` window, so this specific dimension can't be verified at full scale. |

**Adopted governance, per critic response**: a clean three-gate naming — **Primed Gate** (`_passes_primed_checks`, everything knowable pre-entry, powers live IOC orders), **Entry Gate** (`entry_signal`, the exact backtest/performance-population gate), **Audit Gate** (`checklist_pass`/`reject_theta_trap`, post-close-only diagnostics/telemetry, never added to the live gate — doing so would reintroduce hindsight, confirmed directly by this audit since 90.3% of all mismatches are exactly this category behaving as designed). Also adopted: a standing "One Source of Truth" rule — no duplicate gate logic, no duplicate candidate definitions, extending the same discipline already used for `detect_entry`/`check_exit` to the priming/classification layer.

**Not yet done**: turning `population_equivalence_audit.py` into an actual CI regression test (so a future edit to `live_checkpoint.py`/`daily_scan.py` that accidentally adds/removes a gate fails automatically) — script exists, not wired into anything automated yet.

## RQ-48: liquidity floor bucket decomposition — and a real bug found in `concentration()` itself (2026-09-17)

The queued liquidity-floor bucket decomposition (₹0-25cr/25-50cr/50-75cr/75-100cr/100cr+, checking whether the earlier MIN_TRADED_VALUE ablation's result — removing the floor improves every quality metric — was uniform across the range or concentrated in one bucket, per critic flag) surfaced something bigger than the liquidity question itself: **`concentration()` — independently redefined in 19 separate research scripts across this project's history, always identically — has a real bug.**

**The bug**: `concentration()` always took the top **10 trades, a fixed count**, never a percentage of n. For a bucket of n=66-131, top-10 is ~8-15% of the population — a few winners naturally look "concentrated." For a combined n=576 population, that same fixed 10 trades is <2% of the population, so the ratio mechanically collapses even with the same big winners still inside it. Caught directly: the original two-bucket MIN_TRADED_VALUE ablation reported `>=50cr` combined concentration = 7.7% (reassuring), but splitting that same population into `50-75cr` alone and `75-100cr` alone gave 29.3% and 40.8% — a population's own subsets cannot legitimately look structurally riskier than the whole; the metric was lying, not the trades.

**Fix**: `research/metrics.py` (new shared module — see below) introduces `concentration_v2`: top `max(10, 10% of n)` trades by `|pnl|`, scale-invariant. Verified: `>=50cr` combined 7.1%→26.7%, `50-75cr` 29.3%→27.4%, `75-100cr` 40.8%→27.5%, `100cr+` 8.3%→25.5% — the paradox disappears; everything converges to ~25-27% once measured fairly. **The current ₹100cr+ bucket's concentration was understated by every past ablation that quoted it (8.3% reported, ~25.5% real)**, including the original MIN_TRADED_VALUE test and RQ-47.

**Governance adopted (critic, "Versioned Metrics")**: `concentration_v1` (old, fixed-top-10) kept only for reproducing historical reports exactly; `concentration_v2` (aliased `concentration`) is the new default. **Scope decision: fix forward only, spot-check 4 specific findings where concentration was part of the actual promotion decision (liquidity floor, OI buildup, SMA21 trail vs. baseline, stop-family Family C vs. baseline) — do not re-run all 19 scripts.** Frozen research (RVOL, exit architecture, etc.) stays frozen; re-litigating settled findings over a secondary diagnostic (win rate/median/expectancy — the four primary metrics — were never affected by this bug) is exactly the research debt this project's own practicality discipline warns against.

**Liquidity floor result, with corrected concentration**:

| Bucket | n | Swing win | med | exp | conc_v2 | conc_v2 90% bootstrap CI | Real ATM option availability |
|---|---|---|---|---|---|---|---|
| ₹0-25cr | 105 | 70.5% | +4.99% | +3.726% | 24.7% | 21.0-28.4 | 0% |
| ₹25-50cr | 131 | 65.6% | +2.96% | +2.173% | 25.6% | 22.9-28.2 | 30% |
| ₹50-75cr | 96 | 70.8% | +3.09% | +2.211% | 29.3% | 23.7-34.9 | 48% |
| ₹75-100cr | 66 | 71.2% | +2.84% | +2.267% | **40.8%** | **35.4-45.2** | 58% |
| ₹100cr+ (current) | 414 | 62.3% | +2.09% | +0.950% | 25.5% | 23.9-27.0 | 79% |

Bootstrapped the 75-100cr concentration specifically (critic: "n=66 is exactly the kind of bucket where one regime can distort things") — its CI (35.4-45.2%) does not overlap any neighboring bucket's CI at all. **Genuinely the worst bucket, not sample-size noise; cause not yet investigated** (candidate hypotheses: sector composition, thin mid-cap options structurally clustering here, higher false-breakout rate — none tested).

**Decision (signed off)**: production stays **₹100cr** — not because lower-liquidity swing trades perform worse (they don't, once concentration is measured fairly), but because **real options tradability is the binding constraint**, not backtest quality: ATM contract availability collapses from 79% (100cr+) to 58%/48%/30%/0% moving down through the buckets. One engine serves both stock and option recommendations, so the floor has to satisfy the harder constraint. Research populations remain unfloored (₹0+) for future ablations; a possible future refinement (not adopted yet) is splitting the floor by product — swing-only recommendations at ₹50cr+, option recommendations at ₹100cr+ — flagged as v32-scope, not acted on now.

**Second correction, same day, bigger than the concentration one — a real look-ahead bias in the underlying population, caught pursuing an unrelated parked question (the freshness Entry-Gate-vs-Primed-Gate mismatch)**: `min_traded_value_ablation.py` (the script that built this whole bucket decomposition's population, `runs/min_traded_value_0.csv`) computes `freshness_score` from the breach day's own row (`i`) — but that day's RSI14/momentum aren't knowable until after the market closes, while the breach itself fires intraday. Real live priming happens pre-market off *yesterday's* frozen row. Confirmed precisely: recomputing freshness from row `i-1` instead reproduces `runs/rsi_max_sweep_80.csv`'s cached freshness_score at 100% exact match (14,215/14,215) — that file was always correct; this script's `i`-based computation was the bug, not an architectural Entry-vs-Primed-Gate difference as first suspected. Effect size is large: 15.3% of the population was fresh under the biased computation, **56.5% under the corrected one** — 41.3% of all rows flip classification.

**Re-ran the full bucket decomposition with corrected freshness** (`min_traded_value_0_corrected_freshness.csv`):

| Bucket | n (old→corrected) | Swing win (old→corrected) | Swing exp (old→corrected) | conc_v2 (old→corrected) | Real ATM availability (old→corrected) |
|---|---|---|---|---|---|
| ₹0-25cr | 105→492 | 70.5%→72.0% | +3.726%→+5.059% | 24.7%→27.0% | 0%→2% |
| ₹25-50cr | 131→492 | 65.6%→67.7% | +2.173%→+3.331% | 25.6%→26.5% | 30%→19% |
| ₹50-75cr | 96→359 | 70.8%→69.1% | +2.211%→+3.849% | 29.3%→30.0% | 48%→47% |
| ₹75-100cr | 66→252 | 71.2%→67.9% | +2.267%→+3.660% | 40.8%→32.7% | 58%→54% |
| ₹100cr+ (current) | 414→1403 | **62.3%→67.9%** | **+0.950%→+2.912%** | 25.5%→29.6% | 79%→75% |

**The headline correction**: the current ₹100cr+ bucket looked like the clear worst swing performer under the biased population (62.3% win, a real gap below every other bucket) — that gap was mostly a look-ahead artifact. With corrected freshness and a much larger, properly-classified sample (1,403 vs. 414), it lands at 67.9% win, essentially tied with the other buckets (67.7-72.0%). **The production decision itself does not change — it gets more solidly justified, not less**: before, the framing was "give up real swing quality for options tradability"; after correction, it's "give up almost nothing on swing quality, and still get the options tradability." Options-side availability by bucket is basically unchanged in shape. The 75-100cr bucket's elevated concentration also moderates (40.8%→32.7%) with the bigger, correctly-classified sample, though it's still the highest of the five.

**Scope note, not yet done**: this correction was applied only to the liquidity-bucket decomposition (the highest-stakes item, since it fed an actual production decision). Other findings built on freshness-conditioned populations from *other* scripts weren't re-checked here — each script needs its own freshness computation verified against `_freshness_score()`'s real (i-1, yesterday's-row) convention before being trusted, the same standing lesson as the concentration bug: fix forward, spot-check only what actually mattered to a decision, don't re-litigate everything at once.

**OI buildup revival — promoted to Audit-Gate telemetry only, not a live gate**: re-tested `oi_buildup_bullish()` (rejected/deleted 2026-09-06) under current methodology, found the original rejection reversed (buildup-present now outperforms). The concentration-artifact fix removed the main residual doubt (present vs. absent are statistically indistinguishable on both `concentration_v2`, 27.1% vs 27.7% swing, and an independent Gini check, 0.399 vs 0.422 swing — two different sample-size-invariant methods agreeing). Final gate (critic): does OI buildup add incremental value beyond freshness alone, not just look clean?

| Population | n | Swing win | Swing exp | ATM day1 win | ATM day1 exp |
|---|---|---|---|---|---|
| Freshness only | 2579 | 58.9% | +0.237% | 59.6% | +2.037% |
| + OI buildup present | 686 | 60.9% | +0.715% | 61.9% | +2.779% |
| + No buildup (absent) | 1893 | 58.1% | +0.064% | 58.6% | +1.706% |
| + Top breadth (≥80) | 692 | 66.0% | +1.204% | 62.2% | +2.505% |
| + OI present + breadth≥80 | 214 | 67.8% | +1.591% | 67.0% (n=194) | +5.023% |

Real, positive incremental lift confirmed (+2.0pp win/+0.48pp exp swing, +2.3pp win/+0.74pp exp options over freshness-only) — matches the critic's own prediction ("+2-3pp win rate, slight expectancy lift") closely. Breadth alone is the stronger single conditioner; stacking OI+breadth adds a further, thinner-sample lift on top. **Since futures OI data is EOD-bhavcopy-only with no live/intraday feed (structurally confirmed), this can only ever be Audit-Gate-style telemetry — never wired into the live Primed/Entry gates.** Not yet done: deciding a concrete display/telemetry format for it (e.g. surfaced in `trader_dashboard.py`'s evening wrap-up alongside `checklist_pass`/theta-trap diagnostics), and not yet investigated why the original 2026-09-06 test's conclusion reversed (three things changed at once — population scope, options convention, stock exit mechanism — no decomposition done isolating which one mattered).

## Extended universe (small/mid-cap) test — real, negative-leaning result; population parked (2026-09-17)

Prompted by comparing StrykeX's large/mid/small-cap watchlists against our NIFTY 500 universe (see the git history around this date for the full universe-scope investigation: our universe confirmed essentially perfectly current against a fresh NSE fetch, StrykeX's overlap tapering exactly as expected by tier — large ~92%, mid 44%, small 2%) — and motivated by the RQ-48 liquidity-bucket finding that lower-liquidity names within our *existing* universe show better raw swing numbers. Built `extended_universe.csv`: 195 real, individually-verified tickers from StrykeX's large+mid-cap lists that are genuinely outside our NIFTY 500 universe (every symbol checked against NSE's full equity master list; excluded 8 confirmed duplicates already in our universe under a renamed/demerged current symbol — ZOMATO→ETERNAL, LTIM→LTM, PEL→PIRAMALFIN, GMRINFRA→GMRAIRPORT, plus 4 underscore/hyphen/ampersand naming variants — and 25 unresolved names with no findable current NSE symbol). Zero of the 195 have real F&O contracts (checked directly against the live bhavcopy) — stock-only population. Fetched full 5-year price history, ran the real production backtest (`backtest.run()`, `require_regime=True`, no re-derivation):

| | n (unconditioned) | Win rate | Expectancy | Concentration |
|---|---|---|---|---|
| `require_regime=True` (real production) | 30 | 46.7% | −2.424% | 54.8% |
| `require_regime=False` (observation only) | 96 | 42.7% | −2.040% | 27.0% |

**Correction, caught by direct user question ("did we run the same population thing... like freshness etc?") — the table above was never freshness-conditioned, unlike every other population this project reports on.** Applied the standard freshness≤0.40 cut properly:

| | n (freshness≤0.40) | Win rate | Expectancy | Concentration |
|---|---|---|---|---|
| `require_regime=True` (real production) | **0** | — | — | — |
| `require_regime=False` (observation only) | **7** | 57.1% | −0.756% | 100.0% (mechanically forced at n=7, same degenerate-small-n artifact as the OI-buildup work — not a real statistic) |

**Honest, corrected conclusion**: once conditioned the way every other population in this project is conditioned, there's essentially no usable data here at all — not enough trades to say anything, positive or negative. The unconditioned table above (which read as negative-leaning) is not a valid basis for a conclusion either way; it's included only as a record of what was actually computed, not as evidence against the hypothesis. **This population remains genuinely untested, not rejected.** Zero VCP entries either way across the whole 195-ticker set is still a real, freshness-independent observation worth keeping. **Population parked, not deleted** — `extended_universe.csv` and its fetched price history (`data_cache/`) are kept as-is for reproducibility, but this is not an active research thread; not wired into the daily scan, not currently being expanded further. Revisit only if a specific new reason comes up (e.g., a much bigger version of this same test, or a different hypothesis specific to this population) — don't treat the RQ-48 liquidity-bucket finding as license to keep pursuing smaller-cap names in general, since this specific attempt didn't bear it out.

**New shared module**: `research/metrics.py` — `expectancy()`, `win_rate()`, `concentration_v1`/`concentration_v2` (aliased `concentration`), `gini()`, `bootstrap_ci()`. New research scripts should import from here rather than pasting local helper defs (the exact duplication that let this bug go unnoticed in 19 places for weeks). `liquidity_bucket_decomposition.py` migrated as a worked example (verified byte-identical output before/after migration).

### RQ-48 close-out: remaining 2 spot-checks, a real self-caught error, and a meta-finding (2026-09-17)

**SMA21 trail vs. baseline — clean, re-verified with `concentration_v2`, decision unchanged.** Candidate still wins on expectancy and concentration, both populations (full pop: +4.972%/29.7%→+5.133%/28.6%; freshness≤0.40: +2.404%/27.9%→+2.473%/26.8%).

**Family C vs. baseline — a real process error, caught and corrected, decision unchanged.** First attempt patched `stop_family_research.py` (a pre-SMA21/pre-`MAX_HOLD_DAYS` sweep script, never meant to be authoritative afterward) and reported the result as new information — it wasn't; the real question was already answered on 2026-09-14/15 using the actual production `check_exit()` on the correct freshness≤0.40 3-population bracket (see "Family C × SMA21 interaction" section above: daily 59.9%→60.6% win, 0.737%→0.811% exp, conc_v1 10.1%→9.2%; intraday and intraday+cutoff tied-to-slightly-worse). Caught by direct user question ("we only changed concentration — why did everything else change too?"). Confirmed the v1-vs-v2 question specifically: unlike the liquidity buckets (different-sized groups), baseline vs. Family C are always compared at *equal* n, so the dilution artifact mostly cancels — verified directly (same trades, filtered to freshness≤0.40: conc_v1 1.3% for both variants, conc_v2 27.6% baseline vs 29.3% Family C) — **the relative verdict is not flipped by the bug. Decision: keep Family C, unchanged** (real small edge, real small extra concentration cost ~+1.5-2pp under v2).

**Meta-finding**: every v2 recomputation across this whole thread (liquidity buckets, OI buildup, SMA21, Family C) converges to roughly the same ~25-30% concentration regardless of which filter/mechanism is tested. **~25-30% is the honest baseline concentration for this project's swing populations, not a per-test result** — most "concentration checked clean" claims near 0% were an artifact of population size, not evidence of low risk. Record this as the reference range for future concentration checks, not the old "should be near 0%" intuition.

**Process lesson (critic, from the Family C error)**: before trusting a research rerun, verify in this order — (1) population, (2) entry convention, (3) exit implementation, (4) production parameters, (5) only then metric implementation. The Family C error changed #5 deliberately but changed #1-3 unknowingly (wrong script, wrong population, stale exit mechanism) — that combination is exactly how a dramatic-looking "finding" gets manufactured by accident. No production code was touched before the error was caught, so no strategy damage resulted.

**Freshness population-consistency caveat — RESOLVED (2026-09-17, later same day, see "RQ-48" section above for the full writeup)**: originally flagged as an unexplained Entry-Gate-vs-Primed-Gate architectural mismatch (Extended beating Fresh on `min_traded_value_0.csv`, the correct direction on `runs/rsi_max_sweep_80.csv`) and parked. **Root cause found**: not architectural at all — `min_traded_value_ablation.py` computed freshness from the breach day's own row (a real look-ahead bias; that day's RSI/momentum aren't knowable until after close), while `rsi_max_sweep_80.csv` correctly used the prior day's frozen row, matching real live priming timing. Confirmed via 100% exact match recomputing with the prior-day row. RQ-48's liquidity-bucket decomposition (built on the same biased population) was re-run with corrected freshness — production decision unchanged, more solidly justified than before. Standing lesson: verify any research script's `freshness()` reconstruction uses the prior day's row, not the entry/breach day's own row, before trusting a freshness-conditioned result.

**Magnitude test (2026-09-17)**: `oi_buildup_bullish()` is a pure binary (present/absent) by design — `last_price > first_price and net_oi_chg > 0`, throwing away the actual size of both the price move and the OI change. Tested whether magnitude adds value: reconstructed `oi_pct_chg` (net OI change as a % of the pre-window OI base) and `price_pct_chg` for the same 2,234-row population. Correlation with outcome is essentially zero for the OI component (Pearson 0.045 swing, 0.033 options) vs. a real (if still weak) 0.130 for the price component — the price direction carries the signal, not the OI magnitude. Terciles across the whole population show a real "very negative OI change is bad" effect but no dose-response above that; terciles *within* the already-`present` group show expectancy *declining* as OI% increases (0.930%→0.777%→0.467%), the opposite of what a magnitude hypothesis predicts. Concentration checked clean across all terciles (26.7-28.1% swing, 36.1-39.3% options — not an outlier artifact). **Conclusion: keep the binary formulation** — magnitude-weighting would add real complexity (a percentile/z-score transform) for no measurable gain, exactly the kind of addition the critic's "Complexity Budget" governance argues against.

**OI buildup, final documentation**: **EOD Audit Telemetry** — record whether qualifying OI buildup is present after the trade. Informational/audit telemetry only; does not participate in the live Primed Gate or Entry Gate.

**A real bug found live, same day, using the feature for the first time (2026-09-17)**: `trading_days()` derives its calendar purely from whatever files exist in `options_cache/` — when checking real trades (DIVISLAB/OIL/LAURUSLABS, all entered after the cache's then-current bulk-backfill boundary of 2026-09-03), `oi_buildup_bullish()` silently used the last 3 *cached* days (09-01/02/03) instead of a window actually ending on the requested entry date, for every date beyond the cache's real coverage — no error, no `None`, just a plausible-looking wrong answer. Fixed with an explicit `days[-1] != date: return None` guard (the window must genuinely end on the requested date), then backfilled the missing week (`fetch_stock_options.py 2026-09-04 2026-09-17`). **Checked exposure on the published historical finding**: only 3 of 2,579 rows in `runs/oi_buildup_retest.csv` had `entry_date` past the then-current cache boundary (population's own max date, 2026-09-09, barely exceeded it) — 2 flipped True→False on recompute, patched in the CSV. Far too small a shift (2 of 2,579) to move win rate/expectancy/concentration on populations of n=686/1,893 — **the OI-buildup finding itself is unaffected**, only 3 individual rows were ever at risk and now all are correct.

**Wired into production (2026-09-17)**: `oi_buildup_bullish(ticker, date)` restored into `option_backtest.py` (exact reconstruction, verified against the research script's own cached results — 5/5 spot-checked, byte-identical). Hooked into `trader_dashboard.py`'s `run_night()` via `_log_oi_buildup_for_new_entries()`, scoped only to real new entries (`open_positions.csv` rows with `entry_date == today`) — never the whole F&O universe, never re-touches older positions. Lazily fetches just that day's F&O bhavcopy (`fetch_stock_options.fetch_day(today)`, idempotent, ~5.4MB, skipped if already cached) rather than a standing nightly job — triggered by the night refresh you already run, not a new step, and can't be triggered from the intraday `--refresh-primed` step since NSE doesn't publish the day's bhavcopy until after close. Result appended to `trade_journal.csv` via the existing `journal_add()` mechanism (`tier="oi_buildup"`, notes = `present`/`absent`/`N/A (not F&O)`/`N/A (no futures data)`) — pure record-keeping, guarded against duplicate logging on same-day reruns. Never touches `classify_candidates()`, `_passes_primed_checks()`, or `entry_signal()`.

**RQ-48 final state, all items closed**:

| Item | Decision |
|---|---|
| Concentration bug | Fix-forward only; frozen studies not reopened wholesale |
| True concentration baseline | ~25-30% for these swing populations |
| Liquidity floor | ₹100cr stays in production |
| OI buildup | Promoted to Audit telemetry (see above) |
| SMA21−2% trail | Validated; keep |
| Family C initial stop | Validated; keep |
| Freshness gate mismatch | Parked research-integrity issue; not production-blocking |

## base_filters_pass() threshold audit — 3 never-swept core gates, real headroom found on 2 of 3 (2026-09-17)

Audited every tunable constant in `base_filters_pass()`/`checklist_pass()` for when it was last validated. Three of the "universal gates applying to every entry" (`RSI_MIN=55`, `EMA34_RISING_DAYS_MIN=9`, `MOMENTUM_20D_MIN=1.05`) traced back via `git blame` to the project's very first commit (2026-08-30) — original spec-following picks, **never swept at all**, unlike `RSI_MAX` (properly re-swept, RQ-34, 2026-09-13) or `VOL_ZSCORE_MIN`/`vcp.LAST_LEG_TOLERANCE` (swept once, 2026-08-30/31, on an older population definition).

**Methodology note, important**: deliberately NOT freshness-conditioned. `freshness_score = 0.5×percentile(RSI14) + 0.5×percentile(mom20)` — the same two quantities `RSI_MIN`/`MOMENTUM_20D_MIN` gate on directly. Conditioning a re-sweep of those thresholds on freshness≤0.40 would be circular (pre-filtering by the very thing being thresholded). Instead reused the exact "real live-equivalent population" mechanism already established in `live_equivalent_population.py` and used properly for RSI_MAX's own RQ-34 re-sweep: `base_filters_pass()` (with whichever threshold is under test) AND the day's real intraday High crosses the trigger (`high10_prior × 1.005`) — full multi-year, no `intraday_cache` dependency, one threshold swept at a time, others held at current production value. Both real swing (`backtest.check_exit()`, current mechanism) and real options (day+1-open, F&O-scoped) reported, per the standing "check both" convention. Script: `base_filters_threshold_sweep.py`.

**RSI_MIN** (current 55): 40 through 55 are statistically indistinguishable (n≈16,200-16,239, win/exp flat) — very few real breakouts have RSI in that range at the moment of breach, so the current floor does almost no filtering work. Real, monotonic improvement starts above 55, plateauing around **75-80** (n=1,969 at 80: win=70.4%, exp=+3.687%) before the sample gets too thin to trust (n=487 at 85, win rate actually dips to 69.0% despite higher expectancy — the small-sample instability this project's own discipline warns about). Concentration stays flat/mild throughout (30.4%→31.8%) — the gain is real, not a concentration artifact — but comes at a steep candidate-count cost (16,200→1,969 at 80, an 88% reduction).

**EMA34_RISING_DAYS_MIN** (current 9, out of 10): no real signal in either direction across 5-10 (60.8-61.0% win, 0.996-1.065% exp, all within noise). Current value sits in a genuine plateau — nothing to gain by moving it.

**MOMENTUM_20D_MIN** (current 1.05, i.e. +5%): win rate plateaus early, around **1.10-1.15** (61.7% both), essentially flat all the way to 1.30 (62.0%) — rising expectancy beyond the plateau is the "fewer, bigger trades" effect, not a real win-rate gain. Concentration actually *improves* as the floor rises (30.4%→28.2%) — a clean, real signal. Candidate-count cost is far more modest than RSI_MIN's (16,200→7,778-11,982 at 1.10-1.15, a 26-52% reduction).

**Critical correction, caught by direct user pushback ("this makes n×m combos as soon as we find something which affects our population") — the RSI_MIN/MOMENTUM_20D_MIN "headroom" above is NOT independent of freshness, it directly conflicts with it.** Checked the freshness_score distribution of the fires captured at each threshold: RSI_MIN=55 (current) → mean freshness 0.641, only 17.7% actually fresh (≤0.40); **RSI_MIN=80 → mean freshness 0.911, 0.0% fresh**. Raising RSI_MIN/MOMENTUM_20D_MIN as a blanket gate selects for the *opposite* end of the freshness spectrum from what this project's single most validated finding says is best — it isn't complementary headroom sitting on top of the freshness discipline, it's trading away the fresh population entirely in favor of a narrow, fully-extended one. The apparent win-rate/expectancy gain at RSI_MIN=80 is real, but it describes a different, much smaller, extended-only regime, not an improvement to the existing (fresh-favoring) system.

**Conclusion, nothing adopted (explicit user instruction, doubly correct now)**: raising `RSI_MIN` or `MOMENTUM_20D_MIN` as gates would work *against* the freshness discipline, not with it — do not treat either sweep as "found headroom" without this caveat. If there's a real, separate idea buried in here, it's that "very extended + very high RSI/momentum" might be its own distinct pattern (a momentum-continuation regime) worth a dedicated look someday — but that's a new, bounded research question, not a threshold retune, and not proposed for now. `EMA34_RISING_DAYS_MIN` needs no attention either way.

**Queued for this same audit, not yet run (2026-09-18): the `high10_prior` pivot window itself (`signals.py`'s `df.High.shift(1).rolling(10).max()`).** Surfaced by a direct user question while reviewing the RQ-53 fakeout-confirmation work — the 10-day window is in the exact same "first-commit default, never swept" category as `RSI_MIN`/`EMA34_RISING_DAYS_MIN`/`MOMENTUM_20D_MIN` above (confirmed via `git log`/`grep`, no comment anywhere justifying 10 specifically). General industry rationale exists for the *category* (N-day-high breakout pivots — Darvas Box, O'Neil/CANSLIM base breakouts, Minervini VCP all use some recent-high-after-consolidation pivot, commonly in the 1-3 week range), but nothing here justifies 10 over 8/15/20 specifically. When picked up: same mechanism as this section (`base_filters_threshold_sweep.py`-style, real live-equivalent population, both swing and options), sweep the window across e.g. 5/8/10/15/20 days, one at a time, current value (10) held as the comparison baseline.

## Live StrykeX call tracking, ongoing tally (2026-09-17, pure observation, not acted on)

Per explicit user instruction — collecting data on how real StrykeX calls behave over time, not a signal to change anything. Running tally: BOSCHLTD (real loser, 2026-09-16), AEGISVOPAK (mixed, liquidity/weak-close blocked, 2026-09-15), MCX 3250CE (real winner so far, BC rejected on RSI alone — 52.7 vs 55 — everything else passed), AUROPHARMA 1680CE (real winner so far, BC rejected on RSI 49.2 and momentum +1.14%), GOCLCORP swing (real winner so far, BC rejected on **liquidity alone** — ₹16.7cr vs ₹100cr — RSI/EMA34-persistence/momentum all genuinely passed), KSL swing (real winner so far, same liquidity-only rejection, ₹13.7cr), ZOTA swing (real loser/non-starter so far, genuinely weak — fails RSI, momentum, EMA34 persistence, and liquidity all at once). None of GOCLCORP/KSL/ZOTA are in our NIFTY 500 or F&O universe at all. The two liquidity-only-blocked names are 2-for-2 real winners so far, consistent with RQ-48's own finding — still just anecdote at n=7, not evidence, kept as a running log only.

**Watchlist batch, same day (KIMS, RAINBOW)** — both genuinely IN our NIFTY 500 universe this time (unlike GOCLCORP/KSL/ZOTA), and both genuinely weak by our criteria — multiple independent failures each, not a single clean blocker like GOCLCORP/KSL. **KIMS**: RSI14=44.7 (needs >55), EMA34 persistence 0/10, momentum −4.82% (needs +5%, actually negative), liquidity ₹38.5cr (needs ₹100cr+); real move today +3.29% (766.65→791.85), a bounce our setup gave no reason to expect. **RAINBOW**: RSI14=49.7, EMA34 persistence 1/10, momentum −0.10% (flat), liquidity ₹11.9cr; real move today +1.11% (mild). Neither shows a base_pivot either. Read: unlike the liquidity-only-blocked pair, these two look like correct rejects on the merits, not a missed opportunity — real price moved a little, but nothing in the actual setup (as of the prior close) supported it.

## v31 FROZEN (2026-09-17, critic sign-off on Update 50)

Production architecture, as it stands, is internally consistent and frozen — no new production filters until live paper trading produces real evidence, not another backtest sweep.

| Layer | Mechanism |
|---|---|
| Entry | Freshness (ranking, never a gate) + BC/VCP rules + 13:00 execution cutoff |
| Exit | Structural stop + SMA21−2% trail + 15-day cap |
| Options | Day+1-open exit (live-trail experiment only) |
| Audit | OI buildup, weak close, volume z-score — EOD-only, never gates |

## Freshness, precise definition (2026-09-17 — supersedes every earlier "validated across every population" statement)

**Freshness is the strongest validated pre-entry quality signal on the Primed-Gate population. It predicts trade quality before end-of-day confirmation is available. It is largely redundant after Entry-Gate confirmation, because weak-close, volume-confirmation, and `checklist_pass` already encode much of the same information.**

Three phases, three different roles:
- **Primed** (real IOC live entry, no EOD information yet): freshness matters a lot — this is where it was originally validated and where it actually gets used live.
- **Entry** (EOD-confirmed, backtest population): freshness shrinks to near-zero, because EOD confirmation already captured most of what it would have added.
- **Audit** (post-close only): OI buildup, volume z-score, weak-close — these are where the EOD-only information lives.

This isn't a downgrade of freshness — it's a correction of *where* it was claimed to apply. It was never tested as failing anywhere; it was mis-stated as universal when it's actually phase-specific.

## Research Integrity Rule #2 (2026-09-17, critic-proposed, adopted)

**Every feature used for Primed-Gate or live IOC research must be computed from the latest information available *before* the breach.** If a feature uses the breach day's own close, RSI, momentum, or volume, it belongs to Entry Gate or Audit Gate research only — never Primed Gate. This is the rule `min_traded_value_ablation.py`'s freshness computation violated (see the look-ahead bias section above) — the single most valuable bug found in the whole project's history, per the critic, because it's a direct violation of "no information unavailable at decision time," the same principle the Primed/Entry/Audit gate separation (RQ-47) already exists to protect. Sits alongside Rule #1 (One Source of Truth, RQ-47) as a standing governance principle, not a one-off fix.

## Fragility risk wired into the live dashboard (2026-09-17)

Real Fragility Margin is a day+1 outcome, not knowable at entry — what's live is an **estimate** (`live_checkpoint._fragility_risk()`), built from the two pre-entry features `fragility_margin_check.py` found actually predict it: `freshness_score` (already computed live, matches Research Integrity Rule #2) and a live `body_atr` proxy (today's partial intraday bar's Open/Close against yesterday's frozen `atr14` — same live-partial-bar convention as `dist_to_trigger`/`velocity` elsewhere in `classify_candidates()`). Each feature's real quartile fragile-rate (from the n=491-winner research population) is looked up and averaged into a single estimate, bucketed Low(<16%)/Medium(16-22%)/High(>22%) around the population's own 16.5% base rate. Wired into both `live_checkpoint.py`'s and `trader_dashboard.py`'s separately-maintained `_print_tier()` together (learned discipline from the earlier freshness-drift bug) — new `fragility=Low/Medium/High(~NN%)` field. Verified against real live data (2026-09-17 evening check) and all 72 tests still pass. **Explicitly telemetry only, never a gate or filter** — per the critic's own framing, fragile trades include real winners (PAYTM-style explosions), and skipping them would repeat the exact mistake the acceptance/pullback/Body-ATR-as-gate ideas already made and were rejected for.

## v32 roadmap (critic-proposed, adopted as the working priority order)

| Area | Priority |
|---|---|
| Live paper trading (30-50 real trades before touching filters again) | Highest |
| Fragility Margin → live dashboard telemetry | **Done (2026-09-17)** — see below |
| OI buildup telemetry | Done |
| RSI_MIN/MOMENTUM_20D_MIN population-independent audit (critic's proposed RQ-51) | **Done (2026-09-17) — REJECTED, see below** |
| Liquidity floor | Leave at ₹100cr until options/swing universes are actually separated |
| Extended universe (small/mid-cap) | Parked |
| More stop-mechanism experiments | Frozen — none until live paper trading produces evidence |

## RQ-51: RSI_MIN population-independent audit — REJECTED, not even Audit telemetry (2026-09-17)

Critic's proposed test for the RSI_MIN/MOMENTUM_20D_MIN "headroom" flagged in the threshold audit above: sweep RSI_MIN across three populations (Primed Gate, Entry Gate, real intraday+13:00-cutoff), promote only if it improves Primed without degrading Entry and plateaus rather than peaking — the same treatment `RSI_MAX` already got via RQ-34. Reused `base_filters_threshold_sweep.py`'s existing Primed-Gate numbers, built a new Entry-Gate sweep (`backtest.detect_entry()`, full `entry_signal()` chain, `require_regime=False`), and reused the existing real 93-day intraday populations (`runs/pop_fresh40_small.csv`/`pop_fresh40_cutoff.csv`, both already carry `yday_rsi14` — correctly the prior day's row, Research Integrity Rule #2 compliant — just re-filtered, no resimulation needed).

| RSI_MIN | Primed Gate (full history) | Entry Gate (full history) | Intraday+13:00 cutoff (real, 93 days) |
|---|---|---|---|
| 55 | n=16,200, 60.8% win, +1.002% exp | n=2,141, 69.0% win, +3.658% exp | n=272, 62.5% win, +1.255% exp |
| 60 | n=15,826, 61.1%, +1.067% | n=2,133, 69.0%, +3.671% | n=202, 61.4%, +1.111% |
| 65 | n=13,805, 62.3%, +1.342% | n=1,933, 69.8%, +4.023% | n=59, 61.0%, +0.518% |
| 70 | n=9,415, 64.5%, +1.852% | n=1,378, 73.9%, +5.117% | **n=1, 0.0%, −0.049%** |
| 75 | n=4,937, 66.1%, +2.457% | n=730, 77.0%, +6.510% | n=0 |
| 80 | n=1,969, 70.4%, +3.687% | n=307, 79.8%, +8.167% | n=0 |

**Verdict: fails, on the population that actually matters.** By the letter of the promotion rule, both Primed Gate *and* Entry Gate show real, monotonic improvement (Entry Gate even more dramatically) — a naive read would call that a pass. But the real, live-representative population shows none of it: win rate flat-to-declining (62.5%→61.4%→61.0%→0.0%), and the sample is functionally gone by RSI_MIN=70 (n=1, then 0). Two large historical populations agreeing with each other is not sufficient when neither has ever been checked against real, current conditions, and the one population that does check that shows nothing to confirm. **Rejected — not promoted to production, not even Audit telemetry.** The dramatic multi-year numbers likely reflect a real historical pattern (possibly concentrated in specific past episodes/regimes) that simply doesn't have enough live-representative occurrences right now to act on. Directly validates the user's own real-time skepticism ("RSI high = overbought, bound to fail — how are we winning in the increased RSI scenario?") raised independently before this result came back — the classic overbought concern holds up better than the big-population number did.

## v32 governance, agreed with the critic (2026-09-17, after RQ-51) — Research Integrity Rules #3/#4, "three pillars" telemetry model, and the Trader Card/engine split

**Research Integrity Rule #3 (Promotion Rule, revised)**: a production gate must (1) improve the Primed population, (2) not materially degrade the Entry population, AND (3) have enough live-representative support (the real intraday+13:00-cutoff population) to show the effect is observable where it will actually be traded — not necessarily statistically significant, but the sample cannot *disappear*. RQ-51's own RSI_MIN sweep is the exact case this rule exists to catch: it passed conditions 1 and 2 cleanly and still had to be rejected, because condition 3 failed (n→1→0 by RSI_MIN=70). The literal two-condition version of RSI_MAX's original promotion rule would have said "promote" here — this is the correction.

**Research Integrity Rule #4 (Minimum Population Rule)**: never promote a production rule solely because it improves a population smaller than 500 trades, unless it *also* improves a larger parent population, or it has an independently-justified mechanism and is being transferred from elsewhere (e.g. VCP geometry, transferred from BC with its own separate justification, not just "it worked on a small VCP sample"). Prompted by a real, named pattern: freshness≤0.40 → 13:00 cutoff → Primed-only → intraday-cache-only → options-only → ITM-only → current-month-only → DTE≥10 → Family C → SMA21 → 15-day cap — every individual restriction was justified on its own, but stacked together the representative population for some questions had shrunk to ~298 trades in one branch. Each restriction was checked independently at the time, but the rule exists so future stacking gets checked explicitly, not accumulated silently.

**Fragility Margin reframed as a third pillar, not just a new metric**: Freshness = "should I even look at this?" (entry-quality, eligibility). Fragility = "how precise must my execution be?" (execution-quality, never eligibility). OI buildup / weak-close / volume z-score = "how did this validate after the fact?" (Audit-only, post-close). Real, load-bearing distinction: a **bad trade** should never have entered (freshness/entry filters are the right tool); a **fragile winner** is still a winner whose execution needs precision (fragility telemetry is the right tool — filtering fragile trades out would filter out real winners, e.g. PAYTM-style explosions). Conflating the two is the mistake to avoid going forward.

**Design principle for what's allowed to be complex, and where**: "does this reduce decisions, or create another decision?" Night-before ranking computation is allowed to be as complex as it needs to be (freshness, consolidation, distance, RS, liquidity, pattern, breadth, OI, everything) — the engine does that work once, so the human never has to. The live 9:20 decision surface must only ever show the *output* of that complexity, never ask the human to re-derive or re-weigh it. Concretely: **the "9:20 Trader Card"** — Trigger hit (Y/N), Freshness (High/Medium/Low), Fragility, Scan time (before 13:00?), Pattern (BC/VCP) — is the target live view; everything else already used this session (OI, weak-close, vol z-score, acceptance state, raw body_atr number, consolidation_days, dist_to_trigger, breadth, RS rating) either belongs to Audit (doesn't exist yet at 9:20) or is already baked into the ranking (shouldn't be re-litigated live). **Not yet built** — current live dashboard still shows the full, un-trimmed field set from earlier sessions' additions.

**Fragility labels, proposed rename**: Low/Medium/High → 🟢Robust / 🟡Watch / 🔴Precise. "Precise" reframes the worst bucket correctly — not "bad trade, avoid," but "don't FOMO an entry already run past the trigger, get the fill right." **Not yet built.**

**OI buildup clarified for the actual live-refresh pattern (refreshing primes every few minutes/hours intraday, not once per calendar day)**: futures OI is EOD-only and does not update intraday — so it's "sticky telemetry," computed once by the Audit layer and *read* (never recomputed) by every Prime refresh that day. Confirmed it still holds as a real, positive signal post-concentration-fix (Update 48/49) — "among otherwise valid candidates, bullish OI buildup is a positive signal." **Decision**: show it live too, collapsed into a single Confidence badge (Bullish/Neutral-no-data/Bearish) alongside Freshness and Fragility — never a veto/gate. **Implementation note, not yet built**: cache the computed OI-buildup value once per ticker per day; every subsequent intraday refresh reads the cached value rather than recomputing (matches how futures OI genuinely doesn't change until the next EOD close). **RQ-52, parked, not blocking**: Freshness × OI interaction — does bullish OI help fresh names, extended names, or both equally (independent vs. compensating/stacking with freshness)? Not run.

**StrykeX tracking table, simplified per direct correction**: we cannot know what StrykeX did *not* take (no visibility into their rejected candidates), so don't invent that category. Reduced to 4 real fields: Shared candidate (published + exists in our universe) / Liquidity-only reject / Multi-filter reject / Outcome (Win/Loss/Mixed). Critic's own rule: don't evaluate the comparison meaningfully until ~50 overlapping trades accumulate (not 20, not 10) — keep logging, don't conclude yet.

**All three built and verified (2026-09-17)**: the "9:20 Trader Card" is now the default output of `trader_dashboard.py morning` (5 fields: ticker/band/price/freshness High-Medium-Low/fragility/pattern/confidence, plus the held-flag) — `--full` gets the old rich diagnostic view back, nothing lost, just hidden by default. Fragility labels renamed Low/Medium/High → Robust/Watch/Precise everywhere. OI Confidence badge wired live (`live_checkpoint._oi_confidence()`) — reads the prior frozen trading day (matches "sticky telemetry," never fetches, never recomputes differently across a day's repeated refreshes), F&O-gated, shown on both simplified and full views. **Real bug caught and fixed while verifying**: a classic pandas gotcha — a column mixing Python `True`/`False`/`None` silently upcasts to `float64` (`False`→`0.0`), so an `oic is False` identity check never matched, and every real "Bearish" result was mis-displayed as "n/a." Fixed with a `pd.isna()`-based check instead of identity comparison. Verified against real live data post-fix — F&O names now correctly show Bullish/Bearish, non-F&O correctly show n/a. 72/72 tests pass throughout. New dependency, flagged: `classify_candidates()` now reads `options_cache/`, which `README.md`'s Deployment section previously scoped as backtest-only — a lightweight deployment without it degrades to every candidate showing no Confidence badge, not a crash.

**v32's actual next phase, agreed**: live paper trading calibration, not another parameter sweep. Two new logs proposed, not yet created: a **Paper Trading Calibration Log** (date, ticker, freshness, fragility, entry time, real slip, MFE, day-1-open exit, whether SMA21 trail mattered) and a **Rule Break Log** (rule broken, example — e.g. "exited winner early," "held loser hoping," "chased above trigger," "skipped valid trigger that became a winner") — explicitly a discipline/psychology log, not a trade journal. Framing, agreed: the model is no longer believed to be the bottleneck — consistently executing it is.

## RQ-53: "Breakout Failure Exit" — a full day's investigation, CLOSED as rejected across every mechanism tried; the day+1-open exit convention re-validated, not improved (2026-09-18)

**Origin, a real live question**: "we took a trade at breach but it was a fakeout — should I not exit? Do we have early signs at breach time that it could be a fakeout... this is sensitive for options especially, where I'm getting a beating for price and time both." Three prior fakeout-detection attempts already existed and failed (2026-09-07/13): tighter initial stop, MAE early exit (cut 43% of eventual winners), acceptance/streak-confirmation stop-tightening. This is the fourth attempt, tested far more thoroughly, and it also fails — but the *why* is now well understood, and one real, useful (if non-actionable-as-a-rule) observation survived.

**Theoretical grounding, checked before building anything** (per standing "verify negative findings" discipline): web research on fakeout detection (volume confirmation, price close-and-hold, multi-timeframe, MA alignment, market-context/choppiness) plus the SMC/ICT framework (Liquidity Grab = shallow probe that reverses with no follow-through; Liquidity Sweep = a real reversal confirmed by *displacement*, a strong decisive candle). The SMC/ICT "displacement" concept maps directly onto this project's own already-validated `body_atr` fragility feature — real theoretical grounding existed, but as shown below, it didn't translate into a working signal here.

**Attempt 1 — price-drop-and-hold on day 0 (`breakout_failure_confirmation_cost.py`, `FAILURE_THRESHOLD` = trigger×(1−0.5%), 2-bar confirm).** Directly analogous to a rule already tested and REJECTED (2026-09-07, "close back below entry pivot" — caught real losers but cut 30-48% of eventual winners, net-negative). Reproduced the same shape here: of 554 real signal fires, 202 (36.5%) reverse within 2 bars and are fine trades if held (+0.255% exp) — an immediate-exit-always policy is actively worse than doing nothing; a 2-bar-confirmed exit is marginally better than doing nothing **only when measured against the wrong baseline** (see the correction below).

**Threshold sensitivity swept properly** (`breakout_failure_threshold_sweep.py`, 0.4/0.5/0.6% × 1/2/3 confirm bars): 1-bar confirmation is never enough; 2-bar confirmation is consistently the best of the three window lengths at every threshold tested; 0.5-0.6%/2-bar wasn't a cherry-picked lucky value, the qualitative shape is robust across the grid.

**Attempt 2 — volume + displacement instead of pure price (`breakout_failure_volume_displacement.py`)**, prompted directly by a user catch that pure price+time can't distinguish a real failure from a normal retest (exactly the mechanism that killed the 2026-09-07 rule). Real 5-min Volume and `body_atr` at the signal bar tested for discriminating power against the confirmed/reversed label: **essentially zero** (vol_ratio corr −0.055, wrong sign; body_atr corr +0.084, negligible). The gated exit rule built from these actually fires on the wrong population — the 141 trades it cuts were fine if held (+0.014% exp), the 319 it leaves alone contain the real damage (−1.145% exp). Backwards, not just weak. Consistent with `body_atr`'s already-established profile in this project: real for *fragility* (does a winner risk flipping to a loss), never validated as a real-vs-fake discriminator at breach time.

**The methodology drift, caught by direct user challenge ("but how would that help?" / "did you run that on the right place?").** The investigation wandered onto day+1's *own* intraday session (open→close) — a different, later window than the actual question (exit faster than the CURRENT day+1-open exit, starting from day-0 entry). On that wrong window: nothing knowable *before* day+1 predicts it (freshness_score, vol_zscore, body_atr on the breach candle, breach-day's own run%, even the overnight gap itself — all correlate at ≈0.00-0.02 with day+1's own close, a clean comprehensive null, verified with quintile tables, not just correlation). Day+1's *own* early move is a real, strong signal (corr 0.62-0.77, 87-93% directional persistence) but not actionable: 94-103% of the eventual day+1 move is already realized by the time any fixed checkpoint would fire, so an exit-rule built on it barely moves the needle either way. This whole branch, while a real and correctly-caught methodology error, produced no actionable result because it was examining a period *after* the actual decision point.

**Corrected: re-ran both surviving mechanisms (price+time, and separately volume+displacement) on the actual right window — day 0, entered at breach, current exit at day+1's OPEN — with day+1-open as the baseline instead of swing_pnl or day+1's own close.** Script: `day0_exit_timing_check.py`. Extended the strongest mechanism (MAE-anytime — fires whenever price touches a drawdown level at ANY point, not a fixed time, found more informative than fixed-time checkpoints) to this window too, with a realistic resting-stop fill (at the threshold itself, not the bar's worst tick — the naive worst-tick version looked backwards before this fix). **All three fail on the correct window and baseline:**
- MAE-anytime stop-loss (F&O-scoped, n=621): baseline (hold to day+1 open) exp=+0.562%/win=60.5% beats every single stop threshold tested, −0.3% to −2.0% (best case only −0.118pp worse, worst case −0.499pp worse).
- Volume+displacement gate (F&O-scoped, n=280): baseline exp=−0.434% beats the gated exit, −0.547%.
- Nothing beats holding to day+1's open. This isn't a methodology artifact — it reproduces the same conclusion across three independent mechanisms.

**Why acting on the winner/loser MAE separation backfires — a real, clean mechanistic explanation, not just "the data says no."** Winners' median day-0 drawdown after breach is −0.66%; losers' is −1.68%, more than 2.5x deeper — a genuine, real separation (full universe, n=1,032). But **for every threshold tested, the trades that touch it average a BETTER price by day+1's open than the threshold itself**: trades touching −1.50% intraday average only −0.79% by day+1's open; trades touching −2.00% average only −1.31%. A resting stop fires exactly at a locally extreme point that mean-reverts on average before the real decision point (day+1 open) arrives — the same "confirmation consumes the edge" mechanism as the entry-side RQ-37 finding, just showing up as "the worst point of a noisy path is, near-tautologically, followed by partial recovery," not a timing-specific effect.

**One real, non-adopted observation that DID survive scrutiny: gap-up vs. no-gap, and the gap-sustain/fade pattern (`gap_sustain_check.py`).** 68.6% of real trigger-fires gap up the next day; for those, day+1-open decisively beats day0-close (win 64.2% vs 48.4%, exp +1.011% vs +0.249%) — but for the 31.4% that don't gap up, waiting for day+1's open is actively worse than just exiting at day0's close (exp −0.359% vs +0.154%). Of real gap-ups, **87.5% fade below the opening print within 10 minutes** — only 12.5% sustain. The fade costs a real, moderate, but non-compounding amount (give-back ≈0.20-0.27pp, flat whether you react in 10 or 30 minutes — the damage doesn't keep growing the slower you are). The rare sustained case rewards patience further the longer it holds (+1.77% at 10min → +2.04% at 30min). **Not adopted as a rule** (this describes what happens after the exit point already fires, same category as the day+1-own-session tangent), but it is a real, useful piece of context, and it directly explains a real live loss traced below.

**Real trade traced end-to-end: LAURUSLABS's 2026-09-11 breach.** Trigger = 1955×1.005 = 1964.78. Real day+1 (2026-09-15, see data bug below) opened at 1975.00 (a real +0.52% gap vs trigger — theoretically a small win if sold exactly at the open), but crashed intraday to a low of 1915.60, closing at 1926.90 (−1.93% vs trigger, −2.44% from its own open). This is the gap-and-fade mechanism above, playing out exactly: if the gap faded before real execution was possible (the 87.5%-of-the-time case), the trader is chasing a disappearing price and ends up with a real loss instead of the small theoretical gain — consistent with the user's own memory that "the spot moved badly," not an options-specific (theta/IV) effect.

**A real, previously-undiscovered data bug found and fixed while tracing that trade.** Some cached tickers carry bogus zero-volume placeholder rows (OHLC frozen at the prior close) on specific dates the exchange was actually open for the rest of the market — e.g. LAURUSLABS and DIVISLAB both had one at 2026-09-14, while RELIANCE/TCS/HDFCBANK correctly have no row there at all. Every `daily_df.iloc[i+1]`-style "next trading day" lookup used throughout today's entire investigation would silently land on this fake day instead of the real one whenever it occurred right after a breach — which is exactly why LAURUSLABS's real 09-11 trade was untraceable until checked by hand. **Scoped**: 102 of 16,200 real breaches project-wide (0.63%) — too rare to have meaningfully skewed any of today's aggregate numbers (all of which were re-verified post-fix and reproduced within noise), but real enough to corrupt individual lookups outright. **Fixed** in `backtest.py`'s `_finish_load()` — `df = df[df.Volume > 0]` before any indicator/pivot computation, so every rolling/shift calculation also skips the fake day, not just single-row lookups. 72/72 tests still pass.

**Final verdict**: RQ-53 is closed, rejected in every form tested (price+time, price-magnitude-anytime, volume, displacement, on both the correct and — instructively — an incorrect window). The current production convention (enter at breach, exit at day+1's open, no intraday intervention) is not just unbeaten, it's re-validated as already sitting in the right place — every attempt to exit earlier makes things worse, and every attempt to hold longer (day+1's own session) doesn't help either. No code change. The gap-sustain observation and the zero-volume data-bug fix are the two durable, real artifacts of this investigation. Scripts: `breakout_failure_confirmation_cost.py`, `breakout_failure_threshold_sweep.py`, `breakout_failure_volume_displacement.py`, `day0_exit_timing_check.py`, `gap_sustain_check.py`.

## The live pipeline has never applied the Nifty regime gate, and `EMA34_RISING_DAYS_MIN=9` is a real lagging-persistence filter that misfires systematically in a choppy market (2026-09-18)

**Origin, a real live observation**: "since last week Nifty was in breakdown mode and we were getting trades and losing, now last two days Nifty is showing green and now we are not firing trades" — the exact opposite of what a trend-following system should do (fire during the friendly trend, go quiet during the hostile one).

**First, confirmed directly: `market_trending()` (the regime gate — Nifty ADX + `require_above_sma200`, `require_regime=True` by default everywhere in `backtest.py`) returns `False` for every day checked in the recent window (2026-09-09 through 2026-09-16), and has done so continuously since Nifty fell below its own 200-day SMA on 2026-02-26** — over 6 months, per `market_regime.py`'s own docstring ("the live regime-gate drought, Nifty below its own 200-SMA since 2026-02-26"). This is not new information — FINDINGS.md already documented (see the 62-day walk-forward rebuild entry) that re-applying the full regime gate to a live-representative population collapses 533 real fires down to 0-2, and that `live_checkpoint.py`'s actual operational "fired" definition was deliberately built around `_passes_primed_checks()` instead, which — confirmed again directly via `grep` — never calls `market_trending()` at all, only `base_filters_pass()`/`stage2_trend_template()`. **The live system has never had regime-gate protection, for this entire drought.** Last week's losing trades and today's quiet trades are both symptoms of the same standing fact, not a new inconsistency between them.

**But the user's sharper, more specific point survives that explanation and points at something new: a real, measured LAG in `EMA34_RISING_DAYS_MIN=9`, the base filter requiring a stock's own EMA34 to have risen on 9 of the last 10 days.** Persistence requirements are structurally slow in both directions. Measured directly on the full multi-year fire-count-per-day population (`daily_fires_vs_nifty.csv`, correlated against Nifty's own daily return):

| Days into an up-move | Mean fires/day | Days into a down-move | Mean fires/day |
|---|---|---|---|
| 1 (just turned up) | 12.71 | 1 (just turned down) | 14.51 |
| 2 | 16.42 | 2 | 10.37 |
| 3 | 18.90 | 3 | 8.68 |
| 4 | 21.65 | 4 | 7.06 |
| 5 | 21.91 | 5 | 5.82 |
| 6 | 19.27 | 6 | 3.13 |

Fires are **lowest right when a new rally starts** (day 1 of an up-move is the single lowest bucket, 12.71) — most stocks haven't accumulated 9 rising EMA34 days yet, since they were still declining last week. Fires **stay elevated for several days after a rally rolls over** (day 1 of a down-move, 14.51, is actually higher than day 1 of an up-move) — EMA34 is a slow-moving average; one down day barely dents a qualification built over the prior weeks, so the scanner keeps firing on names that look technically sound by this specific measure while the real trend has already turned underneath them. This is precisely "a bad trend taking down a technically sound trade": the setup wasn't fake, the filter's qualification was stale by the time it fired.

**Checked whether the real current market is the kind of environment where this lag matters constantly, not just at rare turning points — it is, more severely than the user's own "10 days up / 10 days down" framing assumed.** Real Nifty daily up/down streak lengths, last ~180 trading days: **median 1 day**, mean 1.8-2.0 days, max 7 days, **98.9% of all streaks ≤5 days, 0% reach 9+ days** — the exact length the filter needs to fully qualify. Honest caveat: `EMA34_RISING_DAYS_MIN` measures each stock's own smoothed EMA34, not Nifty's raw daily direction, so this isn't a 1:1 mechanism match — but an index this choppy day-to-day all but guarantees individual stocks are whipsawing too, consistent with the fire-count lag already measured directly above. In a market this whippy, the filter is close to *never* genuinely caught up — almost always either still building qualification from the last reversal (missing real wins) or still carrying stale qualification into the next one (catching real losses).

**Queued, not yet run**: test whether a shorter `EMA34_RISING_DAYS_MIN` (5 or 6 out of 10, instead of 9) reduces this lag meaningfully without giving up real trend-confirmation value, specifically evaluated across this choppy period rather than folded into the existing multi-year `base_filters_threshold_sweep.py` population (which averages over many different regime characters and would dilute a choppy-regime-specific effect). Script: `daily_fires_vs_nifty.csv` (the fire-count/Nifty-return dataset already built) as the starting population for this next test.

**Ran the shorter-window test (`ema34_lag_check.py`) — real, but a nuanced result, not a clean win.** Two checks:
1. **Aggregate win/expectancy, full multi-year population, unchanged mechanism** (reuses `base_filters_threshold_sweep.py`'s established `sweep()`): shortening from 9 to 5 costs nothing — win rate flat (60.6-60.9% swing, 56.7-57.9% options across 5-10), expectancy marginally *better* at 5 (+1.052%/+0.567% vs current 9's +0.995%/+0.513%), concentration flat (30.2-30.5%/36.9-37.3%). Real bonus: **~23% more candidates** (19,944 vs 16,237 full-history fires at MIN=5 vs 9).
2. **Lag shape in the recent 180-day choppy window barely changes with the threshold.** Day-1-as-%-of-peak-day is 81.3% at MIN=5 vs 79.6% at MIN=9 for up-moves — essentially the same relative shape. Mechanism: `ema34_rising10` is a rolling **10-day window, hardcoded** — lowering the threshold from 9-of-10 to 5-of-10 doesn't shorten that underlying 10-day measurement, just how many of those 10 need to be rising, and in a market this choppy even 5-of-10 still takes several days to accumulate after a reversal.

**Outcome-quality confirmation (`lag_outcome_check.csv`), both swing and options, per the standing "check both" convention — real on the down-move side, a genuine cost of the lag, not just a timing curiosity.**

| Days into decline | n (swing/opt) | SWING win/exp | OPT win/exp |
|---|---|---|---|
| 1-2 (stale bullish qualification) | 5,246 / 3,779 | 58.5% / +0.687% | 49.7% / +0.174% |
| 3-5 | 946 / 653 | 57.2% / +0.002% | **40.4% / −0.314%** |
| 6+ | 61 / 35 | 68.9% / +2.504% | 48.6% / −0.297% |

Quality genuinely degrades past day 2 into a real decline — swing goes to breakeven, options flips to a real loss by day 3-5. **The 6+ bucket (n=61/35) is well under Research Integrity Rule #4's 500-trade minimum and should not be trusted** — the surprisingly good 68.9% swing win there is very likely small-sample noise, not signal, flagged explicitly rather than cited as a real finding.

| Days into rally | n (swing/opt) | SWING win/exp | OPT win/exp |
|---|---|---|---|
| 1-2 (rare, filter barely caught up) | 5,725 / 4,280 | 61.9% / +1.302% | 63.4% / +0.791% |
| 3-5 | 3,335 / 2,634 | 63.1% / +1.363% | 60.8% / +0.735% |
| 6+ (established, more extended) | 924 / 744 | 59.6% / +0.423% | 58.9% / +0.611% |

Up-move side is a different shape: the rare fires that manage to happen early despite the lag are the *best* quality of the three buckets (highest options win, 63.4%) — the lag costs volume here, not quality, consistent with the fire-count-only finding above. Quality declines by 6+ days, consistent with the already-established freshness/extension principle.

**Honest methodology self-audit, before anything gets proposed as a change**: (1) the small-n down/6+ bucket flagged above. (2) A shorter `EMA34_RISING_DAYS_MIN` was checked for aggregate quality (full history, flat/no cost) and fire-timing shape (choppy window, barely changes) — but **never checked for real win/expectancy specifically within the choppy window itself**, which is the actual question a promotion decision would need answered, and Research Integrity Rule #3 (live-representative population, not just a big historical average) applies directly here. Not yet run at the time of the first write-up.

**Gap closed (`ema34_choppy_window_check.py`) — real, well-powered, and a meaningfully stronger result than "free on the full history."** Same population mechanism, restricted to the last 180 real Nifty trading days (the same window already characterized as choppy: median 1-day streaks, 98.9% ≤5 days), swept `EMA34_RISING_DAYS_MIN` across the full 2-10 range (not just 5-10), real swing and options outcomes:

| EMA34_RISING_DAYS_MIN | n (swing/opt) | SWING win/exp | OPT win/exp | conc (swing/opt) |
|---|---|---|---|---|
| 2 | 3,642 / 2,390 | 57.2% / +0.360% | 57.4% / **+0.440% (peak)** | 27.4% / 32.6% |
| 3 | 3,618 / 2,375 | 57.4% / **+0.376% (peak)** | 57.3% / +0.426% | 27.4% / 32.5% |
| 4 | 3,536 / 2,320 | 57.2% / +0.355% | 56.9% / +0.404% | 27.5% / 32.5% |
| 5 | 3,427 / 2,241 | 57.0% / +0.316% | 56.9% / +0.398% | 27.5% / 32.4% |
| 6 | 3,295 / 2,138 | 56.5% / +0.231% | 56.3% / +0.368% | 27.4% / 32.2% |
| 7 | 3,106 / 1,997 | 55.9% / +0.076% | 56.3% / +0.348% | 27.4% / 32.2% |
| 8 | 2,899 / 1,848 | 55.4% / −0.014% | 56.1% / +0.332% | 27.4% / 32.2% |
| 9 (current) | 2,686 / 1,713 | 55.0% / **−0.090%** | 56.7% / +0.354% | 27.5% / 32.6% |
| 10 | 2,328 / 1,484 | 55.1% / −0.138% | 55.3% / +0.304% | 27.6% / 32.5% |

Both populations comfortably clear Research Integrity Rule #4's 500-trade minimum at every threshold tested. **Not a straight monotonic "lower is always better" — there's a real plateau/peak at 2-4** (swing peaks at 3, options peaks at 2), declining steadily from there through 6-10. **The current production value (9) sits in genuinely negative swing expectancy in this specific, live-representative window** (−0.090%, vs the peak's +0.376% at 3) — a real, substantial gap, not noise. Options shows the same direction, more modestly (+0.440% at 2 vs +0.354% at 9). Concentration flat and sane across the entire 2-10 range (27.4-27.6%/32.2-32.6%, within this project's own ~25-30% honest baseline) — not an outlier artifact anywhere in the range. No data below 2 — whether the pattern continues improving or reverses further down is untested. This is now a real, gap-closed, live-representative finding, not just a full-history-neutral one.

**Ran the exact RQ-51 three-population promotion check (`ema34_three_population_check.py`) — direct user request, "show me how this new thing does against our three populations." Unlike RQ-51, the real population does NOT vanish or reverse.**

| EMA34_RISING_DAYS_MIN | Primed Gate (SWING / OPT) | Entry Gate, require_regime=False (SWING / OPT) | Real intraday+13:00-cutoff (SWING / OPT) |
|---|---|---|---|
| 2 | n=20,855, 60.9%/+1.052% — n=15,644, 58.3%/+0.598% | n=3,524, 68.8%/+3.835% — n=2,639, 93.9%/+2.950% | n=1,149, 57.8%/+0.385% — n=703, 60.7%/**+0.663%** |
| 3 | n=20,736, 60.9%/+1.051% — n=15,571, 58.3%/+0.589% | n=3,481, 68.7%/+3.838% — n=2,612, 94.0%/+2.936% | n=1,140, 57.7%/+0.378% — n=697, 60.7%/+0.640% |
| 5 | n=19,944, 60.9%/+1.052% — n=14,979, 57.9%/+0.567% | n=3,327, 68.5%/+3.806% — n=2,495, 93.7%/+2.878% | n=1,088, 57.3%/+0.316% — n=658, 60.0%/+0.604% |
| 9 (current) | n=16,237, 60.7%/+0.995% — n=12,125, 57.0%/+0.513% | n=2,644, 68.3%/+3.730% — n=1,974, 93.6%/+2.800% | n=885, 56.7%/+0.165% — n=527, 60.5%/+0.627% |

The real population stays adequately sized at every value tested (885-1,149, comfortably above Rule #4's 500-trade minimum — RQ-51's real population, by contrast, collapsed to n=1 then 0 by RSI_MIN=70). Swing expectancy improves monotonically across all three populations as the threshold shortens. **Added value=2 directly after the choppy-window sweep showed options peaking there rather than at 3 — it resolves cleanly: 2 is the best value on the real population for BOTH swing and options** (+0.385%/+0.663%, the best options number of any value tested, beating even 3's +0.640%), not just a choppy-window-specific quirk. **This is the first EMA34/RSI/momentum-style threshold lead this session that satisfies Research Integrity Rule #3's spirit as cleanly as this** — real, same-direction movement on a real, adequately-sized live-representative population, not just two large historical averages agreeing with each other. Still explicitly a lead pending critic review, not adopted — posed to the critic in full.

## Critic response to Update 52, and three follow-ups: RQ-52A tested directly (hypothesis mostly refuted), a proposed "new" fakeout research question flagged as substantially already-rejected work, Fragility Margin calibration deferred (2026-09-18)

**Critic's reply to Update 52** agreed the EMA34 finding is real but recommended NOT shipping `EMA34_RISING_DAYS_MIN=2` directly — proposing instead that the real issue is conflating two layers (market-level regime vs. stock-level trend persistence), and floated "Adaptive Persistence" (RQ-52A): vary the threshold by regime bucket — short (2-4) during a fresh recovery, keep long (7-9) during an established uptrend or a downtrend.

**RQ-52A tested directly (`ema34_adaptive_persistence_check.py`) — the specific hypothesis mostly does NOT hold.** Same real-outcome mechanism as the lag investigation, bucketed by Nifty's own streak state at fire time (recovery = days 1-4 of an up-move, established = 5+ days, downtrend = any down day), full multi-year population, swept EMA34_RISING_DAYS_MIN 2/3/5/7/9:

| Bucket | EMA34=2 (SWING/OPT) | EMA34=9 current (SWING/OPT) | Matches the hypothesis? |
|---|---|---|---|
| Recovery | n=10,633, 62.5%/+1.368% — n=8,119, 63.7%/+0.827% | n=8,316, 62.1%/+1.303% — n=6,322, 62.5%/+0.767% | Yes — shorter is better, as predicted |
| Established | n=2,290, 62.0%/+1.180% — n=1,826, 62.0%/+0.865% | n=1,668, 61.9%/+0.932% — n=1,336, 60.0%/+0.692% | **No — shorter is still better** |
| Downtrend | n=7,932, 58.4%/+0.592% — n=5,699, 49.5%/+0.186% | n=6,253, 58.4%/+0.601% — n=4,467, 48.3%/+0.099% | **No — swing flat/noise, options nearly DOUBLES with shorter (+0.099%→+0.186%)** |

Every bucket improves or is flat-to-better with a shorter threshold, not just recovery. The mechanism reasoning behind Adaptive Persistence (persistence lags in both directions) was sound and already validated by the earlier lag-timing/outcome-quality work — but the specific prediction that established/downtrend regimes should *keep* the longer window doesn't survive contact with real data. **A single shorter global value (2-3, matching the earlier three-population result) appears to be the simpler, better-supported conclusion — a regime-conditional scheme adds complexity without adding benefit on this evidence.**

**Critic's proposed "RQ-53: Acceptance Failure Window" flagged as substantially already-tested, not fresh research.** The critic (working only from the Update 52 write-up, without visibility into today's full RQ-53 closure) proposed a 4-rule fakeout-detection test that maps almost exactly onto mechanisms already built and rejected earlier today:

| Critic's proposed rule | Already tested as | Result |
|---|---|---|
| "2 consecutive closes below trigger" | `FAILURE_THRESHOLD` + 2-bar confirm (`breakout_failure_confirmation_cost.py`) | Rejected — baseline (hold to day+1 open) beats every variant |
| "15 continuous minutes below trigger" | 1/2/3-bar confirm windows (5/10/15 min) | Rejected at every window length |
| "Pullback depth 0.3-1%" | MAE-anytime threshold sweep (`day0_exit_timing_check.py`) | Rejected — real mean-reversion-from-extreme mechanism found |
| "Close back inside prior 10-day range" | The 2026-09-07 "close back below pivot" rule | Already rejected then (cuts 30-48% of eventual winners) |

Also re-flagged the numbering collision — the critic has now proposed two different, unrelated ideas both labeled "RQ-53" in separate messages (this session's real RQ-53, "Breakout Failure Exit," is already closed; theirs would need a fresh number, e.g. RQ-54, if pursued at all — not recommended without a genuinely new mechanism, since a relabeled already-rejected idea isn't new research).

**Fragility Margin calibration (critic's 3rd priority item) — deferred, not run.** This depends on accumulating real live/paper trades to calibrate against, which don't exist yet in sufficient number — consistent with the standing v32 plan ("live paper trading calibration, not another parameter sweep," 2026-09-17). Queued, not actionable today.

Scripts: `ema34_adaptive_persistence_check.py`.

## RQ-52A Evidence Checklist, Test P1 — Delta Population Audit: EMA34=2's new trades are real, good trades, not noise, and clear the critic's own pre-registered bar (2026-09-18)

**Critic's framing, adopted directly**: don't ask "is EMA34=2 better on average," ask "what NEW trades does EMA34=2 admit, and are those trades genuinely good?" Isolated the real "Delta" population (`ema34_delta_population_audit.py`) — passes `base_filters_pass()` with `EMA34_RISING_DAYS_MIN` relaxed to 2, but would fail at the current production value of 9 (`ema34_rising10 < 9`) — against "Common" (passes at both), full multi-year history, one pass (the real `ema34_rising10` column already exists, no need to re-scan per threshold).

**Critic's timestamped prediction, scored against the real result:**

| Prediction | Actual | Verdict |
|---|---|---|
| Swing exp better, but by <0.2% | Delta +1.255% vs Common +0.995% (+0.260pp) | Right direction, bigger than predicted |
| Options exp meaningfully better (+0.2-0.4%) | Delta +0.891% vs Common +0.513% (+0.378pp) | Correct, top of range |
| Fragility slightly *higher* in Delta | Delta 15.8% Fragile/70.5% Robust vs Common 20.2%/62.8% — Delta is LESS fragile | **Wrong — a positive surprise** |
| ~70-80% of Delta already Fresh | 50.3% already Fresh | **Wrong — meaningfully lower, real independent signal, not full redundancy with freshness** |
| ~20-25% more candidates/day | +25.2% | Correct, top of range |

**Full numbers:**

| | n | SWING win/exp/median/conc | OPT win/exp/median/conc | % already Fresh | Fragility (winners) |
|---|---|---|---|---|---|
| Common (EMA34≥9, current) | 16,237 | 60.7% / +0.995% / +1.629% / 30.4% | n=12,125, 57.0% / +0.513% / +0.237% / 37.3% | 17.7% | 20.2% Fragile / 17.0% Medium / 62.8% Robust |
| Delta (EMA34=2 only, new) | 4,618 | 61.7% / +1.255% / +1.983% / 29.2% | n=3,519, 63.0% / +0.891% / +0.534% / 35.5% | 50.3% | 15.8% Fragile / 13.8% Medium / **70.5% Robust** |

**This clears the critic's own explicit, pre-registered bar**: *"if Delta trades have similar fragility + similar freshness + materially better expectancy, I'd be ready to seriously consider EMA34=2 for v32."* The result exceeds that bar on two of three counts — fragility isn't just similar, it's **better** (more Robust, less Fragile); freshness overlap isn't near-total redundancy (95%+ would mean "adds nothing"), it's a genuine ~50/50 split, meaning roughly half of Delta's winners are trades freshness alone would *not* have flagged — real, partially independent information, not EMA34 rediscovering freshness under a different name. Expectancy is materially better on both legs, options especially (+0.378pp, with a cleaner concentration too: 35.5% vs 37.3%). Real, operational cost confirmed as predicted: +25.2% more candidates/day.

**Not yet done — the remaining items on the critic's Evidence Checklist**: P2 (Fragility by EMA34 bucket — partially covered above via the winners-only fragility split, but not the full bucketed comparison the critic specified), P3 (Freshness overlap matrix — partially covered above), P4 (daily candidate-count distribution: avg/P95/max, days >15 candidates — only the average is reported here), P5 (transition latency), and the time-of-day interaction test (Evidence 7). Posed to the critic with what's done so far; the remaining items are queued, not run.

**[2026-09-18 CORRECTION, caught by direct user question ("why do we even care about the overall population... how can two different checks both be correct") — the "% already Fresh" row above is WRONG, a real bug, not a data quirk.** All of today's later EMA34 scripts (`ema34_delta_population_audit.py`, `ema2_freshness_reaudit.py`) computed `freshness_score` from the breach day's OWN row instead of the PRIOR day's row — the exact look-ahead bias already found and fixed earlier this session in `min_traded_value_ablation.py`, silently reintroduced here. Recomputed correctly (prior-day row): **Delta's real freshness overlap is 72.7% (3,359/4,620), not 50.3%.** The critic's prediction ("~70-80% of Delta will already be Fresh") was actually **correct** — the "Wrong" verdict in the table above is itself wrong, caused by this bug. See the full corrected P3 table and mechanism-level correction below; this also means the "half of Delta's winners are trades freshness alone would not have flagged" claim in this section's own concluding paragraph is not supported — freshness overlap is high, not ~50/50.

## RQ-52A Evidence Checklist, P2/P3/P4/P5 — real, informative results on three; the fourth (transition latency) is a dead end by definition, not a real finding (2026-09-18)

**P2 — Fragility Margin size, not just discrete labels (`ema34_evidence_checklist_p2_p5.py`).** Delta winners show consistently larger margins across the whole distribution, not just a better Fragile/Medium/Robust label mix: mean +2.134% vs Common's +1.886%, median +1.501% vs +1.179%, even at the bottom of the distribution (p10: +0.257% vs +0.189%). Reinforces P1 — Delta trades aren't just less-often-fragile, their typical safety margin is bigger too.

**P3 — Freshness overlap matrix, and it surfaces something real worth flagging honestly, not just a confirmation.**

| Group | Freshness | n | SWING win/exp | OPT win/exp |
|---|---|---|---|---|
| Common | Fresh | 2,879 | 54.2% / **−0.616%** | 42.8% / **−0.383%** |
| Common | Not Fresh | 13,358 | 62.1% / +1.342% | 60.5% / +0.733% |
| Delta | Fresh | 2,322 | 59.0% / +0.315% | 56.8% / +0.294% |
| Delta | Not Fresh | 2,296 | 64.4% / +2.205% | 70.5% / **+1.616%** |

Within both groups, "Not Fresh" beats "Fresh" — this reproduces the same unresolved tension already flagged in the 2026-09-17 RSI_MIN/momentum threshold audit (a stock with a long EMA34-rising streak that's *also* not extended on RSI/momentum is a narrow, oddly-shaped combination that underperforms). Not a new problem, but it explains why Delta performs so well overall — its best cell (Not Fresh, 70.5% options win) is a genuinely strong, distinct population: a short EMA34-persistence, moderately-extended momentum name, different from what freshness alone would surface.

**[2026-09-18 CORRECTION — this whole P3 table is WRONG, a real bug, not a real finding.** `_freshness_score()` was computed from the breach day's own row instead of the prior day's — the same look-ahead bias found and fixed earlier this session, silently reintroduced. My own reasoning compounded the error: I called this "not new, already documented" by comparing it to the RSI_MIN audit's freshness-distribution check — but I never verified that older check used the corrected (prior-day) convention either, and the two results "agreeing" was worthless as confirmation since I hadn't established they were independent. Caught by a direct user question ("this one is also correct, how can it be?") pointing out that two checks agreeing means nothing if they share the same bug. **Corrected P3 (prior-day freshness, no look-ahead):**

| Group | Freshness | n | SWING win/exp | OPT win/exp |
|---|---|---|---|---|
| Common | Fresh | 5,287 | 60.7% / +0.847% | **63.8% / +0.740%** |
| Common | Not Fresh | 10,951 | 60.8% / +1.088% | 53.2% / +0.387% |
| Delta | Fresh | 3,359 | 62.8% / +1.386% | **67.1% / +1.021%** |
| Delta | Not Fresh | 1,261 | 58.9% / +0.922% | 49.9% / +0.470% |

**Fresh clearly beats Not Fresh on options in both groups (63.8% vs 53.2% Common; 67.1% vs 49.9% Delta)** — the corrected direction matches the established, validated Freshness signal instead of contradicting it. Swing is close either way, options is where the real, large gap is — consistent with the user's own repeated point that options is where freshness/execution quality matters most. This also corrects Delta's real freshness overlap to 72.7% (see the P1 correction above) — freshness is NOT a mostly-independent signal from EMA34=2 after all; it's real, valid, and still applies within the Delta population the same way it always has.

**P4 — Daily candidate distribution, last 90 real trading days — the one result here that should give real pause, independent of the EMA34 question.**

| | avg/day | P95 | max | days >15 candidates |
|---|---|---|---|---|
| EMA34=9 (current) | 16.27 | 32.1 | 49 | **40/90 (44%)** |
| EMA34=2 | 20.44 | 41.0 | 60 | **52/90 (58%)** |

**The dashboard is already overloaded almost half the time under current production settings** — 44% of days already exceed 15 candidates before touching EMA34 at all. EMA34=2 makes this worse but not dramatically (+13pp more high-candidate days, max climbing 49→60). This is a real, pre-existing operational problem, not something EMA34=2 creates — worth its own investigation regardless of the EMA34 decision.

**P5 — Transition latency: the metric as specified doesn't work at this scale, not a real finding.** Defined as "trading days from a real Nifty recovery start to the first fire, any ticker" — came back median 0.0 for both EMA34=9 and EMA34=2 (mean 0.12/0.06 days). With a 500-ticker universe, *some* stock fires almost every single day regardless of Nifty's regime, so "any ticker fires anywhere" is nearly always zero — this is a definition problem, not evidence the lag doesn't matter. The pain being measured isn't "zero fires," it's "fewer fires than usual," which the earlier days-into-a-move fire-count table already captures correctly (12.71 fires on day 1 of a rally vs 21.91 by day 5, at EMA34=9). Dropped as a metric rather than reported as a misleadingly precise non-result.

Scripts: `ema34_evidence_checklist_p2_p5.py`.

## RQ-56: EMA34=2 uniqueness test — clean, decisive pass, real trades not earlier entries into the same ones (2026-09-18)

**Critic's final falsification before considering promotion**: does `EMA34_RISING_DAYS_MIN=2` discover genuinely new trades, or does it just enter the same trades a day or two earlier than 9 would have anyway? For every Delta trade, checked whether EMA34≥9 also fires on the SAME ticker within the next 3 *trading* days (not calendar days, using the real daily-bar index — `ema34_rq56_uniqueness_test.py`). "Early version" = EMA34≥9 fires there in that window (same trade, found sooner); "Unique" = it never does.

**82.7% of Delta trades are genuinely Unique** (n=3,819 of 4,618) — not earlier entries into trades EMA34=9 would have caught anyway. Only 17.3% (n=799) are Early version.

| | n | SWING win/exp | OPT win/exp |
|---|---|---|---|
| Early version | 799 | 78.3% / +4.317% | 62.0% / +0.879% |
| Unique | 3,819 | 58.2% / +0.614% | **63.2% / +0.893%** |

Both groups are real and good — Early version is even stronger (entering a confirmed-strong move slightly ahead of EMA34=9 captures extra upside, makes sense) — but Unique is the group that matters for the uniqueness question, and its options number (63.2% win) is the best in the table, not a marginal tail. **Critic's promotion rule (≥30% of ALL Delta trades must be unique AND profitable): actual result is 48.1%** — clears the bar by a wide margin, not a borderline pass. Script: `ema34_rq56_uniqueness_test.py`.

**EMA34=2 promoted from Tier A Research to Tier A Candidate** (not production) — RQ-56's falsification survived. Two governance items resolved, kept as separate things rather than forced into one numbering:

- **Research Integrity Rule #4 (Candidate vs Executable Portfolio)**: a candidate-level improvement is insufficient for production promotion when a feature materially changes candidate volume or selection — its effect on *executable* opportunities must also be established, not just the candidate population's own stats.
- **Tier-A Candidate Promotion Checklist** (a checklist, not a numbered Research Integrity Rule): (1) multi-year Primed-population improvement, (2) Entry-Gate consistency, (3) independence/uniqueness falsification, (4) operational-capacity validation. EMA34=2 has cleared 1-3; RQ-57 is the remaining box.

**A real methodology near-miss caught and corrected before building anything**: RQ-57 was initially specified against `portfolio.py`'s cash-constrained allocator, until direct verification showed `simulate_lots()` has no ranking mechanism at all (pure chronological + cash-affordability) and its only real input is a static v28-era CSV (`runs/opt_v28_itm_next.csv`) with no connection to the Primed-Gate/EMA34 candidate-generation logic this whole investigation has used. Building the "connecting pipeline" (EMA34 candidates → real option contracts → that allocator) would have been a genuine new build disguised as a replay — correctly rejected. **Final RQ-57 spec**: use the real intraday cache and the actual live 9:20 ranking mechanism (`live_checkpoint.py`'s distance-to-trigger/closing-speed ranking) directly — no portfolio allocator, no v28 artifact, no new option-contract pipeline. Question: does EMA34=2 create opportunities that survive the real Top-5 selection bottleneck a human actually faces at 9:20, not just the candidate population in the abstract.

**RQ-57 result (`ema34_rq57_capacity_test.py`, real 70-day intraday window, real live_checkpoint.py-style combo_rank = 0.8×dist_rank + 0.2×velocity_rank)**: Top-5 composition differs on 46 of 70 days (65.7%) — a routine, not rare, change to what a human would actually see. Swing: a real flip from negative to positive expectancy (EMA34≥9's Top-5 was −0.192% exp/56.8% win; EMA34=2's Top-5 is +0.290% exp/59.9% win), and a higher fire-through rate (49.1% vs 44.3% of Top-5 slots actually becoming real trades). Options: an honest wrinkle, not smoothed over — win rate and expectancy are both slightly *lower* for EMA34=2 (58.3%/+0.360% vs 60.6%/+0.458%), on a larger sample (120 vs 104 trades). Swing clearly clears the promotion bar; options doesn't cleanly satisfy either half of the critic's rule (not better, not "same with more"). Sample sizes are real but modest (104-172 options trades over 70 days) — trust the direction, not the exact magnitude.

**Direct pushback from the user, correctly redirecting the whole thread**: "this is not the way to solve the problem... it really has good trades, then why the [hesitate]... we should be solving it by tightening other filters which probably will need to be revisited because the population has changed." Five rounds of EMA34-in-isolation falsification (RQ-52A/55/56/57) all passed — running a sixth wouldn't change that answer. The real open question reframed: with EMA34=2 as the baseline, are `RSI_MIN`/`MOMENTUM_20D_MIN`/`MIN_TRADED_VALUE` (all tuned against the EMA34≥9 population) still calibrated for the population they now filter, or were they implicitly compensating for EMA34≥9's narrower population? Critic agreed, explicitly cautioned against a joint/multidimensional sweep (can't attribute a joint optimum to any one cause) in favor of one-at-a-time re-sweeps, each reporting: old value, response/plateau shape, and — the critical new metric — % of the RQ-56 "Delta" population (4,618 EMA34=2-unique trades) retained at each threshold value.

## Weekend threshold re-audit with EMA34=2 fixed — found exactly the interaction the critic was hoping to surface, and it's dramatic (2026-09-18)

**`RSI_MIN` and `MOMENTUM_20D_MIN` both directly gut the Delta population as they rise past their current production values — a sharp, real interaction, not a subtle one** (`ema2_threshold_reaudit.py`, EMA34_RISING_DAYS_MIN=2 fixed, full multi-year population):

| RSI_MIN | n | SWING win/exp | OPT win/exp | Delta retained |
|---|---|---|---|---|
| 55 (current) | 20,858 | 61.0% / +1.065% | 58.3% / +0.598% | **100.0%** |
| 60 | 19,934 | 61.5% / +1.162% | 59.8% / +0.680% | 88.2% |
| 65 | 16,297 | 62.5% / +1.440% | 62.5% / +0.867% | 54.2% |
| 70 | 10,503 | 64.6% / +1.984% | 65.7% / +1.147% | 24.4% |
| 75 | 5,260 | 66.1% / +2.583% | 68.7% / +1.545% | 7.8% |
| 80 | 2,044 | 70.0% / +3.752% | 72.0% / +2.113% | 1.8% |

| MOMENTUM_20D_MIN | n | SWING win/exp | OPT win/exp | Delta retained |
|---|---|---|---|---|
| 1.05 (current) | 20,858 | 61.0% / +1.065% | 58.3% / +0.598% | **100.0%** |
| 1.10 | 14,212 | 62.1% / +1.517% | 60.3% / +0.814% | 47.2% |
| 1.15 | 8,750 | 62.4% / +1.949% | 61.7% / +1.084% | 20.1% |
| 1.20 | 5,254 | 61.7% / +2.254% | 63.9% / +1.426% | 9.1% |
| 1.30 | 2,050 | 61.9% / +2.791% | 65.6% / +2.059% | 1.9% |

**Both current production values sit exactly at 100% Delta retention — no accidental over-filtering exists today.** But this decisively confirms, for a third and clearest reason, why the already-parked "raise RSI_MIN/momentum for headroom" idea (rejected earlier via the freshness conflict and RQ-51's real-population collapse) must stay rejected: raising either threshold even modestly now directly and disproportionately destroys the population that justifies EMA34=2. At RSI_MIN=65, over half of Delta is already gone; at MOMENTUM_20D_MIN=1.10, over half is gone too. The aggregate win-rate/expectancy climb visible as these thresholds rise isn't new quality being found — it's the same historical extended-population effect already documented, now shown to be directly, quantifiably incompatible with the Tier-A candidate.

**`MIN_TRADED_VALUE` (liquidity floor) shows the same qualitative shape but far more gently — a real, but much less entangled, interaction:**

| MIN_TRADED_VALUE | n | SWING win/exp | OPT win/exp | Delta retained |
|---|---|---|---|---|
| ₹25cr | 36,538 | 61.0% / +1.203% | 58.4% / +0.607% | 100.0% |
| ₹50cr | 29,560 | 60.9% / +1.138% | 58.4% / +0.602% | 100.0% |
| ₹75cr | 24,628 | 60.8% / +1.050% | 58.3% / +0.594% | 100.0% |
| ₹100cr (current) | 20,858 | 61.0% / +1.065% | 58.3% / +0.598% | **100.0%** |
| ₹150cr | 15,388 | 61.2% / +1.039% | 58.1% / +0.609% | 71.2% |
| ₹200cr | 11,637 | 61.7% / +1.109% | 58.2% / +0.657% | 52.4% |

Aggregate win/exp is nearly flat across the whole range (consistent with RQ-48's finding that liquidity affects contract *availability*, not swing/stock-proxy quality) — the current ₹100cr floor retains 100% of Delta, and even raising it (which RQ-48 already rejected for unrelated options-availability reasons) costs Delta trades far more gradually than RSI_MIN/momentum's sharp cliffs (71.2% retained at ₹150cr vs. RSI_MIN=60's 88.2% or MOMENTUM=1.10's 47.2%).

**Conclusion**: current `base_filters_pass()` thresholds are correctly calibrated for the EMA34=2 population as they stand — nothing needs to change today. The value of this re-audit isn't a threshold change, it's closing off, with direct quantitative evidence, any future temptation to "improve" RSI_MIN/momentum in isolation without checking what it costs the newly-adopted population. Scripts: `ema2_threshold_reaudit.py`.

**Freshness leg (`ema2_freshness_reaudit.py`) — reproduced the established Primed-Gate/Entry-Gate Freshness comparison inside the EMA34=2 population, same Fresh/Extended cutoff (freshness_score≤0.40), no new bins invented.** The relationship survives cleanly — same direction, similar magnitude, at both EMA34 values:

| | EMA34=9 (established) | EMA34=2 |
|---|---|---|
| Primed Gate — Fresh | n=2,879, 54.2% win / −0.606% exp | n=5,201, 56.4% win / −0.192% exp |
| Primed Gate — Extended | n=13,359, 62.2% win / +1.358% exp | n=15,657, 62.5% win / +1.482% exp |
| Entry Gate — Fresh | n=417, 61.9% win / +0.955% exp | n=773, 63.8% win / +1.452% exp |
| Entry Gate — Extended | n=2,227, 69.6% win / +4.277% exp | n=2,751, 70.3% win / +4.529% exp |

Extended beats Fresh on both Gates at both EMA34 values — nothing flips. This is the already-documented tension from the RSI_MIN threshold audit (within an already-`base_filters_pass()`-qualifying population, the remaining Fresh subset skews toward a narrow, underperforming corner — different from freshness's pure, unconditioned effect on the raw trigger population). Not a new surprise; what matters is the shape is identical whether EMA34 requires 9 days or 2. Real bonus: EMA34=2 nearly doubles the Entry-Gate-Fresh sample (417→773), a better-powered read on the same relationship. **Verdict: Outcome A (per the critic's own A/B/C framework) — the Freshness relationship survives. EMA34=2 changes the persistence dimension without invalidating the established Freshness signal.**

**[2026-09-18 CORRECTION — same look-ahead bias bug as the P1/P3 corrections above.** `ema2_freshness_reaudit.py` also computed `_freshness_score()` from the breach day's own row instead of the prior day's. **Corrected Primed-Gate numbers** (recomputed, prior-day freshness):

| | Fresh | Extended |
|---|---|---|
| EMA34=2 SWING win/exp | 61.5% / +1.056% | 60.6% / +1.071% |
| EMA34=2 OPT win/exp | **65.1% / +0.848%** | 52.9% / +0.395% |
| EMA34=9 SWING win/exp | 60.7% / +0.847% | 60.8% / +1.088% |
| EMA34=9 OPT win/exp | **63.8% / +0.740%** | 53.2% / +0.387% |

Swing is close either way at both EMA34 values; **options clearly favors Fresh over Extended, by a large margin (12+ win-rate points), at both EMA34 values.** This is the corrected direction — matching, not contradicting, the established Freshness signal. **The Entry-Gate numbers in the table above have NOT yet been recomputed with the prior-day fix** — given the same bug affects that code path too, they should be treated as unverified until redone, not relied upon. **Revised verdict: still Outcome A (the relationship survives identically at both EMA34 values) — but the relationship itself is "Fresh beats Extended on options," not "Extended beats Fresh on everything" as originally, incorrectly reported.** Caught by direct user pushback (not by internal review) — see the standing methodology lesson at the end of this file's now-updated self-audit: apparent agreement between two calculations is not confirmation if they share the same underlying bug.

**Weekend threshold re-audit closed out.** All four legs done (RSI_MIN, MOMENTUM_20D_MIN, MIN_TRADED_VALUE, Freshness) — every current production value sits correctly calibrated for the EMA34=2 population, no thresholds need to change. The real, durable finding isn't a retune, it's a now-quantified reason the "raise RSI_MIN/momentum for headroom" idea must stay dead, and confirmation that EMA34=2's promotion doesn't require touching anything else in `base_filters_pass()`.

## Research Integrity Rule #6 (2026-09-18, adopted after the look-ahead bias reintroduction above) — theoretical sanity check before reporting

**A new result that contradicts an already-established, validated finding must be treated as a bug signal to investigate first, not a "new tension" to report.** Prompted directly by the freshness look-ahead bug above: a real bug (computing `freshness_score` from the breach day's own row instead of the prior day's, already found and fixed once earlier this session) was reintroduced in two newer scripts, produced a result that directly contradicted this project's own most-validated signal, and was accepted — even "confirmed" by comparing it to another result that, unknown at the time, shared the exact same bug. The user had to catch this by directly questioning the result multiple times across several turns, not by internal review catching it first.

**The rule**: before reporting a new computed result, check whether it contradicts an established finding or basic domain reasoning. If it does, re-verify the computation (look-ahead bias, off-by-one indexing, unit/scale mismatches, sign errors) *before* presenting the contradiction as real. If a "confirming" second check is being used to validate a surprising result, verify the two checks are actually independent (different code path, different data slice) — structurally similar computations can silently share the same bug, and agreement between them is not confirmation. When a surprising result hasn't been re-verified this way yet, say so explicitly rather than reporting it with full confidence.

## EMA34=2 — PROMOTED TO v31.1 CANDIDATE (2026-09-18, critic sign-off, weekend research chain closed)

RQ-56 established that EMA34=2 captures a large, genuinely distinct population (82.7% of Delta, n=3,819) rather than merely earlier versions of EMA34≥9 trades. Subsequent regime (RQ-52A), fragility (P2), and operational-capacity (RQ-57) analyses all support the candidate. The EMA34=2 population was then used to re-audit the remaining base-filter thresholds: RSI_MIN, MOMENTUM_20D_MIN, and MIN_TRADED_VALUE remain appropriately calibrated as-is — raising RSI_MIN or MOMENTUM_20D_MIN materially removes the newly-validated Delta population without establishing a sufficient reason to do so (RSI_MIN=65 already loses over half of it). Corrected Freshness analysis (after the look-ahead bias fix, Research Integrity Rule #6) confirms Freshness retains its established relationship under EMA34=2, particularly on options (65.1%/+0.848% Fresh vs 52.9%/+0.395% Extended at EMA34=2; near-identical shape at EMA34=9) — Freshness and EMA34 persistence remain genuinely distinct dimensions, and Delta is ~73% Fresh, not primarily a "Not Fresh" population as first (incorrectly) reported.

**No threshold changes are warranted from the weekend audit.** EMA34_RISING_DAYS_MIN=2, RSI_MIN=55, MOMENTUM_20D_MIN=1.05, MIN_TRADED_VALUE=₹100cr all frozen as-is; Freshness remains ranking/telemetry, not a new hard gate. The corrected freshness numbers change interpretation, not conclusion — RQ-56's uniqueness result is unaffected (ticker/date/EMA34-condition based, never touched `freshness_score`), and Update 61's RSI/Momentum/liquidity re-audit is unaffected (never touches `freshness_score` either). A correction to interpretation, not a collapse of the evidence chain.

**EMA34=2 is ready to move from research validation into v31.1 implementation and live/paper validation** — not "production-proven in every possible sense," but research-promotion-complete, an implementation candidate. Explicit critic guidance: stop researching EMA34 in isolation; the next question is not "can we find another reason it shouldn't ship" but "what happens when EMA34=2 becomes part of the actual system" — an integration-validation question, not a feature-validation one. The Entry-Gate half of the Freshness leg (not yet recomputed with the look-ahead fix) is a documentation/completeness item, explicitly not a promotion blocker. Next phase: collect the first 30-50 live/paper trades under EMA34=2 (candidate count, Delta/Common split, freshness, fragility, trigger distance, real slippage, outcome, options behavior) — not to re-prove EMA34, but to confirm the production implementation matches the research population.

## RQ-64 + correction: RQ-56's 3-day window undercounted Unique — the honest number is 40.8%, not 82.7%, and true-Unique is a real swing loser (2026-09-18)

**RQ-56's "Early vs Unique" split used an arbitrary, never-sensitivity-tested 3-trading-day lookahead window** (critic-proposed, adopted without question). Direct user mechanical challenge — "EMA=2 vs EMA=9 there is a 1-week gap, how would you find it in 3 days?" — prompted testing the same classification at N=3/5/7/10/15 trading days. Result: **Early% grows monotonically with window length as the window gives EMA34≥9 more time to "catch up"** on the same ticker:

| Lookahead window (N trading days) | Early % of Delta | Unique % of Delta |
|---|---|---|
| 3 (RQ-56's original) | 17.3% | 82.7% |
| 5 | 29.9% | 70.1% |
| 7 | 40.5% | 59.5% |
| 10 | 49.2% | 50.8% |
| 15 (= `MAX_HOLD_DAYS`, the real swing hold period) | **59.2%** | **40.8%** |

A trade only truly deserves the "Unique" label if EMA34≥9 *never* catches up within the period that actually matters — the real swing hold. N=3 was simply too short a leash: many trades it called "Unique" were really "Early, just not caught up yet by day 3," reclassified correctly once the window is widened enough to see the eventual EMA34≥9 fire (or its genuine absence). **N=15 is the honest, non-arbitrary number** — it uses the same horizon the strategy itself already holds for, not an unrelated 3-day cutoff nobody chose for a reason.

**RQ-64 (`rq64_holding_trajectory.py`, critic-revised scope — holding-period trajectory comparison, not breach/acceptance anatomy) then re-ran Early/Unique's SWING outcome at the honest N=15 window, and the result changes materially:**

| | n | SWING win/exp (N=15, honest) | SWING win/exp (N=3, as originally reported) |
|---|---|---|---|
| Early (N=15) | — | 84.0% / **+4.700%** | 78.3% / +4.317% (N=3 Early) |
| Unique (N=15) | 1,883 | **29.5% / −3.743%** | 58.2% / +0.614% (N=3 Unique) |

**True-Unique (N=15) is a real swing loser, not a modest winner as originally reported.** Options are essentially unaffected by the window choice (Early(15d) 63.7%/+0.953%, Unique(15d) 62.0%/+0.795% — both still fine), because the options exit resolves at day+1-open, long before the Early/Unique label can even change.

**Day-by-day trajectory on Unique(15d) confirms a genuine fade-and-crash, not just a fizzle** (mean close vs trigger, and % still profitable): Day0 +0.631%/54.5% profitable → Day1 +0.281%/49.8% → Day2 −0.362%/42.4% → Day3 −0.975%/36.6% → Day5 −2.113%/28.8% → Day10 −4.100%/21.2%. Mean MFE (+4.367%) is much smaller than mean MAE (−9.254%) — a real spike-then-reversal shape, returns peak at Day0 and decline every day after.

**Tested and REFUTED: is this a choppy-market artifact rather than an intrinsic property?** Split Unique(15d) by Nifty's own per-day streak-length regime across the full 5-year history (choppy: streak≤3, n=1,433; trending: streak≥6, n=148). The fade-and-crash pattern occurs equally in both regimes (Day10 −4.661% trending vs −4.169% choppy) — slightly *worse* in trending, if anything. This makes the finding more durable, not an artifact of the currently unusually choppy market.

**Tested: can a trade's own day+1/day+2 price action serve as a live-observable proxy for exit-early decisions (since the Early/Unique label itself needs up to 15 days of future data and can't be used live)?** Checked on the only real-time-knowable population — the full EMA34=2 Delta population (Common+Delta both, and Delta alone), not the hindsight Unique label:

| Check-in day | Baseline SWING (hold to real exit) | Modified (cut immediately if trade is negative vs. trigger at that day's close) |
|---|---|---|
| Day+1 (full population, n=20,858) | 61.0% / +1.065% | 35.9% / +0.725% |
| Day+2 (full population, n=20,858) | 61.0% / +1.065% | 38.0% / +0.699% |

**Complete wash on swing — cutting early on a negative day+1/2 signal is slightly worse than just holding**, because the existing structural-stop/target mechanism already extracts more from names that dip early and later recover than a hard day+1/2 cut would. (Within the hindsight-only true-Unique subset specifically, cutting early *would* have helped — roughly halves the loss, −3.743%→−1.98/−2.09% — but that's not a usable live rule, since you can't tell live whether a given Delta fire is Early or Unique until up to 15 days later; applying the rule blindly to the whole live-knowable Delta population is what produced the wash above.) The idea is closed as tested — no live edge found.

**Options genuinely improve at the whole-population level, not just in a blended-average sense** (`ema2_overall_early_price_proxy.csv`, full multi-year population, no lookahead classification involved at all):

| | n | SWING win/exp | OPT win/exp |
|---|---|---|---|
| Common only (EMA34≥9, current production) | 16,238 | 60.8% / +1.010% | 57.0% / +0.513% |
| Delta only (EMA34 2-8, new) | 4,620 | 61.8% / +1.259% | **63.0% / +0.891%** |
| Overall EMA34=2 (Common+Delta) | 20,858 | 61.0% / +1.065% | **58.3% / +0.598%** |

Options lift from 57.0%/+0.513% (current production) to 58.3%/+0.598% (EMA34=2) is real and majority-driven (Delta's own 63.0%/+0.891% genuinely beats Common, not a small-slice blend artifact) — consistent with RQ-56's original options finding, which is untouched by the window-sensitivity correction above (options resolves at day+1-open, before the Early/Unique label — computed over any window — is even relevant).

**Net correction to the promotion case**: EMA34=2's promotion to Tier A Candidate stands cleanly on **options**, at both the Delta-only and whole-population level. On **swing**, the picture is genuinely mixed, not uniformly positive as originally reported: Common(60.8%/+1.010%) + Early(15d)(84.0%/+4.700%) are both good, but true-Unique(15d) — 40.8% of Delta, a large, non-trivial chunk — is a real loser (29.5%/−3.743%) on swing specifically, driven by an intrinsic (not choppy-market-artifact) fade-and-crash mechanism. No live-observable proxy (day+1/2 price action) rescues this; the existing exit mechanism already handles it about as well as a live rule could. **This does not reopen the EMA34=2 promotion decision** (options case is untouched and sufficient on its own, per the critic's own priority framing that options was always the stronger leg) — but the swing-side "Delta is better than Common" claim should be understood as options-driven, not a broad swing improvement, going forward. Scripts: `rq64_holding_trajectory.py` (never previously logged to this file), plus ad-hoc window-sensitivity/choppy-split/price-action-proxy computations run inline (not yet saved as standalone scripts — a documentation gap to close if this line is revisited).

**Reconciliation, worth stating plainly**: Delta's own blended swing number (61.8% win / +1.259% exp) is invariant to the Early/Unique window choice — it's the same fixed 4,620 trades regardless of labeling. Decomposed at the honest N=15 split: 0.592×4.700 (Early) + 0.408×(−3.743) (Unique) = +1.255%, matching Delta's actual +1.259% almost exactly — confirming this is a real decomposition, not a statistical illusion from overlapping populations. The mechanism: **EMA34=2's genuine unlock is Early(15d)** — entering 1-15 days ahead of EMA34≥9's eventual confirmation on a move that was always going to work, capturing far more of it (+4.700% exp, 84% win, ~5x Common's average). The unavoidable cost of chasing that early entry is **true-Unique(15d)** — trades EMA34≥9 never confirms, 40.8% of Delta, a real fade-and-crash loser. Since there's no live way to separate the two before entry (established above), adopting EMA34=2 for swing means accepting both in the same blended package — a large real win more than offsetting a large real loss in aggregate expectancy, while carrying concentrated downside risk in the 40.8% tail.

## RQ-66: searching for a breach-time (pre-day+1) predictor of the Unique/Immediate-Fade tail — daily-bar Stage 1 exhausted, a real measurement-artifact caught along the way (2026-09-19)

Since Early/Unique isn't separable live, and day+1/2 price action was already ruled out as a live rule, the next question (critic-proposed as RQ-66, refined through discussion into RQ-66A "Immediate Fade" and RQ-66B "immediate weakness at breach"): can any feature knowable **at breach time** predict which Delta trades are about to fade, before you'd ever need day+1 information? Target label for this stage: **Immediate Fade** = `close_d1<0 AND close_d2<close_d1 AND close_d3<close_d2` (monotonically worsening through day+3, a sharper, more direct target than the 15-day maturity label — a True-Unique trade can still be a fine swing that just never trips EMA34≥9, and an Early trade can dip before recovering, so True-Unique is an imperfect proxy for "bad trade").

**A real measurement-artifact caught before reporting (Research Integrity Rule #6 in action)**: `simulate_swing()`/`simulate_day1()` (used for every trade-outcome number all session) measure pnl relative to `trigger_price`, not the real production entry price (`detect_entry()` actually enters at the breach day's own `Close` — a backtest necessity given no full-history intraday data, not a claim that Close is the "true" price; the live system fires nearer the trigger intraday, so trigger remains the right convention for dollar-PnL reporting and nothing above needs revisiting). The issue is narrower and specific to **feature-predicts-outcome tests**: three candidate features (`vol_zscore`, `body_atr_daily`, `dist_to_trigger_pct`) showed a dramatic, clean-looking separation in swing/options outcome when bucketed — until re-tested against returns anchored to the breach day's own Close instead of trigger, at which point the effect **completely vanished** (e.g. `dist_to_trigger_pct`'s day+3-from-own-Close return was flat at +0.01–0.13% in every bucket, vs. an apparent −1.31%→+4.75% swing-exp spread under trigger-anchoring). Root cause: `dist_to_trigger_pct` is *defined* as `(Close/trigger−1)`, so trigger-anchored forward returns carry that exact gap as a built-in constant offset in every subsequent day — any feature correlated with how far Close ends up from trigger (volume surge and candle body both are) inherits a fake predictive-looking signal purely by construction, regardless of what the stock does afterward.

**New standing rule (sibling to Rule #6)**: any test of "does a breach-time feature predict future price action" must measure the outcome from a reference point that has no definitional or correlational overlap with the feature itself — concretely, anchor forward returns to the breach day's own Close, not trigger, when testing feature predictiveness (trigger-anchored pnl remains correct and unaffected for reporting realized dollar outcomes of already-decided trades/populations, e.g. every Common/Delta/Fresh/Extended comparison earlier in this file, none of which are defined by the Close-vs-trigger gap).

**Six daily-bar, large-sample (~4,616-4,620 trade) candidates tested, properly (Close-anchored), all daily-bar-only so applicable to the full 5-year history — none produce a usable classifier**:

| Feature | Trigger-anchored result (looked strong) | Close-anchored (honest) result |
|---|---|---|
| `vol_zscore` (production Breakout Volume Z-score) | exp +0.38%→+3.18% swing across quartiles | **Void** — flat/noisy, no trend |
| `body_atr_daily` (\|Close−Open\|/ATR14, breach day) | exp +0.15%→+3.50% swing | **Void** — flat/noisy, no trend |
| `dist_to_trigger_pct` ((Close/trigger−1) on breach day) | exp −1.31%→+4.75% swing (huge) | **Void** — completely flat (+0.01% to +0.13%) |
| `consolidation_days` (production formula, `live_checkpoint._consolidation_days`) | weak already | Weak/flat, no clean trend |
| `freshness_score` (production formula, prior-day row per the established convention) | fade rate 6.5%→13.5%, swing/options both cleanly better in the freshest bucket | Flat (d3/d15 both ~flat across buckets) — matches, doesn't add to, the already-established options-specific Freshness edge; no new Immediate-Fade classifier value |
| `pullback_depth_pct` ((20-day High−Low)/20-day High before breach) | fade rate noisy, no clean trend | Noisy and internally inconsistent — the deepest-pullback bucket has both the *highest* fade rate and the *best* d15 return, consistent with a general volatility confound rather than a real signal |

**Conclusion: RQ-66 Stage 1 (daily-bar-only, breach-day and pre-breach features) is exhausted without finding a usable predictor.** This isn't a wasted effort — it rules out the cheap, large-sample options and confirms (per the critic's own escalation path, and matching the user's own instinct toward "within a few hours of breach, not day+1") that if a live-usable predictor of the Unique/Immediate-Fade tail exists, it likely requires intraday (first-hours-post-breach) information not present in the daily bar — RQ-66B, real intraday cache (~70-90 days, small sample), next. Script: `rq66_immediate_fade_check.py` (daily-bar Stage 1, `FEATURES` list); freshness/pullback-depth tested via an ad-hoc follow-up run, not yet saved as a standalone script.

**RQ-66B (`rq66b_intraday_breach_check.py`): first-hours-post-breach intraday features, real cache (~71 real days, 500 tickers) — inconclusive, sample too small to confirm or rule out.** Three deliberately non-price-ratio features (to avoid the same trigger-artifact as Stage 1): `time_of_breach_minutes` (since 9:15), `pullback_from_high_pct` (post-breach intraday high vs. EOD Close — shape of the move, not its level), `intraday_vol_ratio` (cumulative volume to breach vs. expected-by-that-time-of-day). Sample: n=303 Delta breaches with intraday coverage, split into buckets as small as 31-76 trades:

| Feature | Trigger-anchored fade-rate trend | Close-anchored sanity check |
|---|---|---|
| `time_of_breach_minutes` | 11.0%→6.3%→13.2% — no clean trend | Noisy, no clear pattern |
| `pullback_from_high_pct` | 6.6%→11.8%→10.7%→13.2% — a suggestive, intuitive-direction trend (more intraday give-back → more fade) | Does not confirm — d15-from-own-Close bounces non-monotonically across buckets |
| `intraday_vol_ratio` | 10.5%→8.0%→13.2% — no clean trend | Noisy, no clear pattern |

`pullback_from_high_pct` is the only one that even looks directionally sensible, but doesn't survive the Close-anchored check cleanly — could be a real, weak effect this sample (n≈75/bucket) is too small to resolve, or could be noise. Reporting as inconclusive rather than either confirming or rejecting it.

**RQ-66 overall conclusion (2026-09-19): nothing tried across day+1/2 live-proxy testing, 6 daily-bar breach-time features, and 3 intraday first-hours features produces a confirmed, live-usable predictor of the Unique(15d)/Immediate-Fade tail.** This is a real, if unsatisfying, result — logged as-is rather than continuing to fish for a signal without a new hypothesis. The practical implication for v31.1: per the critic's own framing, ship EMA34=2 for options now (clean, unaffected by any of this), and ship it for swing with an explicit note that ~41% of Delta is a high-risk tail current research cannot distinguish live — collect telemetry (not a new filter) on Early-vs-Unique outcomes as real trades accumulate, rather than continuing to search for a pre-entry classifier without a fresh idea.

## "Cut it faster" — four live-actionable early-exit variants tested on the full EMA34=2 population, all fail identically (2026-09-19)

Direct user pushback on the RQ-66 conclusion: "we are not even able to cut it... I am not fine with holding it for 1/2/3 days when the drawdown is already 3% down." Tested the actual, sharper version of this — not a single-bad-day check, but genuinely confirmed, worsening trends — on the only real-time-knowable population (full EMA34=2, Common+Delta, n≈20,853):

| Rule | Trigger rate | Baseline exp | Modified exp |
|---|---|---|---|
| Cut at day+2 if confirmed 2-day worsening (d1<0 AND d2<d1) | 24.6% | +1.066% | +0.892% (worse) |
| Cut at day+3 if confirmed 3-day worsening (matches "Immediate Fade" label) | 11.7% | +1.066% | +0.994% (worse) |
| Cut at day+1's gap-open if no gap-up (known at 9:16am next session — the earliest, cleanest signal found all weekend) | 32.4% no-gap | +1.066% | +0.974% (worse) |
| Two red candles immediately after breach (day+1 AND day+2 both red) | 30.8% | +1.066% | +0.827% (worse) |

Every variant, however early or however strictly confirmed, comes out worse than holding. The mechanism, checked directly on the day+2/day+3-confirmed-worsening group: the REAL exit (structural stop, anchored to actual chart structure) averages *less negative* than a hard cut at that day's close (e.g. day+3 group: real exit −4.701% vs cut-there −5.318%) — a same-day price during an active decline tends to sit near a local low, while the structural stop is set off support levels that sometimes let a name breathe past a bad stretch before either recovering or getting stopped at a genuinely better level. Four independent trigger definitions, same shape every time — this closes the "cut it faster" line as thoroughly as RQ-66 closed the "predict it in advance" line. The real, unresolved cost is behavioral (sitting through a visible drawdown), not a math problem the existing exit mechanism is failing to solve.

## Full weekend fakeout-detection catalog re-verified on EMA34=2/Delta — every one of 8 previously-tested mechanisms reproduces its original verdict exactly (2026-09-19)

Direct user request, after the above: audit and re-run *every* fakeout/early-warning mechanism this project has ever built against the new EMA34=2/Delta population, not just today's new ideas — "we have two days, go ahead with everything." Re-ran each original script (not re-derived) with `signals.EMA34_RISING_DAYS_MIN=2`:

| Mechanism (original source) | Original verdict | EMA34=2/Delta result |
|---|---|---|
| Gap-sustain/fade (`gap_sustain_check.py`, RQ-53) | Real, informative, not adopted | Reproduces almost identically: 67.6% gap-up (vs 68.6% original), 87.7% fade-within-10min (vs 87.5%) |
| Acceptance/streak-confirmation as entry-timing delay (RQ-37) | Rejected — delay erases the edge | Reproduces — delayed entry (streak≥2/3/5) worse than immediate on every threshold, both full-population and Delta-only (e.g. Delta immediate opt exp +0.759% vs delayed +0.513-0.589%) |
| RVOL@Trigger (`rvol_trigger_audit.py`, corrected production-baseline version) | Rejected — no clean, monotonic signal | Reproduces — same non-monotonic bounce on both populations (Delta n=157 too small/noisy: Q3 spikes then Q4 crashes) |
| Velocity (closing speed into trigger) | Weak lead, not validated | Reproduces — fastest-approach quartile still worst on swing in both populations (Full Q4 exp −1.054% vs +0.25/+1.06% elsewhere; Delta Q4 −0.251% vs +0.91/+2.24%) |
| Volume+displacement gated exit (`breakout_failure_volume_displacement.py`, RQ-53's "fourth attempt", SMC/ICT-motivated) | Rejected — gate makes things worse, weak discriminating power | Reproduces — vol_ratio corr +0.093/−0.034 with confirmed-label, gated exit exp −0.681% vs baseline −0.339% (worse) |
| Price+time confirmation, immediate/2-bar-confirm exit (`breakout_failure_confirmation_cost.py`, RQ-53 original) | Rejected — do-nothing beats every early-exit variant | Reproduces exactly — portfolio-level: do-nothing −0.396% beats exit-immediately −0.753% and 2-bar-confirm −0.472%; options side exit-immediately gives **0.0% win rate** vs do-nothing's 37.7% |

**Zero of eight independently-built, previously-tested-and-rejected fakeout-detection mechanisms flip verdict under EMA34=2.** This is the most thorough negative-result confirmation of the whole weekend — not a quick sanity check, a full re-run of this project's entire historical fakeout-research effort (including a dedicated full day's investigation, RQ-53, that itself did web research on mainstream TA/SMC-ICT theory before building anything) against the new population. Combined with RQ-66's from-scratch search and the four "cut it faster" variants above, this closes the entire "detect and avoid/exit the bad tail" research direction for now — the ~41% true-Unique tail is a real, accepted cost of the strategy (matching the well-documented 40-45% industry-standard false-breakout rate on daily charts), not a solvable filtering problem with current data. Scripts reused as-is: `gap_sustain_check.py`, `rvol_trigger_audit.py` (production-baseline logic reimplemented inline via `live_checkpoint._normal_day_volume_baseline`/`_clock_time_volume_fraction`), `breakout_failure_volume_displacement.py`, `breakout_failure_confirmation_cost.py`; acceptance-delay and velocity re-implemented inline (original `research_archive/` versions depend on a static, pre-EMA34=2 candidate pool file and couldn't be reused directly).

## Research Population Convention v31.1 (2026-09-20, critic-proposed, adopted): Freshness≤0.40 is the standing EMA34=2 research population

**Unless explicitly stated otherwise, EMA34=2 research uses Freshness≤0.40 going forward** — this project's existing, already-established Fresh/Extended cutoff, not a new number. Every EMA34=2 test through this whole weekend (RQ-56/64/65/66/67, the cut-it-faster tests, the full fakeout re-verification) ran on the raw, unconditioned population instead — not a bug (Freshness is ranking/telemetry, never a gate, so testing the unfiltered population was a fair first question), but not sustainable to keep re-deciding per test. This is explicitly a **backtest population convention, not a live gate** — a candidate with freshness_score>0.40 still fires and can still be taken live; Freshness stays priority/ranking information on the dashboard exactly as before. The real trade-off curve behind this choice, computed on Delta (n=4,618):

| Cutoff | Keeps | Swing win/exp | Options win/exp |
|---|---|---|---|
| None | 100% | 61.8% / +1.259% | 63.0% / +0.893% |
| **≤0.40 (adopted convention)** | 72.7% | 62.8% / +1.386% | 67.1% / +1.021% |
| ≤0.18 (~freshest 40% by rank) | 40% | 64.3% / +1.587% | 73.5% / +1.321% |
| ≤0.10 (~freshest 25% by rank) | 25% | 66.8% / +2.085% | 77.6% / +1.540% |

**A percentile-rank cutoff ("freshest N%") is the wrong shape for a live rule and was never proposed as one** — it only means something relative to a population, and a live day's candidate count (0 to ~15) is too small and too variable in its own distribution shape to rank against meaningfully. The percentile framing is a backtest-exploration tool only; any adopted cutoff must be a fixed, absolute `freshness_score` value, checkable on one candidate in isolation the instant it fires — same requirement as every other production threshold in this project (RSI_MIN, MIN_TRADED_VALUE), including the same caveat that a fixed value needs periodic (not per-test) re-validation against drift.

**Fresh-only re-verification of the weekend's key findings, done before adopting this convention (not just asserted)**: the Early(15d)/Unique(15d) split survives (Unique% moves 40.8%→42.8%, Fresh-only-Unique still a loser at 31.8%win/−3.340%exp); the fixed-R win/loss-ratio finding survives nearly identically (baseline ratio 0.96 vs Fixed-3R 1.46, vs 1.01/1.49 raw); all 6 previously-tested fakeout-detection mechanisms reproduce their raw-population verdicts exactly on Fresh-only too (gap-sustain, acceptance-streak, RVOL@Trigger, velocity, volume+displacement, price+time confirmation — none flip).

**Full retroactive Fresh-only re-check completed 2026-09-20 morning, covering the two remaining pieces not yet re-verified**: RQ-67A's context features and all four "cut it faster" variants, both on the correct Freshness≤0.40 population (Delta n=3,358, vs 4,617 raw). Both confirm exactly. Context features (`rs_rating`, `sector_rs_pct`, `breadth_pct`, `nifty_ret5`) show the same small/negligible Early-vs-Unique gaps as the raw population, and `rs_rating` still reverses direction specifically within Unique(15d)-Fresh-only (highest-RS quartile worst on swing: 29.1%win/−3.993%exp vs lowest quartile's 35.6%win/−2.821%exp) — same shape as raw. Cut-it-faster, Fresh-only Delta baseline exp=+1.385%:

| Rule | Modified exp |
|---|---|
| Confirmed 2-day worsening | +1.352% (worse) |
| Confirmed 3-day worsening | +1.357% (worse) |
| Cut at day+1 open if no gap | +1.309% (worse) |
| Two red candles immediate | +1.330% (worse) |

Every variant still loses to holding. **The entire weekend's negative-result catalog (RQ-66/66B/67A, all 4 cut-it-faster variants, all 8 fakeout-detection mechanisms) is now confirmed on the correct standing research population, not just the raw one — no exceptions found anywhere.**

## A new mechanism tested and rejected: "confirm acceptance, then enter only on a same-day pullback to the trigger" (2026-09-20)

Direct user synthesis of two apparently-conflicting findings (waiting for streak confirmation costs money because price runs up — but 78.8% of accepted trades pull back later the same day per the earlier pullback-anatomy finding): what if you confirm acceptance first, then only actually fill via a resting order if/when price comes back to the original trigger level? This is mechanically distinct from both previously-rejected ideas (not "buy at the confirmed price," not "require any pullback before any entry") and had not been tested. Since same-day intraday timing is invisible to a daily-bar simulation (a fill at 9:20 or 2pm on day 0 produces an identical forward trajectory), the test reduces cleanly to: decompose EMA34=2 breaches into `rejected` (never confirms streak≥3), `accepted_runaway` (confirms, never pulls back to trigger again that day), and `accepted_pullback` (confirms, then does pull back — the group this strategy would actually catch):

| Category (Delta, Fresh≤0.40, n=240) | % | Swing win/exp | Options win/exp |
|---|---|---|---|
| Baseline (everyone, immediate entry) | 100% | 61.3% / +1.008% | 64.9% / +0.984% |
| rejected | 19.2% | 56.5% / −0.673% | 15.2% / −0.838% |
| **accepted_runaway** | 30.8% | **70.3% / +3.129%** | **97.9% / +2.998%** |
| **accepted_pullback (the catchable group)** | 50.0% | 57.5% / +0.345% | 65.6% / +0.578% |

Holds on raw and Fresh-only, Full and Delta-only alike (checked all four cuts). **Rejected**: the group this strategy would actually catch (accepted-then-pulls-back) is *worse* than blanket immediate entry on both metrics — and the group it structurally can never catch (accepted-and-runs-away, since a resting order at trigger never fills for a stock that never returns there) is by far the best group in the whole decomposition. Mechanism: a stock retesting *after* already showing acceptance is itself a mild weakness tell — genuine strength doesn't look back. Same underlying fact as the original pullback-anatomy finding (2026-09-13) and the already-rejected retest-confirmation entry rule, now precisely quantified for a distinct, genuinely new proposed rule. **General principle stated explicitly by the user and worth keeping as a standing frame**: `rejected`/`accepted_runaway`/`accepted_pullback` — like Early/Unique before it — is a real, meaningful decomposition that is knowable only in hindsight; no live policy can selectively capture only the good third of a hindsight-only decomposition, it can only choose *which policy* to run and inherit whatever blend of outcomes that policy produces. This is now the same structural conclusion reached independently through five or six unrelated angles this weekend (EMA34 Early/Unique, RQ-66/67's feature hunt, the four cut-it-faster variants, the fakeout re-verification, and now this) — a strong, convergent result, not a series of separate near-misses.

## Retroactive methodology caveat (2026-09-20): `portfolio.py`/`simulate_lots()` assumes perfect chronological capture with no realistic visibility constraint — every capital-constrained CAGR conclusion built on it (including the 2026-09-06 fixed-3-days-after-arming rejection) should be treated as provisional, not decisive

See the full note inserted in place next to that original finding, above (2026-09-06 section, "Standing methodology caveat"). Surfaced by direct user question while considering whether to reuse `portfolio.py` to validate "Opportunity Cost Exit" for swing. `simulate_lots()` sorts every candidate by `entry_date` and admits purely on cash-affordability — it has no ranking mechanism and assumes the trader is simultaneously aware of and can act on every affordable candidate the instant it appears, with zero real-world execution/visibility risk. This exact gap was independently found and named while building RQ-57 (2026-09-18, months later) but never generalized into a standing rule at the time. **A sharper, related point from the user, more fundamental than the ranking-mechanism gap**: even a fully realistic candidate-ranking simulation still assumes the trader successfully allocates to the ranked-good trade every time — real execution (screen time, attention, luck) can never be guaranteed to match a simulation's assumptions, no matter how realistic the candidate model is. This is the actual theoretical justification for asymmetric risk:reward as a design philosophy separate from whatever any CAGR backtest says: since you cannot guarantee catching the best available trade at the right time, size wins to be large enough relative to losses that the system survives realistic execution variance, rather than depending on always getting the "right" trade. **Do not reuse `portfolio.py` for any future capital-constrained question** — if one is needed, it requires RQ-57's real approach (intraday cache + live 9:20 ranking), not a portfolio allocator.

## Critic review of Update 67, adopted in full (2026-09-20): objective split (Expectancy vs. Robustness), RQ-66 elevated to Tier A Rejected Research, stop-tightening deferred pending an Exit Efficiency Audit first

**Research objective split, named explicitly and adopted as the v31.1 objective**: *Expectancy* (average return over many trades) vs. *Robustness* (behavior under an unlucky realized stretch — the actual concern raised this weekend: "what if I only ever run into the bad third"). Everything found this weekend points toward optimizing Robustness now, not further Expectancy hunting.

**RQ-66 elevated to Tier A Rejected Research, precise wording**: "within currently available breach-time information, Early-vs-Weak separation appears unlearnable" — deliberately scoped to current features/data/timeframe/methodology, not a permanent impossibility claim. **Correction to the critic's own search-space table** (the critic proposed sector participation/market breadth/cross-sectional relative strength as still-untested "unexplored families" — this is wrong, all three were tested in RQ-67A, 2026-09-19, and rejected: `sector_rs_pct`, `breadth_pct`, `rs_rating`, and `nifty_ret5` — none distinguish Early from Unique, and `rs_rating` reverses direction specifically within Unique). Corrected table:

| Search space | Status |
|---|---|
| Single-stock price/volume features (RQ-66 Stage 1/1B/2) | Exhausted |
| Cross-sectional/market context (RQ-67A: sector RS, breadth, stock RS, Nifty tailwind) | Exhausted |
| Options-market context (OI/IV as a genuine classifier, not Audit-only telemetry) | Barely tested — the one real remaining gap |

**Fixed-R exits reframed from "recommendation" to "robustness candidate"** — the win/loss-ratio improvement (baseline ~1.0 → Fixed-3R ~1.46-1.49, survives Fresh-only) is real, but CAGR, drawdown, and capital-utilization were never checked, and a direct follow-up test found the "3R" framing is largely illusory in practice: **83% of Fixed-3R exits are the 15-day `max_hold_cap`, not the R-target** (only 2.1% of trades ever actually reach 3R) — the mechanism is closer to "remove the resistance-target ladder, hold to the cap or the stop" than a genuine R-multiple-targeting system. Tightening the initial stop (0.5×ATR vs the production 1.0×ATR) to test whether a closer target gets hit more often **does not help** — target-hit rate is statistically unchanged (2.1%→2.2%) while stop-hit rate rises slightly (14.3%→14.8%), net win/exp/ratio numbers unchanged (56.3%win/+2.232%exp/1.49 vs 56.3%win/+2.237%exp/1.50). **Do not tighten the stop based on this reasoning — it doesn't work, for the same "stop sits inside the pullback distribution" reason already established this weekend.**

**Standing plan, RQ-68 before RQ-69**:
- **RQ-68 — Exit Efficiency Audit** (first question, no stop changes yet): does the current exit (structural stop + SMA21 trail + resistance ladder + 15-day cap) capture enough of each trade's own MFE? Metrics: % MFE captured, exit efficiency (exit price / max achievable price), MFE-before-SMA21-activates (is the trail engaging too late), MAE-before-+3% (do winners survive the initial stop naturally, without needing a wider one).
- **RQ-69 — Stop Geometry Audit, comparative, NOT Delta-only**: sweep `STRUCTURAL_STOP_ATR_BUFFER` (1.0/0.75/0.5/0.0×ATR) across **Common, Delta, and the overall EMA34=2 population separately** — the structural stop is shared production machinery for both populations, so optimizing it on Delta alone risks silently breaking the ~78%-of-system Common population with no way to detect it. Metrics: average R captured, stop-hit rate, and **Recovery-After-Stop rate** (of trades stopped out, what % would have gone on to be profitable under the current wider stop, and their average MFE after the stop point) — explicitly weighted above raw win rate, since every "tighter stop" idea tested this weekend failed via this exact mechanism (cutting recoverable pullbacks, not filtering genuine noise) and it has never been directly measured before now.

## RQ-68 — Exit Efficiency Audit, real answer, comparative across Common/Delta/Overall, on the correct Freshness≤0.40 population (2026-09-20)

Real production `detect_entry()`/`check_exit()` engine (both BC and VCP patterns), full 500-ticker universe. **First pass accidentally ran on the raw, unconditioned population — caught immediately by direct user question ("is this freshness 0.4 or not?") right after adopting the v31.1 Freshness≤0.40 convention one section above — corrected and rerun properly.** Both passes agree closely (reported below is the corrected, Fresh≤0.40 version, n=1,080 of 1,690 total trades):

| | Exit efficiency (winners, realized/MFE) | Mean MFE (winners) | Mean realized (winners) | % ever engage trail (+3%) | % of eventual MFE already present at engagement | MAE before engage | Never-engage: n, mean pnl, win% |
|---|---|---|---|---|---|---|---|
| Overall | 72.5% (median 79.9%) | +7.49% | +5.63% | 52.7% | 70.7% | −2.10% / median −1.37% | 511 (47.3%), −3.15%, 37.0% |
| Common | 72.8% (median 79.8%) | +7.37% | +5.58% | 53.1% | 68.7% | −2.14% / −1.38% | 315 (46.9%), −2.65%, 40.3% |
| Delta | 71.9% (median 80.2%) | +7.70% | +5.72% | 52.1% | 74.0% | −2.03% / −1.28% | 196 (47.9%), −3.96%, 31.6% |

**Two real findings**: (1) winners give back ~27-28% of their peak favorable move on average before exiting — real, quantified room, consistent across Common and Delta, not dramatic but not nothing. (2) The SMA21 trail only protects the *last* ~26-32% of a winning trade's total move — by the time it engages (+3% up), 69-74% of the eventual total MFE has already occurred, so its real job is locking in the tail end of a move, not capturing the bulk of it. Separately, **MAE before engagement is modest** (median ~1.3-1.4%) — winners generally establish themselves without needing much room, a real data point for RQ-69's stop-width question. **A large group (46.9-47.9% of all trades) never reaches +3% at all** before being stopped or capped out, and is clearly weaker on average (win rate 31.6-40.3%) — Delta's never-engage group is notably weaker than Common's (31.6% vs 40.3% win), a real, Fresh-only-specific divergence worth carrying into RQ-69.

**New angle surfaced for RQ-69, beyond stop width alone**: since the trail engages only after most of a winning move has already happened, `TRAIL_ENGAGE_PCT` (currently 1.03, i.e. +3%) itself may be worth testing alongside stop width, not just the initial stop buffer — engaging earlier could improve exit efficiency, at the risk of whipsawing on volatility before a real move develops (the same failure mode as every "tighter/earlier" idea rejected this weekend, so must be tested with the same Recovery-After-Stop discipline, not assumed to help). Script: `rq68_exit_efficiency_worker.py` (not yet moved from `/tmp`, needs saving into the project if this line continues).

## RQ-69 — Stop Geometry Audit, comparative across Common/Delta/Overall, on Freshness≤0.40 (2026-09-20)

Real production `detect_entry()`/`check_exit()` engine, one entry-detection pass per ticker with 4 parallel exit simulations per trade (entries are identical across variants since only the stop's ATR buffer changes — `atr_entry` scaled by the buffer, not the global `STRUCTURAL_STOP_ATR_BUFFER` constant, so BC and VCP coexist safely and VCP's own stop — which never uses this buffer — serves as an internal no-effect control). Swept `structural_low − buffer×ATR` at buffer=1.0 (current production)/0.75/0.5/0.0 (stop placed exactly at the structural low, no ATR cushion at all), n=1,080 Fresh≤0.40 trades:

| | Buffer 1.0 (current) | 0.75 | 0.5 | 0.0 |
|---|---|---|---|---|
| Overall win/exp/avgR | 64.2%/+1.565%/0.13 | 64.2%/+1.559%/0.13 | 64.2%/+1.571%/0.13 | 64.1%/+1.559%/0.14 |
| Overall stop-hit rate | 10.9% | 11.3% | 11.7% | 12.4% |
| **Recovery-After-Stop** | — | **0.0%** | **0.0%** | **0.7%** |
| Common win/exp/avgR | 66.2%/+1.912%/0.15 | 66.2%/+1.903%/0.15 | 66.2%/+1.906%/0.16 | 66.0%/+1.888%/0.16 |
| Delta win/exp/avgR | 60.9%/+0.995%/0.09 | 60.9%/+0.995%/0.09 | 60.9%/+1.021%/0.10 | 60.9%/+1.018%/0.10 |

**Win rate, expectancy, and average R captured are essentially flat across the entire buffer range, on both Common and Delta separately** — even removing the ATR cushion entirely barely moves anything, while stop-hit rate rises only modestly (10.9%→12.4% at the extreme). **Recovery-After-Stop is ≈0% throughout** — unlike every other "tighten the stop" idea rejected this weekend (streak-based, acceptance-based), the extra stop-outs a tighter ATR buffer causes are not real future winners being cut short; they're trades that were headed to a loss either way, just realized slightly earlier/differently. That's the actual mechanism behind the flat result: win rate can only move if a trade flips from win to loss, and this lever essentially never does that (unlike the earlier levers, which did).

**Real, concrete illustration using actual open positions** (not backtest-detected entries — `detect_entry()`'s own algorithmic pick for these tickers differs from the real manual entries, so these are standalone examples, not double-counted in the aggregate above): GRANULES (entry 872.70, structural_low 816.00, ATR 25.55) and ANANDRATHI (entry 2228, structural_low 2090.00, ATR 41.35) both had real subsequent lows (829.00, 2150.00) comfortably above even the tightest (0.0×ATR) stop — stop width made zero difference to either. **VIJAYA (entry 1525, structural_low 1421.10, ATR 48.55) is a genuine, real exception**: real lowest Low after entry was 1380.00 — above the current 1.0×ATR stop (1372.55, never breached) but below every tighter variant (0.75×=1384.68, 0.5×=1396.82, 0.0×=1421.10, all of which would have stopped it out here) — and the real forward price 15 days later was 1558.90, a real winner. Consistent with, not contradicting, the ≈0% aggregate (buffer=0.0 showed 0.7%, i.e. roughly 1-in-130-odd) — rare individual exceptions exist even when the aggregate rate is near-zero; some stop-outs are also just systematic bad-market-day risk no technical lever can prevent, and nothing here is meant to address that. **Real practical implication, since trade quality doesn't change**: a tighter stop means smaller risk-per-share (e.g. VIJAYA's ₹152.45/share at 1.0× vs ₹103.90/share at 0.0×) for a fixed dollar-risk budget, allowing a larger position for the same risk without hurting trade quality — a position-sizing lever, not an entry/exit-quality one. Not yet tested directly (would need to fix a rupee-risk-per-trade budget and compare realized portfolio-level returns, not just per-share R). Scripts: `rq69_stop_geometry_worker.py` (not yet moved from `/tmp`).

**Direct follow-up, prompted by a sharp user question ("shouldn't average loss size at least shrink with a tighter stop, even if win rate doesn't move?") — verified rather than asserted, and the real mechanism is two offsetting effects, not "nothing happens":**

| Sub-group (tight=0.0×, baseline=1.0×) | n | Tight-stop pnl | Baseline outcome |
|---|---|---|---|
| Stopped under BOTH buffers | 118 | −8.457% | −8.692% (also `stop`, just later/lower) |
| Stopped under tight ONLY (baseline exits `max_hold_cap`/`resistance` instead) | 16 | −10.820% | −8.692% |

The user's intuition holds for the majority (n=118): cutting a trade that's headed for a stop either way, slightly earlier, does shrink the loss a bit (~0.24pp/trade) — smaller than the raw stop-distance gap would suggest, because many of these have already engaged the SMA21 trail before getting stopped, and once engaged both buffers converge toward the same trail level (only the pre-engagement gap actually differs). But a smaller, opposite-direction group (n=16) shows the reverse: these trades dip down to touch the tight stop, get cut there, but under the wider stop are never stopped at all and *partially recover* by day 15 (`max_hold_cap`) to a less-negative price than where the tight stop caught them — cutting exactly at the momentary low is worse than waiting out a partial bounce. **The two effects nearly cancel**: 118×(+0.235pp) − 16×(−2.128pp) ≈ −6.3pp spread across 134 trades ≈ −0.05pp, diluted further across the full 1,080-trade Fresh≤0.40 population ≈ −0.006pp — matching the actually-observed aggregate move (+1.565%→+1.559%) almost exactly. Real, verified mechanism, not a hand-wave: expectancy doesn't move because two genuine, opposite-direction effects are occurring on different sub-populations and roughly offsetting, not because tightening the stop does nothing to anyone.

## Fixed-R CAGR/drawdown check — real, decisive, and reverses the "robustness candidate" framing (2026-09-20)

Direct user objection to any portfolio-simulation approach requiring a candidate-selection/ranking rule ("we might end up choosing lucky trades in the backtest, but in the real world we might not, and there's no way to know") — correct concern, and it killed the RQ-57-style realistic-ranking design before it was built (also too small a sample for CAGR: ~70-90 real intraday days). **Resolved by reusing this project's own existing precedent exactly**: the 2026-09-07 deterministic Risk-of-Ruin methodology — max 5 concurrent positions, admit strictly in chronological entry-date order, skip if the cap is full, no ranking or scoring of any kind. Converted both `pnl_pct` populations into R-multiples first (structural_low/ATR at entry, recomputed per trade, same formula throughout), full 5-year EMA34=2 population:

| | Admitted (of total) | Final cumulative R | Max drawdown | Worst losing streak |
|---|---|---|---|---|
| Baseline (current production) | 263 of 1,697 (15.5%) | **+26.15R** | **−4.57R** | 6 trades, −2.40R |
| Fixed 3R | 192 of 1,570 (12.2%) | +24.49R | −5.02R | **9 trades, −3.45R** |

**Fixed-3R loses on every metric — lower cumulative return, deeper max drawdown, longer and costlier losing streak.** Mechanism: Fixed-3R holds positions longer on average (median 17d→21d, established earlier tonight), so each occupied slot ties up capacity longer under a fixed 5-concurrent-position cap, admitting 27% fewer total trades (192 vs 263) over the same historical window. The per-trade win/loss-ratio improvement (established earlier, ~1:1→~1.5:1, survives Fresh-only) is real in isolation, but doesn't survive contact with realistic trade throughput — fewer opportunities taken outweighs each one being individually better-shaped, and the worse case (a longer, deeper losing stretch) is the opposite of what "robustness" was supposed to buy. **This is the identical failure mode that killed the original fixed-3-days-after-arming exit on 2026-09-06** (good per-trade stats, reversed by a real capacity-aware test) — Fixed-R falls into the same trap. **Conclusion: Fixed-R, as built (targeting 3R against the current wide stop), is rejected as a system-level candidate.** This doesn't invalidate the underlying win/loss-shape insight (bigger wins, smaller losses is still a sound thing to want) — it means this specific mechanism isn't the way to get there; a genuinely better version would need to achieve the asymmetric shape without paying for it in holding time (e.g., a tighter stop paired with a nearer, more frequently-reachable target, rather than a far 3R target that mostly just runs out the 15-day clock — see RQ-68's own finding that 83% of Fixed-3R's exits are `max_hold_cap`, not the R-target itself). Not pursued further tonight — a genuinely new construction would be needed, not a re-tuning of this one.

**[2026-09-20 CORRECTION — the "rejected" verdict above was itself run on the raw, unconditioned population, not Freshness≤0.40, directly contradicting the standing convention adopted earlier the same session. Caught by direct user question ("is this freshness 0.4 or not?").] Re-run on the correct Fresh≤0.40 population, the verdict reverses:**

| | Admitted | Final cumulative R | Max drawdown | Worst losing streak |
|---|---|---|---|---|
| Baseline (Fresh≤0.40) | 253 of 1,081 | +15.21R | −11.21R | 10 trades, −6.02R |
| Fixed 3R (Fresh≤0.40) | 184 of 1,050 | **+19.72R** | **−6.95R** | 12 trades, −6.54R |

Fixed-3R now shows higher cumulative return (~30% more) and a shallower max drawdown (~38% shallower) on the correct population — a reversal significant enough that it was checked for robustness before trusting it (per Rule #6), by sweeping the concurrent-slot count itself (3/5/10/20/50), not just testing at one arbitrary "5":

| Slots | Baseline cumR (n) | Fixed-3R cumR (n) | Baseline maxDD | Fixed-3R maxDD | Baseline streak | Fixed-3R streak |
|---|---|---|---|---|---|---|
| 3 | +8.18R (151) | +12.46R (114) | −6.27R | −4.34R | 6/−3.83R | 9/−2.38R |
| 5 | +15.21R (253) | +19.72R (184) | −11.21R | −6.95R | 10/−6.02R | 12/−6.54R |
| 10 | +41.05R (459) | +43.13R (345) | −14.40R | −11.50R | 11/−6.80R | 10/−3.70R |
| 20 | +70.85R (811) | +82.24R (628) | −23.66R | −21.53R | 7/−4.21R | 13/−5.08R |
| 50 (~unconstrained) | +103.47R (1078) | +121.61R (1006) | −23.62R | −32.93R | 8/−3.07R | 20/−9.65R |

**Per-trade return robustly favors Fixed-3R at every slot count from 3 to 50** — a real, non-fragile signal, not a "5"-specific artifact. **Drawdown/losing-streak are genuinely mixed and flip with capacity**: Fixed-3R is shallower/better at realistic low-to-moderate capacity (3/5/10, plausibly closer to what an individual actually manages), but *worse* at very high, unrealistic capacity (50, ~the whole pool running concurrently) — a 20-trade/−9.65R streak there, the worst number in the whole table. **A separate, real methodological finding surfaced investigating why Freshness initially looked worse than Raw at slots=5**: the full, unconstrained per-trade averages of Raw and Fresh≤0.40 are nearly identical (mean R/trade 0.0972 vs 0.0957, win 64.2% vs 64.3% — Freshness is not worse), but the *admitted* subset after the 5-slot cap diverged sharply (0.0994 vs 0.0601 avg R/admitted trade) — proving the capacity-constrained admission process is itself sensitive to exactly which trades happen to be chronologically available once the candidate pool changes, independent of true underlying quality. This is a real, generalizable caveat: even a zero-ranking, pure-FCFS capacity simulation (built specifically to avoid the "did we get lucky picking trades" concern) is not immune to a *different* flavor of the same problem — which specific trades are available to fill a slot is itself sensitive to small changes in the candidate pool.

**Time-sliced view (6-month/monthly periods, 5-slot, Fresh≤0.40), directly requested to see the real path, not just the endpoint — the most decision-relevant finding of this whole line**: both mechanisms hit a shared, genuinely bad stretch at the same real calendar time (Sept-Oct 2024: baseline −1.46R then −3.80R; Fixed-3R −2.91R then −2.99R) — a systematic market-wide event neither exit mechanism could have avoided, consistent with earlier findings that some drawdowns are just bad-market-day risk. But **Fixed-3R has a real, rockier start baseline never has**: from Aug 2022 to March 2023, Fixed-3R's running total goes *negative* (down to −0.52R by Dec 2022, −0.42R again by March 2023) — baseline's worst point in the same stretch is +0.05R, never below zero. Fixed-3R's path is also generally lumpier (e.g. +5.20R in November 2023 alone, 100% win that month, vs quieter/steadier months for baseline). Both end up positive by 2026, Fixed-3R higher (+19.72R vs +15.21R), but via a path that would have felt materially worse, especially early on.

**User's explicit framing, logged verbatim as the operative principle for this whole line, pending critic input — not adopted, not rejected, held as an open observation**: "while 5-year analysis is looking good, it's also equally good to see how it is playing with my emotions over a period of time, and the more stable it is the better it will be." I.e., path stability/consistency over time is a real, separate criterion from the final aggregate number or even the single max-drawdown statistic — a mechanism that reaches a similar or better endpoint via a choppier, more emotionally taxing path is not automatically preferable just because the endpoint number is bigger. **No decision made — sent to the critic for input, per explicit instruction to keep this as an observation, not act on it yet.**

**Fixed-3R combined with each RQ-69 stop-buffer variant, same 5-slot/Fresh≤0.40 capacity test — isolates a pure R-normalization effect, not a genuine quality change.** Since entries and exit dates barely change across stop-buffer widths, the admitted trade set is *identical* at every buffer (184 trades, 58.2% win, every time) — only the R-multiple scale differs, since R = pnl% ÷ risk%, and risk% shrinks as the buffer tightens:

| Stop buffer | Admitted | Win% | Cumulative R | Max DD | Worst streak | Return/DD ratio |
|---|---|---|---|---|---|---|
| 1.0×ATR (current) | 184 | 58.2% | +19.72R | −6.95R | 12/−6.54R | 2.84 |
| 0.75×ATR | 184 | 58.2% | +20.81R | −7.11R | 12/−6.71R | 2.93 |
| 0.5×ATR | 184 | 58.2% | +22.04R | −7.29R | 12/−6.91R | 3.02 |
| 0.0×ATR (tightest) | 184 | 58.2% | +24.96R | −7.71R | 12/−7.36R | **3.24** |

Real, same-trade-sequence proof that this is pure re-scaling, not new information: if a trader sizes to a fixed rupee-risk-per-trade, a tighter stop means more shares for the same risk, so both return and drawdown grow proportionally in rupee terms — but the *ratio* between them genuinely improves a little (2.84→3.24) as the stop tightens. This is exactly the position-sizing lever already flagged in RQ-69, now confirmed inside the same capacity-constrained frame used to judge Fixed-R's viability — not a new, independent finding, the same one from a different angle.

**Directly tested and REFUTED: does a tighter stop (nearer 3R target) get hit more often — checked at the most extreme case (0.0×ATR, target as close as it can possibly be)**: target-hit rate barely moves (1.7%→1.9% from 1.0×ATR to 0.0×ATR), `max_hold_cap` stays completely dominant (83.5%→81.7%) at every width tested. The binding constraint on reaching 3R isn't distance, it's time.

**Confirmed directly — uncapped (no `max_hold_cap` at all) holding-time distribution, Fixed-3R, Fresh≤0.40**: median 28 trading days, p75=45, p90=65, max=283. Removing the cap entirely makes `target_R` jump from 1.7% (capped) to **11.2%** (uncapped) — most eventual target hits are real, they just take far longer than 15 days to arrive; `stop` still dominates either way (85.8% uncapped). **82.6% of all Fresh≤0.40 trades take longer than 15 days to naturally resolve** — and what actually happens to that group if allowed to run: win rate 58.6%, mean +5.73%, median +1.79%, a genuinely good outcome currently being truncated into a mediocre `max_hold_cap` exit at whatever price sits on day 15. **Real structural finding: a 3R target and the 15-day cap are mismatched** — the target needs roughly double the time the discipline allows, for the median trade. Since the 15-day cap was already a deliberate, settled choice (respects the real 2-3 week ceiling, not a backtest-optimal number), the fix isn't to extend the cap — any future R-multiple exit needs a target sized to actually be reachable within ~15 days, not a distant 3R.

**Checked and refuted: is this specifically a Fresh-population quirk (the "needs time to build up" hypothesis)?** No — median uncapped holding time is identical for Fresh and Extended (28 days each, n=872/404). Extended actually shows a fatter tail (p90 81 vs 65 days) and slightly higher win rate (57.4% vs 51.0%) in this uncapped frame — the long resolution time is a general property of the far 3R target, not something specific to catching Fresh setups.

**Status: held as an open observation, not a decision, per explicit instruction — the main finding standing for now is the reversed-on-Fresh-only capacity result (Fixed-3R ahead on cumulative R and max drawdown at realistic capacity, per-trade return-per-trade robust across every slot count tested), with the real caveats now attached: (1) the improvement is partly pure R-normalization/position-sizing, not new trade quality; (2) the underlying 3R target is structurally mismatched with the 15-day cap, resolving in ~28 days median rather than 15; (3) the path to get there was rockier early on than baseline's. Batching this whole line, plus the remaining pre-rabbit-hole items (average MFE-after-stop-out, `TRAIL_ENGAGE_PCT` sweep, options-context classifier), for one consolidated critic update once all are done, rather than sending piecemeal.**

## RQ-69's remaining requested metric — average MFE after stop-out (2026-09-20)

Of the 134 Fresh≤0.40 trades stopped under the tightest (0.0×ATR) buffer, only 17 have a genuine forward window to measure (baseline's own exit meaningfully later than the tight stop's — most of the other 117 converge to the same SMA21-trail exit point once engaged, or baseline resolves close in time anyway). **For those 17: mean MFE after the stop-out = +4.82% (median +2.60%)** — 82.4% show at least some further upside (≥1%) after being stopped, 35.3% show a real move (≥5%). Split further: the 16 that stayed losers under baseline too averaged +3.76% MFE-after-stop (some upside, not enough to flip the trade); the 1 case that did recover to a winner under baseline showed +21.67%. Honest caveat: n=17 is small — trust the direction (real, modest upside typically exists after a stop-out), not the exact magnitude.

**Explicit, standing caution attached to this finding by the user, to be carried forward with it everywhere it's referenced — this is not a case for wider stops**: "we don't want to keep widening our tight SL just because there is hope that someday it will recover — that is not the way I am planning to trade, and I don't want my system to behave that way either." The finding that real upside often exists after a stop-out is a description of what the data shows, not a recommendation to act on it — using it to justify wider stops (hold on hope of recovery) is precisely the psychologically-dangerous trading behavior being deliberately avoided, and this project's own tighter-stop findings (RQ-69: Recovery-After-Stop ≈0%, trade quality doesn't change with stop width) already argue against loosening stops in the first place. Any future reference to "there's often upside left after a stop" must be read as a description, not a prescription.

## `TRAIL_ENGAGE_PCT` sweep — a real, well-behaved improvement, plateaus clean and doesn't interact with stop width (2026-09-20)

Surfaced by RQ-68 (the SMA21 trail only protects the last ~30% of a winning move, since ~70% of eventual MFE has already happened by the time it engages at +3%) — tested whether engaging earlier or later changes exit efficiency, same single-entry/multi-variant simulation structure as RQ-69 (toggling the `TRAIL_ENGAGE_PCT` global per variant per bar, same technique used all session for `EMA34_RISING_DAYS_MIN`), Fresh≤0.40, n=1,079 trades, 8 thresholds swept (1.01 to 1.20), cross-checked against both the current (1.0×ATR) and tightest (0.0×ATR) stop buffer to rule out interaction:

| Engage threshold | ATR=1.0 win/exp | ATR=0.0 win/exp |
|---|---|---|
| 1.01 (earliest) | 63.3% / +1.487% | 63.2% / +1.487% |
| 1.02 | 63.5% / +1.518% | 63.4% / +1.515% |
| **1.03 (current)** | 64.1% / +1.563% | 64.0% / +1.557% |
| 1.05 | 64.1% / +1.577% | 64.0% / +1.571% |
| 1.08 | 64.4% / +1.596% | 64.3% / +1.590% |
| 1.10 | 64.4% / +1.596% | 64.3% / +1.590% |
| 1.15 | 64.5% / +1.601% | 64.4% / +1.595% |
| 1.20 | 64.5% / +1.601% | 64.4% / +1.595% |

**Engaging earlier is worse, engaging later is better, monotonically up to a clean plateau around 1.08 — no further gain from 1.08 through 1.20 at either stop-buffer setting.** Same mechanism as everything else found this weekend: a tighter, trend-following stop kicking in too soon risks whipsawing out of normal early volatility before a real move develops; more room before the trail activates helps, doesn't hurt. The two ATR variants track each other almost exactly at every threshold, confirming `TRAIL_ENGAGE_PCT` and stop-buffer width are independent, non-interacting levers. **Real, modest, genuinely well-behaved finding — current production (1.03) leaves a small amount on the table; ~1.08 is the actual plateau, not an arbitrarily-picked point.** Held as an observation pending critic review alongside everything else in this batch, not yet adopted.

## Options-market context as a genuine entry-time classifier — tested and rejected, closes the last remaining search-space item; a real bug found and fixed along the way (2026-09-20)

Real `oi_buildup_bullish()` (front-month futures price+OI, 3-day window, prior-day-ending so it's genuinely live-usable — never the breach day's own row), tested as a classifier against the Early(15d)/Unique(15d) label, F&O-only EMA34=2 Delta candidates, Fresh≤0.40 (n=1,507 with real futures data; the futures-data coverage itself only starts ~2024-01, see bug below, so this population skews more recent than most of this weekend's other tests).

**Real bug found and fixed**: `load_day_futures()` crashed with a raw `KeyError` on any pre-2024 date instead of the documented "no data → `None`" contract `oi_buildup_bullish()` already relies on. Root cause confirmed directly: bhavcopy files cached before ~2024-01 only ever contain STO (options) rows, never STF (futures) — a real, permanent data-availability gap already anticipated in the function's own docstring ("pre-2024 bhavcopy gap") but never actually handled — the column-select just crashed instead of returning `None`. Fixed: check for the required futures columns before selecting, return `None` otherwise. All 72 tests still pass; verified pre-2024 now returns `None` cleanly and post-2024 is unaffected (629 real rows for a spot-checked date).

**Population level**: OI buildup rate nearly identical for Early (26.3%) vs Unique (26.5%) — same non-distinguishing shape as every other context feature this weekend (sector RS, breadth, Nifty tailwind, stock RS).

**Whole-population outcome by buildup presence**: Buildup=True (n=398) slightly worse on swing (61.1%/+0.883% vs Buildup=False's 62.9%/+1.089%) and slightly better on options (67.3%/+0.956% vs 66.3%/+0.874%) — small, mixed, not a clean signal; the swing direction here doesn't match the earlier general-population RQ-48 finding (positive lift on both sides), most likely just population-specific (smaller, EMA34=2/Delta-only, recent-years-only) rather than a real contradiction.

**Decisive test, within true-Unique(15d) only**: Buildup=True (n=175): swing win 26.3%, exp **−3.896%** (worse than Unique's own −3.743% average). Buildup=False (n=485): swing win 32.4%, exp **−2.875%** (better than average). Within the genuinely bad tail, OI buildup presence correlates with *worse* outcomes, not better — same reversal pattern already seen with `rs_rating` within Unique. Options side shows no meaningful difference (+0.699% vs +0.715%).

**Options-market context is now exhausted as a classifier, closing the last row of the corrected search-space table** — single-stock technical (RQ-66), cross-sectional/market context (RQ-67A), and options-market context are all tested and rejected. No remaining untested classifier family for the Early/Unique split with currently available data. (Correction to prior wording per critic review: this closes the search space for breach-time classifiers using **currently available data sources** — not a permanent claim; a future data source such as IV history could reopen it.)

## `TRAIL_ENGAGE_PCT` promoted to production: 1.03 → 1.08 (2026-09-20)

Per the critic's review of Update 68 — ranked this the single cleanest, most unambiguous positive finding of the weekend (real, monotonic, clean plateau, no downside found anywhere in the tested range, cross-validated against both stop-buffer settings to rule out interaction) — and the explicit "ship the positive before touching the null" call against the still-open ATR buffer question. Changed `backtest.py`'s `TRAIL_ENGAGE_PCT` constant from 1.03 to 1.08. `python3 -m pytest tests/ -q` still 72/72 (tests reference the constant relatively, not by literal value, so unaffected by the change).

## Standing grounding rule for any ATR-buffer / stop-width research (RQ-70 and beyond) (2026-09-20)

Explicit, user-stated constraint, to be applied to every future stop-loss-width evaluation, not just RQ-70: **the stop buffer must not be judged, kept, or sized based on how well it protects against market-wide shock days (a bad Nifty day), news/event-driven moves, or unusual liquidity dislocations.** Verbatim: "if it turned out to be, it is preventing me from a worse drawdown, Nifty day or something, I don't want that level of protection... a bad market day is a bad market day... that is not something I want to optimize on. Or a news-oriented thing, event thing... I don't want it to be liquidity-seeking for sure." Only ordinary, stock-specific, non-event price action should count as evidence for or against a given stop width. Any future ATR-buffer analysis must isolate/exclude shock and event days from the actual decision, even if it still measures them descriptively.

**Correction to how this gets applied, also user-stated, sharper than the above**: there is no valid "telemetry vs decision-making" split for the stop loss specifically. The stop level is computed BEFORE entry and directly determines position size (risk-per-share → share count for a fixed rupee-risk budget) — unlike a pure classifier feature (OI buildup, RS rating, etc.) which can be observed after the fact without having changed the trade itself, there is no non-causal, observe-only version of a stop width: whichever width is chosen IS the real trade (real exit level AND real position size) that was taken. Any ATR-buffer evaluation must therefore be judged on the real executable trade (actual position-sized dollar/percentage outcome) within the normal, non-shock/non-event subset specifically — not a hypothetical "what would this have looked like as pure telemetry" rendering of shock-day behavior.

## RQ-70 — ATR Buffer Removal Audit, Phase 1 (Gap vs. Wick classification): the buffer's real effect is 100% ordinary intraday noise, and even there it mostly just delays the same loss (2026-09-20)

First real test of whether the ATR buffer is doing anything, and — per the grounding rule above — whether what it does is even the kind of thing worth keeping. Replayed every Fresh≤0.40 trade at both current (1.0×ATR) and tightest (0.0×ATR) buffers side by side (same technique as RQ-69), but this time captured, for every `stop`-reason exit specifically, the stop level in effect that day plus that day's real Open/Low — classified as **gap** (Open already at/through the stop — buffer width was irrelevant, price jumped past both stops from a lower level) vs **wick/intraday** (Open above the stop, Low touched or crossed it — the kind of ordinary single-stock noise the buffer could plausibly matter for).

**Population level (n=186 stop-loss exits across both buffers)**: gap-driven stop-outs are rare either way — 8.9% at 0.0×ATR, 11.8% at 1.0×ATR. The overwhelming majority of all stop-outs (~89-91%) are ordinary intraday wick/close-through events, not gaps — this is squarely within the "ordinary price action" scope the grounding rule says should count as evidence.

**The decisive cut — trades where the buffer actually mattered**: 16 trades stopped under 0.0×ATR but survived (didn't stop that day) under 1.0×ATR — i.e., the buffer's entire measurable effect on this population, isolated to exactly the cases where it changed anything. **All 16 of these (100%) are wick/intraday-driven, zero are gap-driven** — confirms the buffer's real job, when it does something, is genuinely about ordinary intraday noise, not an accidental gap-shield. This is real, in-scope evidence under the grounding rule, not something to discount as shock/event noise.

**But then checked what the 1.0×ATR buffer's "save" actually bought, for those exact 16 trades, under the real executable exit logic**: 15 of 16 (93.75%) still ended up exiting via `max_hold_cap` as a loser anyway (mean −8.69%, median −8.93%) — the wider stop didn't prevent the loss, it just delayed it by however many days until the 15-day cap ran out. Only 1 of 16 (6.25% win rate) went on to become a real winner (resistance exit, +7.66%). This is a direct, itemized confirmation of RQ-69's aggregate "Recovery-After-Stop ≈0%" finding — but stronger, because it's isolated to exactly the trades the buffer changed, with gap contamination ruled out first.

**Reading so far**: the ATR buffer is not an illusory gap-shield (it genuinely engages during ordinary noise, as intended) — but even in that legitimate, in-scope role, it's not actually protecting winners; it's mostly just postponing an already-bad trade's loss by a few days at the cost of a wider stop (smaller position size) for every trade, not just the 16 it "saves." Honest caveat: n=16 is small — trust the direction, not the exact 93.75%/6.25% split.

## RQ-70 Phase 2 (Volatility-regime interaction): no interaction anywhere — refutes the one remaining theoretical case for keeping the buffer (2026-09-20)

Directly tests the critic's own hypothesis for why the buffer might still matter despite Phase 1/RQ-69's flat aggregate result: ATR is meant to normalize for volatility, so maybe it earns its keep specifically in high-volatility names even if it's neutral on average. Bucketed Fresh≤0.40 trades into terciles by `atr14/entry_price` at entry (low <2.51%, mid, high >3.36% — n=360 each), compared buffer=1.0 vs 0.0 win rate/expectancy within each bucket:

| Vol bucket | 1.0×ATR win/exp | 0.0×ATR win/exp |
|---|---|---|
| Low vol | 64.7% / +0.863% | 64.7% / +0.848% |
| Mid vol | 63.5% / +1.350% | 63.2% / +1.287% |
| High vol | 65.0% / +2.573% | 65.0% / +2.634% |

**No interaction anywhere — differences are noise-level (<1pp win, <0.1% expectancy) in every bucket.** Critically, the high-volatility bucket — the one place the buffer's normalization job should theoretically matter most — shows 0.0×ATR *marginally ahead*, not behind. This directly refutes the "maybe it's a volatility-regime hedge, not an alpha lever" defense of keeping the buffer; there's no regime, high or low, where removing it costs anything measurable. Combined with Phase 1 (its only real effect is 16 trades' worth of ordinary-noise saves, 93.75% of which just delay the same eventual loss), the ATR buffer now has two independent negative results and zero positive ones.

## RQ-70 Phase 3 (Position-Sizing / Capital-Efficiency): a real mechanical tradeoff, honestly not decisive at portfolio level — inherits the same admission-artifact fragility already documented for Fixed-R (2026-09-20)

Fresh≤0.40, both buffers, real production exit logic, fixed ₹2,000 risk-per-trade convention (matches the Fixed-R work's own sizing assumption).

**Part A — per-trade, no capacity constraint (n=1,079 each)**: tighter stop mechanically needs *more* capital deployed per trade to hit the same fixed rupee-risk budget, not less — smaller risk-per-share (0.0×ATR avg initial risk 11.50% vs 1.0×ATR's 13.58%) means more shares are needed to reach ₹2,000 of risk, so more capital is tied up per trade (avg ₹20,383 vs ₹18,108, +12.6%). Dollar-PnL-per-trade is correspondingly higher too (avg ₹285.5 vs ₹258.3, +10.5%) — this is the same R-normalization mechanism already proven for Fixed-R, just expressed in rupees: since realized % return is flat across buffers (RQ-69/Phase 1/2), and dollar PnL = risk_budget × r_captured, a smaller `initial_risk_pct` mechanically inflates both r_captured and capital-required together. **This is not a free lunch — return on capital deployed is unchanged (tautologically, since dollar_pnl/capital_deployed = pnl_pct exactly), it's the same trade, just leveraged differently by the fixed-risk sizing rule.**

**Part B — capital-constrained (fixed total ₹ pool, deterministic FCFS admission by entry date, no ranking — same no-selection-bias methodology used for the Fixed-R Risk-of-Ruin check)**: tested at 4 pool sizes (3×/5×/10×/20× the average per-trade capital at 1.0×ATR), since a tighter stop needs more capital per trade and therefore fits *fewer* concurrent positions through the same pool — the real question is whether that throughput loss offsets the higher per-trade dollar edge.

| Pool size | 1.0×ATR: admitted / total $pnl / max DD | 0.0×ATR: admitted / total $pnl / max DD |
|---|---|---|
| 3× | 205 / ₹34,725 / −₹8,913 | 156 / ₹28,116 / −₹7,661 |
| 5× | 306 / ₹47,816 / −₹17,658 | 268 / ₹89,638 / −₹13,425 |
| 10× | 541 / ₹102,880 / −₹47,298 | 482 / ₹116,694 / −₹43,265 |
| 20× | 868 / ₹228,949 / −₹40,791 | 807 / ₹222,947 / −₹51,452 |

**Not robust — the winner flips with pool size** (1.0×ATR ahead at 3× and 20×, 0.0×ATR ahead at 5× and 10×), and the 5× result's win-rate jump for the admitted subset (66.8% vs 63.1%, bigger than anything seen in the unconstrained population) is the exact signature of the capacity-admission-timing artifact already documented and named during the Fixed-R rabbit hole — *which specific trades happen to be chronologically available to fill a slot is itself sensitive to small changes in per-trade capital requirements, independent of true trade quality*. Per Research Integrity Rule #6, a headline number this sensitive to an arbitrary pool-size choice is not being reported as a decision input.

**[2026-09-20 CORRECTION — the rupee-pool version of Part B above used the wrong methodology]**: a fixed ₹-pool sized as a multiple of average per-trade capital silently gives the tighter stop *fewer effective seats* than the wider stop at the same pool size (since it needs more capital per trade) — mixing "how many positions you run" with "how much each one costs," which the user does not actually do (real sizing: a fixed number of concurrent positions, each independently risking a fixed ₹2,000 regardless of stop width). Re-ran Part B the correct way — fixed **seat count** (3/5/10/20 concurrent positions, deterministic FCFS by entry date, no capital tracking, no ranking — same methodology already trusted for the Fixed-R Risk-of-Ruin check):

| Seats | 1.0×ATR: admitted / total $pnl / avg $pnl / maxDD | 0.0×ATR: admitted / total $pnl / avg $pnl / maxDD |
|---|---|---|
| 3 | 171 / ₹44,383 / ₹259.6 / −₹15,559 | 171 / ₹49,254 / ₹288.0 / −₹16,067 |
| 5 | 269 / ₹63,265 / ₹235.2 / −₹26,600 | 269 / ₹69,289 / ₹257.6 / −₹27,447 |
| 10 | 498 / ₹109,091 / ₹219.1 / −₹44,567 | 498 / ₹123,795 / ₹248.6 / −₹44,292 |
| 20 | 845 / ₹191,567 / ₹226.7 / −₹59,862 | 845 / ₹213,585 / ₹252.8 / −₹62,962 |

**This is robust and consistent, unlike the rupee-pool version**: 0.0×ATR wins on total $ P&L and avg $ P&L/trade at every single seat count tested, by a fairly steady ~10-14% margin, with the *identical* admitted trade set/count at every seat count for both buffers (seat occupancy depends only on entry/exit dates, not capital, so this comparison is genuinely apples-to-apples — no admission-timing artifact here, unlike the rupee-pool version or the earlier Fixed-R Raw-vs-Fresh case). Max drawdown is roughly a wash — sometimes marginally worse for 0.0×ATR (3, 5, 20 seats), once marginally better (10 seats) — no consistent direction, small in magnitude either way.

## Re-testing two stale exit-timing rejections on the current EMA34=2/Fresh≤0.40 population and current stop geometry (2026-09-20)

Both the reactive 3-day-stall and fixed-N-days-after-arming were last validated/rejected on a population and stop mechanism that's since changed (pre-EMA34=2, pre-Freshness≤0.40, pre-`TRAIL_ENGAGE_PCT`=1.08 — and fixed-N-days-after-arming's original rejection specifically used `portfolio.py`, since flagged (2026-09-20, see above) as assuming unrealistic perfect chronological capture). Re-ran both directly rather than assuming the old verdicts still apply.

**3-day stall** (arm at 0.55R — this weekend's R-convention, not the old 3×ATR distance — exit after 3 consecutive days with no fresh high): fires on 61/1,079 trades (5.6%), averaging +4.42% on those vs. −1.63% to −2.22% for what they'd have averaged under `max_hold_cap`. But aggregate is nearly flat (win 64.4%→64.7%, exp +1.596%→+1.504%, median +2.282%→+2.249%, return/day +0.3065%→+0.3098%/day) — **reproduces the exact "near-wash" verdict from 2026-09-14, on a materially different population.** The original finding holds up, not stale.

**Fixed-N-days-after-arming** (unconditional exit exactly 3 trading days after arming at 0.55R, no streak-tracking): fires on 76/1,079 trades (7.0%). Per-trade % stats look similar-to-slightly-better (win 64.4%→65.2%, median +2.282%→+2.295%) but mean expectancy and dollar terms are worse (exp +1.596%→+1.479%; at fixed ₹2,000 risk, avg $pnl/trade ₹258.3→₹225.9, about −12.5%). **Then ran the corrected seat-based capital-constrained comparison** (3/5/10/20 seats, FCFS by entry date, per-variant exit-date capture — the methodology fix from earlier today, not the old distrusted `portfolio.py`):

| Seats | Baseline: admitted / total $pnl / avg $pnl | Fixed-3-after-arm: admitted / total $pnl / avg $pnl |
|---|---|---|
| 3 | 171 / ₹44,383 / ₹259.6 | 175 / ₹43,987 / ₹251.4 |
| 5 | 269 / ₹63,265 / ₹235.2 | 276 / ₹49,984 / ₹181.1 |
| 10 | 498 / ₹109,091 / ₹219.1 | 513 / ₹99,892 / ₹194.7 |
| 20 | 845 / ₹191,567 / ₹226.7 | 861 / ₹181,613 / ₹210.9 |

**Baseline wins at every seat count, consistently** — confirms the original 2026-09-06 "do not adopt, natural exits compound better" verdict independently, on a different population AND a methodology this project now trusts more than the one that produced the original rejection. Two independent confirmations (old flawed methodology, new trusted one) agreeing is real evidence, not a coincidence of one bad tool. **Status: both re-confirmed rejected/near-wash — no change to the frozen exit architecture from either re-test.**

## Fixed 1R/2R/3R targets side-by-side, current population/settings, with return/day and dollar-expectancy (2026-09-20)

Direct request: put 1R, 2R, and 3R fixed targets (replacing the moving resistance target, stop/climax/max_hold unchanged) side by side with `return/day` and dollar-expectancy at fixed ₹2,000 risk — same current EMA34=2/Fresh≤0.40 population/stop geometry as everything else re-tested today.

| Variant | Win | Exp | Median | Avg days | Ret/day | Avg $pnl (₹2000 risk) | Target hit rate |
|---|---|---|---|---|---|---|---|
| Baseline (moving resistance) | 64.3% | +1.606% | +2.262% | 15.0 | **0.3098%/day** | ₹255.6 | 49.7% |
| 1R | 57.5% | +1.978% | +1.471% | 19.3 | 0.2136%/day | ₹287.5 | 16.1% |
| 2R | 56.9% | +2.143% | +1.332% | 20.5 | 0.0871%/day | ₹330.8 | 5.4% |
| 3R | 56.9% | +2.134% | +1.332% | 20.9 | **0.0347%/day** | ₹335.3 | 1.3% |

Clean, monotonic pattern as the target widens: win rate drops, average dollar-per-trade rises, but **return/day collapses** (0.31%→0.21%→0.09%→0.03%, roughly 9x worse at 3R than baseline) because target-hit rate falls off a cliff (49.7%→16.1%→5.4%→1.3%) and almost every trade just rides out to the 15-day `max_hold_cap` instead (baseline 42.3% share → 3R 89.0% share). This is the same 15-day-cap-vs-far-target mismatch already found for 3R specifically during the earlier Fixed-R rabbit hole, now shown cleanly across all three targets together: **the wider the fixed target, the more the trade converts from "hit a real target" into "ride the clock and hope," and the worse the capital-rotation efficiency gets, even though raw $-per-trade looks better.** Consistent with the standing critique already on record (2026-09-06) that return/day only matters if freed-up capital is genuinely redeployed — the real decisive test for any of these, if pursued further, is the seat-based capital-constrained comparison already built and trusted this weekend (used for Fixed-3R and fixed-N-days-after-arming), not this per-trade table alone.

**Re-checked at the tighter candidate stop (0.0×ATR, the RQ-70 removal candidate) instead of the current live 1.0×ATR** — same population (n=1,049, confirmed identical since entry detection doesn't depend on the stop buffer):

| Variant | Win (1.0×→0.0×) | Avg $pnl (1.0×→0.0×) | Ret/day (1.0×→0.0×) | Target hit rate (1.0×→0.0×) |
|---|---|---|---|---|
| Baseline | 64.3%→64.2% | ₹255.6→₹283.8 | 0.3098%→0.3018% | 49.7%→49.6% |
| 1R | 57.5%→57.6% | ₹287.5→₹317.7 | 0.2136%→0.2330% | 16.1%→19.6% |
| 2R | 56.9%→56.8% | ₹330.8→₹372.8 | 0.0871%→0.0866% | 5.4%→6.7% |
| 3R | 56.9%→56.8% | ₹335.3→₹376.9 | 0.0347%→0.0301% | 1.3%→1.5% |

**No change to the conclusion.** Win rates unchanged, dollar-per-trade higher across the board (same R-normalization mechanism as everywhere else this weekend), target-hit rates nudge up slightly but nowhere near enough to matter (a tighter stop makes the same distant target only marginally easier to reach, matching the already-established "tighter stop barely moves target-hit rate" finding). Return/day still collapses monotonically as the target widens, baseline still wins clearly. **Confirms the core problem is time (15-day cap vs. how far the target sits), not stop width** — switching the stop doesn't rescue fixed-R targets.

**RQ-70 overall verdict**: three results now, all pointing the same direction. Phase 1: the buffer's only real effect is 16 ordinary-noise saves, 93.75% of which just delay the same eventual loss rather than prevent it. Phase 2: zero interaction with volatility regime, including high-vol, the one regime where it should matter most if it mattered at all. Phase 3 (corrected): at real, fixed-seat position sizing — which is how this is actually traded — removing the buffer produces a consistent, robust $-P&L improvement (~10-14%) with no meaningful drawdown cost, because the underlying % trade quality is unchanged (Phase 1/2/RQ-69) while the fixed-risk sizing rule mechanically extracts more rupees per unit of realized % return from a tighter stop. No dimension tested shows a reason to keep the 1.0×ATR buffer; capital-efficiency, once measured the way it's actually used (seats, not a rupee pool), is a real reason to remove it, not just a non-decisive mechanical curiosity.

**[2026-09-20 methodology re-check]**: found and fixed the same per-variant exit-date bug in this Phase 3 script that was independently caught while building the 3-day-stall/fixed-N-days-after-arming re-tests (both variants' exit_date was being stamped from whichever variant finished last, not each one's own real exit day). Re-ran the seat-based table above with the fix — **barely changed** (only 1.6% of trades ever had a genuinely different exit date between the two buffers to begin with): 3/5/10/20 seats now admit 171/171, 269/270, 498/498, 845/847 respectively (vs. forced-identical before), and 0.0×ATR still wins total $pnl and avg $pnl/trade at every seat count by the same ~10-13% margin. The conclusion was not an artifact of the bug.

## A foundational exit-mechanism bug: stop and resistance were both evaluated on the day's CLOSE, not real intraday order execution — found, root-caused, and fixed on the stop side (2026-09-20)

**How this surfaced**: investigating the loss-bucket distribution's extreme tail (a −₹5,135 IEX trade, −₹4,723 BEML trade, well past the intended ₹2,000 risk). Traced IEX directly: a real, confirmed **-29.6% single-day regulatory crash** (CERC's market-coupling decision breaking IEX's exchange monopoly, 2025-07-24 — verified via web search, not assumed; stock hit its lower circuit at exactly ₹131.50, matching the cached data precisely, so not a data artifact or corporate action). This one was genuine, unavoidable gap risk — the day's Open (₹169.10) was already below the stop (₹178.50), so no order type could have done better. Correctly out of scope for the ATR-buffer decision per the standing grounding rule.

**But checking further found something much bigger**: of 80 stop-exits (Fresh≤0.40, 0.0×ATR) realizing worse than −1.05R, only 2 (IEX, BEML) were genuine opening gaps. **The other 78 were NOT gaps** — the day opened above the stop, but `check_exit()`'s `hit_stop = row.Close < current_stop_level(...)` only evaluates the day's **close**, so on a day where price crosses the stop intraday but keeps declining into the close, the model records the exit at that full closing loss instead of where a real resting stop order would have filled — near the stop, the moment price first touched it.

**Initially misdiagnosed as a deliberate, defensible design choice** (reasoned by analogy to the entry side's own explicit "close-based breakout, not intraday touch, by design" convention, already tested and kept — see the near-miss-high-breakout section). **User correction, important and worth preserving precisely**: this analogy doesn't hold. The entry-side close-confirmation was a real, deliberate, tested decision. The exit-side stop/target checks were never designed that way — a real stop-loss and a real target order are resting orders that fire the instant price touches them, intraday, not "wait for end of day and see." Conflating the two was a mistake, not a subtlety.

**Also found, separately, a symmetric issue on the target side** (the very complaint that opened this whole thread — "why does GRANULES/IFCI look like it should have exited on day 1, yet the system holds for 15+ days" — was correct, not a misunderstanding): `hit_resistance` is also purely Close-based (`row.Close >= state["target"]`). Under a real resting limit-sell, a wick up through the ratcheting daily-pivot target would already have filled. Testing this properly (touch-based: `High >= target`) showed the current mechanism is dramatically over-sensitive to real execution — target-hit share jumps from 49.7% to 89.1%, average holding time for a resistance exit collapses from 9.78 days to 3.63 days, and the target's own average gain shrinks from +6.07% to +2.03% (real profit-taking becomes mostly incidental noise-catching, not genuine breakout capture). **Not yet fixed — target-side redesign is the next phase, several candidates already tested (see below), not yet decided.**

**Stop side, fixed**: touch-based (`Low <= stop_level`), with a 0.5% slippage haircut on the fill (`stop_level*(1-0.005)`) to reflect realistic trigger/fill variance rather than an optimistic "fills exactly at the level" assumption. Tested both buffers (1.0×ATR, 0.0×ATR), Fresh≤0.40, target left Close-based (isolating the stop-side fix specifically):

- Stop-exit share rises (7.9%→11.6-13.2%) — real execution catches wick-through-and-recover cases the close-based model was letting ride (sometimes into a later win that was never real).
- **But each individual stop loss becomes smaller, not bigger** (−9.70%→−8.4%) — a real order fires at the touch, not at whatever the close happens to be after riding out a bad day.
- **Flip-rate, checked directly**: 17-18 trades (1.6-1.7% of the population) flip from winner (close-based) to loser (touch-based) — **zero flip the other direction**, confirming this is a one-way correction (touch-based can only catch stops close-based missed, never remove a real one).
- **Drawdown improves substantially and consistently** at every seat count (3/5/10/20) and both buffers in the seat-based capital-constrained simulation — 22-55% smaller max drawdown (e.g., 5 seats/1.0×ATR: −₹26,600→−₹11,916), while total $ P&L stays roughly a wash. The IEX/BEML-driven extreme loss-bucket tail (below −₹3,000) disappears entirely under touch-based execution; worst loss in the population drops from −₹5,135 to −₹2,297.

**Reading**: this is good news, not bad. The close-based model was making the system look *riskier* on its worst days than real execution would actually be — fixing it mainly removes exaggerated tail-risk that was a modeling artifact, not a real return cost. **Standing implication, not yet acted on**: `MAX_HOLD_DAYS`, the Freshness≤0.40 population convention, EMA34=2's own adoption, and essentially every win-rate/expectancy-based finding in this project's history were measured using the old close-based mechanism — absolute numbers everywhere are provisional pending the corrected mechanism; relative comparisons (does classifier X separate good from bad trades) are plausibly more robust to a bias hitting both compared groups equally, but this has NOT been verified and should not be assumed. Planned order: finish the exit mechanism (stop done, target next, then `MAX_HOLD_DAYS`), then spot-check Freshness/EMA34=2 specifically against the corrected baseline before deciding whether wider re-validation is needed.

**Standing note, not a decision**: if the ATR buffer is ultimately removed (0.0×ATR), the user's original ₹2,000-risk-per-trade convention (bumped up from a preferred ₹1,000) was itself a response to the current wide stop not allowing enough shares at ₹1,000 risk. A tighter stop may make ₹1,000 risk workable again — revisit position sizing once the ATR-buffer decision is finalized, not before.

## Target-side redesign, touch-based execution: which pivot rung, and what happens to the stall/arming overlays now (2026-09-20)

**Pivot-rung sweep** (touch-based target `High >= target`, touch-based stop already fixed, Fresh≤0.40): only pp/r1/r2 exist (no r3), swept which rung(s) the target is allowed to use.

| Variant | Win | Exp | Median | Avg days | Ret/day | Hit rate |
|---|---|---|---|---|---|---|
| pp_only | 61.1% | +1.468% | +0.540% | 4.6 | 0.112%/day | 94.7% |
| r1_only | 80.1% | +1.249% | +1.933% | 8.0 | 0.658%/day | 77.5% |
| r2_only | 64.6% | +1.301% | **+2.642%** | 13.7 | 0.425%/day | 50.6% |
| **nearest_r1_r2 (skip pp)** | **80.3%** | +1.296% | +1.969% | 7.8 | **0.773%/day** | 77.8% |
| current_pivot (production, nearest of all 3) | 68.1% | +1.259% | +1.630% | 5.1 | 0.550%/day | 89.1% |

**`pp_only` is confirmed as the worst offender** — it's the closest of the three levels, producing the tightest, noisiest exits (94.7% hit rate, median only +0.540%). **`nearest_r1_r2` (drop pp from the target computation entirely) is the standout candidate** — best win rate in the table (80.3%) and best return/day by a clear margin (0.773%/day, 40% ahead of current production), without needing to go all the way to the slower, rarer r2_only. Leading replacement for the current mechanism, pending further scrutiny.

**Re-tested the 3-day stall and fixed-3-days-after-arming overlays (arm at 0.55R) on top of both the current target and `nearest_r1_r2`** — both are now essentially inert:

- On current target (touch-based, 89.1% hit rate, 3.6-day average): overlays fire on only 5 of 1,174 trades (0.4%) — baseline/stall/fixed3afterarm statistically identical (68.3-68.4% win, same everything).
- On `nearest_r1_r2` (77.8% hit rate, 7.8-day average, more room to matter): overlays fire on 13 of 1,127 trades (1.15%) — still statistically indistinguishable from baseline (80.4-80.6% win, +1.26-1.29% exp across all three).

**Real conclusion, not just a null result**: the 3-day stall and fixed-N-days-after-arming were built to solve a problem the *broken close-based target* was creating — trades lingering unresolved for weeks because the target rarely got close-confirmed. Once the target is touch-based and honest (even before picking the final rung), 78-89% of trades resolve via a genuine hit within 4-8 days, leaving only 11-14% of trades that ever reach a point where a stall/arm rule could act. There's no lingering population left for these overlays to work on anymore — not because the underlying idea was wrong, but because the thing it was compensating for (an artificially slow-resolving target) no longer exists once the target mechanism itself is fixed.

## `nearest_r1_r2` drawdown table and per-trade dollar PnL, both buffers — validating the leading target candidate before deciding (2026-09-20)

Same seat-based capital-constrained methodology as the ATR-buffer work, now on `nearest_r1_r2` + touch-based stop (0.5% slippage), Fresh≤0.40, comparing against the original all-close-based baseline:

| Seats | Original (close-stop + close-target) | Corrected (touch-stop + `nearest_r1_r2` touch-target) |
|---|---|---|
| 3 | 171 admitted / ₹44,383 / **−₹15,559** | 303 admitted / ₹64,900 / **−₹8,657** |
| 5 | 269 admitted / ₹63,265 / **−₹26,600** | 470 admitted / ₹117,403 / **−₹10,243** |
| 10 | 498 admitted / ₹109,091 / **−₹44,567** | 803 admitted / ₹169,822 / **−₹20,334** |
| 20 | 845 admitted / ₹191,567 / **−₹59,862** | 1,101 admitted / ₹197,882 / **−₹26,234** |

Roughly half the drawdown, 45-75% more total $ P&L, 60-80% more trades admitted at every seat count — because trades resolve in ~8 days instead of ~15, so the same seats turn over far more often. Not a marginal tweak, a materially better system on every axis simultaneously.

**Per-trade dollar PnL (₹2,000 risk), 1.0×ATR vs 0.0×ATR**:

| | Win | Avg WIN | Avg LOSS | Blended avg/trade | Median $pnl/trade |
|---|---|---|---|---|---|
| 1.0×ATR | 80.4% | +₹539 | −₹1,261 | ₹186.3 (0.093R) | ₹291.3 |
| 0.0×ATR | 80.4% | +₹602 | −₹1,360 | ₹217.6 (0.109R) | ₹352.1 |

Same win rate (target-hit is buffer-independent), but every dollar figure is bigger at 0.0×ATR — the same R-normalization mechanism found throughout RQ-70. Worth flagging honestly: the *blended average* per trade here (₹186-218) is actually a bit lower than the original close-based baseline's ₹255.6 — win rate went way up (64%→80%) but each individual win got smaller (quick, modest moves instead of letting bigger ones develop) while losses got a bit bigger. The real payoff is at the portfolio level (faster turnover → far more trades fit through the same capital → better total $ and drawdown), not in the raw single-trade average — a genuinely different trade rhythm (frequent small wins) than before (occasional bigger ones), not just a better version of the same one.

**Dollar-outcome bucket table** (0.0×ATR): worst loss capped at −₹2,264 (same touch-based-stop safety), but the shape is now heavily concentrated in small wins (70.8% land in ₹0-1,000, up from 39.6% originally) with a much thinner upper tail (1.6% above ₹2,000, vs. 7.2% before).

## Two more target candidates tried and rejected: bare "exit at first no-fresh-high streak" (catastrophic without an arm gate), and the arm-gated version (better, still loses to `nearest_r1_r2`) (2026-09-20)

Motivated directly by the divergence investigation below: since a real trade's life involves many short pauses before a genuine reversal, why not use the trade's *own* first pullback as the exit signal instead of an external pivot level? Tested two ways.

**Bare version (no arm gate at all, K=1/2/3 days of no fresh high triggers exit)** — a clean, decisive failure:

| K | Win | Median | Ret/day | Fires on |
|---|---|---|---|---|
| K=1 | 43.8% | **−0.344%** | −0.316%/day | 98.9% of trades |
| K=2 | 44.4% | **−0.409%** | −0.207%/day | 96.5% |
| K=3 | 45.3% | **−0.459%** | −0.151%/day | 92.0% |

Below-50% win rate, negative median at every K, fires on nearly everything — this independently reproduces a failure mode already found and named on 2026-09-05: "removing the arming gate entirely is a real regression... cuts good trades before they've developed." A real uptrend pauses constantly without it meaning anything; catching the very first pause with no other condition just catches normal noise.

**Arm-gated version (arm at 0.55R first, same as the 3-day-stall convention, then watch for K days of no fresh high)** — better, but still clearly behind the leading candidate:

| Variant | Win | Median | Ret/day | Max_hold share |
|---|---|---|---|---|
| K1_armed | 58.0% | +1.603% | 0.107%/day | 57.8% |
| K2_armed | 57.3% | +1.471% | 0.056%/day | 61.0% |
| K3_armed | 57.0% | +1.317% | 0.027%/day | 64.8% |
| `nearest_r1_r2` (standing leader) | **80.3%** | **+1.969%** | **0.773%/day** | 8.0% |

Fixing the arm-gate problem stops the mechanism from firing on everything (23-31% instead of 92-99%), but `nearest_r1_r2` still wins decisively on every metric, and most tellingly, `max_hold_cap` still swallows 58-65% of trades under this mechanism vs. only 8% for `nearest_r1_r2` — most trades still never get caught by either condition and just run out the clock. **Verdict: the trade's own swing structure, even with the arm-gate fix, is a less reliable signal than a simple external pivot level (r1/r2). `nearest_r1_r2` remains the standing leader across every target mechanism tested (pivot rungs, fixed-R, fixed-%, stall/arm overlays layered on a target, and now stall/arm used as the target itself).**

## Reverse-engineering the real reversal point: does RSI/volume divergence across swing highs predict what's coming — tested capped and uncapped, decisively rejected both times, with a real mechanism found (2026-09-20)

Different angle from hypothesis-driven candidate testing: instead of guessing target mechanisms, look at where trades *actually* reverse and check what the market looked like there. Replayed trades under `trail_only` (SMA21 trail + stop + climax, no separate target), found each trade's swing-high sequence (K=2-day fractal: a High counts once 2 days pass without being exceeded), and compared RSI/volume at the first swing high vs. the final one for trades with ≥2 genuine higher highs.

**First pass (capped at `MAX_HOLD_DAYS`=15)**: divergence (RSI down + volume down despite a higher price high) was real and detectable (47.6% RSI divergence, 42.1% volume, 22.7% both) but predicted *better* outcomes, not worse — divergent trades: 88.0% win/+6.13% mean vs. non-divergent: 72.9%/+5.20%. **But then checking the exit-reason breakdown revealed the cap was hiding the real question**: 95.8% of these trades exit via `max_hold_cap`, not `stop` — they weren't reversing at all, just stalling (still +5.78% average) and getting force-closed by the calendar, not by any real technical breakdown.

**Re-ran fully uncapped** (`MAX_HOLD_DAYS` removed for this experiment specifically, bounded only at 250 trading days) to see the trade's real, natural life: 95.4% now exit via a genuine `stop` (real reversal, not a time-out), average holding time jumps to ~51 days, and even stop-exits average **+5.21%** overall (**+12.49%** for the higher-high subset) since it's a trailing stop — by the time it actually catches you, you've usually banked real profit first. **Divergence result holds up, even more clearly, on this real dataset**: 132 diverging trades (94.7% win, +15.62% mean) vs. 364 non-diverging (87.1% win, +12.55% mean) — divergence still predicts *better*, not worse.

**Verdict: closed, with a real mechanistic explanation, not just two null results.** Classic bearish-divergence lore comes from reversal/topping-pattern contexts; it doesn't transfer to a system built to catch stocks *early* in a fresh momentum move — a second high made on softer RSI/volume here is usually just a normal healthy pause within an intact trend, not distribution. This is the same underlying pattern as every other "detect the bad tail early" investigation this project has run (RQ-53, "cut it faster") — a signal that looks like weakness in isolation carries no predictive value in this specific population.

**Real structural finding surfaced along the way, independent of divergence**: the trade's genuine, natural, undistorted life is ~51-52 days on average (for trades that develop at least 2 real swing highs) before a real reversal (trailing-stop hit) — nowhere close to the current 15-day cap. This directly informs the still-open `MAX_HOLD_DAYS` re-tuning question flagged earlier: the cap isn't just occasionally early, it's cutting off the *majority* of a real trend-following trade's natural life for this subgroup specifically.

## A market-microstructure detour, a real portfolio-metric bug caught, and the target definition finally rebuilt properly on scipy — where the target-side investigation actually lands (2026-09-20)

**A metric bug, caught mid-session**: the "return/day" figure used throughout today's target comparisons (mean of each trade's own `pnl%/holding_days`) is distorted — a single fast, sizeable loss dominates that average (e.g., −8% in 5 days = −1.6%/day) while a slow winner barely registers (+3% in 22 days = +0.14%/day), so it can show a mechanism as clearly worse when the real, portfolio-level money is fine. Switched to **portfolio $/day = total $pnl ÷ total capital-days held**, which doesn't have this distortion. Under the corrected metric, **pure trail-only (no target at all) actually beats every target-based mechanism tested today** — the opposite of what the flawed metric suggested. This means every earlier "X beats Y on return/day" claim from today (pivot rung sweep, fixed-R comparison, stall/arm tests) should be treated as unreliable; only the portfolio-$/day numbers below are trusted.

**Swing-low trail, a real established technique, tested against SMA21**: per real swing-trading practice (trail the stop below the most recently confirmed higher low, not a moving average distance), built and tested. Nearly identical portfolio $/day to SMA21 (₹13.24 vs ₹13.34) — not a clear win — but a genuinely different risk shape: stops out more often (16.6% vs 13.7% of exits) at **half the average loss size** (−3.98% vs −7.52%), the same kind of offsetting-effects cancellation found for the ATR buffer (RQ-69) and now a third time here.

**Target + trail combinations tried, twice, with real bugs caught each time**: (1) the pre-entry 252-day high (`high_252`) frequently collapsed onto the entry day's own high for fresh-breakout entries — a degenerate, meaningless "target" barely above entry, caught by direct inspection of real trade examples, not assumed; (2) a hand-rolled ZigZag state machine had a genuine bug (multiple consecutive same-type pivots, violating basic alternation) — caught the same way. **Per direct instruction, stopped hand-rolling and installed `scipy` instead** (`requirements.txt` updated) — rebuilt on `scipy.signal.find_peaks` applied to **log(High)** (so a fixed `prominence` parameter maps to a fixed % move regardless of price level), `distance=3`/`prominence=log(1.05)` matching the standard ZigZag "Deviation/Backstep" convention from the trading literature, lookback strictly excluding the entry day itself (fixes the `high_252`-style degenerate case structurally, not just by patching one example). Verified directly against real dates before trusting any aggregate number.

**Portfolio $/day, final comparison**: `scipy ZigZag target → swing-low trail` = ₹12.84/day (65.3% of trades get a real, verified-legitimate target, resolving in 14.2 avg days) vs. pure SMA21 trail ₹13.34/day and pure swing-low trail ₹13.24/day. Pure trail still edges ahead (~3-4%) on raw aggregate money.

**But the real, decisive question — for trades that end up as stop-losses, how much genuine upside got touched and fully given back before the reversal**:

| | Avg MFE touched | Avg final pnl | Avg give-back | Touched ≥2% first |
|---|---|---|---|---|
| SMA21 trail, stop-outs | +4.97% | −7.52% | **12.48pp** | **61.8%** |
| ZigZag target, stop-outs | +4.84% | −6.51% | **11.35pp** | **58.2%** |

**58-62% of eventual stop-losses genuinely touched at least +2% favorable movement first** (a quarter touched +5%+) before fully round-tripping into a net loss — real, common give-back, not a rare edge case. This is a genuine tension with the aggregate $/day result, not a contradiction: pure trail wins in total because it preserves more upside on *winning* trades that run far, but on *losing* trades specifically it's measurably costly — it lets real, touchable gains fully reverse instead of banking any of it. The ZigZag-target mechanism already reduces this somewhat (11.35pp vs 12.48pp give-back) simply by intercepting some trades before they complete the full round trip.

**Decision for now**: adopt `scipy ZigZag target → swing-low trail` as the standing target mechanism, not pure trail — nearly identical aggregate efficiency, genuinely reduces the give-back tension, and is the one candidate with fully verified numbers (library-based, real examples checked) rather than a hand-rolled implementation with two caught bugs behind it. **Not a final answer** — the give-back tension is only partially addressed. Next, explicit follow-up: test a genuine partial-exit design (bank some position size at the real target, trail the remainder) to see if it captures more of the give-back without giving up much of what pure trail preserves on winners.

## Update 71 governance decisions — versioning, new Tier A metric, and standing workflow rules (2026-09-20)

**Version boundary adopted**: "Legacy Exit Engine" (≤ Update 69, close-based stop/target) vs. "Execution Engine v2" (Update 70+, touch-based stop + touch-based target, both real fixes validated). All exit-dependent metrics from the Legacy Engine are frozen/obsolete unless explicitly replayed under v2 — this includes the entire breach-classifier line (RQ-51, RQ-64-67), RQ-68/69, and the original ATR-buffer research, none of which are re-verified under v2 yet.

**Give-back Ratio promoted to a Tier A audit metric**, alongside Exit Efficiency — different populations, different questions: Exit Efficiency measures how much MFE *winners* surrender before their real exit; Give-back Ratio (`MFE − ExitPnL`, computed for trades that end up losers) measures how much MFE *losers* surrender before finishing as a loss. Directly actionable per the user's own stated trading weakness (cutting winners early, holding losers too long) — give-back is measuring the system's version of the same failure in reverse: holding a real winner long enough for it to become a loser.

**Research Integrity Rule #7 adopted — Metric Integrity Before Optimization**: a metric cannot be optimized until its measurement point is causally valid. Four independent cases this weekend alone: the original Freshness look-ahead bug (must use the PRIOR day's row), the target-ratchet lookahead (must use the prior close, not today's), the trigger-anchored return artifact (anchor must be at the actual measurement point, not a later one), and the return/day averaging artifact (portfolio capital-days, not a mean of per-trade ratios). (Numbered #7 to continue this project's existing Rule #6 sequence, not restart numbering.)

**Standing workflow rule adopted — inspect before trusting**: every surprising aggregate finding requires at least 3 manually inspected real trade examples (tickers, dates, actual values) before being promoted or rejected — not after being challenged on it. This caught the IEX gap, the `high_252` degenerate-target bug, the hand-rolled ZigZag alternation bug, the target-ratchet lookahead, and the return/day averaging artifact — five real catches from one weekend, all from checking examples rather than trusting an aggregate table on its own.

**Sequencing, agreed with one modification**: Phase A (execution semantics: touch stop + touch target + prior-close ratchet + 0.5% slippage) is frozen, do not revisit. Phase B (working, not-final exit baseline: ZigZag target + swing-low trail) is locked for now. Phase C (spot-check EMA34=2 vs 9, then Freshness≤0.40, on the Phase B baseline) comes *before* partial exits specifically to avoid replaying EMA34/Freshness twice if partial exits turn out to need their own exit architecture. Phase D (MAX_HOLD_DAYS and ATR buffer, both mechanically coupled to whichever exit is in place, retuned specifically for Phase B) follows. Partial-exit design (RQ-72) comes last in this ordering, once the rest of the architecture is settled once, not before.

**ATR buffer — burden of proof flipped, based on evidence already in hand**: per direct user instruction, ATR-buffer width is being treated as a risk/position-sizing decision, not a pure statistical one — "this is something I decide my position and risk on, not something I can change dynamically." Reframed: ATR1 (the current 1.0× buffer) must now prove itself against ATR0 (structural low only, no cushion), not the other way around. Every finding so far is one-sided against ATR1: only ~1.5% of trades ever differ between the two buffers at all; 15 of those 16 differing trades still ended up losers anyway (the buffer just delayed the loss); Recovery-After-Stop ≈0%; zero interaction across volatility regimes, including high-vol where a normalization role should show up if it existed; seat-based capital efficiency favors ATR0; and the touch-execution fix itself already recovered most of the drawdown improvement previously (wrongly) credited partly to buffer width. **No positive evidence for ATR1 has surfaced in any test run this weekend.** One more specific, cheap check queued before fully closing this out: a distance-distribution audit — bucket trades by how much *extra* stop distance ATR1 actually adds (0-0.25% / 0.25-0.5% / 0.5-1% / >1%), then check whether the trades receiving the largest ATR-driven distance penalty are actually better for it. If not (expected), this closes the book: ATR1 isn't just unnecessary, it's a real, uncompensated position-size tax concentrated on the highest-risk trades.

## Phase C spot-check, part 1 — EMA34=2 vs EMA34≥9 (Common vs Delta) replayed on Execution Engine v2, and a real, understood driver found (2026-09-20)

Direct replay of RQ-52A's Test P1 comparison (2026-09-18, Legacy Engine) on the current v2 baseline (touch stop, ZigZag target, swing-low trail), same population split (`is_delta = ema34_rising10 < 9`):

| Engine | Common (EMA34≥9) | Delta (EMA34=2..8) |
|---|---|---|
| Legacy (close-based), full population | 60.7% win / **+0.995%** exp / +1.629% median | 61.7% win / **+1.255%** exp / +1.983% median |
| Execution Engine v2, full population | 65.9% win / **+2.040%** exp / +1.556% median | 67.3% win / **+1.008%** exp / +1.334% median |
| Execution Engine v2, Fresh≤0.40 | 67.4% win / +1.629% exp / +1.444% median, $13.13/day | 68.7% win / +1.063% exp / +1.355% median, $12.24/day |

**[Correction, caught by direct user pushback]** — the Fresh≤0.40 row above is NOT comparable to a Legacy Fresh≤0.40 baseline the way it's laid out; the Legacy rows shown are full-population only. The actual Legacy Fresh≤0.40 baseline is RQ-69's (this weekend, same population): **Common 66.2% win / +1.912% exp; Delta 60.9% win / +0.995% exp — Common already led Delta on expectancy on Fresh≤0.40 in the Legacy engine, by an even bigger margin than v2 shows.** There is no Fresh≤0.40 reversal at all; that comparison was a population mismatch on my part, not a real engine effect. The **full-population** comparison (both rows genuinely apples-to-apples) is the one real reversal: Delta legitimately beat Common on expectancy under Legacy, full population; Common now leads under v2, full population.

**Root cause traced directly, not assumed** — checked the win→loss flip rate (Legacy vs v2, exact ZigZag+swing-low-trail mechanism, full population) split by Common/Delta: Common 6.4%, Delta 5.9% (Delta's flip rate is *not* higher — the "Delta has more wick-through-stop-then-recover trades" hypothesis is directly disproven). Decomposed by exit reason instead:

| Exit bucket | Common share/avg | Delta share/avg |
|---|---|---|
| target (real, progressed trades) | 27.6% / +2.99% | 46.6% / **+3.56%** (Delta better) |
| stop (never really got going) | 11.9% / −4.04% | 12.8% / **−7.28%** (Delta worse) |
| max_hold_cap (drifted, unresolved) | 59.8% / +2.67% | 40.4% / **+0.61%** (Delta worse) |

**Delta's real winners are fine, even slightly better than Common's. The entire gap is concentrated in Delta's weak, non-progressing trades** (stop-outs and drifting max_hold_cap exits) — the same population RQ-68 already flagged under Legacy as Delta's "never-engage" group being meaningfully weaker than Common's (31.6% vs 40.3% win). Not a new problem — the corrected exit mechanism just measures that pre-existing weakness more honestly (touch-based stops capture real severity; the old close-based/ratchet mechanism smoothed it over less accurately for both groups, but Delta's thinner baseline margin means the same relative move costs it more in absolute terms).

**Verdict, unchanged from before but now on firmer ground**: not a reversal of the EMA34=2 decision. Uniqueness (entry-timing, engine-invariant), fragility (confirmed pre-entry/structural, engine-invariant), operational capacity, and the options-side freshness lift (separate, untouched exit mechanism) all still stand. Only the raw stock-side expectancy comparison is genuinely weaker under v2, and it's weaker for a well-understood, localized reason — Delta's already-known-weak subgroup, not its real winners.

## Phase C spot-check, part 2 — Freshness≤0.40 vs Extended on Execution Engine v2: real, but not a reversal of established wisdom (2026-09-20)

Same EMA34=2 population (Common+Delta combined), split by `fresh≤0.40` vs `fresh>0.40` (Extended) instead of by is_delta:

| Engine | Fresh≤0.40 | Fresh>0.40 (Extended) |
|---|---|---|
| Pure Legacy (close-stop + close-target), unmodified | 64.4% win / +1.596% exp / $17.25/day | 64.4% win / **+2.312%** exp / **$21.15**/day |
| Touch-stop only (target still close-based) | 62.7% win / +1.418% exp / $14.64/day | 63.6% win / **+2.260%** exp / **$21.06**/day |
| Execution Engine v2 (touch-stop + ZigZag target) | 67.9% win / +1.414% exp / $12.84/day | 63.5% win / **+2.376%** exp / **$20.13**/day |

**Extended already beat Fresh≤0.40 on expectancy and portfolio $/day in the original, untouched Legacy engine, for this exact EMA34=2 population — before any fix this weekend touched anything.** Ruled out the touch-stop fix as the cause directly (win→loss flip rate by freshness bucket: Fresh 1.7%, Extended 1.0% — real but far too small, ~18 vs ~6 trades, to explain a gap this size). The gap widens somewhat through each successive engine fix (0.72pp→0.84pp→0.96pp in expectancy terms) but did not originate from them.

**Traced back to the original source, not just asserted**: the documented Legacy-engine finding for this exact EMA34=2 population (line ~2714 above, `ema2_freshness_reaudit.py`, corrected for the look-ahead bug) already showed **swing was a near-wash between Fresh and Extended** (61.5% win/+1.056% exp vs 60.6%/+1.071% — essentially tied), while the real, strong Freshness signal was always on **options** (65.1%/+0.848% Fresh vs 52.9%/+0.395% Extended, a 12+ win-rate-point gap). **This is not a reversal of established wisdom — there was never a strong "Fresh beats Extended on swing" finding to reverse.** What's shown here is an extension of an already-known "swing barely cares about freshness" pattern, now showing a bit more separation in Extended's favor rather than a dead heat — not a genuine collapse of the Freshness signal. The real, load-bearing evidence for Freshness≤0.40 has always been the options leg, which uses a separate, untouched exit mechanism (day+1-open) — not yet re-verified this weekend, and the actual next open question, not "did we break Freshness."

## Governance decision — Primed Gate is canonical for research going forward; `detect_entry()`/Entry Gate is legacy-only (2026-09-20)

Re-ran `ema2_freshness_reaudit.py`'s Entry Gate leg (never recomputed correctly since the 2026-09-18 look-ahead fix) and found Extended beating Fresh on both swing and options — the opposite of Primed Gate's clean, reproduced result. Investigated, not dismissed: the trigger-anchoring in the options metric is legitimate (matches real trigger-based execution, not a bug — corrected after initially mis-calling it one, caught by direct user pushback). The real cause: **Entry Gate is a different estimator of the strategy population, not the executable one** — it requires `entry_signal()`/`checklist_pass()`'s close-based confirmation, which selects for days that already closed strong, so a forward-return calculation on that population partly re-counts the same day's own already-realized strength. Precise wording adopted (per critic correction — "biased" implies implementation error, this is a different population definition): **Entry Gate estimates performance for a hindsight-confirmed breakout subset, not the executable Primed strategy.**

**This reopened a bigger question**: `backtest.detect_entry()` — the entry mechanism used throughout this entire weekend's execution-engine rebuild (touch-based stop, ZigZag target, swing-low trail, give-back audit, both EMA34 and Freshness spot-checks) — is Entry-Gate-equivalent (close-based confirmation), not Primed-Gate-equivalent (the real, live mechanism: `base_filters_pass()` + an actual intraday trigger-band cross, matching `_passes_primed_checks()`). **Resolved with the critic**: yes, `detect_entry()` is deprecated for new performance claims — Primed Gate is canonical going forward. `detect_entry()`/Entry Gate is retained only for legacy comparisons and regression testing, not new research.

**Scope of what actually needs re-running, per the critic's decomposition — NOT everything**:

| Category | Examples | Re-run on Primed Gate? |
|---|---|---|
| Population-invariant (validates exit *logic*, not which trades exist) | Touch-based stop validation, ZigZag target reconstruction, swing-low trail mechanics, give-back audit, M1 look-ahead fix | **No** — these hold regardless of which population they're demonstrated on |
| Population-sensitive (strategy statistics) | Win rate, expectancy, profit factor, Fresh vs Extended, EMA34=2 vs 9 promotion metrics, capacity | **Yes** — depends directly on which trades exist |
| Structural findings (subgroup characterization) | Delta's weak subgroup exists / is "never-engage" behavior (high confidence, likely survives); exact stop-out/max-hold severity gap (spot-check magnitude only) | Spot-check, not full re-run |

**Why using Entry Gate this weekend wasn't itself a mistake**: this weekend's work was about execution mechanics (does touch-based stop/target behave correctly), deliberately holding entry fixed as a controlled baseline — changing the execution engine and the entry population simultaneously would have confounded attribution. The actual mistake would only be promoting those absolute metrics as production numbers without the Primed Gate rerun — which is exactly the caveat now attached.

**Recommended rerun order (dependency-ordered, not everything at once)**: P0 build the Primed Gate canonical trade list → P1 recompute baseline metrics (win rate/expectancy/profit factor/capacity) on it → P2 EMA34=2 vs EMA34≥9 comparison on the same Primed population → P3 Freshness audit → P4 spot-check the Delta subgroup decomposition's magnitude. Everything else inherits the already-validated execution logic.

**Standing note for every result produced between the exit-mechanism bug and this decision**: validated under the corrected execution engine, but still pending the canonical Primed Gate rerun for absolute numbers (win rate, expectancy, profit factor, freshness lift, EMA34 promotion metrics specifically) — not "everything is invalid," a narrower and more precise caveat than that.

**Architectural recommendation, not yet actioned**: formalize entry-model naming so this ambiguity can't recur — `base_filters_pass()` (candidate generation) → `primed_gate()` (entry eligibility) → `trigger_cross()` (execution) as the canonical chain, with `detect_entry()` renamed/wrapped as an explicit `detect_entry_legacy()` adapter rather than something that can be accidentally reached for in new research code.

## A real, pre-existing gap in Primed Gate's structural stop, found while building P0 — real, but not a P0 blocker (2026-09-20)

Before running the full Primed Gate population, inspecting real examples first (per this session's standing rule) surfaced repeated same-ticker re-entries into one continuing move (GRANULES fired "fresh" entries on 7 separate dates across 6 weeks, each recomputing `structural_low` over a 20-day lookback that reaches back to before the whole move started, producing 15-29% initial risk vs this project's normal 7-12% range). **Verified this is not new** — the identical, already-cited "established, reproduced cleanly" Primed Gate numbers (`ema2_freshness_reaudit.py`'s `primed_gate()`, 65.1%/61.5%) share the same lack of re-entry tracking. On a 10-ticker sample, 49% of all Primed Gate fires already exceed 15% risk (median 14.83%). Confirmed as a live-relevant gap too, not backtest-only — `monitor_positions.py` computes real position stops with the identical formula; `extension_days` exists as an informational dashboard flag but is not a hard filter.

**Critic verdict, adopted**: real (7/10 severity) but explicitly not a P0 blocker. Key distinction clarified — this conflates two separate research questions: **RQ-A (trade population)** — when does a breakout count as a genuinely new opportunity — and **RQ-B (stop construction)** — given an accepted entry, where should the initial stop live. The stop math itself isn't wrong; a 20-day structural low is computed exactly as specified, it's just answering "where did the whole breakout start" rather than "where should a late re-entry actually risk against."

**Explicit caution on the 49% figure — do not trust yet**: it measures all *qualifying* Primed fires, not *executed* trades — a real trader would very plausibly take only the first fire in a continuing move and skip/ignore the rest, meaning the executed-trade population could look materially different from the raw-fires population. A large stop on a repeat entry also isn't necessarily a simulation bug — it may correctly describe "this isn't an attractive trade," not "this trade is mis-simulated." **Three diagnostics queued before drawing conclusions**: (1) risk% vs `extension_days` — do wide stops only appear after long extensions; (2) risk% vs first-breakout/repeat-breakout label — quantify how much of the 49% is driven by re-entries specifically; (3) risk% distribution restricted to genuinely executed live trades, if that history exists.

**Fix options scored, none adopted yet**: cooldown-after-exit (3/10, measures time not market structure, would skip legitimate second setups after a real pullback); gate on `extension_days` (8/10, already computed, already live, a candidate filter not a stop fix); recompute `structural_low` from the latest real pullback/swing low instead of a fixed 20-day window (9.5/10, most principled, but unproven — needs testing without introducing lookahead or excessive stop-outs before replacing anything); "breakout lineage" campaigns (a ticker's breakout gets a first/continuation/late-extension stage label, ends on structure loss/deep pullback/fresh consolidation) — proposed as the richer, eventual replacement for `extension_days`.

**Sequencing, agreed**: P0 (build the canonical Primed Gate trade list) proceeds unchanged — its job is reproducing the trade population as currently defined, not redesigning risk logic. P1 (baseline metrics) follows. **RQ-73A — Breakout Lineage & Structural Stop Anchoring** spun off as its own, independent research item (first/repeat-breakout labeling, risk% distribution by label, structural-stop alternatives tested only after the problem is properly isolated) — does not block P0/P1, and does not retroactively invalidate this weekend's execution-engine work (touch-based stop, ZigZag target, give-back audit, swing-low trail, M1 fix — those validate exit *behavior*, independent of this entry-population question). What it *does* potentially affect once resolved: capacity, average risk-per-trade, win rate, expectancy, and position-sizing research specifically, since those depend directly on initial stop distance.

**RQ-73A repeat-entry hypothesis: rejected directly, on the full population, not just the small sample.** First breakouts (`extension_days=0`, genuinely fresh) already show 60.6% exceeding 15% risk (median 16.69%) — barely below repeats' 68.9% (median 18.26%), and only 28% of all fires are repeats to begin with. Removing repeat entries does not fix the wide-risk phenomenon; it's something more fundamental than breakout-lineage tracking (plausibly the fixed 20-day `structural_low` window vs. a stock's actual, variable-length base structure) — parked as RQ-73A's remaining open question, not pursued further right now.

**SL calculation independently verified correct**: 18 real Primed Gate trades (mixed across high-risk >18%, normal 7-12%, and `extension_days=0` cases), recomputed entirely from scratch (not reusing `current_stop_level()`) — trigger, 20-day structural low, ATR, buffer, final risk% all matched the code's output exactly on every sample. Wide initial risk is a real property of the current stop definition on Primed Gate, not a calculation bug. Closes the audit cleanly: safe to proceed with the actual experiment.

## P0/P1 baseline, and New SL / New Target / Trail-only isolated one at a time on the real Primed Gate population (2026-09-20)

Canonical Primed Gate trade list (`base_filters_pass()` + real intraday trigger cross, `entry_price=trigger`, EMA34=2 capturing both Common/Delta), full 500-ticker universe, n=7,903 (vs. ~1,000-1,700 under the deprecated Entry-Gate/`detect_entry()` population all weekend — confirms the expected scale difference). Then tested New SL and New Target as isolated, independent changes (not just combined), since the user explicitly wants to track these as two clearly separable things going forward — SL is considered settled (ATR buffer aside, a separate future question), target is expected to keep evolving:

| Variant (Fresh≤0.40) | Win | Exp | Median | Portfolio $/day |
|---|---|---|---|---|
| **Legacy (original baseline)** | 63.7% | +1.451% | +2.110% | **$12.36** |
| New SL only (touch stop + slippage, target/trail unchanged) | 63.1% | +1.315% | +2.064% | $11.33 |
| New Target only (ZigZag + swing-low trail, stop unchanged) | 71.4% | +0.996% | +1.437% | $10.51 |
| Trail legacy (no target, close-stop, SMA21 trail) | 56.2% | +1.780% | +1.158% | $10.92 |
| Trail new (no target, touch-stop, swing-low trail) | 56.4% | +1.570% | +1.199% | $9.81 |
| Combined (New SL + New Target, = P0/P1 baseline) | 71.3% | +0.902% | +1.435% | $9.65 |

## ATR buffer distance-distribution audit — closes the ATR question, confirms RQ-69 rather than reversing it (2026-09-20)

Per the user's prioritization (settle `MAX_HOLD_DAYS`/ATR before continuing to iterate Target, since those "settle once and for all" while Target won't), ran the one remaining queued ATR test from Update 71: bucket trades by how much extra stop distance the 1.0x ATR buffer adds (as % of entry price — this is fixed at 1.0x always, so the bucket is really a volatility-regime split, not different buffer multiples), then check whether the trades paying the largest ATR-driven distance penalty are actually better for it. Built on the canonical Primed Gate population (rq93/94's mechanism — touch-based stop, ZigZag target, swing-low trail), n=7,922 full / 4,858 Fresh≤0.40, comparing ATR0 (structural_low only) vs ATR1 (structural_low − 1.0×atr14, current prod default).

**First pass (raw %-return) looked like a reversal of RQ-69's "no benefit" verdict** — ATR1 showed +0.089pp/trade average edge, win rate 66.6% vs 66.1%. Three real trades hand-verified across the distance distribution (AXISBANK, KAYNES, GALLANTT) confirmed the mechanism itself is bug-free — day-by-day stop levels, hit conditions, and exit prices all reconstructed by hand exactly matched the worker's output.

**But the full breakdown kills the reversal.** 90.9% of trades never even reach ATR0's tighter stop — buffer choice is irrelevant to them, but they still pay for it in position size (see below). Of the 9.1% that do reach it: 46% stop out the same day regardless (pure stop-level/slippage noise, not a real effect). The remaining 4.9% of the whole population is where it actually matters, and it splits almost evenly both ways:
- **2.7% of trades (212) benefit** from the extra room — avg +6.43pp better.
- **2.2% of trades (178) get hurt** — price just kept bleeding with the extra room, avg **-2.63pp worse**. This losing-side failure mode hadn't been surfaced before.
- Net: +0.172pp/trade from the winners of this split, -0.059pp/trade cost from the losers — nets to the thin +0.089pp headline. This is the *same* "two small offsetting effects roughly cancel" pattern RQ-69 found on the old Entry-Gate population — a confirmation, not a new finding, just netting slightly positive here instead of ~zero.

**Capital-efficiency-adjusted, ATR0 wins outright.** ATR1's avg initial risk is 18.43% vs ATR0's 15.16% (1.22x wider on Full; 1.255x on Fresh≤0.40) — meaning ~19-25% smaller position size for the same rupee risk, on every trade, permanently. R-multiple (pnl% ÷ risk%, the correct fixed-risk-sizing comparison): **ATR0 = 0.0619R avg vs ATR1 = 0.0536R avg on Full; 0.0654R vs 0.0558R on Fresh≤0.40 — ATR0 wins both.** The raw +0.089pp comparison only looked good because it ignored that ATR1 trades carry proportionally more risk to get there.

**Two structural questions answered, one proven not just observed**: (1) *Can ATR1 ever cut a genuine winner?* No — provably. `stop_level_atr1 ≤ stop_level_atr0` on every single day by construction (same buffer subtracted throughout, no exceptions), so any trade that never touches ATR0's stop mathematically cannot touch ATR1's either. Confirmed empirically too — all 5,240 ATR0 winners are byte-identical under ATR1. (2) *Does volatility predict which trades benefit vs get hurt, enabling a selective buffer?* No — divergence rate by ATR% bucket is flat (3.8%, 4.4%, 2.9%, 4.1%, 3.1%), no monotonic relationship. Volatility bucket doesn't concentrate the benefit; a volatility-gated buffer wouldn't improve this trade-off.

**Verdict: ATR0 (structural low only, no buffer) stands as the settled baseline**, confirmed on both Full and Fresh≤0.40. Not sent to critic — re-confirms RQ-69's prior call rather than overturning it. ATR question closed; proceeding to `MAX_HOLD_DAYS` re-tuning next.

## MAX_HOLD_DAYS sweep — plateau-shape puzzle resolved by isolating entry population (2026-09-20)

Swept N∈{5,10,15,20,25,30,45} on the settled Primed Gate mechanism (ATR0, ZigZag target, swing-low trail). First attempt (single 45-day simulation, bucketed post-hoc per candidate N) had a real methodological bug, caught before trusting it: a longer simulation blocks a ticker's one-position-at-a-time slot for the full 45 days regardless of which N is being evaluated, silently dropping re-entries a shorter cap would have freed up sooner (caught directly on NMDC: the 45-day run skips 2022-03-25 and 2022-04-01 entries the N=15 baseline takes, because the prior trade is artificially held open past them). Rebuilt as 7 fully independent simulations, sanity-checked against the existing rq93 canonical population at N=15 (entry dates matched exactly).

Result: win/exp/median climb steadily with no plateau anywhere in 5-45 days (win 66.2%→69.8%, exp +0.890%→+1.007%), while portfolio-%/day falls monotonically favoring shorter holds (0.092→0.053) — a different shape from the original 2026-09-14 decision, which found a clear plateau by day 20 and picked 15 as a cheap trade-off inside the user's stated 2-3-week practical hold ceiling.

**User's hypothesis, tested directly**: is this because Entry Gate (`detect_entry()`, close-confirmed) is a fundamentally different, pre-filtered population than Primed Gate (raw intraday breach)? Isolation test — identical exit stack held fixed (ATR0, ZigZag, swing-low trail), only entry swapped back to `detect_entry()`/breakout_cont-only. **Confirmed cleanly**: Entry Gate reproduces the original 2026-09-14 plateau almost exactly (win rate flat 70.1%/70.1%/70.2% across days 20-30, exp barely moves 2.427%/2.502%/2.505%), while Primed Gate keeps climbing throughout the same range under the identical exit mechanism. The shape difference is driven entirely by entry population — Entry Gate only takes already-close-confirmed trades, so most of what's going to resolve already has by day 20; Primed Gate includes raw breaches (including weaker/failed setups) that take longer to wash out or occasionally come good — not by the touch-execution or ZigZag-target changes originally suspected.

**Practical upshot**: the 15-day ceiling's real cost, measured on the actual executable (Primed Gate) population, is larger than the 2026-09-14 estimate, which was made on a hindsight-biased population. User is not moving the ceiling regardless — a real, stated operational constraint (can't manage an open position past 2-3 weeks) independent of what the data show — so this doesn't change any action, but the mechanism is now understood rather than mysterious. Portfolio-%/day continues favoring shorter holds under both entry populations, but this assumes frictionless capital reinvestment (the same assumption that sank Fixed-R exits under the real capacity-constrained test) and remains unverified — deprioritized for now per user's call, since they aren't holding longer either way.

## Freshness=0.40 re-swept under the new mechanism — a real, unresolved problem (2026-09-20)

The 0.40 cutoff (adopted 2026-09-14) was explicitly logged at the time as "no natural knee anywhere... not a validated optimum, just a reasonable, moderately strict, defensible reference point," on the old exit mechanism (close-based stop/target, SMA21 trail) and a different entry population. Never re-swept since — this weekend's Phase C part 2 only checked the *direction* of Fresh-vs-Extended (held up, not reversed), not the threshold value itself.

Re-ran the full cumulative sweep on today's settled mechanism (ATR0, ZigZag target, swing-low trail, `MAX_HOLD_DAYS=15`), full Primed Gate population (n=7,920):

| Threshold | n | Win | Exp | Portfolio %/day |
|---|---|---|---|---|
| ≤0.20 | 2,993 | 72.2% | +0.670% | 0.088 |
| ≤0.30 | 4,064 | 70.7% | +0.704% | 0.087 |
| ≤0.40 (current) | 4,877 | 69.8% | +0.721% | 0.086 |
| ≤0.50 | 5,549 | 68.8% | +0.702% | 0.081 |
| ≤0.60 | 6,131 | 67.7% | +0.641% | 0.072 |
| ≤0.80 | 7,151 | 66.6% | +0.710% | 0.076 |
| No filter | 7,920 | 66.2% | +0.880% | 0.091 |

Win rate is still monotonic (freshness works as a rank signal, as always claimed). Expectancy and portfolio-%/day are not — they dip through the middle and no-filter beats every cumulative threshold including ≤0.40. Decile breakdown shows why: a real U-shape. Verified before trusting it — outlier concentration on the standout decile (top-10 share 26.5%, under the 40% danger line; excl.-top-10 expectancy still +1.79%), and whether it's just the already-known Delta-weak-subgroup showing through a correlated proxy (fresh↔is_delta correlation only -0.370, not the whole story) — **the U-shape persists within Common trades alone**: decile 9 (fresh 0.845-0.989, most "extended") = +2.73% exp / 0.212 portfolio-%/day, the single best cell in the table; decile 6 (fresh 0.50-0.61, right where the current 0.40 cutoff sits) = +0.07% exp / 0.006 portfolio-%/day, the worst. Checked R-multiple since decile 9 also carries much wider initial risk (27.05% avg vs decile 6's 16.76%) — survives risk-adjustment: 0.1045R vs 0.0111R, compressed from the raw gap but still real and still ordered the same way.

**New wrinkle, not yet reconciled**: correlation(fresh, initial_risk_pct) within Common = 0.696 — very strong. Looks entangled with the RQ-73A structural-stop-width issue (parked, unresolved, from earlier the same day) rather than an independent signal — possibly "freshness" and "how wide the 20-day structural stop ended up" are two views of the same underlying "how extended is this setup" property, not two separate findings.

**Tension resolved, not just observed**: the standing assumption was "fresher = better," implying a monotonic relationship — so a U-shape looked like an anomaly demanding a missing filter. Checked the actual formula: `freshness = 0.5×RSI14_percentile + 0.5×20-day-momentum_percentile` (`live_checkpoint.py`'s `_freshness_score()`) — "less fresh" literally means higher RSI and higher recent momentum, i.e. an emphatic, already-confirmed move, not a weak one. "Fresher = better" is a mean-reversion-style prior (get in before it's overbought); but momentum persistence is an equally real, competing edge (a stock already showing strong RSI/momentum at breakout is higher-conviction, not stale). Both are legitimate and point opposite directions on the same one-dimensional metric — which is exactly why the shape isn't monotonic: crisp fresh breakouts win one way, confirmed strong-momentum trades win another way, and the muddled middle (neither clean nor confirmed) is genuinely the weakest population, not noise.

**Tested the direct "logic around" implication — a two-sided filter (keep both tails, cut the middle) instead of a one-sided cutoff:**

| Variant | n | Win | Exp | Portfolio %/day |
|---|---|---|---|---|
| Current: Fresh≤0.40 (one-sided) | 4,877 | 69.8% | +0.721% | 0.086 |
| No filter | 7,920 | 66.2% | +0.880% | 0.091 |
| **Two-sided: Fresh≤0.20 OR ≥0.80** | 3,762 | **70.3%** | **+1.034%** | **0.121** |
| Two-sided: Fresh≤0.30 OR ≥0.80 | 4,833 | 69.4% | +0.982% | 0.112 |
| Extended-only: Fresh≥0.80 | 769 | 62.6% | +2.452% | 0.197 |
| Extended-only: Fresh≥0.70 | 1,250 | 61.5% | +1.970% | 0.162 |

**Retracted immediately after — a real gap, caught directly**: a stricter filter mechanically changes the trade population size, so per-trade and per-deployed-day metrics improving as a filter tightens isn't automatically a real edge. Checked total realized output (`sum(pnl_pct)` across the whole test period, unconstrained by capacity) instead:

| Variant | n | Exp/trade | Portfolio %/day | Total pnl%-sum |
|---|---|---|---|---|
| Current: Fresh≤0.40 | 4,877 | +0.721% | 0.086 | 3,516 |
| No filter | 7,920 | +0.879% | 0.091 | **6,965** |
| Two-sided: ≤0.20 OR ≥0.80 | 3,762 | +1.034% | 0.121 | 3,890 |
| Extended-only: ≥0.80 | 769 | +2.452% | 0.197 | 1,885 |

No-filter produces almost double the total output of the "better-looking" two-sided filter, purely from trade count; extended-only (best per-trade number) produces the *least* total output of all four — too few qualifying setups to compound through. Per-trade and per-deployed-day metrics improve as the filter tightens; total output collapses as it tightens — the exact same throughput trap as the MAX_HOLD_DAYS question above, resting on the same unverified assumption (capital freed by skipping a trade gets redeployed into something equally good elsewhere) that sank Fixed-R exits once actually tested with a real capacity constraint.

**Honest state**: the U-shape and its RSI/momentum mechanism are real and hold up (outlier-checked, subgroup-decomposed, risk-adjusted). The two-sided-filter *fix* is not yet established — it's an unresolved per-trade-quality-vs-total-output trade-off, needing the same deterministic capacity-constrained methodology as everything else flagged today before promotion either way.

## Critic's control-flow verdict on Update 75, and P0 — the primary new-SL/new-target experiment, full battery (2026-09-20)

Critic's response to Update 75: close several loops and prune the research tree aggressively rather than let Freshness become another open-ended thread. Verdict, item by item — Primed Gate population, `detect_entry()` deprecation, initial SL arithmetic, ATR0 vs ATR1, repeat-entry hypothesis: all **closed**, no further work. `extension_days` as a freshness control: insufficient, parked. 20-day structural-low question (RQ-73A): stays parked — a strategy-design question, not a correctness one, and shouldn't be resolved before seeing how the new SL behaves in practice. MAX_HOLD_DAYS: mechanism explained (entry-population driven), optimization deferred — 15 stays as the operational ceiling regardless of what the unconstrained curve shows. Freshness U-shape: real and worth recording, but the two-sided-filter fix is unproven and explicitly should NOT be chased into a capacity test right now — doing so now would be "optimizing entry filtering and holding-period throughput before seeing how the new SL and target actually work," exactly the control-flow drift being guarded against. The 0.696 fresh↔initial-risk correlation: a dependency to watch, not yet enough to merge RQ-73A and the Freshness thread into one question — critic's reasoning: the new SL experiment is a natural bridge, since if the U-shape survives a substantially different SL, that's evidence freshness is independent; if it disappears, much of the "freshness effect" was actually a stop-construction artifact.

**One prerequisite before the primary experiment**: same minimal standard as the SL check — a few real trades, manually reconstruct the new ZigZag target, confirm it's not a research project, just a correctness check. Done: 3 real NMDC trades (2022-04-01, 2023-08-01, 2024-04-10). Two produced a target — both confirmed as genuine local price peaks strictly prior to entry (printed the surrounding price window, target date's High is a real local max, no higher High exists between target date and entry), entry day itself correctly excluded from the lookback. The third correctly returned no target — confirmed the entire 300-day lookback window's max High (41.90) sits below entry price (42.11), a genuine "making a fresh high, nothing above to target" case, not a bug. Target computation passes the correctness check same as SL did.

**P0 result — full battery, per critic's exact list**, on the settled mechanism (ATR0, ZigZag target, swing-low trail K=2, `MAX_HOLD_DAYS=15`), Primed Gate population:

| | Full (n=7,920) | Fresh≤0.40 (n=4,877) |
|---|---|---|
| Win rate | 66.2% | 69.8% |
| Expectancy | +0.879% | +0.721% |
| Median | +1.279% | +1.380% |
| Avg / median days held | 9.6 / 15.0 | 8.4 / 9.0 |
| R-multiple (mean/median) | 0.0613 / 0.0928 | 0.0654 / 0.1183 |
| Initial risk (mean/median) | 15.16% / 13.85% | 12.30% / 11.65% |
| Portfolio %/day (descriptive only, not a promotion criterion per critic) | 0.0912 | 0.0855 |

**Exit-reason mix**: max_hold_cap 49.3%, target 40.9%, stop 9.1%, climax 0.2% (full pop). 67.5% of trades have a target at all (32.5% are making fresh highs with nothing above to aim at); of those with a target, 60.5% hit it. The no-target subset resolves almost entirely via max_hold_cap (85.5%) or stop (13.2%).

**Trail behavior**: engages (crosses +8% from entry) in 18.5% of trades; actually binding (overriding the base structural stop) in just 2.6% of all trades.

**Give-back (losers)**: 60.5% touched ≥2% favorable move before finishing as a loss, avg give-back 9.98pp — consistent with the earlier give-back audit (58-62%/11.35-12.48pp), slightly better under this mechanism.

**Exit efficiency (winners)**: 53.3% of peak MFE captured on average — notably lower than the legacy mechanism's ~72-73% (RQ-68). Mechanically explained: max_hold_cap is now 49.3% of all exits (a pure calendar cutoff, zero profit protection) vs. the legacy mechanism's SMA21-trail-dominated mix — the same gap partial-exit design was meant to address, now quantified precisely on the real mechanism.

**Stop-out behavior, split by type** (critic's remaining explicit ask): stops aren't a uniform bucket. Trail-floor stops (28.5% of all stops, full pop) are winners on average (**+4.64%**) — the trail only fires after the trade already moved up ≥8%, so hitting it means giving back some profit, not losing money. Base-structural-stop exits (71.5% of stops) are the real losers (avg **-12.48%**). Realized loss on a stop averages only 0.67x (full) / 0.85x (Fresh≤0.40) of the planned initial risk — pulled toward zero/positive by the trail-floor subset.

**This closes out every item on critic's P0 list.** Next per critic's stated sequencing: P1 partial-exit design, now that the all-or-nothing exit system's behavior is fully characterized rather than assumed.

## P1 — Partial-exit design, run as an observation only, not a candidate for adoption (2026-09-20)

**Explicit framing, stated by the user before running this**: "I don't really like partial exit trades. More operational headache, let's run it but I will keep it as an observation only." Not being adopted regardless of result — recorded here so this doesn't get mistaken for a pending decision later.

Design: bank 50% of the position at the first Close ≥ entry×`TRAIL_ENGAGE_PCT` (the same +8% milestone the trail already uses), move the remaining 50%'s stop to breakeven at that moment, let the remainder ride under the existing target/stop/trail/max_hold_cap logic unchanged. One variant, not a sweep. Same trade population in both arms (no confound, verified: the 81.4% of trades that never reach +8% are byte-identical between baseline and blended).

| | Full (n=7,966) | Fresh≤0.40 (n=4,879) |
|---|---|---|
| Baseline (100%, all-or-nothing) | 64.4% win / +0.739% exp / +1.098% median | 68.8% / +0.632% / +1.297% |
| Partial-exit (blended 50/50) | **67.1% / +0.920% / +1.455%** | **70.2% / +0.818% / +1.493%** |

The entire improvement comes from the 18.6% of trades that ever reach +8% — verified the other 81.4% are mathematically unchanged. Within the triggered subset, the blended result hits 100% win rate by construction: once profit is banked and the remainder's stop moves to breakeven, the worst-case outcome on that half is roughly flat, structurally removing the "give it all back to a loss" scenario quantified in P0's give-back audit (60.5% of losers had touched ≥2% profit first). Real, but expected/definitional — this is the known mechanical benefit of the technique (protect earned gains), not a surprising discovery. No further work planned on this thread per the user's operational-overhead call.

## A bigger, unexpected finding surfaced from the same data: flat exit at +8% beats both riding AND the partial-exit design (2026-09-20)

User's direct follow-up question to the partial-exit result: "what if I would have booked flat 8% close always?" — i.e., take the entire position off (100%, not 50%) the first time it closes at `entry×TRAIL_ENGAGE_PCT`, no partial/tranche management at all. Derived directly from the existing partial-exit data (no new simulation): for the 18.6% of trades that ever reach +8%, this variant books the trigger-day close; the untriggered 81.4% are unchanged.

| | Full (n=7,966) | Fresh≤0.40 (n=4,879) |
|---|---|---|
| Baseline (ride to natural exit) | 64.4% / +0.739% / total 5,885 | 68.8% / +0.632% / total 3,084 |
| Partial 50/50 blended | 67.1% / +0.920% / total 7,330 | 70.2% / +0.818% / total 3,991 |
| **Flat: 100% off at first +8%** | **67.1% / +1.102% / total 8,775** | **70.2% / +1.004% / total 4,899** |

Beats both other variants on expectancy and total output, same population, no confound. On the 18.6% (14.6% Fresh≤0.40) of trades that reach +8%, riding further **loses 1.95pp/trade on average** (2.55pp Fresh≤0.40) versus taking it flat there — the current target/trail/max-hold mechanism actively costs money on average once a trade has already proven itself.

**Verified this isn't outlier-driven before trusting it**: median delta (ride − flat) = -1.89pp, matching the mean's story; worst-10 trades account for only 3.9% of the total negative effect — a broad, majority pattern (60.7% of triggered trades lose from riding), not a tail artifact.

**Mechanism, by exit reason, on the triggered subset**:
- **Riding loses (60.7% of triggered)**: 39.5% are genuine stop-outs — real reversals giving back the whole move, the same pattern the give-back audit already quantified. 36.3% are, surprisingly, `target` exits that *still* lose to flat-8% — a real pricing quirk: the ZigZag target only needs to sit above entry price, not above the +8% level, so it can be below +8%; if the trade gaps past both levels on the same day, booking at the exact target price leaves money on the table versus what a flat exit at that day's actual close would have captured.
- **Riding wins (35.4% of triggered)**: 71.1% are max_hold_cap (slow, steady grinders that kept climbing the full 15 days) and 23.6% are genuine target hits *above* +8% — real, bigger structural moves that justify holding.

**Why this is more significant than the partial-exit result, and unlike it, not ruled out on complexity**: partial exits require managing two tranches (a real operational cost the user explicitly rejected). This is a single, flat exit rule — same operational shape as the existing target mechanism, just triggered earlier and unconditionally. It directly challenges the "let winners run" assumption built into the whole target/trail/max-hold design for this subset of trades. Not yet promoted — needs the same standard as everything else today (real-example inspection of a few "riding lost" and "riding won" cases, and a check for whether this holds at other flat-exit levels near +8%, not just this one point) before treating it as more than a strong candidate. Sent to critic as a genuinely new, unexpected finding, not a confirmatory one.

**Sent to critic (Update 75)** with this corrected framing — the U-shape mechanism as a trustworthy finding, the two-sided filter as a promising but unvalidated candidate pending the capacity check.

## Update 76 exchange — the +8% flat exit is downgraded, a design-principle debate resolves the trail-vs-flat-exit inconsistency, and stall exits get reframed as the project's central unresolved question (2026-09-20)

Critic's first response to Update 76 promoted the flat +8% exit to top research priority (three reasons: same population/no filtering artifact, median agrees with mean so it isn't a few spectacular give-backs, and 60.7% of triggered trades is a majority effect, not noise) and proposed a verification ladder — Stage A: manually inspect ~20 trades split across ride-loses-badly/slightly and ride-wins-moderately/hugely; Stage B: sweep nearby flat-exit levels (6/7/8/9/10%) to check whether the shape is a real plateau or a coincidence tied to exactly +8%. Also flagged a genuine, separate design inconsistency: the ZigZag target only needs to sit above entry price, not above the trail-engage threshold, so a trade can have its target below +8% — meaning the system can book an exit at +5.5% via "target" even after momentum has already closed above +8%, an ordering that doesn't match the intended semantics. Proposed invariant: "a structural target below the trail-engage threshold is not a valid structural target" — pending a one-line audit (what % of target exits have a target below +8%; ignore if ~1%, real issue if ~25%).

**User pushback, immediately fatal to the "promote +8%" framing**: "if only ever in the history 18% trades are gonna touch 8%, why should I be tuning my strategy for that? That is clearly an outlier." Critic agreed fully and reversed: the entire +0.363pp aggregate improvement comes from redesigning exit behavior around one-fifth of the trade population — a high bar that isn't met just because the effect is statistically real. Reframed the finding's actual value: not "8% is the right exit level" but a diagnostic — "trades that become meaningful winners often give back gains after reaching +8%," pointing at a broader, more valuable question ("what characterizes winners that have already done enough vs. winners that keep trending"). Recommended a cheap descriptive breakdown instead of a threshold sweep: split the 18.6% triggered subset into stop/trail winners, max-hold winners, max-hold losers, target-exits-below-+8%, target-exits-above-+8%, to understand the give-back mechanism without proposing a new rule. **+8% flat exit removed from the active roadmap, kept only as a documented observation.**

**User's sharper follow-up, catching a self-inconsistency**: the existing trail (engages in 18.5% of trades, per P0) was never subjected to the same "too small a population to justify" objection that just killed the flat +8% exit — and the trail *actually binds* (overrides the base stop) in only 2.6% of all trades, an even smaller footprint than the rejected +8% rule. Critic agreed this was valid, distinguished two categories of rule: core/execution rules (need to improve the strategy broadly to justify their complexity) vs. safety/exceptional rules (an airbag analogy — rare activation is fine if it prevents a specific catastrophic failure mode cheaply) — but conceded the trail has never actually been proven to be earning its keep; its 18.5%/2.6% footprint is consistent with either "essential rare protection" or "decorative trim; we don't yet know which." Proposed a trail-on-vs-trail-off contribution experiment (same entry/target/stop/max-hold, only the trail toggled) to measure it directly, not yet run.

**User's own design principle, stated directly**: "I would like to keep it like this, a filtering rule/bad-trade recognizing, I like if it works on a subset, because that is what I want, as less bad trades as possible — but random improvements which only work for 5% population is complexity." Critic formalized this into a standing project rule, refined one step further: the real dividing line isn't subset-size, it's whether the subset is **identifiable before entry**. Filtering/bad-trade-recognition rules (Freshness, Fragility, Delta/Common split) are allowed to target a small, niche subset, because their job is deciding whether to take a trade at all, using only pre-entry information — a subset that disproportionately removes losers is exactly the point, however small. Execution/exit-management rules (the trail, partial exits, a flat +8% exit, stall exits) act only after capital is already committed, using post-entry information ("+8% reached" is not knowable until the trade is already running) — these must justify their complexity by a broad contribution across the strategy, not by improving a small post-entry subset in isolation, since they add ongoing complexity to every single trade for a payoff realized on only a few of them.

**Standing design principle, adopted**: *Filtering rules may target a subset, because their job is pre-entry trade selection using only information available before commitment. Execution/exit rules must justify their existence by contribution to the whole strategy, because they add complexity to every trade for a payoff realized on only some of them.* Applied to the current queue: flat +8% exit — rejected (execution rule, small post-entry population, doesn't fit). Trail after +8% — audit pending (execution rule of unproven value, not yet rejected or confirmed). Freshness U-shape — worth pursuing (entry-side, pre-entry-identifiable). Structural-stop redesign — revisit only if it improves pre-entry trade selection or risk realism broadly. Stall exits — execution rule, re-test conditional on whether the new mechanism changes the old capital-constrained rejection.

**The central reframe — stall exits promoted from a queued item to the project's most important open question**: user reiterated the original framing directly ("we are not doing general swing, we are doing breakout momentum swing but we sit through things even in fakeouts and momentum stalls like regular swing and wait for recovery"). Critic's response: this is "the central unresolved research question of the entire project," and P0's own data supports it directly — 49.3% of ALL trades exit via `max_hold_cap`, and (from the loser breakdown) 78.3% of losing trades exit that way, averaging -5.22%. The dominant loser isn't a violent reversal (only 20.9% of losers are active stops, averaging a worse -11.83%) — it's "breakout never became momentum, and we watched it decay for two weeks." Distinguished two failure modes: Type A, fake breakout (momentum disappears almost immediately) vs. Type B, momentum stall (price just stops behaving like momentum — the larger population, and the one the current mechanism has no detector for at all).

**Explicit mandate, not to be violated**: this is now **RQ-77: Momentum Failure Recognition**, reframed away from "test stall exits" — no new rule is to be designed or invented ("do not invent Stall v4"). This project already built and validated three stall detectors pre-dating this weekend's engine rebuild (3-day-stall, Energy Stall, the Efficiency-trigger Wyckoff redefinition — the latter explicitly logged at the time as "a genuinely clean, robust result... and then died under capital constraints" once tested with a real capacity limit). The task is strictly diagnostic: reuse an existing detector as-is under the new canonical engine, and ask (1) when it would have first fired for each trade, (2) what P/L was at that moment for the 78.3% max-hold losers (damage avoided), (3) whether those trades would have recovered by day 15 anyway (false-exit risk), (4) how many eventual winners it would have incorrectly cut (opportunity cost). No portfolio/capacity simulation yet — that comes only after the diagnostic, and only if the detector still looks genuinely promising, per the explicit reminder that Efficiency Stall's earlier "clean, robust" per-trade result did not survive a real capacity-constrained test.

**Revised roadmap, in order**: P1 RQ-77 (Momentum Failure Recognition, diagnostic only) → P2 +8% sanity check (demoted from redesign to a small 20-chart-plus-nearby-sweep check on a benchmark, not a live candidate) → P3 target-below-trail-engage audit (one statistic) → P4 Freshness capacity simulation (parked) → P5 structural-stop redesign/RQ-73A (parked, most invasive, last).

## RQ-77 — Momentum Failure Recognition, diagnostic result: the reused stall detector doesn't fix this either (2026-09-20)

Reused the plain, already-validated 3-day-no-fresh-high stall (volume condition dropped, historically shown to add nothing) purely as an observer against the P0 canonical population — armed, tracked, and recorded, but never actually exiting a trade. Per critic's explicit mandate: no new rule invented, exact historical arm definition reused (`0.5×R`, `R = ATR_TRAIL_MULT(3.0) × atr14` — the literal old convention, in ATR terms, not translated through the new structural-low stop distance).

**Caught and fixed before trusting the result**: a first attempt mistakenly defined the arm threshold as `0.5 × initial_risk_pct` (the new mechanism's own stop-distance concept, averaging ~15%) instead of the historical `0.5 × 3×ATR14` (~9.8%, so an arm around ~4.9%) — putting the arm bar at ~7.5%, nearly as strict as the already-rejected +8% level. That version only fired on 9.6% of trades / 2.9% of max-hold losers, an obviously-too-conservative artifact of the wrong translation, not a real result. Corrected to the exact historical R definition before reporting anything.

**Result, on the corrected definition** (fires on 17.4% of all 7,920 trades):

Max-hold losers (n=2,094, avg -5.22%): the detector catches only **9.7%** of them (203 trades) — the other 90.3% never show a clean "made a high, then flatlined 3+ days" pattern; they're choppier, still ending as losers without ever tripping this specific detector. Where it does fire on this subgroup: 85.2% correct calls, avg **4.35pp of further damage avoided** (avg pnl at fire +1.16%, avg pnl at actual day-15 exit -3.19%) — genuinely useful when it triggers, just incomplete coverage.

Eventual winners (n=5,244): the detector fires on **21.4%** of them before their real, profitable exit — 95.7% of those firings were already positive (avg +6.87% at fire vs +8.34% at actual exit), so adopting it wouldn't turn a winner into a loser, but it would give up an average **1.47pp of upside**, mostly on slow max_hold_cap grinders (81.4% of this subgroup) that eventually worked out anyway — the same "slow grinder" pattern the +8%-flat-exit analysis already surfaced.

**Naive population-wide effect of adopting it as a live exit rule** (exit at the stall price whenever it fires, keep actual outcome otherwise): expectancy +0.879%→+0.835%, total output 6,965→6,614 — **a small net decline**, not an improvement, splitting almost exactly 50/50 between helping (46.7% of fires) and hurting (47.0%) on the trades it touches.

**Conclusion**: the reused, historically-validated stall detector does not fix the momentum-failure problem under the new mechanism either. It correctly identifies a real subset of failing trades early (genuine value when it fires), but coverage is incomplete (misses ~90% of max-hold losers) and the cost of cutting eventual winners short roughly offsets the benefit — the same "looks clean per-trade, doesn't clearly win in aggregate" shape that killed it historically under capital constraints, this time visible even before reaching that stage. Per critic's own stated mandate (only proceed to the deterministic capacity-constrained test if the diagnostic still looks genuinely promising), this does not warrant that next step. RQ-77 stays open as a real, unsolved question — the existing detector families (plain 3-day stall tested here; Energy Stall and the Efficiency-trigger Wyckoff redefinition not yet re-tested under this mechanism) don't close it, and no new detector has been invented per the explicit "don't build Stall v4" instruction.

## RQ-77 continued — the arming gate is a real structural blind spot for catching losers, and Efficiency trigger (unarmed) doesn't escape the underlying trade-off either (2026-09-20)

Direct user critique of the whole arm-then-detect convention: every stall detector arms only after the trade is already up a meaningful amount (0.5R ≈ +4.9%), which means these detectors can only ever catch *fading winners* — they are structurally blind to trades that go straight down, flat, or choppy-negative from day one, which is exactly the population that "hurts more." Verified directly before building anything new: of the plain 3-day stall's 1,891 "never fired" max-hold losers, **100% were net negative at exit, and 67.8% were already down ≥3%** — the +4.9% arm threshold was never remotely reachable for most of them. The blind spot is real and large, not a minor edge case.

**Efficiency trigger's own formula** (`|3-day net return| < 2.0% AND Volume3/Volume20 > 1.2`) has no dependency on cumulative P&L — it only reads a rolling 3-day window, so it's mechanically capable of firing on a flat or losing trade with no arm gate at all. Tested unarmed (checked from day 3 onward regardless of current P&L), also flagging, per the user's separate caution below, whether each entry's same-day close would *also* have confirmed as a valid close-based Entry Gate candidate (`detect_entry()`, not reimplemented).

**Result: removing the arm gate does fix the loser-blindness, but at a cost that roughly cancels the benefit.** Fires on 31.0% of all trades (vs the armed version's 17.4%). Catches ~45% of max-hold losers (vs 9.7% armed) with real damage avoided (~2.5-2.75pp). But it also now fires on 26.6% of all eventual winners before their real exit (vs 21.4% armed), catching them earlier (avg pnl at fire only 3.90% vs eventual 7.06%) for a bigger average opportunity cost (3.16pp vs 1.47pp armed). Naive population-wide adoption: expectancy +0.890%→+0.777%, total 7,063→6,164 — a **larger** net decline than the armed version's, not an improvement; fires split 46.8% help / 49.3% hurt, essentially a coin flip. **Conclusion: removing the arm gate doesn't escape the underlying tension, it just relocates the cost from "missed losers" to "clipped winners," and nets out slightly worse. Neither the armed nor unarmed version of this detector family solves RQ-77.**

## A bigger, unexpected finding surfaced along the way: same-day close-confirmation is a huge, early quality signal — but a near-identical intervention already failed once (2026-09-20)

While building the unarmed-Efficiency-trigger diagnostic, flagged each Primed Gate entry with whether that same day's close would *also* have confirmed as a valid close-based Entry Gate candidate (`detect_entry()` with the real regime gate, `require_regime=True` — not a bare `entry_signal()` check).

**Result: only 9.1% of all Primed Gate breaches would also close-confirm — and that 9.1% is a dramatically different, much stronger population**: 83.6% win / +3.318% expectancy, vs. 64.5% win / +0.648% for the 90.9% that wouldn't confirm. Known by end of the *same day* — far earlier than any multi-day signal tested in this whole RQ-77 thread.

**Reconciled the 9.1% figure against an already-established historical number before trusting it**: FINDINGS.md's original 2026-09-13 Entry-Gate-vs-Primed-Gate discovery documented ~1,600-1,646 `checklist_pass()`-confirmed trades out of ~10,764-14,225 raw breaches (~11.6-15.3%, ~13% midpoint) — meaningfully higher than today's 9.1%. Checked directly on a 30-ticker sample rather than assuming a bug: `entry_signal()` alone (no regime gate) gives 14.9% — squarely inside that historical range. Adding `detect_entry()`'s regime gate (`market_trending()`, `require_regime=True`) on top cuts it to 6.5% on that sample (9.1% on the full population). **Fully explained, not a bug**: the historical figure measured `checklist_pass()`/`breakout_continuation()` confirmation alone; today's number additionally requires the regime gate, which is what production `detect_entry()` always applies. Both numbers are legitimate, answering slightly different questions — 9.1% is the correct one for "would this fully replicate as a real Entry-Gate trade," which is what the quality-gap finding above is built on.

**A directly relevant historical precedent, caught before treating this as actionable**: this is not the first time a same-day confirmation-based quality gap has been found and quantified. The 2026-09-13 "Acceptance as an execution-state variable" test found an almost identical shape — a real quality gap between same-day "accepted" and "rejected" trades (accepted: 59.8% win/+1.48% median/+0.89% mean; rejected: 54.5%/+0.70%/-0.73% mean) — and then tested acting on it directly (tightening the stop specifically for the "rejected" group, leaving "accepted" trades alone). **That intervention was explicitly REJECTED**: it made the rejected group meaningfully worse (win rate 54.5%→42.1%, median +0.70%→-2.03%), because non-acceptance/non-confirmation is normal behavior even in trades that go on to become real winners — a tighter stop on that subgroup whipsaws out the ones that would have come back, converting recoverable trades into locked losses.

**Standing caution, not yet resolved**: knowing a subgroup is statistically worse does not mean intervening on that subgroup helps — the intervention itself can destroy exactly the trades within it that were going to work out, as already demonstrated once for a near-identical signal. Today's would_confirm finding is logged as a genuine, real, and now more sharply quantified observation (a stronger and cleaner version of the already-known pattern), **not yet treated as actionable** — any future test of intervening on the would_confirm=False group (tightening stops, cutting size, early exit) needs to reckon with this exact precedent first, not repeat it.

## P2/P3 — critic's Update-76 sanity ladder, completed (2026-09-20)

**P3 (target-below-trail-engage audit, one statistic)**: for `target`-exit trades, exit price equals the target price exactly (no slippage applied there), so `pnl_pct` for those rows *is* the target level relative to entry — no rerun needed. Result: **92.2% of all target exits (2,984 of 3,238) have a target below the +8% trail-engage threshold** (median target level: only +2.29% above entry). As a share of the whole population: 37.7% of ALL trades resolve via a target sitting below where the trail would even start protecting. This is far past critic's stated "25% = real architecture issue" bar — it's the dominant case, not an edge case. Confirms the design inconsistency flagged in Update 76 is structural, not marginal.

**P2, Stage B (nearby threshold sweep, 6/7/8/9/10%)**: extended the same real, unchanged baseline simulation to additionally record — purely as bookkeeping, never used to actually close a position early — the first day Close crosses each candidate level. This does NOT carry the MAX_HOLD_DAYS-style re-entry-population bug, since the real simulated position and its timing are completely unaffected by which levels are tracked.

| Level | Fires | Flat-exit win | Flat-exit exp | Flat-exit total |
|---|---|---|---|---|
| +6% | 27.2% | 68.06% | +1.1389% | 9,020 |
| +7% | 21.9% | 67.35% | +1.0979% | 8,695 |
| +8% | 18.5% | 67.11% | +1.1017% | 8,726 |
| +9% | 15.2% | 66.81% | +1.0803% | 8,556 |
| +10% | 12.7% | 66.64% | +1.0509% | 8,323 |

(Baseline for comparison: exp +0.8795%, total 6,965.) A broad, smooth plateau — all five levels beat baseline substantially, peaking gently at +6% and declining gradually to +10%, no single spike at exactly +8%. Passes critic's Stage-B robustness check cleanly — the +8% finding is not a coincidence tied to one threshold.

**P2, Stage A (real-example inspection, 4 of the requested ~20)**: pulled real OHLC data for one example per bucket rather than all 20 superficially.
- **CEMPRO (ride loses badly, delta -34.99pp)**: ZigZag target sat barely above entry (~0.3%) and was blown through the very next day (that day's High +38%) — exit booked at the exact target price (+0.39%) while the stock went on to run 50%+ over the following weeks. A vivid, real instance of the P3 design flaw, not just a statistic.
- **KPITTECH (ride loses slightly, delta -6.23pp)**: crossed +8% on day 1's close (+12.16%), then a slow multi-week grind down with a genuine mid-decline bounce (day 8, back to +14.95%) before stopping out at +5.92%. Reversal was not obvious in real time.
- **DIXON (ride wins moderately, delta +3.65pp)**: crossed +8% on day 12 (+8.36%), continued a genuine uptrend to the 15-day cap (+11.96%) — real "let it run" success, not decay.
- **TTML (ride wins hugely, delta +65.39pp)**: crossed +8% on day 1 (+9.69%), then an extraordinary near-vertical rally to +84% before settling at +75.08% at the cap.

**Pulled the remaining 16 (full 20, per follow-up request) — sharper conclusion than expected, the buckets split cleanly by cause, not just magnitude**:
- **Ride loses badly, 5/5 are `target` exits** (IRFC, MRPL, GALLANTT, UCOBANK, CEMPRO) — every single one blows through both target and +8% the same day, booking at the low target price while the stock keeps running. Not diffuse momentum failure — 100% the target-floor bug, mechanically, every time.
- **Ride loses slightly, mixed causes, the real give-back cases** (NH/stop, JWL/max_hold_cap, MAXHEALTH/stop, YESBANK/target-but-developed-over-17-days-not-instant, KPITTECH/stop) — genuine reversals/grinds, damage far smaller (-6pp range) than the target-bug bucket (-22 to -35pp).
- **Ride wins moderately, 5/5 `max_hold_cap`** (HEROMOTOCO, EXIDEIND, BHARATFORG, ABB, DIXON) — consistent slow-grinder category.
- **Ride wins hugely, 4/5 `max_hold_cap`, 1 `stop`** (NBCC, TATAPOWER, AWL, TTML ride to cap; IRFC-2024 peaks ~+68% then gives back to +54% before the trailing stop finally catches it) — even the biggest winners give back something, just not enough to matter.

**This means the target-floor fix isn't a marginal improvement — it would likely eliminate almost all of the catastrophic "riding loses badly" cases specifically**, since they're mechanically the same bug in this sample, not a diverse set of momentum-failure stories.

Both P2 stages and P3 complete. Sent to critic together (Update 78) with the RQ-77 conclusion from the prior section.

## Target-floor invariant implemented and rerun — critic's Update 78 verdict, closes the loop cleanly (2026-09-20)

Critic's response to Update 78: RQ-77 CLOSED (no viable detector found under the canonical mechanism, narrowly — "existing tested detectors do not provide sufficient evidence for replacing the current exit architecture," not "momentum-failure recognition is impossible"). would_confirm CLOSED AS OBSERVATION (keep as telemetry, don't turn into a rule — a near-identical intervention already failed once). Target-floor invariant promoted from "pending audit" to an actual minimal implementation fix, precise wording: *"Once the strategy contains a profit-protection mechanism that activates at +8%, a structural target below +8% cannot remain an unconditional exit target."* Implementation instruction, deliberately minimal: don't invent a new target formula — if the ZigZag target sits below the trail-engage threshold, it's simply non-actionable; the trade falls back to normal stop/max-hold/trail logic, exactly as if no target existed. Also reframed the whole flat-+8%-exit finding as a diagnostic artifact of this same bug, not evidence that +8% itself is a correct exit level — the earlier "riding loses" signal was partly the target-floor bug hiding inside it. P4/P5 stay parked — "we're about to make a load-bearing exit correction... it makes no sense to optimize entry selection against the old exit behavior and then redo it again."

**Implemented exactly as specified** (one line, in the scratchpad worker, mirroring what a real fix would look like in `resistance_target()`/`find_zigzag_target()`'s caller): after computing the ZigZag target, `if zz_target is not None and zz_target < entry_price * TRAIL_ENGAGE_PCT: zz_target = None`. Reran the full canonical P0 battery.

| | Before (rq99) | After (rq104, target-floor applied) |
|---|---|---|
| n | 7,920 | 6,270 |
| Win rate | 66.2% | 55.2% |
| Expectancy | +0.879% | +1.495% |
| Median | +1.279% | +1.041% |
| Avg days held | 9.6 | 13.8 |
| **Total pnl-sum** | **6,965** | **9,374** |
| R-multiple (mean) | 0.0613 | 0.1094 |
| Has target available | 67.5% | 17.9% |
| Trail ever engaged | 18.5% | 31.8% |
| Stopped via trail floor | 2.60% | 6.91% |
| Exit efficiency (winners) | 53.3% | 58.3% |
| Give-back (losers, touch≥2% / avg pp) | 60.5% / 9.98pp | 69.0% / 10.54pp |
| Exit mix (target/max_hold/stop) | 40.9% / 49.3% / 9.1% | 3.5% / 78.9% / 16.5% |

**Population-size caveat, flagged explicitly, not hidden**: n drops 21% (trades hold longer on average without an early target lock, reducing how many new entries fit each ticker's single-position slot over the same period — same dynamic as the MAX_HOLD_DAYS finding, verified sound methodology since this compares two fully independent simulations, not a single-run bucketing artifact like the first, flawed MAX_HOLD_DAYS attempt).

**Despite 21% fewer trades, total realized output is up 35%** — this is the load-bearing number, since it doesn't depend on the "more trades = better" assumption that tripped up several findings today (Freshness two-sided filter, the naive stall-adoption tests). Fewer trades, more total profit, a genuinely robust result.

**The trail gets used exactly as predicted**: engagement rate roughly doubles (18.5%→31.8%), trail-floor-binding stops nearly triple (2.60%→6.91%) — direct, quantitative confirmation that the target was previously preempting the trail from ever getting a chance to operate, exactly the CEMPRO mechanism. Exit efficiency for winners improves too (53.3%→58.3%) — the remaining winners are ones that genuinely developed, not ones artificially capped at a near-entry target.

**Real, acknowledged cost**: win rate drops meaningfully (66.2%→55.2%) and give-back gets slightly worse (60.5%→69.0% touch rate, 9.98→10.54pp avg) — expected, since far fewer trades now get a quick, locked-in small win via target (target-exit share collapses 40.9%→3.5%), so more trades ride further and are exposed to more reversal risk before resolving via stop or max_hold. This is the honest trade-off, not swept under the rug — the aggregate numbers (total output, R-multiple, trail utilization) say the correction is a genuine net improvement, not a free lunch.

**Target-floor invariant: adopted for the canonical research mechanism.** Sent to critic (Update 79) for the next read — per their own prescribed next step, the real question is now "what problem actually remains" once this correction is in place, not further target tuning.

## Two controlled checks critic asked for before full promotion, both done (2026-09-20)

Critic's read on Update 79: the target-floor correction itself is validated (target availability 67.5%→17.9%, trail engagement 18.5%→31.8%, trail-floor exits 2.60%→6.91%, winner MFE capture 53.3%→58.3% — "almost a textbook confirmation of the hypothesized mechanism"). But before calling the engine fully promoted, wanted two specific, narrow checks — not new research branches: (1) what happened to the ~1,650 entries "displaced" by longer-held positions blocking a ticker's slot, and (2) a descriptive audit of what the now-dominant 78.9% max-hold population actually consists of, specifically to decide whether RQ-77 should reopen.

**Displaced-entry accounting**: for each ticker, any old-engine entry that falls inside a new-engine trade's now-longer holding window (blocked because that ticker's single position slot is occupied) counts as displaced. Population gap matches exactly: 1,650 (7,939→6,289 old vs new raw counts before the freshness dropna). 2,355 individual old-engine entries were blocked at some point (exceeds the net gap since some overlap/cascade). **Displaced entries' own quality under the old engine: 60.2% win / +0.835% avg — meaningfully worse than the old engine's overall population (66.2% win / +0.890% avg)**, total value 1,967. This is the favorable scenario: blocked trades are below-average quality, not the strategy's best opportunities. Critically, the new engine's +35% total-output gain (9,374 vs 6,965) happens *despite* forgoing this 1,967 of real value — not because of a favorable reshuffling into better substitutes. The underlying per-trade improvement is larger than the headline total suggests, not an artifact of capital-occupancy luck.

**Max-hold descriptive audit** (n=4,945, 78.9% of the new engine's population): 51.6% winners (avg +8.52%), 10.7% near-flat, 37.7% losers (avg -5.51%). Split the losers exactly as critic specified — "genuine drift" (never touched +2% MFE) vs "real give-back" (touched real progress, then reversed): **only 30.5% are genuine drift** (avg MFE just 1.03%, final avg -6.35% — the breakout never developed) — **the majority, 69.5%, are real give-back** (avg MFE +5.07%, reversed to avg -5.14% by day 15, avg giveback 10.21pp). Both subsets had a pre-floor target available at the same rate (19.8% each), so this split isn't an artifact of the floor correction itself.

**Implication for RQ-77**: this points toward keeping it closed, not reopening it. The dominant max-hold-loser pattern (69.5%) is exactly the "volatile development → temporary stall → still negative at day 15" scenario critic flagged as the dangerous case for an early momentum-failure exit — the same failure mode already demonstrated three separate times today (armed 3-day stall, unarmed Efficiency trigger, and the historical 2026-09-13 "Acceptance as execution-state variable" precedent) of cutting trades that show real, genuine progress. Only the minority (30.5%) matches the "pure drift, never develops" pattern that would justify reopening it — not the dominant story.

**Separately, per direct user pushback on treating +8% as a validated boundary rather than a diagnostic scaffold**: critic agreed explicitly — the architectural finding (a ZigZag target below the profit-protection engagement level can preempt the whole momentum-management machinery) is validated; the specific +8% boundary is not. It was only ever the pre-existing `TRAIL_ENGAGE_PCT` value, reused for a clean first diagnostic, not derived as an optimum. Revised framing, adopted: **"Target-floor hypothesis: targets below the trail-engagement region should be treated as non-actionable. Exact boundary TBD."** The nearby-threshold sweep's "gentle peak at +6%, no discontinuity at +8%" is reconfirmed as evidence for a broad region, not an 8% optimum — and that sweep was pure bookkeeping (never actually closes a position early), so a genuine boundary search needs a proper sequential simulation per candidate level (same rigor as the corrected MAX_HOLD_DAYS sweep), not just re-reading the bookkeeping numbers. Current 8% implementation kept as a temporary diagnostic correction; the boundary itself is queued as its own, separate, small research question — explicitly not to be rushed or conflated with the architectural finding.

## R-multiple floor tested as an alternative to a flat percentage — reveals a sharp step function, not a curve, and re-entangles with RQ-73A (2026-09-20)

Prompted by recalling this project's own earlier web research on standard swing-trading target conventions (targeting the prior swing high, or a fixed 1:2/1:3 risk:reward multiple) — tested whether the target-floor boundary is better framed as a minimum R-multiple (target must sit at least N×that trade's own initial risk above entry) rather than one fixed percentage applied to every trade regardless of stop width. Six genuinely independent full simulations (R_FLOOR ∈ {0.0, 1.0, 1.5, 2.0, 2.5, 3.0}, not bookkeeping — same rigor as the corrected MAX_HOLD_DAYS sweep, since changing which targets are actionable changes hold times and therefore the entry population).

| R_FLOOR | n | Win | Exp | Total pnl | Target-exit share |
|---|---|---|---|---|---|
| 0.0 (no floor) | 7,939 | 66.2% | +0.890% | 7,063 | 40.8% |
| 1.0 | 6,209 | 55.1% | +1.541% | 9,567 | 0.9% |
| 1.5 | 6,195 | 55.1% | +1.534% | 9,505 | 0.1% |
| 2.0 | 6,194 | 55.1% | +1.535% | 9,507 | 0.0% |
| 2.5 | 6,194 | 55.1% | +1.535% | 9,507 | 0.0% |
| 3.0 | 6,194 | 55.1% | +1.535% | 9,507 | 0.0% |

**A sharp step function, not a smooth curve**: R_FLOOR=1.0 alone already beats the flat-8% floor (exp +1.541% vs +1.495%, total 9,567 vs 9,374) and essentially eliminates target exits (0.9%); raising the bar further (1.5R through 3.0R) changes almost nothing, since virtually no target clears even a 1R hurdle in the first place.

**Why, and what it reconnects to**: median ZigZag target sits only +2.29% above entry (per the P3 audit), while median initial risk (R) in this mechanism is ~14-15% (the already-parked RQ-73A wide-structural-stop finding). A genuine 1:1 R:R target would need to sit ~15% above entry; almost none do. The traditional 1:2/1:3 convention from standard swing-trading references is essentially unreachable in the current system — not because targets are badly chosen, but because R itself is unusually wide. **This re-entangles the target-floor question with RQ-73A** in the same way the Freshness U-shape did earlier (correlation(fresh, initial_risk_pct)=0.696 within Common) — both point at the same underlying wide-stop property from different angles.

**Practical implication for the "boundary TBD" question**: there's no meaningful percentage or R-multiple left to tune once you're past ~1R — it's a cliff, not a curve, so further boundary-sweeping in this direction is low-value. The deeper, real question is whether the 20-day structural-low stop anchor itself (RQ-73A, parked since 2026-09-20) is the actual root cause making almost every real swing-high target structurally unreachable at any sensible R:R.

## RQ-73A promoted to active root-cause investigation by critic, with an explicit guardrail against jumping straight to "shorten it" (2026-09-20)

Critic's read on Update 81: the R-floor boundary question is answered (a cliff between 0R and ~1R, not a curve — stop sweeping it; 1R adopted as a temporary architectural guardrail, not an optimized parameter). RQ-73A promoted from "parked optimization" to "active root-cause investigation" — three independent threads now point at the same underlying property (wide structural-stop distance directly measured; Freshness↔initial-risk correlation 0.696 within Common; ZigZag targets universally too close relative to R). Explicit guardrail: don't jump from "20-day low creates wide R" to "therefore shorten it" — first establish what the stop is actually protecting. Five specific diagnostics proposed: does price actually revisit the 20-day low; would a tighter anchor have stopped out eventual winners before they developed; how many winners depend on the wide stop to survive normal consolidation; is the wide risk driven by legitimate structure vs. an unusually deep pre-entry drawdown; does tightening improve R geometry without just converting winners into stop-outs. Also explicitly deprioritized reopening RQ-77 and P4 until this settles, since both may be measuring downstream artifacts of the same stop-width issue.

**First test — tighter 10-day structural low, two fully independent simulations (not bookkeeping) under the R-floor=1.0-corrected mechanism, everything else unchanged:**

| | Current 20-day min | Tighter 10-day min |
|---|---|---|
| n | 6,209 | 6,308 |
| Win | 55.1% | 53.4% |
| Exp | +1.541% | +1.368% |
| Total pnl | 9,567 | 8,629 |
| Avg initial risk | 14.55% | 10.86% |
| R-multiple (mean) | 0.1151 | 0.1359 |

Q1 (does price revisit the 20-day low at all): only 9.7% of trades ever touch it — 90.3% never test it either way. Q2/Q3 (does tightening kill legitimate winners): of current-engine winners (n=3,371), the tighter stop fires *before* the real winning exit in only 3.4% (113 trades) — a real but small cost (those trades average +4.66% under current vs. -8.30% under tighter). Q5 (does tightening improve R geometry): yes on the risk-adjusted metric — same pattern as ATR0-vs-ATR1: raw totals favor the wider stop only because it's not adjusted for the larger position risk it demands; R-multiple (the fair, capital-efficiency comparison) favors the tighter stop by ~18%.

**Second test, per direct user instruction not to trust the earlier web research at face value**: verified "recent swing low" (Minervini: stop below the low of the *final contraction*, not the deepest point over the whole lookback) against the data directly, using the same scipy `find_peaks` machinery already adopted for the ZigZag target (not a new library) — applied to `-Low` instead of `High` to find troughs, over a short 40-day local window (not the target's 300-day scope, since a stop should reflect recent structure, not an old level from months back), taking the most recent confirmed trough.

Verified the implementation before trusting the result: finds a genuine confirmed trough in 97.5% of cases (2.5% fallback to the 20-day min), at a sensible median distance of 11 days from entry — not a bug.

| | Current 20-day min | Tighter 10-day min | Recent swing-low (scipy, 40d/3%) |
|---|---|---|---|
| Avg initial risk | 14.55% | 10.86% (-25%) | 13.21% (-9%) |
| R-multiple (mean) | 0.1151 | 0.1359 (+18%) | 0.1178 (+2.3%) |
| Winners hurt (stopped before real exit) | — | 3.4% | 1.62% |

**Conclusion**: the article's underlying principle (anchor to recent structure, not the deepest point in a wide window) is directionally sound and correctly implemented here, but on this data the simpler "just shorten the window to 10 days" approach clearly beats the more sophisticated swing-low version on the metric that matters most (R-multiple), while only modestly worse on winner protection (3.4% vs 1.62%). The mechanical reason: a "confirmed" swing low requires several days of higher lows after it to validate, so by construction it can never anchor to the absolute most recent low — it sometimes lands on a slightly higher, less extreme point than the true recent minimum over the same span. The added complexity of swing-low detection isn't earning its keep versus the naive tighter window, at least with these parameters (40-day window, 3% prominence).

## Q4 — descriptive audit of the 113 sacrificed winners, per critic's explicit final test before a stop decision (2026-09-20)

Critic's read on the two RQ-73A tests: Q2/Q3/Q5 substantially answered (10-day stop is the leading candidate — real R-multiple gain, bounded winner cost), swing-low parameter tuning explicitly dropped ("that feels exactly like the kind of rabbit hole we were trying to avoid... the proposed sophisticated alternative has failed its burden of proof," parked/rejected for the current mechanism unless Q4 reveals a specific reason to revisit). One remaining test before any actual stop decision: characterize the 113 trades where the tighter 10-day stop would have prematurely killed a current-engine winner — are the extra 10 days protecting genuine breakout structure, or mostly preserving trades that already made an unusually deep, borderline-failed excursion?

Pulled real price history for all 113 trades and computed, per critic's exact question list:

- **Max drawdown (full hold)**: mean -9.66%, median -8.65%.
- **Drawdown at the moment the 10-day stop fires**: mean -9.23%, median -8.45% — nearly identical to the eventual max drawdown, meaning the 10-day stop typically fires right near the actual bottom, not prematurely on a shallow dip.
- **Days to 10-day stop fire**: median 7. **Days to recover back to breakeven from that point**: median 6 (the real profitable exit comes later still, near the 15-day cap for most).
- **Share where price kept falling even further after the 10-day fire point** (not a clean V-turn, a genuinely prolonged decline first): 30.1%.
- **Share that came within 2 percentage points of also threatening the wide 20-day stop**: 23.9% — for roughly a quarter of these trades, the extra 10 days of room wasn't comfortable slack, it was barely enough. The remaining ~76% had a real, independent cushion (avg 4.95%, median 3.49% below even the 20-day level).

**Conclusion, nuanced, not a clean resolution either direction**: this is real structure being protected (median 7-day-fire/6-day-recovery round trip, drawdown depth matching the eventual bottom, not random noise) — not simply "failed breakouts eventually clawing back." But the full 20-day width isn't uniformly necessary: a genuine minority (23.9%) needed nearly all of it, while the majority (76.1%) had meaningful room to spare, suggesting an intermediate anchor (something between 10 and 20 days) might capture most of the same protection while still tightening risk for the majority. Sent to critic (Update 83) as the final input before a stop-width decision, per their explicit sequencing.

## Full 10-20 day structural-lookback sweep — resolves as a genuine monotonic frontier, not a knee (2026-09-20)

Critic's read on Update 83: the split evidence (24% need the full width, 76% don't) justifies an actual sweep, not just one intermediate 15-day test — explicitly reversing their own earlier "don't parameter-hunt" caution, since Q4 gave a specific reason a sweep is now warranted rather than fishing. Explicit pre-registered framing before running it: look for the *shape* of the tradeoff (a stable knee/plateau vs. a genuine monotonic frontier), not just whichever value has the highest expectancy. Constraint: sweep the structural lookback only (10 through 20 days, one day at a time) — prominence, swing-low definitions, ATR buffer all held fixed.

Eleven fully independent simulations (not bookkeeping), everything else unchanged (ATR0, R-floor=1.0 target-floor, swing-low trail, `MAX_HOLD_DAYS=15`):

| Lookback | n | Win | Exp | Total pnl | Avg risk | R-mean | Winner-sacrifice vs 20d |
|---|---|---|---|---|---|---|---|
| 10 | 6,308 | 53.4% | +1.368% | 8,629 | 10.86% | 0.1359 | 3.35% |
| 11 | 6,292 | 53.6% | +1.390% | 8,744 | 11.22% | 0.1313 | 2.93% |
| 12 | 6,281 | 53.8% | +1.413% | 8,876 | 11.56% | 0.1308 | 2.54% |
| 13 | 6,269 | 54.0% | +1.424% | 8,926 | 11.91% | 0.1280 | 2.15% |
| 14 | 6,266 | 54.1% | +1.437% | 9,003 | 12.22% | 0.1259 | 1.88% |
| 15 | 6,256 | 54.2% | +1.444% | 9,032 | 12.52% | 0.1217 | 1.53% |
| 16 | 6,247 | 54.4% | +1.468% | 9,171 | 12.87% | 0.1210 | 1.23% |
| 17 | 6,235 | 54.7% | +1.491% | 9,295 | 13.29% | 0.1196 | 0.85% |
| 18 | 6,226 | 54.8% | +1.503% | 9,355 | 13.70% | 0.1176 | 0.70% |
| 19 | 6,215 | 54.9% | +1.524% | 9,474 | 14.13% | 0.1165 | 0.35% |
| 20 | 6,209 | 55.1% | +1.541% | 9,567 | 14.55% | 0.1151 | — (baseline) |

**R-multiple decreases smoothly and monotonically from 10d to 20d — no interior peak, no plateau, no knee.** Winner-sacrifice vs the 20d baseline also decreases smoothly and monotonically in the opposite sense (3.35%→0.35%). Total output, expectancy, and win rate all rise monotonically with longer lookback. This is exactly critic's second pre-registered scenario ("R steadily improves as the window gets shorter, while winner protection steadily deteriorates... a genuine risk/protection tradeoff rather than a sweet spot"), not the first (a stable region/knee).

**Implication**: there is no data-discoverable "optimal" lookback in 10-20 days — it's a genuine, continuous frontier between capital efficiency (favors shorter) and winner-protection/total-output (favors longer). Picking a point on this frontier is a policy/preference decision, not something further sweeping or analysis can resolve. Sent to critic (Update 84) to decide where on this frontier to land, or whether fixed lookback itself is the wrong abstraction given the shape found.

## RQ-73A closed as a resolved frontier (not an optimization), and a concrete new stop-design north star found (2026-09-20)

Critic's read on Update 84: the monotonic frontier is itself the finding — R-multiple and total output disagree because they're answering genuinely different questions (capital efficiency per unit risk vs. what actually happened through time including preserved recovery trades), and manufacturing a threshold (e.g., "<1% winner-sacrifice") to pick a day from the table would mean choosing the objective function after seeing results. **RQ-73A closed as: the fixed structural lookback is an explicit, deliberate risk/protection tradeoff, not an accidentally oversized parameter** — the 20-day anchor buys +3.35pp of winner preservation at the cost of +3.69pp average risk and materially worse R (0.1151 vs 0.1359). Explicitly not moving to a dynamic/conditional stop yet — "the fact that the frontier doesn't resolve does not automatically mean we need a smarter stop; it means the current data cannot tell us what risk/protection tradeoff the strategy should prefer. That's a strategy-level decision, not a parameter-search problem." Proposed the real next question: not "which day is optimal" but "what stop philosophy should this system use" — with an explicit caution against inventing a formula (e.g., "entry − 3%" or "1×ATR") before checking whether the setup has a meaningful structural invalidation level at all.

**User's design preference, stated directly, resolving the "what tradeoff to prefer" question**: "I would like my SL generally cuts 2-3% on the cost of 3-5% winners. But not really force this" — a soft design target (typical risk near 2-3%, accepting some 3-5% winners get sacrificed), explicitly not a hard per-trade rule. Critic's reframing: the research question changes from "which structural lookback maximizes something" to "why does this system need 10-15% of adverse movement before invalidation, and can a more appropriate level be defined that usually sits much closer to entry" — proposed characterizing the actual distribution (percentiles, bucket counts, relationship to ATR) before inventing any new formula.

**Distribution characterized directly, decisive result**: under the CURRENT 20-day mechanism, **0.0% of trades fall in the 2-3% target zone** (median risk 13.13%, p10 still 8.01%); even the most aggressively tightened tested variant (10-day) only reaches **0.1%** in that zone (median 9.77%, 47.9% still >10%). This proves something the lookback sweep alone didn't: shortening the N-day-minimum window, no matter how far within the tested 10-20 range, cannot reach anywhere near the stated target — the entire "minimum Low over N days" family of stop construction is structurally incapable of producing 2-5% risk for the vast majority of trades. Validates critic's proposed pivot empirically, not just philosophically: the next research must be a genuinely different anchor concept, not another window-size variant.

**ATR relationship, the concrete new lead**: median ATR is only 2.95% of price, but the current 20-day structural low sits at a median of **5.12x ATR** away from entry (p25 4.22x, p75 6.22x, p90 7.42x) — almost completely decoupled from the stock's own real, recent volatility. To land in the stated 2-3% target zone given the median stock's actual ATR, the multiple would need to be roughly **0.68x-1.02x ATR — essentially 1x ATR**, not the 3x this project's own older Family-C-era work used, and nowhere close to the current mechanism's ~5x. A plain `entry − 1×ATR` anchor would naturally scale with each stock's own volatility (wider for genuinely volatile setups, tighter for calm ones) rather than forcing a flat percentage — structurally compatible with "don't force this."

**Not yet tested or adopted** — this is a concrete, well-grounded candidate for the next stop-design investigation (a volatility-normalized anchor, not another lookback variant), sent to critic (Update 85) before building or testing it, per the standing discipline of proposing a genuinely new anchor concept before running it.

## Pure ATR anchor tested directly — a clear negative result, validates the whipsaw concern empirically (2026-09-20)

Before testing, checked the web literature on ATR vs. structural stops for breakout trading: the standard recommendation is explicitly a **hybrid** — "structure-based with ATR buffer typically wins for technical strategies... place stop beyond the level by 0.3-0.5x ATR" — a small ATR buffer added to a real structural level, not a flat ATR distance from entry with zero structural reference. Also: "a stop placed without reference to structure may sit just inside a key technical level [and] get hit by normal noise" — the whipsaw risk this test was designed to check.

Tested the pure version anyway, as directly requested (`entry − N×ATR`, no structural low at all), five multiples (0.5x, 0.75x, 1.0x, 1.5x, 2.0x), fully independent simulations, otherwise identical mechanism:

| ATR mult | n | Win | Exp | Median risk | R-mean | pct stop | 20d-winners sacrificed |
|---|---|---|---|---|---|---|---|
| 0.5x | 9,868 | 28.7% | +0.558% | 1.56% | 0.2727 | 74.0% | 48.89% |
| 0.75x | 8,699 | 33.8% | +0.678% | 2.35% | 0.2322 | 69.2% | 40.53% |
| 1.0x | 7,919 | 37.7% | +0.777% | 3.14% | 0.2090 | 64.9% | 33.90% |
| 1.5x | 7,036 | 44.3% | +0.967% | 4.71% | 0.1800 | 55.0% | 20.63% |
| 2.0x | 6,621 | 48.9% | +1.061% | 6.27% | 0.1485 | 45.8% | 11.97% |

**A clear negative result.** 1.0x ATR does land at the target median risk (3.14%, right in the stated zone), but win rate collapses to 37.7% (vs. 53-55% for the structural-low family) and stop-dominated exits reach 64.9% (vs. 17-27% for structural-low variants). Winner-sacrifice is an order of magnitude worse than anything in the lookback sweep: **33.9% of the 20-day-structural winners get killed early at 1.0x ATR**, versus the tighter-10d variant's worst case of 3.35%. Even 2.0x ATR still sacrifices 12.0%. This is the whipsaw failure mode exactly as the web research warned — a stop with zero structural reference gets hit constantly by ordinary volatility unrelated to whether the breakout thesis is actually invalidated.

**Methodological flag, explicitly called out rather than left to mislead**: R-multiple looks *better* at low ATR multiples (0.27 at 0.5x vs. the structural family's best of 0.14) — this is an artifact, not a real finding. With risk this small (1.6%), any winning trade produces an inflated R-multiple purely from the tiny denominator; it isn't comparable to the lookback sweep's R-multiples, which were all computed in a similar risk-magnitude range (11-15%). The real signal is in win rate, exit mix, and winner-sacrifice, and those are unambiguous.

**Conclusion**: pure ATR-only anchoring is rejected — confirms the web research's hybrid recommendation empirically, not just theoretically. The next candidate is a real structural level (e.g., recent swing low) plus a small ATR buffer (0.3-0.5x, per the literature), not either pure extreme (the current 20-day min or a flat ATR distance) — not yet tested.

## Small ATR buffer on the tighter 10-day base — converges onto the same frontier, doesn't escape it (2026-09-20)

Direct user catch: `structural_low − ATR_BUFFER×atr14` is exactly the hybrid formula, and this project already tested it (ATR0 vs ATR1) — but on the already-wide, settled-oversized 20-day base, where ATR0 (no buffer) won decisively. The untested combination is a small buffer on the *tighter* 10-day base from this round of RQ-73A, since a base sitting much closer to price is more exposed to ordinary noise, where a small buffer might behave differently than it did on the wide base.

Five fully independent simulations (ATR_BUFFER ∈ {0.0, 0.25, 0.5, 0.75, 1.0} on the 10-day structural low, everything else unchanged):

| Buffer | n | Win | Exp | Avg risk | Median risk | R-mean | 20d-winners sacrificed |
|---|---|---|---|---|---|---|---|
| 0.0x | 6,308 | 53.4% | +1.368% | 10.86% | 9.77% | 0.1359 | 3.35% |
| 0.25x | 6,268 | 54.0% | +1.419% | 11.66% | 10.54% | 0.1294 | 2.22% |
| 0.5x | 6,241 | 54.7% | +1.459% | 12.47% | 11.36% | 0.1244 | 1.21% |
| 0.75x | 6,222 | 55.0% | +1.493% | 13.27% | 12.14% | 0.1186 | 0.82% |
| 1.0x | 6,209 | 55.2% | +1.538% | 14.08% | 12.91% | 0.1135 | 0.59% |

**Converges directly onto the same monotonic frontier from the pure lookback sweep, reached via a different formula.** Buffer=0.75x (risk 13.27%, sacrifice 0.82%) lands almost exactly on the 17-day lookback point (risk 13.29%, sacrifice 0.85%); buffer=0.5x (12.47%, 1.21%) sits between the 12-day and 13-day lookback points. "10-day window + N×ATR buffer" and "use a longer fixed window directly" trace out essentially the same tradeoff — the specific mechanism used to add stop distance doesn't matter much, only how much distance is added. Confirms the frontier found in the lookback sweep is a fundamental property of this exit architecture, not an artifact of one particular formula. The hybrid doesn't provide an escape from the tradeoff — it's the same frontier, differently parameterized.

## Freshness-filter gap caught and closed — none of the RQ-73A investigation applied it, verified it doesn't change anything (2026-09-20)

Direct user catch: every RQ-73A worker from the R-floor sweep onward (tighter-10d/root-cause, recent-swing-low, the full 10-20 day lookback sweep, pure ATR anchor, hybrid buffer) ran on the full, unfiltered Primed Gate population — none of them computed or applied the Freshness≤0.40 convention this project otherwise applies automatically. A real gap, not a deliberate choice.

Re-ran the full 10-20 day lookback sweep with freshness tracked to check whether any RQ-73A conclusion was an artifact of skipping the filter. Full-population numbers reproduce the original sweep almost exactly (tiny ~19-trade difference per lookback value, from a handful of corp-action-interrupted rows lacking a computable freshness score — expected, not a discrepancy).

**Fresh≤0.40 shows the identical monotonic frontier shape**: R-multiple decreases smoothly from 10d (0.1463) to 20d (0.1266); win rate, expectancy, and total output all rise smoothly the other way — same direction, same shape, no knee, nothing qualitatively different from the full population. Freshness filter now added to the RQ-73A worker template for any future continuation of this thread.

**Extended the check to every other RQ-73A test, not just the lookback sweep** — built one per-ticker freshness lookup (entry-time-only, independent of which exit mechanism generated a given trade) and joined it onto all the remaining merged datasets without rerunning any simulations (99.7-99.8% match rate on each). All five hold up cleanly on Fresh≤0.40, no reversals:
- R-floor sweep: same step function (0R is the outlier; 1.5R-3.0R stay essentially identical).
- Tighter 10d vs 20d: same direction (10d = lower risk, higher R, lower win/exp/total).
- Recent swing-low: same conclusion (comparable to/marginally behind 10d, not a clear win).
- Pure ATR anchor: same catastrophic pattern — win rate collapses to 32-50% even as risk correctly lands in the 1.5-6% target zone. Whipsaw rejection holds.
- Hybrid buffer on 10d: same monotonic convergence onto the identical frontier.

**None of the RQ-73A conclusions (the frontier, its shape, the ATR-anchor rejection, the hybrid-equals-lookback finding) were an artifact of running on the unfiltered population.** The whole investigation is confirmed robust to the freshness-filter gap.

## RQ-73A's final hypothesis — "final contraction/base low" — tested with theory and data in agreement, closes the whole investigation (2026-09-20)

Critic's read on Update 87: close RQ-73A as a stop-construction search — three materially different formula families (10-20d lookback, pure ATR, 10d+ATR-buffer hybrid) all either fail outright (pure ATR) or trace the identical continuous risk/protection frontier, so the choice of stop width is a strategy-design/risk-tolerance decision, not a discoverable parameter optimum. Explicitly pushed back on treating the user's "2-3% risk, some 3-5% winners lost" preference as a target to force the data toward — even the most aggressive tested construction (10d) only reaches median risk 9.77%, nowhere near 2-3%; forcing it down there would mean abandoning the structural-invalidation concept entirely, a different strategy design, not an RQ-73A finding. Distinguished one final, genuinely different hypothesis worth testing before closing: "the low of the final contraction/base immediately preceding the breakout" — a different semantic question ("what price invalidates this specific setup") than every prior test ("how much historical downside should I tolerate"). Explicit requirement: a deterministic, entry-time-only definition, not a subjective/hindsight-prone "find the final contraction."

**Researched before implementing, per direct user instruction to check whether this mixes two different trading styles**: confirmed "stop below the base/consolidation low" is a genuine, well-established technique — the Darvas Box method (1950s-60s: new high → range-bound box → breakout above the box, stop just below the box bottom) and flag/pennant continuation patterns (sharp move → tight consolidation → breakout, stop below the consolidation low) both use exactly this logic. But critically, both come with an explicit precondition found in the same research: the technique only applies within pattern families (Darvas Box, VCP, flags/pennants) whose *entry criteria themselves require* a genuine, identifiable box/consolidation to exist before the breakout. This project's `breakout_continuation` entry (EMA34 rising, price crossing `high10_prior`, volume z-score, `checklist_pass`) never screens for that Darvas/VCP-style "new high → range → breakout above the range" shape — it's a looser, momentum-based continuation signal. Flagged before testing: applying a base-low stop here may mean presupposing a structure the entry logic never verified exists — a real risk of mixing two different trading-style philosophies (range-then-breakout vs. momentum continuation), which would also explain why the earlier "recent swing low" test (rq107) underperformed.

**Implementation, deterministic and entry-time-only**: (1) find the most recent confirmed swing high before entry via scipy `find_peaks` (60-day local window — marks where the current pullback/contraction began); (2) base low = `min(Low)` from that swing high's day to entry (the contraction that followed it); (3) fallback to the plain 10-day min if no qualifying swing high exists in the window. Computed independently of the target/trailing logic, per critic's explicit constraint.

**Result: theory and data agree.** 85.5% of trades found a genuine recent-swing-high-anchored base (not a fallback artifact), but the outcome lands squarely on the already-established frontier, roughly equivalent to a 16-17 day fixed lookback — median risk 12.04%, mean 13.63%, R-mean 0.1181, sacrifice 1.30%, total pnl 9,318 (compare: 15d gives 1.53%/9,032; 20d gives 0%/9,567 — final-base sits between them on every axis, not below/outside them). The telling detail: **even among trades where a genuine base was found, average risk (14.60%) is actually wider than the current 20-day baseline (14.55%)** — the technique, when it successfully computes something, mostly reaches back to some earlier peak and rediscovers a similarly wide distance, because most Breakout Continuation entries don't have a genuine, tight, recent Darvas-box-style consolidation to anchor to. It finds "some earlier high, whatever it happens to be," not "the low of a compact base."

**RQ-73A closed, definitively, with both theory and empirical evidence in agreement**: no tested anchor — historical-minimum window (10-20d), pure ATR, structural+ATR hybrid, or genuine Darvas/VCP-style base-low — escapes the structural risk/protection frontier intrinsic to this entry population. Pure ATR fails outright (whipsaw). Every structural variant, including the theoretically best-grounded one, lands on the same continuous tradeoff. The stop-construction question is resolved: **choice of stop width is a strategy-design/risk-tolerance decision, not a discoverable parameter optimum** — and the user's 2-3% preference remains a genuine design preference for a *different* strategy shape, not a target this entry population's actual structure can support without abandoning structural invalidation altogether.

## Fragility/robustness audit begun — critic-directed backlog rebuild, pure observations logged as found (2026-09-20)

Critic's read on RQ-73A's close: rebuild the research backlog before jumping to Freshness. Tier 0 (finish/validate what's in motion) includes fragility/robustness of the major conclusions before anything else — the concern being that some of today's findings might not be stable enough to deserve further optimization. Tier 0 item 1 (target-floor capital-occupancy attribution) was already satisfied by the earlier displaced-entry accounting (1,650 population gap, quality 60.2% win vs. 66.2% overall, confirming favorable). Remaining Tier 0 work: a final sanity audit and fragility/robustness testing, before Tier 1 (breach behavior), Tier 2 (options audit), and Tier 3 (Freshness capacity, redone on the settled architecture).

**Trade and ticker concentration (standard project checks) — clean, no red flags**: top-10 trades are only 6.8% of total pnl (top-20: 12.1%), both far under the 40% danger threshold. All 454 tickers in the universe contribute; top-10 tickers are 20.9% of total pnl — broad-based, not a handful of lucky names.

**Winner-removal stability — clean**: removing the top 10/20/50 winning trades entirely, expectancy stays solidly positive throughout (+1.396% / +1.318% / +1.133%, vs. the full population's +1.541%) and win rate barely moves (55.16% / 55.09% / 54.87% vs. 55.11%). The result isn't propped up by a small number of outsized trades.

**Time-period stability — a real, more significant concentration than trade/ticker level suggested**: by calendar year of entry, **2023 alone contributes 48.6% of the entire backtest's total profit** (4,551 of 9,374), with a dramatically higher win rate (67.0% vs. 50-57% other years) and R-multiple (0.325 vs. 0.04-0.09 other years). 2021 is negative for both the new and old engine (-0.574% and -0.436% exp respectively, small n~220-250, likely partial-year/early-cache-history noise). Checked whether 2023 itself is a data artifact: its internal ticker concentration (20.1% top-10) matches the overall population's (20.9%) — not a handful of names, and its top contributors (BSE, SUZLON, IRFC, MAZDOCK, COCHINSHIP, INOXWIND, RECLTD, BHEL, PFC, ADANIPOWER) are the well-documented 2023 Indian PSU/infra/defense/renewable rally, a real, broad market regime — not a computation error. **The strategy's overall absolute profitability is genuinely regime-dependent** — this is a real fragility finding, not a false alarm.

**Reassuring nuance, checked directly rather than assumed**: the *target-floor improvement itself* (new engine total minus old engine total, matched by year) is considerably less concentrated than the raw totals — 2023 contributes only 35.9% of the total improvement (865 of 2,408), and the improvement is positive in 5 of 6 years (2022: +255, 2024: +183, 2025: +520, 2026: +600; only 2021 is slightly negative in both engines equally, ~-16, consistent with small-sample noise rather than the fix failing). So while the strategy's absolute profitability leans heavily on catching favorable regimes like 2023, the target-floor fix's *relative* value is broadly consistent across years, not a 2023-specific artifact.

**A more significant finding — the RQ-73A "continuous frontier" itself is substantially an artifact of 2023, not a stable structural property**: re-ran the R-multiple-by-lookback comparison (10d through 20d) split into 2023-only vs. all other years combined. **Within 2023 only, the frontier is real and steep** — R-multiple falls monotonically from 0.436 (10d) to 0.328 (20d), matching what was reported earlier. **Within all other years combined, R-multiple is nearly flat across the entire 10-20 day range** (10d: 0.069, 12d: 0.069, 15d: 0.066, 17d: 0.066, 20d: 0.068) — noise-level differences under 10% relative spread, no meaningful monotonic trend. The direction still marginally favors shorter lookbacks even outside 2023, but the *magnitude* of the whole "continuous risk/protection tradeoff" finding is overwhelmingly driven by one exceptional bull-regime year, not a stable property of the strategy across typical market conditions. This meaningfully tempers (not reverses) today's RQ-73A conclusion: the tradeoff is directionally real, but far weaker in ordinary years than the aggregate frontier suggested — meaning the stop-width decision matters much less in most years than 2023 made it appear, and a decision maker choosing a point on "the frontier" should weight the aggregate numbers accordingly, not treat them as representative of a typical year.

**Checked whether the pure-ATR-anchor rejection is similarly a 2023 artifact — it is not, and if anything the rejection is stronger outside 2023.** Win rates for every ATR multiple tested (0.5x-2.0x) are severely depressed in both slices (27.8-46.3% outside 2023, 32.6-60.7% within it) and never approach the structural-low family's 53-55% baseline in either slice. The whipsaw failure mode is a robust, regime-independent finding, not an artifact of the dominant year.

**Fragility audit, first pass, summary**: trade concentration (6.8% top-10, healthy), ticker concentration (20.9% top-10, broad-based, all 454 tickers contribute), and winner-removal stability (expectancy survives removing the top 50 winners) are all clean — no red flags. Time-period concentration is real and significant (48.6% of total profit from 2023 alone, a genuine, well-documented market regime) — the strategy's absolute profitability is regime-dependent, a real finding worth carrying forward, not a false alarm. The RQ-73A frontier's *direction* is regime-independent but its *magnitude* is substantially a 2023 artifact — a real, important qualifier on today's stop-construction conclusion. The ATR-anchor rejection is confirmed robust and regime-independent. Not yet checked: full market-regime split (beyond calendar year), bootstrap-style uncertainty bounds, and fragility of the RQ-77/stall-detector and would_confirm findings specifically — queued for continuation, not a rabbit hole to chase further right now.

## Tier 1 begun — breach behavior, a major new finding, cleaner and more independent than would_confirm (2026-09-20)

Per critic's backlog rebuild, started the breach-behavior thread: does the behavior of price around the intraday breach itself (not just whether the entry criteria pass) contain useful information about eventual outcome? Pulled real breach-day OHLCV for every Primed Gate entry in the settled (target-floor-corrected) population and computed overshoot (how far intraday High cleared the trigger), close-vs-trigger distance (does the close hold above the trigger by end of day, and by how much), close-position-in-range (did the day close near its high or its low), and volume z-score.

**A major, clean, strongly monotonic result — the single strongest gradient found in the breach-behavior thread**: correlation(close_vs_trigger_pct, final pnl) = 0.2785, the strongest of the four features tested.

**41.0% of all Primed Gate breaches fail to even hold the trigger by end of day** (Close < trigger) — and that group has **negative average expectancy** (44.6% win, -0.65% exp). The full gradient:

| Close vs. trigger | n | Win | Exp |
|---|---|---|---|
| Below trigger (failed to hold) | 2,572 | 44.6% | -0.65% |
| 0-1% above | 1,428 | 53.4% | +0.83% |
| 1-3% above | 1,350 | 63.6% | +2.84% |
| 3%+ above | 920 | 75.4% | +6.55% |

Same clean, monotonic pattern on close-position-in-range (closed in bottom 30% of the day's range: 42.8% win/-0.78% exp; closed in top 30%: 60.6% win/+2.54% exp) and overshoot magnitude (barely cleared the trigger by ≤1%: 47.2% win/-0.39% exp; cleared by 7%+: 77.0% win/+7.33% exp).

**Verified before trusting it, per standing rule**: outlier concentration is clean on both ends (strong bucket top-10 share 9.1%, weak bucket worst-10 share 15.3%, both well under the 40% danger threshold; weak-bucket median (-1.14%) is actually more negative than its mean, so the negative expectancy is broad-based, not outlier-inflated). **Checked whether this is just rediscovering Freshness or Delta in disguise — it is not**: correlation(close_vs_trigger_pct, fresh) = -0.090, correlation(close_vs_trigger_pct, is_delta) = 0.099, both very weak. This is genuinely new, independent information.

**Relationship to the earlier would_confirm finding**: same general idea (same-day, end-of-day information distinguishing quality) but far more granular — would_confirm was a binary pass/fail on the full `entry_signal()`/regime-gated checklist (9.1% pass rate); this is a continuous measure of breach strength alone (close position relative to the trigger, no checklist), splitting nearly the whole population (not just 9%) into a clean four-step gradient from -0.65% to +6.55% expectancy.

**Not yet treated as actionable** — per the same standing caution already established for would_confirm (the 2026-09-13 "Acceptance as an execution-state variable" precedent: a real quality gap doesn't mean intervening on the weak subgroup helps, since non-confirmation/weak-breach behavior is normal even in eventual winners). Logged as a pure, verified observation, per explicit instruction, before any consideration of turning it into a rule.

**Mechanistic color, exit-reason mix by breach-quality bucket**: the weak-breach bucket (close below trigger) resolves mostly via `max_hold_cap` (82.7%) — it doesn't stop out fast, it just drifts to a mediocre-to-negative outcome by day 15 (avg 14.1 days held). The strong-breach bucket (close 3%+ above trigger) resolves faster overall (12.9 avg days) and shows both more target hits (7.9% vs 1.9%) *and* more stops (24.6% vs 14.5%) — strong initial moves apparently also see more real give-back some of the time, not purely more follow-through. Consistent with the give-back pattern already documented elsewhere in this project.

**Checked whether the gradient is a repeat-entry artifact (echoing RQ-73A's already-rejected repeat-entry hypothesis) — it is not.** Recomputed `extension_days` directly for this population (23.6% are repeat breaches). The same monotonic close-vs-trigger gradient holds nearly identically in both subgroups: first breaches show -0.48%/+1.02%/+2.86%/+6.46% exp across the four buckets, repeat breaches show -1.24%/+0.13%/+2.77%/+6.77% — same shape, same direction, comparable magnitude (repeats slightly worse at the weak end, essentially identical at the strong end). This is a genuine, broad-based signal independent of first-vs-repeat status.

**The standout finding of the whole breach-behavior thread — day+1 adverse movement, correlation 0.3417, stronger than close-vs-trigger itself.** Checked how far below entry (the trigger price) day+1's Low reaches: **64.8% of all trades see day+1's Low dip below entry** — an immediate pullback the very next day is the norm, not the exception. The gradient:

| Day+1 Low vs. entry | n | Win | Exp |
|---|---|---|---|
| Drops >3% below entry | 1,094 | 34.8% | -2.70% |
| Drops 1-3% below entry | 1,736 | 47.7% | +0.05% |
| Drops 0-1% below entry | 1,231 | 55.2% | +1.17% |
| Stays at/above entry | 2,209 | 71.3% | +4.89% |

**Verified before trusting it**: outlier concentration is clean on both ends (best-bucket top-10 share 5.8%, worst-bucket worst-10 share 8.8%, both well under the 40% danger threshold); the worst bucket's median (-3.73%) is actually more negative than its mean (-2.70%) — the negative expectancy is broad-based, not tail-inflated — and spans 371 of 454 tickers, genuinely universal, not a handful of names. This is the strongest, cleanest signal found in the breach-behavior thread so far — makes intuitive sense (whether a fresh breakout immediately shows weakness the very next session is a direct read on real conviction), but like every other breach-quality finding today, **not yet treated as actionable**, logged as a pure, verified observation.

## Status checkpoint — autonomous research stretch, pure observations only, nothing acted on (2026-09-20)

Per explicit instruction (run the full fragility/robustness pass, keep going through the backlog, log pure observations, don't chase rabbit holes, no critic round-trip during this stretch since no one was available to relay responses). Summary of what this stretch covered, for continuation:

**Tier 0 (fragility/robustness) — first pass complete**: trade concentration (6.8% top-10), ticker concentration (20.9% top-10, all 454 tickers contribute), and winner-removal stability (expectancy survives removing top 50 winners) all clean, no red flags. Time-period concentration is real (48.6% of total profit from 2023 alone, a genuine documented market regime, not an artifact) — the strategy's absolute profitability is regime-dependent. The RQ-73A frontier's magnitude (not direction) is substantially a 2023 artifact — nearly flat outside that year. The ATR-anchor rejection is confirmed robust and regime-independent. **Not yet done**: full market-regime split beyond calendar year, bootstrap-style uncertainty bounds, fragility of the RQ-77/stall-detector and would_confirm findings specifically.

**Tier 1 (breach behavior) — strong start, one major new finding**: close-vs-trigger distance (correlation 0.28) and day+1 adverse movement (correlation 0.34, the strongest signal found) both show clean, monotonic, outlier-checked, non-Freshness/Delta-redundant gradients between breach quality and eventual outcome. Both confirmed robust across first vs. repeat breaches. **Not yet done**: the remaining items on critic's breach-behavior list (does a breach that immediately rejects intraday, before end of day, behave differently; volume-weighted breach quality beyond the weak raw vol_zscore correlation already checked at 0.069; distinguishable "bad breach" archetypes via clustering rather than single-feature buckets).

**Tier 2 (options audit) — not started as a full pass, but one major, directly-actionable lead surfaced.** Direct user question: the day+1-adverse-movement finding above is useless for options specifically, since an options position is typically already resolved by day+1 open — is there a pattern knowable *at* the breach (or by end of the entry day) that matters for that short horizon instead?

Checked two candidates. **Gap-through-at-open** (stock's Open already clears the trigger before the session starts, 10.0% of trades): real but modest signal (correlation with full-swing pnl only 0.07-0.09), win 65.1%/exp +4.14% vs. 54.1%/+1.20% for trades that had to climb intraday — some outlier influence (top-10 concentration 20.6%, still under the 40% danger threshold but higher than other checks today).

**Far more important: the already-established close-vs-trigger signal, re-tested against the actual options-relevant horizon (entry at trigger, exit at day+1 open — the standard options recipe)**: correlation = **0.937**, near-deterministic. Worth being precise about why — a stock's next-day open closely tracks its prior close under normal overnight-gap behavior, so this is largely mechanical, not a mysterious new pattern. But the practical implication is direct and large:

| Close vs. trigger (known by end of entry day) | Day+1-open win rate | Mean |
|---|---|---|
| Below trigger (41% of trades) | 23.4% | -0.92% |
| 0-1% above | 88.7% | +0.74% |
| 1-3% above | 98.2% | +2.29% |
| 3%+ above | 99.6% | +6.46% |

**Directly actionable for the options thread specifically, PENDING verification against real premiums (see correction below)** — the actual options mechanics (contract selection, liquidity, real premium behavior vs. this stock-price proxy) haven't been checked, which is the remaining Tier 2 work.

## Correction — the above options claim was overstated, caught by testing against real option premiums with the correct exit convention (2026-09-20)

Tested the close-vs-trigger → options-outcome relationship against real option data. **First attempt made a real, already-documented mistake**: used `simulate_option_trade()`'s built-in exit, which resolves close-to-close (exit at day+1's option *Close*) — but this project's own history (2026-09-14 methodology note) already flagged that the actual adopted day+1 recipe exits near day+1's *Open*, not its close, and that close-based day+1 exit is "dramatically worse" (documented then: 45.5% vs 82.0% win for ATM). Repeated that exact mistake initially — the first-pass result (n=585, correlation 0.084, overall win only 42.7%, median -3.82%) was measuring the wrong horizon entirely and is discarded.

**Rebuilt correctly** using the established recipe from `research_archive/theta_bleed_check_open_exit.py`: entry at the entry day's option Close, exit at day+1's option Open. Same underlying 1,000-trade sample, n=557 successfully matched to real, liquid contracts (ATM, current expiry).

| Close vs. trigger | n | Win | Mean | Median |
|---|---|---|---|---|
| Below trigger (weak) | 221 | 52.5% | **+0.28%** | +0.16% |
| 0-1% above | 160 | 54.4% | +0.88% | +0.71% |
| 1-3% above | 129 | 58.1% | +3.62% | +0.94% |
| 3%+ above | 47 | 63.8% | +4.41% | +0.68% |

Correlation(close_vs_trigger_pct, real option day+1-open pnl) = **0.137** — real and directionally consistent (the earlier stock-proxy claim wasn't fabricated, the direction holds), but nowhere near the 0.937 the flawed proxy suggested. **Most importantly, the "weak breach" bucket is not a loser on real options** — it's still mildly positive (+0.28% mean), unlike the stock-proxy's claim that it averaged -0.92%. This matches the project's own already-established finding that the day+1-open exit captures a real, fairly robust edge on its own ("the open isn't the ceiling, it's a safe floor") — breach quality is a genuine, real amplifier of that edge, not a hard gate that turns the trade into a loser.

**Practical implication, revised**: waiting for close confirmation before entering options would modestly improve average outcomes (roughly +0.3pp to +4pp of amplification depending on how strict the bar), not rescue a losing population from being a loser — the overstated version of this claim is retracted. Still worth testing formally with a larger real-option sample and proper significance/concentration checks before treating even this corrected version as actionable.

## RQ-90A — Close Quality Ladder, per critic's reframe (Bad Breakout Recognition, options-first) (2026-09-20)

Critic's read on Update 89, a genuine project reframe: the stock swing side can tolerate "Type B" trades (breakout works initially, may give back later over 15 days — a P&L optimization problem), but options are dominated by "Type A" trades (breakout fails to establish momentum the same day, hurts immediately overnight — a risk-management problem, the user's actual stated pain). Proposed splitting stock and options research permanently, with a new thread, RQ-90 (Bad Breakout Recognition), starting with a no-intervention "close quality ladder": a binary checklist of same-day, pre-overnight-hold features, checking whether the checklist count is monotonic against both stock and options outcomes, before considering any actual filter.

**Checklist (4 binary items, all known by market close on entry day)**: closed above trigger; closed in top 40% of the day's range; day's Low never dipped below trigger (held the whole day); volume z-score ≥1.5 (matching `entry_signal()`'s own volume-confirmation convention). Computed for the full settled population (n=6,270).

**Stock swing outcome — clean, near-monotonic**: 0/4: 44.8% win/-0.97% exp → 1/4: 44.4%/-0.26% → 2/4: 56.9%/+1.60% → 3/4: 65.8%/+3.77% → 4/4: 84.8%/+7.89% (n=92 at the top, smaller but a strong, real gradient throughout).

**Real options (day+1-open, correct recipe) outcome — a genuinely different shape, not a smooth ladder**: 0/4: 48.9% win/-0.65% mean (clearly worst, matches the stock story) → 1/4: 61.5%/+2.14% → 2/4: 60.6%/+2.07% → 3/4: 55.4%/+1.87% → 4/4: 40.0%/-2.53% (n=15, too small to trust). Checklist 1, 2, and 3 are roughly similar/overlapping (+1.87% to +2.14%), no clean ordering among them — **this looks like a threshold effect (clear the weakest bar or don't), not a continuous ladder**, at least at the very short day+1-open horizon. More quality clearly buys more 15-day swing edge, but doesn't obviously buy more overnight-specific edge past the first bar cleared. A real, useful distinction between the two products, not assumed from the stock-side pattern.

## RQ-90B — Overnight Filter Simulation, options-first, per critic's exact test design (2026-09-20)

Real option outcomes (day+1-open, correct recipe), n=1,382, four variants: skip close<trigger (A), skip worst-ranked 10%/20%/25% by close-vs-trigger distance (B/C/D).

| Variant | Options: n / win / mean | Stock: n / win / mean |
|---|---|---|
| Baseline (hold all) | 1,382 / 58.3% / +1.93% | 1,382 / 56.3% / +1.14% |
| A: skip close<trigger | 835 / 60.2% / +2.72% | 835 / 63.2% / +2.33% |
| B: skip worst 10% | 1,244 / 59.6% / +2.32% | 1,244 / 58.2% / +1.46% |
| C: skip worst 20% | 1,106 / 60.3% / +2.49% | 1,106 / 59.9% / +1.67% |
| D: skip worst 25% | 1,037 / 60.7% / +2.66% | 1,037 / 61.4% / +1.96% |

All four variants improve both win rate and mean on both products at once — the first result in this whole session to hit critic's "both improve — excellent" promotion bar simultaneously for stock and options.

**Important correction, caught by checking what's actually skipped rather than trusting the aggregate improvement at face value**: the full "close<trigger" group (n=547, skipped by Variant A) is itself still net-positive (mean ≈+0.72%, median +0.76%) — not a losing population. The improvement in the kept group is partly a mechanical artifact: removing any below-average-but-still-positive subgroup raises the average of what remains, by simple arithmetic, regardless of whether that subgroup is genuinely bad. That's a legitimate capital-concentration effect, but a different, weaker claim than "these are Type A losers."

**The more precise, honestly-defensible "true losers" signal is in the tail specifically**: Variant B's worst-ranked 10% (a smaller, more extreme cut than the full close<trigger group) genuinely averages **-1.58%** — real, net-negative, the actual Type A signal. Widening the cut toward 20-25% dilutes this back toward flat (skipped-group averages -0.34%, -0.26%). So the honestly-defensible filter is narrower than "skip anything below trigger" — closer to "skip the worst-ranked 10% specifically."

**Concentration check on Variant A (kept group)**: top-10 share 27.9% (elevated but under the 40% danger threshold), median (2.25%) close to mean (2.72%), not wildly outlier-inflated.

**Status**: real, promising, first result to clear critic's dual-promotion bar — but the precise mechanism (concentration effect vs. true loss-avoidance) needs to be stated correctly, and the narrower worst-10% version is the more defensible next candidate to test properly (larger sample, significance check) rather than the broader close<trigger cut. Not yet promoted — per the standing discipline, needs the same rigor (bigger real-option sample, proper significance/concentration checks) before treating even the corrected version as a live rule. Sent to critic (Update 90) for their read on the concentration-effect vs. loss-avoidance distinction and next steps.

## Correct framing of the action, per direct user pushback, and a properly-powered significance check that weakens the worst-10% claim (2026-09-20)

**Framing correction, important**: the "skip" decision above was mis-described as an options entry gate. The real intraday option price at breach time is unknowable (daily-bhavcopy-only data), so the established convention already treats the option's entry as happening at breach time in reality — the day's Close is only a backtest proxy for that unknown price, not a description of when the trade is actually placed. Since the user's real execution enters the option at breach time (same as the stock), by the time the close prints they're already holding the position — same timing constraint already established for the stock leg. **The correct, actionable framing: this is not an entry filter, it's an overnight-hold-vs-exit-at-close decision** — given the option is already held from breach time, at end of day you have a real, tradeable choice between selling now (at the close-time value) or holding through the gap to exit at tomorrow's open. The close-to-open pnl already measured is exactly the right quantity for this decision (it directly answers "does holding overnight gain or lose value relative to selling now"), and since it's built from real observed option prices (not a theoretical recompute), theta decay and IV changes are already fully embedded — no separate adjustment needed.

**Properly-powered significance check, per direct request, before trusting the worst-10% number**: pulled a bigger real-option sample (n=2,436, up from 1,382) and tested each tail cut against zero.

| Cut | n | Mean | p-value | Significant? |
|---|---|---|---|---|
| Worst 5% | 121 | -2.80% | 0.015 | Yes |
| Worst 7% | 182 | -1.74% | 0.045 | Borderline |
| Worst 10% | 243 | -1.26% | 0.086 | **No** |
| Worst 15% | 365 | -0.79% | 0.221 | No |
| Worst 20% | 487 | -0.63% | 0.249 | No |
| Worst 25% | 609 | -0.08% | 0.863 | No |

**The earlier worst-10% finding weakens and loses significance with the bigger sample** — mean shrinks from -1.58% (n=1,382) to -1.26% (n=2,436), bootstrap 95% CI [-2.70%, +0.11%] includes zero. Only the more extreme cuts (worst 5%, worst 7% borderline) remain genuinely significant. This is exactly why the significance check matters: the smaller sample made a noise-driven number look more solid than it actually is.

**Corrected conclusion**: a real Type A signal exists, but it's narrower and more modest than previously stated — closer to the worst 5-7% of trades (mean -1.74% to -2.80%, holding through the gap for this subset genuinely loses money relative to exiting at the close), not the worst 10%+. Past that, the effect shrinks toward zero and isn't statistically distinguishable from noise. Correcting Update 90's framing before it goes further — this is a smaller, more precise finding than first reported, not a broad-brush filter.

**Extended further (per explicit instruction to finish the list before sending another update, not report piecemeal) — pulled an even larger real-option sample (n=4,276, up from 2,436) and re-ran the boundary search at 1% granularity.** The picture stabilizes rather than shrinking further: a clear, contiguous significant band from **worst 5% through worst 11%** (all p<0.05, mean losses -1.2% to -2.3%), fading to non-significant from worst 12% onward. This is the expected pattern for a real but modest effect that was simply underpowered at the intermediate (n=2,436) sample size — not a reversal, a stabilization with more data.

**Concentration check on the worst-10% band, and an important distributional nuance**: worst-10-trades' share of the band's total negative pnl is 18.3% (healthy, not outlier-driven). But **median in this band is nearly zero (+0.03%) while the mean is -1.42%** — meaning it is not that most trades in this group lose money; a real subset takes a genuinely bad loss, dragging the average down, while the typical trade is close to flat. This is better understood as a **tail-risk finding** (a real, identifiable elevated risk of a bad overnight loss concentrated in ~10% of trades) rather than "this whole subgroup is a loser" — a more precise, and arguably more directly useful, framing for a risk-management objective than an average-return framing.

## RQ-90C — False Breakout Anatomy, descriptive characterization of the worst 5-11% band (2026-09-20)

Characterized the entry-day candle shape and volume for the now-precisely-identified worst 5-11% band (n=376) against a clean comparison group well clear of the tail (n=4,389):

| | Worst band | Healthy comparison |
|---|---|---|
| Body as % of day's range | 30.8% | 61.8% |
| Upper wick as % of range | 51.4% | 22.8% |
| Volume z-score | 2.48 | 5.76 |
| Overnight gap % | 0.69% | 0.79% |

A coherent, textbook "false breakout" shape: small real body, a large upper rejection wick (2.3x the healthy group's) — a classic shooting-star/rejection candle — and notably lower volume (less than half the healthy group's) despite still clearing the minimum entry threshold. Gap size at the open isn't a differentiator between the two groups. This is descriptive, not independent of the close-vs-trigger/close-position signals already found (a small body with a big upper wick mechanically implies a weak close position), but it gives a concrete, visual characterization of what the tail-risk group actually looks like — consistent with, not contradicting, the earlier findings.

## RQ-91A — Price+OI Quadrant, first read, inconclusive (2026-09-20)

Built the full 4-quadrant classical framework (long buildup: price↑/OI↑; short covering: price↑/OI↓; short buildup: price↓/OI↑; long unwinding: price↓/OI↓) from real front-month futures data (trailing 3-day window ending on entry day, EOD-only, matching the already-existing `oi_buildup_bullish()` convention), tested against real option day+1-open outcomes, n=1,121.

Since this is a long-only breakout strategy, the sample is heavily skewed toward "price up" quadrants (long_buildup n=359, short_covering n=745) — the "price down" quadrants are far too small to read anything from (n=7, n=10) and are excluded from interpretation entirely.

Between the two viable quadrants, short covering showed a nominally *better* option outcome than long buildup (59.3%/+2.43% vs 56.0%/+1.19%) — the opposite of what the classical framework would predict (fresh long buildup is usually considered the more bullish, durable signal). **Checked before trusting it: not statistically significant (p=0.147), and short_covering's top-10 trade concentration is 35.0%** (close to the 40% danger threshold) — the apparent edge could easily be a handful of large winners rather than a real quadrant effect.

**Honest conclusion: no trustworthy signal from this OI classifier at this sample size.** Not a rejection of the underlying idea (RQ-48's history already showed this exact classifier flipping between rejected/reversed depending on conditioning), but a clean, appropriately-caveated null result for now — needs a bigger sample before drawing any real conclusion, and even then the "obvious" classical direction isn't showing up.

## Status checkpoint — full RQ-90 arc complete (A/B/C), RQ-91A first read done (2026-09-20)

Per explicit instruction to finish the list before sending another consolidated update. Summary: RQ-90A (close quality ladder, stock vs. options shape difference), RQ-90B (overnight filter simulation, corrected framing to overnight-hold-vs-exit-at-close, properly significance-tested to a stable worst-5-11% band across n=4,276 real option trades), RQ-90C (false breakout candle anatomy) are all complete. RQ-91A (price+OI quadrant) has a first, inconclusive read. RQ-91B (futures OI long-buildup vs. short-covering in isolation, without the full quadrant framework), RQ-91C (IV percentile/expansion/crush), and RQ-91D (combine breach quality + derivatives confirmation) are not yet started.

## Direct follow-up: is there a pattern *before or at* the breach itself (not after it) that flags the bad 41%, or a short-term pullback regardless of eventual swing outcome? (2026-09-20)

Sharper version of the same question: the close-vs-trigger and day+1 signals above are only knowable *after* the breach day develops — too late to avoid the trade, and irrelevant to someone who'd want to skip the entry altogether or worry that even an eventual swing winner could still hurt an options position via an early pullback. Checked systematically, honest negative result on most fronts.

**Pre-entry (prior-day-only, before the breach) technicals — no meaningful signal.** Correlation of each against both the close-vs-trigger outcome and a short-term (day 1-3) maximum-adverse-excursion metric (regardless of eventual swing result): freshness (-0.09 / -0.14), RSI14 (-0.08 / -0.10), volume z-score (0.03 / -0.05), ATR% (0.05 / -0.15), prior distance to trigger (0.005 / 0.13), is_delta (0.10 / 0.07). All weak, none above ~0.15. None of the standard, already-computed technicals meaningfully distinguish which breaches will fail before the breach actually happens.

**Genuine intraday check, using real 5-minute data (the only ~3-month window, June-September 2026, where it exists; n=417 matched entries)**: volume on the exact 5-minute bar where price first crosses the trigger shows essentially zero signal (correlation ~0.02 with both the day's close-vs-trigger outcome and final pnl). Whether price ever dips back below the trigger within an hour of the initial cross is too common to be useful as a filter (93.5% of trades do this at some point — normal wobble around a freshly-broken level, not a meaningful weak-breach signal). The small subset that holds immediately with zero pullback in that first hour (27 of 417, ~6.5%) does show a real gap (81.5% win/+4.77% exp vs. 50.5%/+0.85% for the rest) — but the sample is too small to trust on its own, and confined to one recent 3-month window, not tested across regimes.

**Honest overall conclusion**: no reliable way found to identify the bad 41% (or a short-term-pullback-prone trade generally) before or at the moment of the breach. The market appears to genuinely decide over the course of the breach day itself — via real order flow, follow-through, and close — not something visible in advance from static pre-entry setup or the crossing instant. The one hint worth more data (immediate, zero-pullback holds) is flagged for continuation with a larger intraday sample if/when more history becomes available, not treated as a finding yet.

**Tier 3 (Freshness capacity, max-hold descriptive re-audit) — not started**, intentionally deferred behind Tier 0/1 per critic's revised sequencing.

**Nothing from this stretch has been proposed as an actionable rule** — every finding (breach-quality gradients, day+1 adverse-movement gradient, the 2023 regime-dependency, the frontier-magnitude qualifier) is logged as a verified observation only, consistent with the explicit instruction and the standing 2026-09-13 precedent against reflexively acting on a real quality gap. No critic update drafted for this stretch — queued for the next round when critic can actually weigh in on sequencing and which of these threads to pursue further.

**Confirms the pattern already established on the deprecated Entry-Gate population, now on the correct, real Primed Gate population — not a new finding, a reproduction.** Legacy wins on raw portfolio $/day at every step; each change trades some of that away for a different, real benefit (New SL: smaller/safer losses, stop-exit avg −11.97%→−10.85%; New Target: higher win rate and faster resolution, 63.7%→71.4%; Trail-new: dramatically smaller stop-outs, −9.42%→−3.57%, the same offsetting-effects shape as everything else this weekend). Not sent to the critic as its own update — confirmatory, not novel, doesn't meet the "new/unexpected finding" bar for a check-in on its own.

## RQ-93 — Current-engine Breach rebuild, per critic's explicit sequencing after the Type A/Type B reframe (2026-09-20)

Critic's concrete next-step instruction: rebuild the breach study under the CURRENT SL/target architecture (Primed Gate + ATR0 structural stop + ZigZag target with R_FLOOR=1.0 + swing-low trail + MAX_HOLD=15), since every prior breach finding predates the target-floor/R-floor fixes. Froze this exact mechanism as the control population (n=6,201, matches the R_FLOOR=1.0 table from earlier today within noise) and recomputed breach-day (entry-day) OHLCV features fresh: overshoot, close/high/low-vs-trigger %, close-position-in-range, body/wick %, volume z-score, gap-at-open. Trigger-recross-count and time-of-breach were NOT recomputed — both require intraday data, and the only available intraday window (3-month, already tested 2026-09-20) already showed no usable signal there; not worth re-deriving from a sample that can't grow.

**Outcome A (stock swing, current engine) — the close-vs-trigger gradient reproduces cleanly, if anything slightly stronger than before the rebuild.** Full 10-decile ladder: win 35.4%→77.4%, expectancy -2.29%→+7.76%, R-multiple -0.14→+0.55, all monotonic. Confirms breach quality still matters exactly as before under the new stop/target mechanics — the earlier finding wasn't an artifact of the pre-fix architecture.

**A new sub-finding, only visible at full population scale**: only 3.0% of trades (188/6,201) have a day where the Low never dips back below the trigger at all intraday. That small group is dramatically better than the rest: 80.9% win/+8.04% exp/0.58R vs. 54.3%/+1.34%/0.10R for the 97% that do dip. This scales up (188 vs. the earlier 27-trade hint) and confirms the same "immediate, zero-pullback hold is a real edge" signal flagged as too-thin-to-trust on 2026-09-20's intraday check — now visible in the full daily-bar population too, not just the narrow 3-month intraday window. Still very rare (3% of trades), so not something to build a live gate around, but a real, confirmed pattern.

**Outcome B (real options, day+1-open, current engine) — pulled the full population (n=3,383 matched, the largest single option pull this project has run) and reproduces RQ-90A/B almost exactly.** Correlation with close_vs_trigger_pct drops to a weak 0.053 (vs. 0.281 for the stock outcome) — confirms RQ-90A's "threshold effect, not a ladder" finding: decile 0 (worst) is clearly worst (49.3% win/-1.74% mean), deciles 1-9 overlap with no clean ordering (55.7-66.9% win, +0.69% to +3.55% mean). No other breach feature (overshoot, wick %, volume z-score, gap-at-open) shows a meaningfully stronger correlation with options outcome (all under 0.08) — close-vs-trigger remains the standout signal.

**Worst-tail significance reproduces the RQ-90B band almost exactly on the fresh current-engine sample**: worst 5% through 12% all significant (p<0.05, mean -1.4% to -2.4%), fading outside that range (worst 3-4%: not significant, too few trades; worst 15%+: mean shrinks toward zero, not significant). Median inside the band stays ≈0% throughout while mean is meaningfully negative — same tail-risk shape as before, now confirmed on an independently-rebuilt population under the corrected SL/target mechanics rather than carried over from before the rebuild.

**Critic's requested gap-attribution validation, done**: for the worst 5-11% band specifically (n=203 after matching to daily stock data), split day+1's real stock gap into gap-down (<-0.5%), flat, gap-up (>+0.5%):

| Gap category | n | Freq | Mean opt pnl | Median opt pnl |
|---|---|---|---|---|
| Gap-down | 28 | 13.8% | **-12.40%** | -8.48% |
| Flat | 127 | 62.6% | -1.19% | +0.27% |
| Gap-up | 48 | 23.6% | **+5.92%** | +4.24% |

This answers critic's exact question directly. **Most of the band's negative mean comes from the 13.8% that gap down catastrophically** (-12.4% mean, a real, severe overnight-gap loss) — the mechanism the "exit at close" rule is specifically meant to avoid, and it would. **But the rule is not a free lunch**: 23.6% of the same band gaps up strongly (+5.92% mean) — real winners that an unconditional "exit the worst band at close" rule would also kill. The majority (62.6%) is roughly flat either way. Net effect of the rule on this band would be trading away a real +5.92%-mean subgroup to avoid a real -12.40%-mean subgroup — asymmetric in the right direction for a risk-averse objective (removes a fat left tail at the cost of some right-tail upside), but not without cost, exactly as critic anticipated.

**Concentration check, an honest caveat**: worst-10-trades' share of the band's total negative pnl is 33.7% (up from 18.3% on the earlier, larger 4,276-sample pull) — elevated, closer to the 40% danger threshold than before, though not over it. With n=203 for this specific 5-11% sub-band (smaller than the full worst-band samples pulled earlier), a handful of large losers matter more; worth another look if the sample grows further.

**Independence check, current engine**: close_vs_trigger_pct correlation with fresh (-0.17), initial_risk_pct (-0.11), is_delta (0.13) — all still weak, confirms this remains genuinely new information, not a restatement of an existing filter.

**Conclusion**: RQ-93 confirms the entire RQ-90 arc survives the current-engine rebuild essentially unchanged in shape and magnitude — nothing from the target-floor/R-floor fixes invalidated the earlier breach-quality findings. The one genuinely new piece of information is the gap-attribution result: the worst-5-11% overnight signal is real and is substantially (though not entirely) a gap-down phenomenon, but an unconditional "exit at close" rule on that band would also sacrifice a non-trivial gap-up subgroup — a real, quantified trade-off for critic/the user to weigh before promoting the rule, not a clean win.

## RQ-91B — exact reconstruction of the old bullish/bearish OI-buildup signal, retested against the current weak-breach gap-down/gap-up question (2026-09-20)

Per critic's explicit instruction: research archaeology first, not a new indicator, and not a repeat of RQ-91A's quadrant framework.

**Step 1 — recovered the exact old definition, from the codebase's own history and docstrings, not from memory.** `oi_buildup_bullish(ticker, date)` (`option_backtest.py`): front-month FUTURES price and open interest, trailing `OI_BUILDUP_WINDOW=3` trading-day window ending ON `date` itself (uses that day's own EOD bhavcopy — computed AFTER close of the entry/breach day, never intraday). Pure binary: `last_price > first_price and net_oi_chg > 0` (magnitude-weighting was tested 2026-09-17 and rejected — binary formulation wins). Returns `None` (not `False`) when no real futures data exists (non-F&O ticker or pre-2024 bhavcopy gap, which carries no futures OI columns at all) — this distinction was the exact bug that caused the original 2026-09-06 rejection (58.8-60.9% of trades were silently misclassified "absent" when the honest answer was "no data"). History: rejected 2026-09-06 (backwards result, data-bug-contaminated) → revived and reversed 2026-09-17 under corrected freshness/concentration/options methodology (RQ-48) → promoted to **Audit-Gate telemetry only, never a live gate** (EOD-only, structurally can't be intraday) → reversed AGAIN within the true-Unique(15d) tail specifically (2026-09-20, this weekend's RQ-52 spot-check) → RQ-91A's quadrant framework found it inconclusive (p=0.069). Critic's own read on this history stands: "this exact classifier flipping between rejected/reversed depending on conditioning."

**Step 2 — reproduced the original "useful" result before touching anything new.** Recomputed summary stats directly from the still-existing `runs/oi_buildup_retest.csv` (n=2,579, the exact population RQ-48's promotion was based on): Freshness-only 58.9% win/+0.237% swing exp → buildup present (n=684) 61.1%/+0.725% → buildup absent (n=1,895) 58.0%/+0.061%. Matches the FINDINGS.md-recorded numbers (686/60.9%/+0.715%) within rounding noise (3 rows were patched for a stale-cache bug after original publication). **Confirmed: the code and cached data reproduce the historical result cleanly** — no drift, no need to investigate a decay/bug before proceeding.

**Step 3 — retested against the actual current problem: does OI buildup distinguish the gap-down tail from the gap-up/right-tail within RQ-93's weak-breach band?** Computed the real, current `oi_buildup_bullish()` (not the frozen historical reconstruction) for the full RQ-93 real-option population (n=3,383) — 69.6% real coverage (2,353 resolved True/False, 1,030 `None` for no-data).

**(a) Population-level, this sample: the signal reverses yet again.** Buildup present (n=749): 56.7% win/+1.39% mean vs. buildup absent (n=1,604): 59.2%/+2.24% — buildup PRESENT now underperforms, opposite of RQ-48's original direction. One more data point for the same "flips depending on conditioning" pattern, not a new phenomenon.

**(b) Within the worst 5-11% band (n=149 with known buildup status): same reversed direction, more pronounced.** Buildup present (n=53): 49.1% win/**-3.01%** mean vs. buildup absent (n=96): 47.9%/**-0.42%** mean. If bullish OI buildup meant anything like "genuine support, not dangerous," presence should make the weak-breach band's outcome *better* — it does the opposite here.

**(c) The literal killer question — gap-down vs. gap-up within the band, buildup-conditioned (n=149 known-buildup, matched to real stock gaps):**

| Gap category | Buildup | n | Mean opt pnl | Median |
|---|---|---|---|---|
| Gap-down | False | 13 | -8.77% | -6.95% |
| Gap-down | **True** | 8 | **-19.08%** | -19.28% |
| Flat | False | 66 | -1.14% | 0.00% |
| Flat | True | 30 | -2.54% | +0.09% |
| Gap-up | False | 17 | **+8.76%** | +5.29% |
| Gap-up | **True** | 15 | +4.61% | +4.78% |

**Consistently wrong-signed in all three gap categories**: bullish OI buildup presence makes the gap-down subgroup's loss WORSE (-19.08% vs -8.77%), and makes the gap-up subgroup's gain SMALLER (+4.61% vs +8.76%) — the opposite of the hoped-for mechanism ("buildup present distinguishes a genuinely-supported, likely-gap-up move from an unsupported, dangerous one"). Checked the gap-down+buildup=True group (n=8) isn't a single-outlier artifact before trusting it: 5 of 8 individual trades lose more than -13% (POLYCAB -30.4%, BIOCON -34.4%, IPCALAB -35.9%, NATIONALUM -25.0%, ANGELONE -13.6%), median -19.28% close to the mean — broad-based within the tiny group, not one blown-up trade.

**Honest conclusion, appropriately caveated for sample size (each cell is n=8-17): the original bullish/bearish OI-buildup signal does NOT solve the gap-down-vs-gap-up separation problem, and if anything points consistently in the wrong direction across all three gap categories.** Not a confident rejection — samples this thin (n=8-17 per cell) can't support a strong claim either way — but a clean, internally consistent, non-cherry-picked negative result across every subgroup tested, using the exact signal and methodology that was previously found useful in a different, unconditioned context. Matches the now well-established pattern (RQ-48/RQ-52/RQ-91A) that this classifier's direction depends heavily on what population it's conditioned on, and within tail/weak-breach populations specifically, it has now reversed sign three separate times (Unique(15d) tail, RQ-91A's quadrant framework trending the "wrong" direction, and now this gap-attribution test).

## Prospective close-time carry-vs-exit economic validation, per critic's Update 94 directive — a real, out-of-time-robust candidate found (2026-09-20)

Critic's exact ask: not another worst-N%-selection significance test, but a full economic accounting (avoided downside vs. sacrificed upside) across regions derived from the feature's own distribution, then validated out-of-time/across regimes, before calling anything a candidate.

**Setup**: `opt_pnl_pct` (entry-day option Close → day+1 option Open) IS already the exact "hold overnight vs. exit at close" quantity, since the entry-day Close is the backtest's own close-time-value proxy — no new metric needed. For each region: mean/median pnl, 5th-percentile tail loss, gap-down/gap-up frequency (real stock day+1 gap, matched for the full n=3,383 population this time, not just the earlier 203-trade sub-sample), winners-sacrificed (n and $-sum of positive-pnl trades that an exit-at-close rule would kill), avoided-loss-sum (total negative pnl an exit rule would recover), and net exit value (avoided-loss minus sacrificed-upside, netted — positive means exiting the region is a net economic win).

**Fixed, meaningful regions first (the original close-vs-trigger bucket scheme, not reverse-engineered from outcomes)**: below-trigger (n=1,367), 0-1% (n=957), 1-3% (n=766), 3%+ (n=293). **Every single one of these is net-negative to exit** (net values -1,646.6, -2,557.2, -2,022.3, -603.3) — the broad "close below trigger" cut from the original RQ-90B first pass was never actually a good rule on full economic accounting, consistent with that finding's own later correction (the whole below-trigger group is itself net-positive).

**Finer deciles reveal exactly one region that's genuinely net-positive to exit**: decile 0 only (net value **+590.5**), every other decile (1-9) net-negative (-234.5 to -1,201.2). Decile 0 = close_vs_trigger_pct < -1.16% (100% below-trigger, but a much narrower, more extreme cut than the full below-trigger bucket) — n=339, mean -1.74%, gap-down freq 11.2%, gap-up freq 23.9%, winners-sacrificed 167 trades/+1,203.1 vs. avoided-loss -1,793.6.

**Out-of-time / regime robustness, checked before calling this a candidate**:
- Chronological split (first half vs. second half by entry_date): both net-positive (+388.2 and +202.3) — no reversal.
- Every individual year 2022-2026 independently net-positive (+106.7, +122.8, +163.9, +57.1, +140.1) — genuinely consistent across 5 separate years, not one lucky year.
- **2023-regime-dependency check (given this project's own documented 2023-concentration caveat) comes back clean here**: non-2023 years contribute *more* net value (+467.7) than 2023 alone (+122.8) — unlike several earlier findings this weekend, this one is NOT a 2023 artifact.
- Concentration check: worst-10-losers' share of decile 0's total negative pnl is 21.1% (healthy, well under the 40% danger threshold).

**Conclusion: this is a genuine, out-of-time-validated candidate** — a close-time carry/exit rule specifically at "stock closes more than ~1.16% below the trigger by end of day" (roughly the worst 10% by this metric) recovers more real value than it sacrifices, consistently across time, regime, and concentration checks. Narrower and more precise than any of the fixed round-number buckets, and specifically NOT derived by searching for where the worst outcomes happened — it emerged from a systematic decile scan of the same already-validated feature. Per critic's own decision tree: this clears the "works → validate robustness" bar — ready to discuss as an actual candidate rule, not just telemetry.

## RQ-95 promoted, local threshold stability confirmed; RQ-96 (intraday deterioration exit) hits a real, structural data blocker (2026-09-20)

**Local threshold stability around -1.16%, per critic's explicit ask before treating it as more than a lucky spike** — cumulative net exit value ("exit everything with close_vs_trigger_pct below this threshold") across a neighborhood of cuts:

| Threshold | n | Mean | Net exit value |
|---|---|---|---|
| -0.50% | 785 | -0.23% | +178.9 |
| -0.75% | 586 | -0.68% | +399.4 |
| -1.00% | 424 | -1.21% | +512.0 |
| **-1.16%** | 337 | -1.73% | **+584.5** |
| -1.25% | 301 | -1.71% | +513.7 |
| -1.50% | 210 | -2.14% | +449.1 |
| -1.75% | 146 | -2.18% | +318.4 |
| -2.00% | 109 | -1.90% | +206.8 |
| -2.50% | 52 | -5.58% | +290.3 |
| -3.00% | 30 | -9.24% | +277.2 |

**Positive across the entire neighborhood, never crosses zero, peaks around -1.0% to -1.16%** — a genuinely stable extreme-weak-close regime, not a lucky boundary at exactly -1.16%. Confirms RQ-95 as a real candidate, not calibration-dependent. **RQ-95 formally promoted to candidate status**, per critic: "at EOD, if close_vs_trigger_pct < ~-1.16%, do not carry the long option overnight; exit at close" — architecture unchanged (Primed Gate → breach → enter → hold → EOD carry decision → Day+1 open), not a new entry filter.

**RQ-96 (does exiting at the first INTRADAY breach of the -1.16% level beat waiting for EOD) hits a real, structural data blocker, not a sample-size problem alone.** Two separate issues, both material:

1. **No intraday option price data exists anywhere in this project.** NSE's F&O bhavcopy (the only options data source used throughout) is EOD-only — confirmed repeatedly this session (RQ-91A's fetch investigation, the whole day+1-open-vs-close-to-close methodology). There is no way to compute a real option premium at an arbitrary intraday moment. Any intraday-exit economics would have to use a stock-price-proportional proxy for the option move — exactly the approximation this project has already twice found unreliable this session (the flawed stock-proxy correlation of 0.937 for close-vs-trigger collapsed to a real 0.137 once actual option premiums were used). Building RQ-96 on that same proxy would repeat a mistake already caught and corrected twice.
2. **The available intraday stock data is far too thin to even attempt the stock-only half of the question properly.** The only 5-min intraday cache covers a single 3-month window (2026-06-10 to 2026-09-18, already flagged as thin/single-regime in the 2026-09-20 breach-behavior check). Of the full 3,383-trade population, only 21 land in this window AND qualify for the -1.16% weak-close gate. A quick check of all 21 found "crosses the breach level intraday" trivially true 100% of the time, with 14/21 crossings timestamped at the very first 09:15 bar — a red flag that the check isn't correctly sequencing the crossing relative to when the trigger was actually touched (a stock that gaps up through the trigger and pulls back within the same opening range can show its day's Low below the breach level in the very first bar, before the "entry" that supposedly precedes any "deterioration" has meaningfully happened). Fixing that sequencing bug wouldn't fix the sample-size problem (n=21, one regime).

**Honest conclusion, not forced through with an inferior proxy**: RQ-96 as scoped cannot be properly answered with current data. This is a genuine data-availability gap (no intraday option prices exist in this project, ever) plus a genuine sample-size gap (n=21 in the only intraday window available), not something more analysis effort can route around. The EOD close-time gate (RQ-95) is the ceiling of what the current data can support — an intraday version would need either real intraday option pricing (a different, unavailable data source) or a much larger intraday stock cache before even the stock-only half of the question could be tested honestly.

## RQ-95's real-world firing frequency, and a second, failed attempt at RQ-96 via a calibrated stock-price approximation (2026-09-20)

**Firing frequency, a real operational question worth stating plainly**: the -1.16% gate is not a rare tail event — it fires on **15.3%** of the full Primed Gate population (n=6,201) and **10.0%** of the real-option-matched subsample (n=3,383, the population all the RQ-95 net-value numbers were computed on). Roughly 1 in 7-10 trades. The earlier net-value numbers already reflect this full firing rate — not diluted by rarity, not a lucky-tiny-sample artifact.

**Second attempt at RQ-96 (intraday deterioration exit), per direct user instruction to try an approximation rather than declare it unanswerable outright.** Built a per-trade calibrated linear scaling factor from real same-day data — `(option's entry-day Close − Open) / (stock's entry-day Close − Open)` — applied to the stock's real intraday price at the actual crossing moment (properly sequenced this time: the crossing must occur strictly after the bar where the stock's High first touches the trigger, fixing the earlier sequencing bug that let a gap-through-then-pullback masquerade as a false "crossing" before entry). n=19 (of 53 weak-close candidates in the one available intraday window, most lost to no-real-option-match).

**Result: the approximation is uninformative, not just noisy.** Correlation between the approximated "exit at crossing" pnl and the real overnight outcome (`opt_pnl_pct`) is **0.0004** — statistically zero. Several individual values are implausible on inspection (e.g., TMPV's interpolation implies the option was worth *more* at the intraday crossing than at the day's open, despite both the stock and option ultimately closing lower that day).

**Why it fails, not just that it does**: a straight line between only two points (the entry day's Open and Close) is a poor model of an option's actual intraday path — real option prices move on gamma (an accelerating/decelerating relationship to the stock as it moves), vega (intraday IV wobble), and a generally choppy, non-monotonic path over a multi-hour session, none of which a 2-point linear interpolation can capture. It doesn't add bounded noise to a real signal — it points in essentially random directions relative to the true path, actively misleading rather than merely imprecise.

**Honest conclusion, unchanged from the first attempt but now with a concrete method-level reason why**: RQ-96 (intraday deterioration exit) cannot be answered with a linear approximation over this data — the problem isn't the concept, it's that a 2-point interpolation is the wrong tool for path-dependent option pricing. A meaningfully better approximation would need either (a) a mid-session anchor point beyond just Open/Close (not available — no intraday option data exists at any granularity), or (b) a real options-pricing back-out (Black-Scholes using known strike/spot/DTE, assuming a flat or entry-day-implied IV) — a materially heavier build than a quick script, not attempted here, flagged to critic as a real infra question rather than pushed through.

## RQ-96 parked (blocked on data, per critic); severity-curve check on RQ-95's left tail, per critic's follow-up question (2026-09-20)

**RQ-96 formally parked**: "EOD option data cannot identify whether an intraday -1.16% breach should trigger an earlier exit. Stock-only interpolation and two-point option scaling were tested and rejected as invalid proxies. Reopen only if genuine intraday option quote/trade data becomes available." Not pursuing a Black-Scholes back-out per critic's explicit reasoning (would model the exact unknown the research is trying to discover — self-referential risk).

**Severity curve, per critic's exact ask: does the economic damage accelerate as the close gets further below trigger, or is -1.16% just separating a bad population from the rest?** Marginal (non-cumulative) bands, real option data (n=3,383), plus each band's share of the full Primed Gate population:

| Band | n (options) | % of full Primed Gate | Mean opt pnl | Median | Gap-down | Gap-up | Net exit value |
|---|---|---|---|---|---|---|---|
| 0 to -1% | 943 | 23.3% | +2.29% | +1.98% | 7.2% | 27.8% | -2,158.6 |
| -1 to -1.5% | 214 | 6.2% | -0.29% | +0.40% | 14.5% | 24.8% | +62.9 |
| -1.5 to -2% | 101 | 4.3% | -2.40% | -0.20% | 8.9% | 20.8% | +242.3 |
| -2 to -3% | 79 | 4.0% | +0.89% | +0.28% | 6.3% | 30.4% | -70.4 |
| -3 to -5% | 25 | 2.3% | -9.40% | -11.47% | 24.0% | 16.0% | +235.1 |
| < -5% | 5 | 0.8% | -8.43% | 0.00% | 40.0% | 40.0% | +42.2 |

**Honest answer: neither story cleanly wins.** It is NOT a smooth, accelerating deterioration curve — the "-2 to -3%" band flips back net-positive (+0.89% mean, net exit value -70.4, i.e. holding beats exiting there), breaking a monotonic-severity story. But it's also not simply flat/noise — mild weakness (0 to -1%, by far the largest band at 23.3% of the whole population) is clearly, robustly a *good* outcome (+2.29% mean, strongly net-negative to exit), while every band beyond -1% is at or near net-positive-to-exit. **Most likely honest read: the marginal bands beyond -1% are individually too small (n=214 down to n=5) to resolve a clean shape — real sampling noise, not a real "recovery zone" at -2 to -3%.** The cumulative view from the earlier threshold-stability check (which pools all these noisy bands together) is the more trustworthy signal and remains solidly positive throughout -0.75% to -3%.

**On "is -1.16% a meaningful transition point or just a common failure mode"**: the population-share column is the clearer answer here. Share drops sharply right around this boundary — 23.3% for mild weakness (0 to -1%, and this large group is *not* dangerous) down to 6.2% for -1 to -1.5%, continuing to shrink from there (4.3%, 4.0%, 2.3%, 0.8%). So -1% does mark a real transition in *prevalence* (ordinary noise gives way to a much smaller, minority regime) even though the per-band economics curve itself is too small-sample-noisy beyond that point to call a clean accelerating gradient. **Conclusion: -1.16% is closer to marking the start of a genuinely less-common regime than to being an arbitrary cut through a smooth continuum — but the fine-grained shape inside that regime can't be resolved with the current sample size.** No new threshold search follows from this — consistent with critic's explicit instruction not to turn this into a cutoff hunt.

## RQ-95A — deterioration-severity shape, with the 5th-percentile tail and cumulative population share added, per critic's exact spec (2026-09-20)

Same frozen 3,383-trade real-option population, no new model, no parameter search — just the requested table with p5 added:

| Band | n | Mean | Median | p5 | Net exit value | % of full Primed Gate |
|---|---|---|---|---|---|---|
| 0 to -1% | 943 | +2.29% | +1.98% | -14.73% | -2,158.6 | 23.3% |
| -1 to -1.5% | 214 | -0.29% | +0.40% | -18.46% | +62.9 | 6.2% |
| -1.5 to -2% | 101 | -2.40% | -0.20% | -26.63% | +242.3 | 4.3% |
| -2 to -3% | 79 | +0.89% | +0.28% | -17.41% | -70.4 | 4.0% |
| -3 to -5% | 25 | -9.40% | -11.47% | -40.52% | +235.1 | 2.3% |
| < -5% | 5 | -8.43% | +0.00% | -26.04% | +42.2 | 0.8% |

**Cumulative "below -X%" population share (full Primed Gate, n=6,201)**: below -1% = 17.6%, below -2% = 7.05%, below -3% = 3.06%, below -5% = 0.76%. A classic decaying-tail failure distribution — each doubling of severity roughly halves (or better) the population share, matching critic's hypothesized "normal-looking failure distribution with a progressively smaller severe tail" almost exactly.

**Which of the three outcomes: none of them cleanly, but closest to (3) messy, with one real exception.** Not (1) clean monotonic deterioration — the mean bounces (0.89% at -2 to -3%, better than -1 to -1.5% and -1.5 to -2%). Not (2) a clean step function either — the bands below -1% range from +0.89% to -9.40%, not a uniform "similarly bad" level. **But the 5th-percentile column tells a more consistent story than the mean does**: -14.73% → -18.46% → -26.63% → -17.41% → -40.52% — not perfectly monotonic either, but the tail clearly widens with severity in a way the mean doesn't (roughly 3x worse by -3 to -5% than at 0 to -1%). Consistent with the standing tail-risk framing already established for RQ-90B/95 (median near zero, mean dragged down by a real minority) — the marginal bands are individually too small (n shrinking 943→214→101→79→25→5) to resolve the mean's fine shape cleanly, but the widening tail risk is visible even at this sample size.

**Honest conclusion, per critic's own framing**: -1.16% doesn't represent a clean "deterioration mechanism" with an accelerating gradient, nor is it an arbitrary cut through flat noise — it sits at a real, sharp drop in population share (23.3%→6.2% just past -1%) with a genuinely widening tail-risk beyond it, but the marginal mean's shape inside that regime is not resolvable at current sample size. RQ-95 remains a valid, independently-demonstrated empirical candidate on its own economic accounting (already validated via the earlier out-of-time robustness checks) — the more defensible framing per critic: "extreme close deterioration carries real, widening tail risk; -1.16% is where the accounting first turns net-positive, not a discovered natural boundary of a smooth mechanism." No new threshold search follows from this, per critic's explicit instruction.

## RQ-90→RQ-95 arc formally closed by critic; Freshness capacity-constrained validation — the deferred test finally run, decisive result (2026-09-20)

Critic closed the whole arc: RQ-90 close (stock ladder + options tail-risk), RQ-91A park/closed, RQ-91B close, RQ-93 close, **RQ-95 promoted to candidate** ("EOD close deterioration below ~-1.16% → exit option rather than carry overnight"), RQ-95A close (tail evidence real, mean shape not resolvable, no further threshold search), RQ-96 parked/data-blocked. Explicit instruction: stop tuning -1.16%, move to the next queue item — Freshness capacity-constrained validation ahead of Type-B/max-hold research, since Freshness already has a partially-established signal and an explicit prior deferral (2026-09-20 Update-75 verdict: "should NOT be chased into a capacity test right now... doing so now would be optimizing entry filtering before seeing how the new SL and target actually work" — that condition is now satisfied, the whole target-floor/R-floor/Primed Gate architecture has since settled).

**Reused the exact deterministic max-N-concurrent-positions methodology** (2026-09-07 Risk-of-Ruin precedent, FCFS chronological admission, no ranking, already used to correctly reject then re-validate Fixed-R) — on the CURRENT settled architecture (`rq128_breach_merged.csv`, n=6,182 with valid fresh+r_multiple), comparing three populations: No filter, Fresh≤0.40 (current), and the parked two-sided variant (Fresh≤0.20 OR ≥0.80, which looked best on unconstrained per-trade/total metrics back on 2026-09-20's original U-shape investigation):

| Slots | No filter (admitted/cumR/maxDD/streak) | Fresh≤0.40 (admitted/cumR/maxDD/streak) | Two-sided (admitted/cumR/maxDD/streak) |
|---|---|---|---|
| 3 | 240 / +33.33R / -4.32R / 4-−3.51R | 242 / **+37.17R** / -8.09R / 5/-4.72R | 239 / +28.94R / -12.02R / 6/-3.84R |
| 5 | 397 / +53.34R / -8.64R / 7/-5.26R | 397 / **+62.47R** / -12.52R / 8/-6.98R | 393 / +59.09R / -11.45R / 6/-4.52R |
| 10 | 787 / +117.32R / -15.74R / 11/-8.11R | 771 / **+144.36R** / -11.55R / 8/-6.64R | 764 / +127.96R / -12.46R / 9/-6.17R |
| 20 | 1,524 / +196.26R / -23.62R / 12/-9.60R | 1,474 / **+242.79R** / -25.75R / 12/-9.22R | 1,425 / +215.47R / -23.81R / 10/-8.68R |
| 50 | 3,343 / +435.55R / -64.05R / 20/-15.40R | 3,066 / **+448.67R** / -55.60R / 16/-12.84R | 2,756 / +387.21R / -48.73R / 20/-14.45R |

**Decisive, robust result: current Fresh≤0.40 beats BOTH no-filter AND the two-sided variant on cumulative R at every single slot count tested (3, 5, 10, 20, 50)** — this is the opposite conclusion from the earlier unconstrained-total-sum check (which favored no-filter purely by raw trade count). The mechanism: at low-to-moderate capacity, the number of trades actually admitted is nearly identical across all three populations (capacity, not candidate-pool size, is the binding constraint — there's always a queue) — so restricting the candidate pool to higher-quality setups doesn't cost admitted trade count the way it did for the throughput-sensitive Fixed-R/MAX_HOLD_DAYS questions; it just changes WHICH trades fill the same number of slots, and Fresh≤0.40's average R per admitted trade is higher.

**Drawdown/streak are genuinely mixed and capacity-dependent, same pattern already documented for Fixed-R**: Fresh≤0.40 is worse (deeper drawdown, costlier streak) than no-filter at low capacity (3, 5 slots) but better at higher capacity (10, 20, 50 slots) — plausibly a diversification effect (fewer candidates at very low slot counts means less opportunity to offset a bad stretch with an unrelated concurrent position).

**The two-sided variant, which looked like the strongest per-trade candidate in the original unconstrained U-shape investigation, does NOT survive this test** — it underperforms current Fresh≤0.40 on cumulative R at every slot count (e.g. slots=10: 127.96R vs 144.36R) and shows the worst max drawdown of the three at low capacity (slots=3: -12.02R). **Conclusion: the current one-sided Fresh≤0.40 filter is validated under a realistic capacity constraint — it was never actually a throughput trap the way Fixed-R/MAX_HOLD_DAYS tightening was, and the two-sided "fix" proposed back on 2026-09-20 is rejected, not adopted.** This closes the "unresolved per-trade-quality-vs-total-output trade-off" flagged at the time — the current production Freshness gate stands as-is, no change needed.

## Production gap audit + RQ-95 execution-timing decision, weekend freeze (2026-09-20)

**Audit, before any implementation work starts**: checked the real code (`backtest.py`, `daily_scan.py`, `monitor_positions.py`) rather than assume the weekend's settled architecture was already live. It is not — everything this weekend (ATR0, ZigZag+R_FLOOR target, swing-low trail, Freshness-as-capacity-filter, RQ-95) exists only in scratchpad research scripts. Production still runs: `STRUCTURAL_STOP_ATR_BUFFER=1.0` (not ATR0), `resistance_target()` pivot-point target (not ZigZag+R_FLOOR), `SMA21`-based trail (not K=2 swing-low). `MAX_HOLD_DAYS=15` and `TRAIL_ENGAGE_PCT=1.08` do match. `daily_scan.py`'s own candidate list still calls the close-based `detect_entry()`/`entry_signal()` — real intraday Primed Gate tracking exists only in `live_checkpoint.py`'s separate monitoring path. Freshness≤0.40 has no live enforcement anywhere (backtest-only convention). This is a real, scoped implementation task for whenever picked up next — not a config change.

**RQ-95 execution timing, user's own operational call, overriding my first-pass 3:20-3:28 PM suggestion**: check and act **2:45-3:15 PM**, not later. Reasoning: RQ-95's candidate population is specifically the weak-breach/deteriorating group, which RQ-90C already showed carries materially lower volume all day (z-score 2.48 vs 5.76 for healthy trades) — this is exactly the population where option liquidity is most likely to thin further into the last 15 minutes of the session, compounding the risk of a bad fill right when trying to exit. Trading a small amount of estimation accuracy on the exact final close for a materially safer, more liquid execution window is the right call given the objective is avoiding a bad overnight outcome, not optimizing the last few paise of the close price. Recorded as the answer to critic's own production-validation checklist item #5 ("EOD option exit is actually executable with available liquidity").

## Production gap #1 closed — `primed_engine.py` built, verified against research, wired into `monitor_positions.py` with RQ-95 (2026-09-20)

Built a new module, `primed_engine.py`, rather than modify `backtest.py` in place — the existing test suite (72 tests) exercises `backtest.py`'s legacy `detect_entry()`/`check_exit()`/`current_stop_level()`/`resistance_target()` directly, and those serve VCP/coiled_spring plus legacy comparisons, per the standing 2026-09-20 governance decision ("detect_entry()/Entry Gate is legacy-only... retained only for legacy comparisons and regression testing"). Zero changes to `backtest.py` itself — `primed_engine.py` imports its shared constants (`MAX_HOLD_DAYS`, `TRAIL_ENGAGE_PCT`, `STRUCTURAL_LOOKBACK_BC`, `CLIMAX_*`) and adds the settled mechanism: `detect_primed_entry()` (base_filters_pass + real intraday trigger touch, no regime gate — matches `daily_scan.py`'s own `_passes_primed_checks()` convention), `find_zigzag_target()` (scipy, R_FLOOR=1.0 invariant), `check_primed_exit()`/`current_primed_stop_level()` (ATR0 stop, K=2 swing-low trail).

**Verified against the weekend's own research before wiring anything live**: spot-checked `simulate_primed_ticker()` against `rq128_breach_merged.csv` (the already-validated RQ-93 population) on the 15 most-traded tickers, 500 trades — 497 exact matches. The 3 differences: 2 are a cosmetic exit-reason label only ("open" vs "still_open" for a position still open at the data boundary — fixed, relabeled to match), 1 (TITAN) is a deliberate, correct difference — the research script never evaluated exit conditions on the very last cached day (a backtest-only safety convention for possibly-incomplete data), but a live position monitor should evaluate today's own stop/target, which `primed_engine.py` does. `python3 -m pytest tests/ -q` still 72/72 after the change, as expected — `backtest.py` untouched.

**Wired into `monitor_positions.py`, additively, not by repointing an existing label**: real open positions right now (`open_positions.csv`) include 3 live `breakout_cont` trades (GRANULES, ANANDRATHI, VIJAYA) and 1 `coiled_spring` (AEGISLOG) — their real broker stop-loss orders were set from the legacy mechanism (1.0x ATR buffer, pivot-point target, SMA21 trail). Repointing `breakout_cont` at the new engine would have silently changed this tool's displayed stop for those open positions to a number that no longer matches what's actually resting at the broker — a real, avoidable risk. Instead, added a new pattern label, `primed_bc`, dispatched separately in `monitor()`; `breakout_cont`/`coiled_spring` behavior is byte-identical to before (confirmed by running `monitor_positions.py` against the real `open_positions.csv` before and after — output unchanged for all 4 existing positions). Log new entries as `primed_bc` going forward to get the settled architecture; the 4 existing ones stay on their original mechanism until they close naturally.

**RQ-95 (EOD overnight-option-carry gate) implemented as `primed_engine.overnight_carry_recommendation()`**, wired into `monitor()`: for any `primed_bc` position whose `entry_date` is the most recent cached trading day (i.e., checked on the evening it was entered), prints the `close_vs_trigger_pct` and a carry/exit recommendation against the `-1.16%` threshold. Advisory only for the options decision — does not touch the stock position's own exit logic in any way. Smoke-tested end to end (both the normal day-N stop/target path and the entry-day overnight-check path) against real cached data before considering this done.

**Explicitly NOT changed, flagged as the next open decision rather than silently done**: `daily_scan.py`'s own candidate-generation (`scan()`) still calls the legacy, close-based `detect_entry()`, not `detect_primed_entry()` — the daily candidate list a user reviews is not yet using the real intraday-touch Primed Gate mechanism for pattern/stop/target display. This is a more visible, higher-blast-radius change (it changes which stocks appear as candidates each day and what stop/target they're shown with) than the additive `monitor_positions.py` change above, and wasn't made without explicit confirmation first.

**Freshness stays telemetry-only, per explicit instruction** — no live admission gate was added despite tonight's capacity-constrained validation; that result is recorded as a research finding only, not wired into `shortlist_primed()`/`scan()`/anywhere live.

## Production gap #2 found and closed — `EMA34_RISING_DAYS_MIN` was still 9, never actually flipped to 2 after its 2026-09-18 sign-off (2026-09-20)

Caught by direct user question while reviewing the refreshed primed list ("wasn't EMA34=2 signed off like ATR0?"). Checked `signals.py` directly: `EMA34_RISING_DAYS_MIN = 9`, the OLD value — despite the 2026-09-18 entry "EMA34=2 — PROMOTED TO v31.1 CANDIDATE... ready to move from research validation into v31.1 implementation and live/paper validation." Same category of gap as the ATR0/target/trail fix earlier tonight: validated and signed off, but never actually wired into the live default. Root cause of why this was invisible all weekend: every research script sets `signals.EMA34_RISING_DAYS_MIN = 2` at the start and resets it to `= 9` at the end (to restore "the default") — that reset was itself restoring the wrong value the whole time, silently masking the gap in every research run.

**Verified no test depends on the specific value** (`grep EMA34_RISING_DAYS_MIN tests/` — zero hits; the one test using `ema34_rising10` values that could be threshold-sensitive, `_passing_base_row()`'s `ema34_rising10=10`, passes under either 9 or 2) before changing anything. Flipped to 2, `python3 -m pytest tests/ -q` still 72/72.

**Real effect on today's primed list, worth being direct about since it's the opposite of what was expected going in**: correcting the value made the list slightly BIGGER, not smaller — 39→46 tickers, 11→14 F&O names (added ADANIPORTS, BHEL, MAXHEALTH). The intuition that fixing this would shrink the F&O count was wrong; EMA34=2 is a *looser* persistence requirement (2 of the last 10 days rising, vs. 9 of 10), so it structurally admits more candidates, not fewer, exactly as its own research characterized it ("captures a large, genuinely distinct population... 82.7% of Delta").

**Standing follow-up, not yet done**: any research script still setting `signals.EMA34_RISING_DAYS_MIN = 9` at the end of its run (the "restore the default" pattern used throughout this weekend) is now restoring the wrong value — should be corrected to restore 2 the next time any of those scripts are touched, not fixed proactively across all of them right now (per the project's own "fix forward, don't re-litigate everything at once" discipline).
