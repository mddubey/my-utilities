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
- Trigger Velocity (rate of distance-closing between two checkpoints, 2026-09-06):
  wired in -- see VELOCITY_WEIGHT below. Swept across three checkpoint pairs before
  trusting it (real plateau in the 70-90% distance / 10-30% velocity zone, no single
  ratio wins every pair); the 10-minute lookback itself, however, was NOT validated
  the same way -- swept separately and found no consistent optimum (best window
  bounces 5/15/20 min depending on the anchor checkpoint), kept as an arbitrary
  reasonable choice, not a data-backed one. Both fully detailed in FINDINGS.md.
- Distance Calibration Curve (2026-09-06, see FIRE_RATE_BY_DISTANCE below): each
  tier-3 row shows a historically-grounded fire probability alongside its raw
  distance, not just a rank -- checked robust across checkpoints (same curve shape
  at 09:20 and 09:40 independently), not a time-of-day artifact.
"""
import sys
from datetime import datetime, timedelta

import pandas as pd

from backtest import load, resistance_target
from daily_scan import shortlist_primed, fetch_live_bars, LIVE_CUTOFF_DEFAULT
from sector_strength import sector_rs

TRIGGER_CLEARANCE_LOW = 0.003   # 0.3% -- earliest honest fire point
TRIGGER_CLEARANCE_HIGH = 0.006  # 0.6% -- limit-order ceiling, never pay more than this
PULLBACK_MIN_PCT = 0.5          # retrace at least this much off the day's high-so-far to count as "pulled back"
NEAR_BAND_PCT = 2.0             # unused by classification since 2026-09-07's redefinition below, kept for reference
PULLED_BACK_TOLERANCE_PCT = 0.5  # user-defined (2026-09-07): the 0.3-0.6% clearance band IS the expected/
                                  # standard entry price, not a discount -- a genuine "pulled back, better
                                  # price" entry means sitting within this tolerance EITHER SIDE of the RAW
                                  # pivot (high10_effective) itself, not just "not too far above trigger_low".
                                  # Real case that prompted this: GLAND/IDEA/SOLARINDS were showing "Tier 1:
                                  # pulled back" at +1.0-1.6% above the raw pivot (already past the official
                                  # 0.3-0.6% band) under the old NEAR_BAND_PCT=2.0%-from-trigger_low rule --
                                  # nowhere near a real discount, just tolerated by too loose a threshold.
TOP_N = 10
VELOCITY_LOOKBACK_MIN = 10   # minutes between the two snapshots used to compute closing speed
VELOCITY_WEIGHT = 0.20      # blend weight on velocity-rank vs distance-rank for tier 3 (2026-09-06:
                             # swept 0-100% blend across three checkpoint pairs -- no single ratio wins
                             # every pair (real plateau, not a pinned-down optimum, same honesty
                             # standard as the entry-clearance band and VCP tolerance), but 80/20 never
                             # lost and usually won: R@1 55.7%->65.6%, R@2 80.3%->88.5% at 09:20->09:30;
                             # R@1 62.3%->65.6%, R@2 82.0%->86.9% at 09:30->09:40; R@1 63.9%->73.8% at
                             # 09:25->09:35. See FINDINGS.md's Round-13 section for the full sweep.

# Distance Calibration Curve (2026-09-06): P(fires later today | distance-to-trigger
# right now), pooled across checkpoints 09:20-09:45 (n=21,273 candidate-checkpoint
# pairs, 62 real days) -- checked robust at 09:20 and 09:40 independently before
# trusting it. (upper_bound_pct, fire_rate_pct) pairs, ascending -- see FINDINGS.md's
# "Distance Calibration Curve" section for the full table including sample sizes.
FIRE_RATE_BY_DISTANCE = [
    (0.2, 88.0), (0.3, 81.3), (0.4, 77.8), (0.5, 68.0), (0.6, 71.9),
    (0.8, 56.7), (1.0, 48.0), (1.5, 32.9), (2.0, 22.3), (3.0, 11.7),
    (5.0, 3.8), (float("inf"), 0.5),
]


def calibrated_fire_rate(dist_pct):
    """Historical P(fires later today) for a candidate currently this far from its
    trigger -- a lookup, not a model fit, deliberately: the underlying curve is
    monotonic enough that a simple bucket table is more honest than pretending to
    interpolate precision the data doesn't support."""
    for upper, rate in FIRE_RATE_BY_DISTANCE:
        if dist_pct <= upper:
            return rate
    return FIRE_RATE_BY_DISTANCE[-1][1]


# Tiers on top of the raw calibrated rate (2026-09-06, outside critique): a person
# makes better decisions off a small number of named buckets than off two numbers that
# only differ by a percentage point or two (e.g. "63.2% vs 64.7%") -- the raw number is
# still shown alongside each tier for reference, not hidden.
FIRE_TIERS = [(70, "HIGH"), (50, "WATCH"), (25, "WEAK"), (0, "IGNORE")]


