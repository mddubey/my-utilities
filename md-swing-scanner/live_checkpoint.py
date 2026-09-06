"""Run any time during market hours (works whenever called, not tied to a fixed
checkpoint time) to answer: of today's primed watchlist, what's actually tradeable
RIGHT NOW, and in what order? Redesigned 2026-09-06 from the original single-list
version after a live discussion surfaced the real problem with ranking purely by
same-day distance-to-trigger: it optimizes for TIMING (will this fire soon), not for
whether you can actually catch it -- a top-ranked pick can fire and fill within 5
minutes of a checkpoint (46.3% of the time, see FINDINGS.md's Round-13 section),
which is a real race against a commute/attention-constrained schedule.

The fix isn't a faster checkpoint -- it's changing WHAT gets ranked. A trade that has
ALREADY fired has a known, settled price the moment you check, whenever that moment
is -- there's no race left to lose, only a choice of which already-confirmed setup to
take. So candidates are bucketed into three tiers, each internally ordered, rather
than one flat distance-sorted list:

  1. PULLED BACK -- fired, then gave back at least PULLBACK_MIN_PCT off its high
     since firing, currently still within NEAR_BAND_PCT of the trigger. Best price of
     the three tiers (checked directly, 2026-09-06: avg entry ~0.2-0.35% BELOW the
     trigger level). NOT a higher-win-rate tier though -- tested properly (anchored to
     bars-since-fire, not wall-clock time, to avoid a real confound an earlier
     wall-clock-anchored version of this test had) and win rate here is roughly even
     with "kept going near" (55-58% vs 57-63% across two offsets tested) -- the value
     of this tier is a settled, better price and zero timing race, not a proven edge
     in outcome quality.
  2. KEPT GOING, NEAR -- fired, hasn't pulled back OR run away, still within
     NEAR_BAND_PCT of the trigger. Also settled, no timing race. Roughly the same
     realized quality as tier 1 in testing, just a slightly worse average price.
  3. WATCHING, not yet fired -- the original mechanism, sorted by distance to
     trigger. Validated (2026-09-05): Recall@1 60.7-68.9%, Recall@2 76.3-83.6%,
     Recall@5 88.1-96.7% across the whole clearance band (n=59 real days) -- this
     part is unchanged from the original version of this file.

A fourth state -- fired and running well past the band, not settled -- is deliberately
NOT surfaced as an actionable tier. By the time you'd place an order the price is
already stale and moving; per direct instruction (2026-09-06), these are logged as
MISSED and dropped. If price comes back into the near-band or pulls back on a later
run, it'll naturally reappear in tier 1 or 2 then -- no special-casing needed, since
every run is a fresh, stateless snapshot.

Quality annotations, added per direct request (2026-09-06) -- reuses only ALREADY
VALIDATED signals from elsewhere in this project, nothing new invented:
  - quality_score: the same 4-feature composite tomorrow_candidates.py uses
    (range_compression, ema8_dist_pct, atr_trend_15d, narrowing_range), percentile-
    ranked against this run's own primed pool. Night-before, not live -- describes
    the SETUP's quality, independent of today's price action or which tier it lands in.
  - sector / sector_rs: real, adopted signal (2026-09-01) -- VCP trades in a
    top-quartile-RS sector win 68.1% vs 55-61% in the bottom three (see FINDINGS.md).
  - pattern: breakout_cont vs coiled_spring -- the two patterns have historically
    different profiles (see FINDINGS.md throughout), worth knowing which is which.
These are NOT re-validated as tier-ranking signals in their own right within this
file -- they're shown as reference context for choosing between candidates inside
the same tier, same spirit as sector_rs being a ranking aid in daily_scan.py, not a
hard filter.

Two-pass design, unchanged from the original: Pass 1 (shortlist_primed, cheap,
yesterday's cached close only) narrows the 500-ticker universe down to whatever could
plausibly fire today at all. Pass 2 (fetch_live_bars, the only part that costs
anything) fetches one aggregated "today so far" OHLCV bar per shortlisted ticker.
Tier classification reuses that SAME aggregated bar -- no raw intraday bars needed
live: a ticker can't have gone above its trigger before actually firing, so the day's
own High-so-far IS the peak-since-fire by construction, and Close-so-far is the
current, tradeable price.

Real caveats, not swept under the rug:
- yfinance intraday is itself delayed, not a real broker feed.
- Trigger clearance uses the 0.3-0.6% band (2026-09-05 finding) -- checked directly
  that the tier-3 (distance) ranking is robust across the whole 0.3-1.0% range.
- Volume was tested as a secondary tier-3 ranking signal and made it WORSE, not
  better (Recall@1 60.7%->44.3%) -- deliberately not used.
- Trigger Velocity (rate of distance-closing between two checkpoints) tested
  2026-09-05 as a real, promising secondary tier-3 signal (Recall@1 55.7%->65.6%
  blended) but NOT wired in here yet -- needs a two-checkpoint data flow this
  single-snapshot design doesn't have, and hasn't been through the same
  break-testing rigor as the distance-only mechanism. Logged in FINDINGS.md as a
  real lead, not forgotten.
"""
import sys

