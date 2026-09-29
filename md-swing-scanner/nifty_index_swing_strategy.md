# NIFTY Index Swing Strategy — standalone exploration (NOT part of the main project)

Separate from FINDINGS.md, PARKING_LOT.md, and zero_to_hero_observations.md on purpose.
This is index-level (NIFTY spot/options), multi-day swing research using real, sourced,
published mean-reversion methodology — a genuinely different character from both the main
stock-swing project (individual F&O names, BC/VCP patterns) and the zero_to_hero file
(deep-OTM near-expiry lottery bets). Not critic-reviewed, not wired into any other file's
research-integrity process. Real data, real numbers, own standing.

---

## 2026-09-27 — Origin and method

Started from a live question about a real RBLBANK support/pinbar bounce, generalized into
NIFTY index-level intraday exploration, which hit a hard data ceiling (no real intraday
NIFTY options data anywhere accessible — `options_cache/` is EOD bhavcopy only, yfinance
has no NIFTY options chain). Pivoted to daily-timeframe strategies, which the project's data
actually supports well (5 years of real NIFTY daily OHLC, thousands of days of real NIFTY
options EOD bhavcopy since 2022-06).

Read real, published, sourced methodology rather than inventing a signal from scratch:
**Larry Connors / Cesar Alvarez, "Short Term Trading Strategies That Work"** — two specific,
well-documented mean-reversion systems:

1. **RSI(2)**: buy when RSI(2)<5 while above SMA200 (uptrend filter); exit when RSI(2)>65 OR
   Close crosses back above the 5-day SMA. Real cited result (SPY): 75-88% win rate, ~1.26%
   avg gain, ~3.7 day avg hold.
2. **Double 7s**: buy when Close makes a trailing-7-day low while above SMA200; exit when
   Close makes a trailing-7-day high. Real cited result (SPY since 1993): 77% win rate,
   ~7%/yr, no stop-loss in the original rules.

Both real event-driven trade simulations (not fixed-horizon forward-return snapshots) —
actual entry on signal, actual exit on the rule firing, on NIFTY's real 5-year daily
history (`data_cache/_NIFTY.csv`).

## Results — LONG side (validated, credible)

| Strategy | n | Win rate | Median ret/trade | Median hold | Cumulative (5yr, uncompounded) |
|---|---|---|---|---|---|
| RSI(2) Long | 19 | 68.4% | +0.28% | 4 days | +9.0% |
| **Double 7s Long** | **36** | **75.0%** | **+1.18%** | 8 days | **+21.7%** |

Double 7s Long is the standout — largest sample of anything tested in this whole NIFTY
exploration, win rate matches the cited SPY literature almost exactly (75.0% vs 77%),
mechanics are simple and unmodified from the published rules. Concentration check: top 4
trades (11% of sample) = 61.2% of total return — moderately concentrated, worth knowing,
not disqualifying for a real mean-reversion strategy (a few standout trades is normal for
this style).

RSI(2) Long is real but weaker than the cited benchmark (68.4% vs 75-88%), smaller sample
(n=19), hold period matches almost exactly (4d here vs ~3.7d cited).

## Results — SHORT side (only works with a corrected regime filter)

**First pass, mirrored rules exactly (Close<SMA200 as the downtrend filter)**: both sides
looked broken — RSI(2) Short 33.3% win/-2.1% cum, Double 7s Short 50.0% win/-5.6% cum.

**Diagnosed why, per direct user challenge**: split trades by whether they fell in the real,
sustained 2026 breakdown (Nifty's real ATH was 2026-01-02 at 26,328.55; last close above its
own 200-SMA was 2026-02-26) vs the 2022-2025 period, which was mostly a strong bull run
(~17,850 -> 26,215) with only brief, temporary dips below SMA200. Split cleanly:

| | Pre-breakdown (2022-2025) | 2026 breakdown regime |
|---|---|---|
| RSI(2) Short | n=4, 25.0% win, -4.90% | n=5, 40.0% win, +2.76% |
| Double 7s Short | n=5, 20.0% win, -11.36% | n=7, **71.4% win, +5.74%** |