def fire_tier(rate):
    for lower, label in FIRE_TIERS:
        if rate >= lower:
            return label
    return FIRE_TIERS[-1][1]


def _minus_minutes(cutoff_ist, minutes):
    t = datetime.strptime(cutoff_ist, "%H:%M")
    return (t - timedelta(minutes=minutes)).strftime("%H:%M")


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
    effective_cutoff = cutoff_ist or LIVE_CUTOFF_DEFAULT
    prior_cutoff = _minus_minutes(effective_cutoff, VELOCITY_LOOKBACK_MIN)
    live = fetch_live_bars(pool, cutoff_ist=effective_cutoff)
    live_prior = fetch_live_bars(pool, cutoff_ist=prior_cutoff)

    feature_rows = {}
    for t in pool:
        try:
            df = load(t).reset_index()
        except FileNotFoundError:
            continue
        i = len(df) - 1
        if i < 15 or pd.isna(df.iloc[i].atr14) or df.iloc[i].atr14 == 0 or pd.isna(df.iloc[i].ema8):
            continue
        # Real bug found live (2026-09-07): the cached row's own `high10_prior` column
        # is `High.shift(1).rolling(10).max()` -- the 10-day high as of the day BEFORE
        # that row, not as of that row itself. When the cache is one session behind
        # "today" (the normal case intraday, before today's own bar exists yet), using
        # that stored value as today's reference misses the last cached day's own high
        # entirely -- if that day itself set a fresh high (e.g. a breakout day), the
        # trigger band silently uses last week's level instead. Real case: RBLBANK's
        # cached row showed high10_prior=410.70 (window ending the day before), but the
        # correct 10-day high through the last cached day was 417.05 (that day's own
        # high) -- the stored band [411.93,413.16] was ~1.5% too low, wrongly flagging
        # a stock that hadn't actually broken out yet as "pulled back, good entry".
        # Fixed: recompute the effective high10 fresh as the max High over the actual
        # last 10 cached rows, which correctly includes the most recent cached day.
        high10_effective = df.High.tail(10).max()

        # Informational only (2026-09-07, user-flagged live on RBLBANK): how many
        # consecutive cached days has this ticker ALREADY been closing above its own
        # day's high10_prior. The historical backtest only ever contains DAY-1 entries
        # for a given move (simulate_ticker's in_position state prevents re-entering a
        # ticker it's already holding) -- there is NO validated evidence either way on
        # entering day 2/3/4+ of an already-running move, so this is NOT a filter, just
        # a visible flag so a re-triggering old move isn't mistaken for a fresh one.
        already_extended = df.Close > df.high10_prior
        extension_days = 0
        for v in already_extended.iloc[::-1]:
            if v:
                extension_days += 1
            else:
                break

        feature_rows[t] = dict(row=df.iloc[i], features=_quality_features(t, df, i),
                                date=df.iloc[i].Date, high10_effective=high10_effective,
                                extension_days=extension_days)

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
        high10_effective = feature_rows[t]["high10_effective"]
        if pd.isna(high10_effective):
            continue
        trigger_low = high10_effective * (1 + TRIGGER_CLEARANCE_LOW)
        trigger_high = high10_effective * (1 + TRIGGER_CLEARANCE_HIGH)
        quality_score = quality_pool.loc[t, "quality_score"] if t in quality_pool.index else None
        sector, sector_rs_pct = sector_rs(t, feature_rows[t]["date"])
        common = dict(ticker=t, trigger_low=trigger_low, trigger_high=trigger_high,
                     quality_score=quality_score, sector=sector, sector_rs=sector_rs_pct,
                     extension_days=feature_rows[t]["extension_days"],
                     high10_effective=high10_effective)

        if bar["High"] >= trigger_low:
            pullback_pct = (bar["High"] - bar["Close"]) / bar["High"] * 100
            clearance_now_pct = (bar["Close"] / trigger_low - 1) * 100
            # user-defined "real bargain" metric (2026-09-07): distance from the RAW
            # pivot (high10_effective, the 0% base level the 0.3-0.6% band is measured
            # FROM), not from trigger_low (the 0.3% mark itself). The 0.3-0.6% band is
            # the expected/standard entry price, not a discount -- a genuine better
            # price means coming back down toward the raw pivot, below the band, not
            # just staying inside it.
            clearance_vs_raw_pivot_pct = (bar["Close"] / high10_effective - 1) * 100
            entry_vs_trigger_pct = (bar["Close"] / trigger_low - 1) * 100
            resistance = resistance_target(bar["Close"], row)
            rec = dict(**common, day_high=bar["High"], current_price=bar["Close"],
                      pullback_pct=pullback_pct, clearance_now_pct=clearance_now_pct,
                      clearance_vs_raw_pivot_pct=clearance_vs_raw_pivot_pct,
                      entry_vs_trigger_pct=entry_vs_trigger_pct, resistance=resistance)
            band_ceiling_pct = TRIGGER_CLEARANCE_HIGH * 100  # 0.6%, the official band's own top edge
            # Downside deliberately uncapped (2026-09-07, explicit user instruction):
            # further below the raw pivot is only ever a BETTER price, never "missed" --
            # only chasing above the tolerance gets penalized. Only the upside is bounded.
            if clearance_vs_raw_pivot_pct <= PULLED_BACK_TOLERANCE_PCT:
                pulled_back.append(rec)
            elif PULLED_BACK_TOLERANCE_PCT < clearance_vs_raw_pivot_pct <= band_ceiling_pct:
                kept_going_near.append(rec)
            else:
                missed.append(rec)
        else:
            dist_pct = (trigger_low / bar["Close"] - 1) * 100
            resistance = resistance_target(bar["Close"], row)
            rec = dict(**common, close=bar["Close"], dist_to_trigger_pct=dist_pct, velocity_pct=None,
                       fire_rate_pct=calibrated_fire_rate(dist_pct), resistance=resistance)
            bar_prior = live_prior.get(t)
            if bar_prior is not None and bar_prior["High"] < trigger_low:
                dist_prior_pct = (trigger_low / bar_prior["Close"] - 1) * 100
                rec["velocity_pct"] = dist_prior_pct - dist_pct  # positive = closing fast
            watching.append(rec)

    def _df(recs, sort_col, ascending):
        return pd.DataFrame(recs).sort_values(sort_col, ascending=ascending) if recs else pd.DataFrame(recs)

    watching_df = _df(watching, "dist_to_trigger_pct", True)
    if not watching_df.empty and watching_df["velocity_pct"].notna().sum() >= 3:
        watching_df["dist_rank"] = watching_df["dist_to_trigger_pct"].rank(pct=True, ascending=True)
        watching_df["vel_rank"] = watching_df["velocity_pct"].rank(pct=True, ascending=False)
        # candidates with no velocity reading (too early in the day for a prior snapshot)
        # fall back to a neutral 0.5 vel-rank so they aren't penalized relative to unmeasured peers
        watching_df["vel_rank"] = watching_df["vel_rank"].fillna(0.5)
        watching_df["combo_rank"] = (1 - VELOCITY_WEIGHT) * watching_df["dist_rank"] + VELOCITY_WEIGHT * watching_df["vel_rank"]
        watching_df = watching_df.sort_values("combo_rank", ascending=True)

    return (_df(pulled_back, "pullback_pct", False),
            _df(kept_going_near, "clearance_now_pct", True),
            watching_df,
            _df(missed, "clearance_now_pct", False))


