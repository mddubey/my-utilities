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