**Tried ADX/DI (this project's own trusted stock-side regime tool) as a fix — it didn't
work, result was backwards** (ADX-confirmed "strong downtrend" trades did WORSE, not
better — plausibly because shorting into an already-strong, crowded downtrend risks getting
caught in a violent relief bounce). Read real research instead of guessing further:
**the SLOPE of the 200-day MA matters more than price's position relative to it** — "two
stocks can both have price at the 200-day MA, but if one has an upward-sloping 200-day and
the other has flat/declining, they represent very different technical situations."

**Rebuilt the SHORT entry filter as SMA200 itself declining (vs 20 days ago), not just
Close<SMA200, and reran as the actual entry rule (not a post-hoc split)**:

| Strategy (v2, SMA200-slope filter) | n | Win rate | Median ret/trade | Cumulative |
|---|---|---|---|---|
| RSI(2) Short v2 | 9 | 44.4% | -0.10% | +2.4% (concentration-failed, 95% from 1 trade — don't trust) |
| **Double 7s Short v2** | **12** | **75.0%** | **+0.84%** | +7.4% (54.9% from top 1 trade — real but lopsided) |

**Double 7s Short v2 now matches Double 7s Long's own win rate (75.0% both sides)**, and
critically the trades spread across 2022, 2025, AND 2026 — not just the current regime —
meaning the SMA200-slope filter is genuinely identifying real downtrend windows wherever
they occurred over 4 years, not just getting lucky on the current one.

## Standing conclusions

1. **Double 7s (both directions) is the most credible strategy found in this whole session**
   — real, published, unmodified methodology; results in the same range as the cited
   literature; the long side alone (n=36) is the best-powered result of anything tested.
2. **SMA200 position (Close vs SMA200) is not a trustworthy regime filter on its own** — it
   conflates real trend reversals with brief pullbacks inside a larger trend. **SMA200 slope
   (is the average itself rising or falling) is the corrected, validated version** — use this
   going forward for any regime-gated strategy on NIFTY, not raw position.
3. **RSI(2) doesn't hold up as well as Double 7s here** on either side — weaker win rate than
   cited literature (long) and concentration-failed (short v2). Not disqualified, just
   secondary to Double 7s.
4. Everything above is on the **index itself**, not yet translated into real options P&L —
   NIFTY weekly expiries land every ~5 trading days, and these strategies' median holds
   (4-10 days) typically span more than one weekly cycle, so a real options implementation
   needs an explicit expiry-selection rule (this project's own stock-side research already
   has a validated analog: ITM + next-month, chosen specifically to avoid this exact
   mid-trade-expiry problem) rather than assuming a weekly contract survives the hold.

## 2026-09-27 (continued) — Bank Nifty independent validation: LONG corroborated, SHORT fails

Fetched real Bank Nifty daily history (`data_cache/_BANKNIFTY.csv`, via yfinance, ~5yr) as
a genuinely independent second series and reran both Double 7s sides unchanged.

| | NIFTY | Bank Nifty (independent) |
|---|---|---|
| Double 7s LONG | n=36, 75.0% win | **n=40, 72.5% win — replicates** |
| Double 7s SHORT v2 (SMA200-slope filter) | n=12, 75.0% win | **n=5, 40.0% win, -1.5% cum — does NOT replicate** |

**Double 7s Long is now the one genuinely well-corroborated finding of this whole
exploration** — two independent indices, both close to 75%, both close to the original
cited SPY literature (77%). Trust this one.

**Double 7s Short v2 (the SMA200-slope fix) failed the independent test.** Only 40% win on
Bank Nifty, n=5 (small, but a clear miss, not a near-replication). Honest read: the
SMA200-slope filter likely wasn't a genuinely generalizable regime rule — more likely
calibrated to NIFTY's own specific 2026 decline shape than a real, transferable fix.
**Downgrading the short side back to "unresolved / doesn't reliably work"** — the earlier
"fixed it" conclusion doesn't survive independent validation and should not be treated as
solid. This is exactly why the corroboration check was worth running before building
anything further on the short side.

## 2026-09-27 (continued) — v3 refinement, and a real correction to the "why" explanation

First hypothesis (from real sourced research, but NOT verified against our own data before
writing it down — a mistake, corrected below): Bank Nifty is 1.5-2x more volatile than
Nifty, mean reversion needs range-bound conditions, so maybe Bank Nifty's confirmed
downtrends are less range-bound and blow through short levels instead of reverting.

**Added ADX<20 (range-bound, not strongly trending) on top of the SMA200-decline filter:**

| | NIFTY | Bank Nifty |
|---|---|---|
| ADX<20 | **n=7, 85.7% win, +1.16% median** | n=2 — too small to test either way |
| ADX<18 | n=6, 83.3% win, +0.95% median | n=1 — too small |

Real improvement on NIFTY (75.0%->85.7%). But the Bank Nifty sample nearly vanishing (n=2)
demanded checking the actual mechanism rather than accepting the plausible-sounding
research-based story — per direct user pushback ("population getting shrunk sounds like
that filter is too aggressive").

**Checked the real conditional distributions — the sourced hypothesis was WRONG:**

| | NIFTY | Bank Nifty |
|---|---|---|
| SMA200 genuinely declining (all days) | 16.7% (n=207) | **7.4% (n=92) — less than half** |
| Given declining, also ADX<20 (conditional) | 46.9% | **56.5% — HIGHER, not lower** |
| Joint (declining AND ADX<20) | 7.8% (n=97) | 4.2% (n=52) |

Bank Nifty is actually MORE likely to be range-bound during a confirmed downtrend, not
less — the "higher beta means less range-bound" theory does not hold up against our own
data. **The real, correct explanation: Bank Nifty simply spends less than half as much
time in a genuinely-declining-SMA200 state to begin with (7.4% vs 16.7% of all days)** —
fewer/shorter real structural downtrends in this 5-year window, not a range-bound/trending
difference. A second, separate collapse (52 qualifying days -> only 2 actual trades) shows
Bank Nifty also rarely prints a fresh 7-day-high entry trigger while in that state — a real,
distinct property, not yet explained.

**Standing conclusion, corrected**: Double7s Short v3 (SMA200 declining + ADX<20) is real
and improved on NIFTY specifically (85.7% win, n=7). It is NOT claimed to generalize to
other indices — not because of a range-bound/trending mechanism (that theory was checked
and rejected), but simply because Bank Nifty had too few real downtrend windows in this
period to test it either way. Double 7s Long remains the only side actually corroborated
across both indices.

## 2026-09-27 (continued) — Sensex as a third independent series: both sides now corroborate

Fetched real Sensex daily history (`data_cache/_SENSEX.csv`, via yfinance, ~5yr) as a third
independent index. Sensex's SMA200-declining base rate (15.8%, n=195) is close to NIFTY's
(16.7%) and nothing like Bank Nifty's thin 7.4% — a broad, diversified index with comparable
real downtrend history, unlike the sector-concentrated Bank Nifty.

| | NIFTY | Bank Nifty | Sensex |
|---|---|---|---|
| Double 7s LONG | 75.0% (n=36) | 72.5% (n=40) | **75.7% (n=37)** |
| Double 7s SHORT v3 (SMA200-decl + ADX<20) | 85.7% (n=7) | too small (n=2) | **85.7% (n=7) — exact match** |

**Both sides now corroborate.** Long: three independent indices, all in the 72.5-75.7% band,
matching the original SPY literature (77%). Short v3: matches NIFTY's win rate exactly on a
second broad index with comparable downtrend history. **Confirms the earlier diagnosis was
right**: the short side isn't index-specific, it just needs a real amount of downtrend
history to test — Bank Nifty didn't have enough in this window, Sensex (similar profile to
NIFTY) does, and it replicates cleanly. Both Double 7s directions are now the most credible,
multi-index-corroborated findings of this entire exploration.

## 2026-09-27 (continued) — real options P&L on Double 7s Long: the signal does NOT survive the wrap

Layered real NIFTY options EOD P&L onto the corroborated Double 7s Long signal: real ITM
(~2%) CE, expiry chosen as the smallest real available expiry >20 calendar days out on the
entry day (comfortably covers the hold, avoids mid-trade expiry), tracked day-by-day via
real bhavcopy from entry to the actual signal-driven exit (not a fixed date).

**n=21 of 36 underlying signals had usable option data.**

- Win rate: **47.6%** — below a coin flip, nowhere near the underlying's 75.0%
- Median option return: **+0.00%** (flat). Mean +1.96%, but concentration check **362.6%
  failed** — a couple of huge winners (2024-06-04: +111.3%, 2024-07-23: +33.2%) are doing
  all the work; most trades are flat-to-negative.
- Median underlying return on the same 21 trades: +1.34% (consistent with the validated
  signal) — confirms the underlying edge is real, it just doesn't transfer.
- Implied leverage on winners: ~6x.

**Real conclusion: the validated underlying signal does NOT survive being wrapped in an
option.** Leverage cuts both ways — a modest, still-genuinely-winning underlying move can
still produce a real option loss once theta eats extrinsic value over a 4-16 day hold. The
option P&L only clearly wins on unusually large, fast underlying moves (same "gamma reward
only shows up on genuinely big moves" pattern found throughout the rest of this whole
NIFTY/zero-to-hero exploration). **This is the same lesson as the zero_to_hero file, arrived
at from the validated side this time, not the gambling side** — a real, corroborated
technical edge on the index does not automatically make a good options trade.

**Data-quality flag, not chased down further**: 3 of 21 trades show exactly 0.000 return
(entry premium = exit premium to the rupee) — plausibly stale/illiquid closing prints on
longer-dated NIFTY ITM options rather than genuine flat moves. Worth knowing if this gets
revisited.

## 2026-09-27 (continued) — why some trades take >5 days: real consolidation, not just "slow same trend"

Per direct user challenge to confirm rather than assume: checked whether SLOW (>5 day)
Double 7s Long trades are a genuine trend that just takes longer, or real chop. Computed
"efficiency" (net move / total distance travelled) for every trade's real daily path:

| | FAST (<=5d) | SLOW (>5d) |
|---|---|---|
| Median efficiency | 1.00 (moves almost directly to target) | **0.18 (only 18% of the distance travelled was net progress)** |
| Mean crossings back through entry price | 1.0 | 1.9 |

**Confirmed real consolidation, not just a slower version of the same trend.** This means
both ATM and ITM bleed theta roughly equally during SLOW trades (neither benefits from net
directional progress) -- explains why the earlier ATM/ITM hybrid filter (predict fast vs
slow, choose instrument accordingly) made things WORSE (median -2.91% vs pure ATM's
+24.6%) -- it was solving a strike-selection problem when the real problem is time/theta
exposure during genuine chop, which strike choice can't fix.

## 2026-09-27 (continued) — current-week ATM with NO rollover: a real, clean, negative answer

Tested current-week (nearest available, >3 days out) ATM CE, held with NO roll -- either
the underlying signal fires before the contract expires (real signal exit, same premium
tracking as before), or the contract is held to real cash settlement at expiry (intrinsic
value = max(spot_at_expiry - strike, 0), using real NIFTY closes). n=24 (2024-01 onward,
weeklies didn't exist in the cache before then).

| Outcome | n | Mean | Median |
|---|---|---|---|
| Signal fired before expiry | 8 | +102.6% | **+95.5%** |
| **Expired before the signal ever fired** | **16** | **-68.9%** | **-97.2%** |
| **ALL (no-roll current-week ATM)** | **24** | **-11.8%** | **-48.7%, win rate 37.5%, 33.3% expired fully worthless** |

**Clean, conclusive, negative result: current-week ATM with no roll is a net LOSING
strategy for this signal**, not marginally worse than the alternatives. Two-thirds of
trades (16/24) never resolve within a single week -- the underlying Double 7s Long signal's
own median hold (8 days) simply exceeds a weekly contract's lifespan most of the time. The
minority that DO resolve fast pay off huge (+95.5% median), but are outnumbered 2:1 by
near-total losses. **Do not use current-week/no-roll ATM for this signal** -- the real
usable choices remain ITM (~2%, >20-day expiry: 47.6% win, flat median, survives) or ATM
with a genuinely longer expiry (>20 days: 57.1% win, +24.6% median -- the best result found
so far), not a weekly contract held to expiry.

## 2026-09-27 (continued) — CORRECTION: the ITM/ATM options P&L numbers above were inflated by a real bug

Per direct user catch: the original ">20 day expiry" ITM/ATM backtests picked the smallest
available expiry with >20 days runway AT ENTRY, but never re-checked whether that same
expiry still had enough runway to cover the REAL, eventual signal-driven exit. When it
didn't (the exit-day contract lookup simply found nothing, since the contract had already
expired/delisted), the trade was silently dropped from the sample instead of being counted
as a real forced settlement. This affected exactly the 3 longest-duration trades (24/25/34
day holds) -- precisely the ones the efficiency-ratio finding says are most likely real
chop, i.e. likely the worst outcomes, quietly excluded rather than counted.

**Fixed: if the exit-day lookup fails because the contract is already gone, fall back to
real cash settlement (intrinsic value = max(spot_at_expiry - strike, 0)) at that expiry
date using real NIFTY closes, instead of skipping the trade.**

| | Original (bug: 3 worst trades silently dropped) | **Fixed (all 24 trades counted)** |
|---|---|---|
| ITM win rate / median / mean | 47.6% / +0.00% / +1.96% | **41.7% / +0.00% / -10.78%** |
| ATM win rate / median / mean | 57.1% / **+24.63%** / +14.9% | **50.0% / +4.76% / +0.52%** |

**All 3 previously-dropped trades expired completely worthless (-100% each)** -- and all 3
had negative underlying returns too, confirming these are exactly the genuine-chop cases:
the underlying eventually squeaked out a technical "fresh 7-day high" exit signal, but only
after grinding to a level still below the original entry, long after the option had already
expired worthless with no chance to participate.

**Corrected standing conclusion**: ATM remains the better choice than ITM for this signal
(50.0% vs 41.7% win, positive vs negative mean), but the real edge is far smaller than first
reported -- **+4.76% median, not +24.6%**. The earlier headline number was a real,
meaningful overstatement from silently excluding the worst-performing trades, not a
legitimate result. Treat the whole "layer options onto Double 7s Long" conclusion as
modest-positive, not strong, going forward.

## 2026-09-27 (continued) — real PE options P&L on Short v3, and finding the Long-side equivalent

**Short v3, real ATM PE, n=7 (all real, zero forced settlements)**: 71.4% win rate, +33.26%
median, +29.28% mean. Better than Long's real result, but n=7 is genuinely thin -- real,
not proven at scale.

**Per direct user question ("why didn't we make Long better the same way")**: tried the
symmetric filter (SMA200 rising + ADX<20) -- n=17, win 52.9%, median +24.63% but
**concentration check 519.4%, badly failed, not trustworthy**. Read real research on why:
bull markets are naturally calmer/lower-ADX by default ("climbing a wall of worry," gradual,
skeptical grinds), so requiring ADX<20 barely narrows the uptrend population. Bear markets
are more volatility-coupled and persistent, so ADX<20 within a downtrend is a genuinely rare,
distinctive, information-dense state -- explains why the same filter shape works cleanly for
Short but not Long. This is a real, structural market asymmetry, not an implementation gap.

**Per direct user follow-up ("SMA200 hasn't been positive in months, try SMA50 instead")**:
confirmed real -- SMA200 has been declining 72.2% of the last 180 trading days. Rebuilt with
SMA50 rising (vs 10 days ago, faster-reacting) + ADX<20 instead:

| | Plain Long | SMA200 v3 | **SMA50 v4** |
|---|---|---|---|
| n | 24 | 17 | 16 |
| Win rate | 50.0% | 52.9% | **62.5%** |
| Median | +4.76% | +24.63% (concentration-failed) | **+24.79%** |
| Mean | +0.52% | +2.10% | **+15.39%** |
| Concentration | -- | 519.4% (untrustworthy) | **73.7% (real, passes)** |

**SMA50 v4 is now the best, most trustworthy Long-side result in this whole exploration** --
higher win rate than any prior version, and unlike SMA200 v3, the strong median actually
survives the concentration check. Confirms the user's instinct: SMA50 (faster-reacting)
catches genuine short-term up-pulses that SMA200 (still "declining" for months after) would
keep filtering out. Even so, only 2 real trades qualified in the last 9 months -- the recent
regime is genuinely thin for long setups by any reasonable filter, not a filter artifact.

**Updated standing conclusion**: for CE, use SMA50 rising + ADX<20 (not plain Close>SMA200)
as the entry filter -- real, validated improvement. For PE, Short v3 (SMA200 declining +
ADX<20) remains the best found, with the caveat that n=7 is thin.

## Open, not yet done

- Layer real NIFTY (and now Bank Nifty) options EOD P&L onto the Double 7s LONG signal
  specifically (the corroborated one) — real bhavcopy, real expiry selection (ITM +
  next-month, this project's own validated analog), exit on the same signal rather than a
  fixed date. This is the natural next step now that the underlying signal is trustworthy.
- Short side: do not build further on the SMA200-slope fix as-is. If revisited, needs a
  fresh regime-filter idea tested on BOTH indices from the start, not fit to one and
  checked on the other after the fact.
- Volume-based reversal confirmation (real vs pullback) was found in research but not yet
  tested against our own data — pullbacks show declining volume, real reversals show 150%+
  average volume spikes; worth checking whether entries with volume confirmation outperform
  those without, same spirit as the SMA200-slope fix.
- Sample sizes throughout (n=9-36) are real but not huge — nothing here should be treated as
  fully validated at project-research standard; it's a credible, sourced starting point.
