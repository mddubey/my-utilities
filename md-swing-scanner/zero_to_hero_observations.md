# Zero-to-Hero Observations (NOT project research)

Separate dumping ground for high-risk/high-reward "lotto" options-buying curiosity —
explicitly NOT wired into FINDINGS.md or PARKING_LOT.md, NOT a validated project finding,
NOT critic-reviewed, NOT subject to the project's usual research-integrity rules. Kept here
on direct user instruction so it doesn't get confused with the real research log.

Read the numbers here as "interesting, real, but small-sample and not something to size
real capital around" — not as edges.

This file was rewritten clean on 2026-09-27 to consolidate a long back-and-forth session
that corrected itself multiple times (methodology bugs caught mid-stream, a wrong premise
corrected, a hindsight-vs-predictive distinction clarified). What follows is the FINAL,
corrected picture — earlier scattered entries and disproven intermediate numbers are not
reproduced here; ask the session history if the trail of corrections itself is ever needed.

---

## Part 1 — Stock-side: pinbar-at-support + cheap OTM CE near expiry (real, well-powered)

**Real trigger**: RBLBANK's Friday 2026-09-25 daily candle — long lower wick (50.7% of
range), small body (35.5%), close near the high (86.2%), low (409.10) exactly matching the
prior day's low — a real double-tested-support pinbar. Question: does buying a fairly-OTM
(<=Rs 2 premium), 0-3-trading-day-to-expiry call on a setup like this show real asymmetric
payoff, more than buying the same kind of contract on an ordinary day?

**Method**: real NSE bhavcopy (`options_cache/`, 2022-06 through 2026-09-22), real monthly
stock-option expiry calendar (54 dates, verified from actual STO-type rows). F&O universe
(210 tickers). For each qualifying event, tracked the cheapest OTM CE (ClsPric<=Rs 2 that
day) every trading day from entry to expiry. **n=546 pinbar events, n=285 baseline events**.
Script: `zero_to_hero_check.py`.

| | Pinbar-at-support | Baseline (ordinary day) |
|---|---|---|
| % reaching >=2x at some point on the path | 9.0% | 7.7% |
| % reaching >=5x | 3.1% | 1.8% |
| % reaching >=10x | 1.3% | 0.7% |
| median best-case path multiple | 1.00x | 1.00x |
| median outcome HELD TO EXPIRY | **0.12x** | **0.15x** |
| % expiring worthless (<0.1x) | 46.7% | 47.4% |

**Verdict**: a real, modest, consistent tilt (1.2-1.8x better odds of a big multiple) from
having a technical trigger vs. buying blind — but it ONLY shows up on the best-case path, if
actively exited into a spike. Held to expiry it's flat-to-slightly-worse than baseline.
Over half of ALL these trades, pinbar or not, never even get back to entry premium at any
point. Loss-dominated either way. Real research context: 95%+ of deep OTM options expire
worthless generally; gamma from a genuine move is the real mechanism behind any "hero"
outcome, not the option being cheap.

---

## Part 2 — NIFTY weekly index options: the long, self-correcting thread

This part went through several real methodology corrections. Recording only the final,
survived-scrutiny conclusions.

### 2a. Strike selection: "pick the strike closer to a technical level" does NOT reliably win

Tested three ways, each more rigorous than the last:
1. **Single real day (2026-09-22)**: 23400 CE (closer to the real peak) beat 23450/23500 CE
   on Open->High multiple. Real, but n=1 — not something to generalize from.
2. **143 real weekly expiries since 2024, near-R1 vs 150pt-further-OTM strike**: near-R1
   strike won only 53.1% of days (near coin flip), and its better-looking MEAN was
   concentration-failed (top 10% of the sample = 48.4% of the total, i.e. a few outlier days
   were carrying the whole result — not trustworthy). Real edge: none found.
3. **9 real days with true intraday data, comparing strike proximity to the ACTUAL,
   hindsight-known peak (not a predicted level)**: near-peak strike won only 55.6% of days —
   close to random EVEN WITH PERFECT HINDSIGHT. Root cause found: cheap, deep-OTM strikes
   mechanically produce bigger % multiples off a tiny starting base, regardless of whether
   they were ever really "in play" — a structural bias in using multiplier/ratio as the
   success metric, not a real edge for far-OTM strikes.

**Conclusion: don't chase further-OTM strikes for "more multiplier potential" — that
instinct is measuring a ratio artifact, not a real edge.** Pick a strike close enough to a
real level that it can plausibly matter at all; don't optimize the strike choice further
than that.

### 2b. Underlying mechanism: does support -> resistance actually happen, and how often