def _print_tier(label, df, note, price_col, price_label):
    print()
    print(f"=== {label} ({len(df)}) ===")
    if note:
        print(f"    {note}")
    if df.empty:
        print("  (none)")
        return
    has_velocity = "velocity_pct" in df.columns
    has_fire_rate = "fire_rate_pct" in df.columns
    has_dist = "dist_to_trigger_pct" in df.columns
    for _, r in df.iterrows():
        q = f"quality={r.quality_score:.2f}" if pd.notna(r.quality_score) else "quality=n/a"
        sec = f"{r.sector} (sector RS {r.sector_rs:.0f})" if r.sector and pd.notna(r.sector_rs) else (r.sector or "n/a")
        dist = f"  dist={r.dist_to_trigger_pct:+.2f}%" if has_dist and pd.notna(r.dist_to_trigger_pct) else ""
        vel = ""
        if has_velocity:
            vel = f"  vel={r.velocity_pct:+.2f}%/{VELOCITY_LOOKBACK_MIN}min" if pd.notna(r.velocity_pct) else "  vel=n/a"
        fire = f"  [{fire_tier(r.fire_rate_pct)}] ~{r.fire_rate_pct:.0f}%" if has_fire_rate and pd.notna(r.fire_rate_pct) else ""
        print(f"  {r.ticker:12s} band=[{r.trigger_low:.2f},{r.trigger_high:.2f}]  "
              f"{price_label}={r[price_col]:9.2f}  {q}  {sec}{dist}{vel}{fire}")


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
                "ranked by distance blended 80/20 with closing-speed vs 10 min ago -- "
                "[HIGH]>=70% [WATCH]>=50% [WEAK]>=25% [IGNORE]<25%, per the Distance Calibration Curve",
                "close", "close")
    _print_tier("MISSED (fired, ran well past the band -- not actionable, informational only)", missed,
                "if it settles back into tier 1/2 on a later run, it'll reappear there", "current_price", "price")