import pandas as pd

from backtest import load
from daily_scan import shortlist_primed, fetch_live_bars
from sector_strength import sector_rs

TRIGGER_CLEARANCE_LOW = 0.003   # 0.3% -- earliest honest fire point
TRIGGER_CLEARANCE_HIGH = 0.006  # 0.6% -- limit-order ceiling, never pay more than this
PULLBACK_MIN_PCT = 0.5          # retrace at least this much off the day's high-so-far to count as "pulled back"
NEAR_BAND_PCT = 2.0             # clearance-above-trigger cap to still call a fired name "near", not "missed"
TOP_N = 10


def _quality_features(t, rows, i):
    """Same 4 features/formula as tomorrow_candidates.py's build_candidates() --
    intentionally identical, not re-derived, so the two tools never quietly drift
    apart on what "quality" means."""
    row = rows.iloc[i]
    range10 = (rows.High.iloc[i - 9:i + 1].max() - rows.Low.iloc[i - 9:i + 1].min())
    range_compression = range10 / row.atr14
    ema8_dist_pct = (row.Close - row.ema8) / row.Close * 100
    atr14_15ago = rows.atr14.iloc[i - 15] if i >= 15 else None
    atr_trend_15d = row.atr14 / atr14_15ago if pd.notna(atr14_15ago) and atr14_15ago else None
    recent3 = (rows.High.iloc[i - 2:i + 1] - rows.Low.iloc[i - 2:i + 1]).mean()
    prior3 = (rows.High.iloc[i - 5:i - 2] - rows.Low.iloc[i - 5:i - 2]).mean()
    narrowing_range = recent3 / prior3 if prior3 else None
    return dict(range_compression=range_compression, ema8_dist_pct=ema8_dist_pct,
                atr_trend_15d=atr_trend_15d, narrowing_range=narrowing_range)