**Full 5-year NIFTY daily history (real floor-trader pivots, prior-day formula, n=554
S1-touch days)**: 64.4% bounce back to/through PP (the pivot midpoint) same day — real,
concentration-checked, well-powered. BUT this number **overstates what's actually tradeable**
— it doesn't check that the bounce happened AFTER the touch, just that both occurred
somewhere in the same day.

**Corrected for real sequencing, using the ~60 real trading days with true intraday data
(entry must precede exit)**: S1 touched intraday on 52.5% of days. Of those, only reached PP
AFTERWARD 22.6% of the time (not 64.4%) — a big, important downward correction.

**Corrected further** — PP is just the pivot midpoint, not a proper directional target.
Redid as the real, symmetric full swing (S1->R1 for bullish, R1->S1 for bearish), restricted
to entries at/after 13:30 (the user's real trading window):

| | Bullish (S1->R1) | Bearish (R1->S1) |
|---|---|---|
| Touch rate (>=13:30) | 47.5% | 25.4% (touched less than half as often) |
| Fully reached target | 3.6% (1/28) | 0.0% (0/15) |
| Median points captured toward target | +10.9 | -28.5 (moved AWAY from target more often) |
| % showing any real progress | 60.7% | 46.7% |

**Full swings are rare — ~1 in 25-28 for a complete support-to-resistance move in the real
afternoon window.** Most of the time you get partial movement, not a clean target hit.

**A real correction to the premise that motivated testing "bearish"**: the "market has been
bleeding for 2 years" framing that prompted checking the reverse/PE side was factually
wrong. Real all-time closing high was 2026-01-02 (26,328.55) — the actual decline is a
~9-month drawdown (-12.1% as of 2026-09-25), sitting on top of a genuine 3-year bull run
(2023-2025, ~17,850 -> 26,215). In the recent window actually tested, bearish was NOT
stronger than bullish — if anything weaker (touched less often, 0% completion, negative
median progress).

### 2c. Does a failed attempt lead to consolidation? No.

Checked both ways:
- **Daily, 441 real cases (S1 touched, R1 not reached same day)**: forward daily range over
  the next 1-10 days stayed at or slightly ABOVE baseline (not compressed). Net drift near
  zero on average, but only 26-39% of cases actually stayed within a tight +/-1% band — most
  of the time real movement continued, it just wasn't consistently biased either way.
- **Real intraday, 26 cases (S1 touched >=13:30, R1 not reached for the rest of that
  session)**: median remaining-session range 0.34%, median net move +0.05% (flat on
  average), but only 34.6% of cases actually stayed tight (<0.3% range) and only 46.2%
  ended within +/-0.15% of the touch price. **Majority of cases (54-65%) still moved
  meaningfully in the remaining session** — real movement continues more often than not,
  just without a reliable directional bias.
- **Matches independent research**: a failed breakout usually "falls back into the price
  channel... sometimes breaks down below it" — and **volume at the point of rejection is the
  real disambiguator** (low-volume rejection -> more likely to reverse/re-range; high-volume
  rejection -> signals real follow-through, more likely to extend). Not tested with our own
  data yet — a real, concrete next check if this gets revisited (split the 441/26-case
  populations by volume-at-rejection).

### 2d. What we genuinely cannot answer with available data

- **Exact option premium magnitude/timing** (the real "Rs 10 -> Rs 38" type move) — no
  intraday tick/1-5min data exists for NIFTY options anywhere accessible in this project
  (`options_cache/` is EOD bhavcopy only; yfinance returns nothing for NIFTY options). Every
  multiplier computed in this whole thread (Open->High, Low->High, etc.) answers a specific,
  narrow question about two DAILY reference points — none of them equal "the price at a
  specific intraday time," which is what would actually be needed to verify a real trade.
- **GIFT Nifty**: real, legitimate pre-market gap-direction indicator, but no data feed for
  it exists in this project and most retail can't trade it directly. Context only.

---

## Bottom line, if this ever gets picked back up

1. Watching real intraday structure (support/resistance testing) before acting is sound —
   it's common, real, and better than blind entry timing.
2. Don't expect a full support-to-resistance swing to complete — it's rare (~1-in-25 to
   1-in-28 properly measured). Plan to exit into partial progress, not hold for a formal
   target.
3. Don't chase further-OTM strikes for a bigger multiplier — that's a ratio artifact of
   cheap options, not a real edge. Pick a strike close enough to matter, no further.
4. The bearish/PE angle isn't currently better than bullish/CE — and the "2-year bear
   market" reasoning behind testing it was factually wrong (real decline is ~9 months).
5. "Rejected from both sides" does not mean quiet — real movement continues most of the
   time; volume at the rejection point (untested here) is the likely real disambiguator of
   which way it resolves.
6. The actual option-premium magnitude of any of this can never be verified with data
   available in this project — treat every multiplier discussed here as describing the
   underlying's behavior or a narrow day-level option proxy, never a confirmed real P&L.