def classify_candidates(tickers, cutoff_ist=None):
    """Returns (pulled_back, kept_going_near, watching, missed) -- four DataFrames.
    pulled_back/kept_going_near/watching are the three actionable tiers, in priority
    order. missed is informational only (fired, ran past the band, not settled) --
    not meant to be acted on, just visible so nothing silently vanishes."""
    pool = shortlist_primed(tickers)
    live = fetch_live_bars(pool, cutoff_ist=cutoff_ist) if cutoff_ist else fetch_live_bars(pool)

    feature_rows = {}
    for t in pool:
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        i = len(df) - 1
        if i < 15 or pd.isna(df.iloc[i].atr14) or df.iloc[i].atr14 == 0 or pd.isna(df.iloc[i].ema8):
            continue
        feature_rows[t] = dict(row=df.iloc[i], features=_quality_features(t, df, i), date=df.iloc[i].Date)

    quality_pool = pd.DataFrame({t: v["features"] for t, v in feature_rows.items()}).T
    if not quality_pool.empty:
        quality_pool["quality_score"] = (
            (-quality_pool.range_compression).rank(pct=True)
            + (-quality_pool.ema8_dist_pct).rank(pct=True)
            + (-quality_pool.atr_trend_15d).rank(pct=True)
            + (quality_pool.narrowing_range).rank(pct=True)
        ) / 4

    pulled_back, kept_going_near, watching, missed = [], [], [], []
    for t in pool:
        bar = live.get(t)
        if bar is None or t not in feature_rows:
            continue
        row = feature_rows[t]["row"]
        if pd.isna(row.high10_prior):
            continue
        trigger_low = row.high10_prior * (1 + TRIGGER_CLEARANCE_LOW)
        trigger_high = row.high10_prior * (1 + TRIGGER_CLEARANCE_HIGH)
        quality_score = quality_pool.loc[t, "quality_score"] if t in quality_pool.index else None
        sector, sector_rs_pct = sector_rs(t, feature_rows[t]["date"])
        common = dict(ticker=t, trigger_low=trigger_low, trigger_high=trigger_high,
                     quality_score=quality_score, sector=sector, sector_rs=sector_rs_pct)

        if bar["High"] >= trigger_low:
            pullback_pct = (bar["High"] - bar["Close"]) / bar["High"] * 100
            clearance_now_pct = (bar["Close"] / trigger_low - 1) * 100
            entry_vs_trigger_pct = (bar["Close"] / trigger_low - 1) * 100
            rec = dict(**common, day_high=bar["High"], current_price=bar["Close"],
                      pullback_pct=pullback_pct, clearance_now_pct=clearance_now_pct,
                      entry_vs_trigger_pct=entry_vs_trigger_pct)
            if pullback_pct >= PULLBACK_MIN_PCT and clearance_now_pct <= NEAR_BAND_PCT:
                pulled_back.append(rec)
            elif clearance_now_pct <= NEAR_BAND_PCT:
                kept_going_near.append(rec)
            else:
                missed.append(rec)
        else:
            dist_pct = (trigger_low / bar["Close"] - 1) * 100
            watching.append(dict(**common, close=bar["Close"], dist_to_trigger_pct=dist_pct))

    def _df(recs, sort_col, ascending):
        return pd.DataFrame(recs).sort_values(sort_col, ascending=ascending) if recs else pd.DataFrame(recs)

    return (_df(pulled_back, "pullback_pct", False),
            _df(kept_going_near, "clearance_now_pct", True),
            _df(watching, "dist_to_trigger_pct", True),
            _df(missed, "clearance_now_pct", False))


def _print_tier(label, df, note, price_col, price_label):
    print()
    print(f"=== {label} ({len(df)}) ===")
    if note:
        print(f"    {note}")
    if df.empty:
        print("  (none)")
        return
    for _, r in df.iterrows():
        q = f"quality={r.quality_score:.2f}" if pd.notna(r.quality_score) else "quality=n/a"
        sec = f"{r.sector} (sector RS {r.sector_rs:.0f})" if r.sector and pd.notna(r.sector_rs) else (r.sector or "n/a")
        print(f"  {r.ticker:12s} band=[{r.trigger_low:.2f},{r.trigger_high:.2f}]  "
              f"{price_label}={r[price_col]:9.2f}  {q}  {sec}")


if __name__ == "__main__":
    cutoff = sys.argv[1] if len(sys.argv) > 1 else None
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    print(f"Checking as of {'now' if cutoff is None else cutoff} IST...")
    pulled_back, kept_going_near, watching, missed = classify_candidates(tickers, cutoff_ist=cutoff)

    print()
    print("NOTE: for tiers 1/2/missed, 'band' is reference only (where it fired earlier today) --")
    print("      the real order price is the 'price' column, which can sit below trigger_low")
    print("      (round-tripped back down) or above trigger_high (ran past the ceiling) -- it is")
    print("      NOT bounded by the band the way tier 3's still-watching candidates are.")

    _print_tier("TIER 1: PULLED BACK (best price, settled, no timing race)", pulled_back,
                "sorted by how much it's pulled back -- more pullback = cheaper entry", "current_price", "price")
    _print_tier("TIER 2: KEPT GOING, STILL NEAR TRIGGER (settled, no timing race)", kept_going_near,
                "sorted by clearance -- closest to trigger_low first", "current_price", "price")
    _print_tier(f"TIER 3: WATCHING, not yet fired (top {TOP_N} of {len(watching)})", watching.head(TOP_N),
                "validated ranking: top-1 catches the real mover 60-69% of the time, top-2 76-84%",
                "close", "close")
    _print_tier("MISSED (fired, ran well past the band -- not actionable, informational only)", missed,
                "if it settles back into tier 1/2 on a later run, it'll reappear there", "current_price", "price")
