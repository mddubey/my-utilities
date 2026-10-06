"""RQ-EMAPB-07 -- Episode Lifecycle Mapping (critic-specified, 2026-10-04).
Expansion -> Peak -> Pullback -> Consolidation -> Resumption/Failure, on the CANONICAL
population rebuilt UNGATED (no position-blocking, no 15-day lockout -- see FINDINGS.md for why
RQ-EMAPB-06 was retracted). Descriptive discovery only -- no entries, exits, thresholds,
profitability. See FINDINGS.md for the full pre-registered design.

Usage: python3 swing_qs_emapb/13_rq_emapb07_lifecycle.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = "data/daily"
LOOKBACK = 10            # same as the canonical A definition, not tuned
VOL_RATIO_MIN = 0.3      # RELAXED for RQ-EMAPB-08b comparison only -- NOT the canonical population
BOX_CONFIRM_DAYS = 3     # literature-grounded minimum (3-5 days commonly cited), pre-declared
WINDOW_DAYS = 150        # generous, pre-declared -- genuine bases run 4-12+ weeks per literature


def load_daily(ticker):
    f = os.path.join(DAILY_DIR, f"{ticker}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty or len(d) < LOOKBACK + 50:
        return None
    d["Date"] = pd.to_datetime(d["Date"])
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def find_episode_starts(d):
    """Ungated: every qualifying day retained. Returns first-of-cluster (episode start, cluster_length,
    a_day_vol_ratio) -- vol_ratio tracked per-episode so trigger strength can be diagnosed, per user's
    request (TATACONSUM 1.64x marginal vs HILTON Dec-13 2M-share bar both currently pass the same
    binary 1.5x gate with no way to tell them apart).

    FIX (2026-10-05, GRASIM catch): now also requires Close > Open -- a bullish candle. 17.8% of the
    prior population (20,080 of 112,556 episodes) were RED candles that merely poked a new 10-day
    high intraday on elevated volume, which is not a breakout by any human definition regardless of
    its downstream statistics."""
    prior_high = d.High.rolling(LOOKBACK).max().shift(1)
    prior_vol_avg = d.Volume.rolling(LOOKBACK).mean().shift(1)
    vol_ratio = d.Volume / prior_vol_avg
    qualifies = ((d.High > prior_high) & (d.Volume >= VOL_RATIO_MIN * prior_vol_avg) &
                 (d.Close > d.Open)).fillna(False).values
    out = []
    i, n = 0, len(qualifies)
    while i < n:
        if qualifies[i] and (i == 0 or not qualifies[i - 1]):
            j = i
            while j < n and qualifies[j]:
                j += 1
            out.append((i, j - i, float(vol_ratio.iloc[i])))
        i += 1
    return out, int(qualifies.sum())


def find_peak(d, ia, end):
    """Phase 1: zero-parameter running-high walk. Unchanged from RQ-EMAPB-04."""
    running_high = d.High.iloc[ia]
    peak_i = ia
    for k in range(ia + 1, end):
        if d.High.iloc[k] > running_high:
            running_high = d.High.iloc[k]
            peak_i = k
        else:
            break
    else:
        return peak_i, running_high, True  # ran to window end still extending
    return peak_i, running_high, False


def a_low_breach_stats(d, ia, a_day_low, start, stop):
    """Min Low reached from `start` through `stop` (inclusive), vs the A-day's own Low. Answers
    'did this episode ever threaten the structural level a trader would actually stop out on,'
    independent of whether it eventually resumed or failed."""
    min_low = d.Low.iloc[start:stop + 1].min()
    return dict(
        min_low_vs_a_day_low_pct=(min_low / a_day_low - 1) * 100,
        breached_a_day_low=bool(min_low < a_day_low),
    )


def lifecycle(d, ia, peak_i, peak_high, end):
    """Phase 2-4: mirrored running-low walk with 3-day box confirmation + re-arm, per
    FINDINGS.md's pre-registered design. Returns a dict describing the full episode path.

    FIX (2026-10-05, BAJFINANCE catch): now tracks, up through resolution, whether price ever
    closes below the A-day's own Low -- a "clean vs round-trip" quality dimension the binary
    resumed/failed outcome was hiding. BAJFINANCE 2025-11-27 pulled back to within 0.3% of its
    own A-day Low over 5 sessions before "resuming" -- mechanically identical to a clean win
    under the old labeling, not practically identical to one."""
    a_day_low = d.Low.iloc[ia]
    if peak_i + 1 >= end:
        return dict(outcome="no_room_after_peak")

    # first_lower_close: simple separate descriptive marker, not used to define the pullback low
    first_lower_close_i = None
    for k in range(peak_i + 1, end):
        if d.Close.iloc[k] < d.Close.iloc[k - 1]:
            first_lower_close_i = k
            break

    # State transitions (what counts as "a new low" / "exceeds peak") now use CLOSE, not the
    # intrabar wick -- per user's TCS chart catch: a bar that pokes through a level but closes
    # back inside is the classic false-breakout signature, not a real break, in either direction.
    # Descriptive extent (max_retracement_pct, range stats) still uses the real Low/High wick,
    # since "how far did price actually reach" is a different question from "did the level break."
    running_low_close = d.Close.iloc[peak_i + 1]
    running_low_i = peak_i + 1
    lower_low_streak = 1
    max_lower_low_streak = 1
    i = peak_i + 2
    rearm_count = 0

    while i < end:
        if d.Close.iloc[i] < running_low_close:
            running_low_close = d.Close.iloc[i]
            running_low_i = i
            lower_low_streak += 1
            max_lower_low_streak = max(max_lower_low_streak, lower_low_streak)
            i += 1
            continue
        lower_low_streak = 0

        # candidate stabilization day at i -- run the 3-day box confirmation
        candidate_i = i
        box_low_close = running_low_close
        box_break_i, box_break_type = None, None
        for k in range(candidate_i, min(candidate_i + BOX_CONFIRM_DAYS, end)):
            if d.Close.iloc[k] < box_low_close:
                box_break_i, box_break_type = k, "new_low"
                break
            if d.Close.iloc[k] > peak_high:
                box_break_i, box_break_type = k, "exceeds_peak"
                break

        if box_break_type == "new_low":
            rearm_count += 1
            running_low_close = d.Close.iloc[box_break_i]
            running_low_i = box_break_i
            i = box_break_i + 1
            continue

        if box_break_type == "exceeds_peak":
            actual_low_reached = d.Low.iloc[peak_i + 1:candidate_i + 1].min()
            out = dict(
                outcome="immediate_continuation",
                a_to_peak_days=peak_i - ia, peak_high=peak_high,
                days_peak_to_candidate=candidate_i - peak_i,
                max_retracement_pct=(actual_low_reached / peak_high - 1) * 100,
                max_lower_low_streak=max_lower_low_streak, rearm_count=rearm_count,
                first_lower_close_days=(first_lower_close_i - peak_i) if first_lower_close_i else None,
                consolidation_days=box_break_i - candidate_i,
                resolution_days_from_peak=box_break_i - peak_i,
            )
            out.update(a_low_breach_stats(d, ia, a_day_low, peak_i + 1, box_break_i))
            return out

        # survived BOX_CONFIRM_DAYS days with no break either way -> CONFIRMED consolidation
        pullback_low_i = running_low_i
        box_low_confirmed_close = box_low_close
        consolidation_start_i = candidate_i
        box_span_end = min(candidate_i + BOX_CONFIRM_DAYS, end)

        resolution_i, resolution_type = None, None
        for k in range(box_span_end, end):
            if d.Close.iloc[k] < box_low_confirmed_close:
                resolution_i, resolution_type = k, "consolidation_failure"
                break
            if d.Close.iloc[k] > peak_high:
                resolution_i, resolution_type = k, "consolidation_resumption"
                break

        box_slice = d.iloc[consolidation_start_i:box_span_end]
        range_width_pct = (box_slice.High.max() / box_slice.Low.min() - 1) * 100
        daily_range_pct = ((box_slice.High - box_slice.Low) / box_slice.Close).mean() * 100
        vol_mean_box = box_slice.Volume.mean()
        vol_mean_pre_peak = d.Volume.iloc[max(0, ia - LOOKBACK):ia].mean()
        actual_low_reached = d.Low.iloc[peak_i + 1:consolidation_start_i + 1].min()

        out = dict(
            a_to_peak_days=peak_i - ia, peak_high=peak_high,
            days_peak_to_low=pullback_low_i - peak_i,
            max_retracement_pct=(actual_low_reached / peak_high - 1) * 100,
            max_lower_low_streak=max_lower_low_streak, rearm_count=rearm_count,
            first_lower_close_days=(first_lower_close_i - peak_i) if first_lower_close_i else None,
            consolidation_start_days=consolidation_start_i - peak_i,
            box_low=box_low_confirmed_close, range_width_pct=range_width_pct,
            daily_range_pct=daily_range_pct, vol_mean_box=vol_mean_box,
            vol_ratio_box_vs_prepeak=(vol_mean_box / vol_mean_pre_peak) if vol_mean_pre_peak else None,
        )
        if resolution_i is None:
            out.update(outcome="unresolved_at_window_end", consolidation_days=end - 1 - consolidation_start_i)
            out.update(a_low_breach_stats(d, ia, a_day_low, peak_i + 1, end - 1))
        else:
            out.update(outcome=resolution_type, consolidation_days=resolution_i - consolidation_start_i,
                       resolution_days_from_peak=resolution_i - peak_i)
            out.update(a_low_breach_stats(d, ia, a_day_low, peak_i + 1, resolution_i))
        return out

    # loop exhausted the window while still re-arming / making new lows
    actual_low_reached = d.Low.iloc[peak_i + 1:end].min()
    cd_out = dict(
        outcome="continued_decline_no_stabilization",
        a_to_peak_days=peak_i - ia, peak_high=peak_high,
        max_retracement_pct=(actual_low_reached / peak_high - 1) * 100,
        max_lower_low_streak=max_lower_low_streak, rearm_count=rearm_count,
        first_lower_close_days=(first_lower_close_i - peak_i) if first_lower_close_i else None,
    )
    cd_out.update(a_low_breach_stats(d, ia, a_day_low, peak_i + 1, end - 1))
    return cd_out


def main():
    tickers = sorted(f[:-4] for f in os.listdir(DAILY_DIR) if f.endswith(".csv") and not f.startswith("_"))
    print(f"Scanning {len(tickers)} tickers (ungated, canonical A definition)...")

    rows = []
    total_raw_qualifying = 0
    total_episodes = 0
    for n, ticker in enumerate(tickers):
        d = load_daily(ticker)
        if d is None:
            continue
        starts, n_raw = find_episode_starts(d)
        total_raw_qualifying += n_raw
        for ia, cluster_length, a_vol_ratio in starts:
            end = min(ia + 1 + WINDOW_DAYS, len(d))
            if end - ia < 10:
                continue
            peak_i, peak_high, peak_hit_window_end = find_peak(d, ia, end)
            if peak_hit_window_end:
                rows.append(dict(ticker=ticker, a_entry_date=str(d.Date.iloc[ia].date()),
                                  cluster_length=cluster_length, a_vol_ratio=a_vol_ratio,
                                  outcome="peak_hit_window_end"))
                continue
            res = lifecycle(d, ia, peak_i, peak_high, end)
            res.update(ticker=ticker, a_entry_date=str(d.Date.iloc[ia].date()),
                        peak_date=str(d.Date.iloc[peak_i].date()), cluster_length=cluster_length,
                        a_vol_ratio=a_vol_ratio)
            rows.append(res)
            total_episodes += 1
        if (n + 1) % 500 == 0:
            print(f"  ...{n+1}/{len(tickers)} tickers, {len(rows):,} episodes so far")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb08b_novolfloor.csv", index=False)

    print(f"\n=== A. POPULATION SUMMARY ===")
    print(f"Total raw qualifying days (ungated): {total_raw_qualifying:,}")
    print(f"Episodes (first-of-cluster): {len(df):,}")
    print(f"Unique tickers: {df.ticker.nunique()}")
    print(f"Year breakdown:")
    df["year"] = pd.to_datetime(df.a_entry_date).dt.year
    print(df.year.value_counts().sort_index())
    print(f"\nCluster-size distribution:")
    print(f"  isolated (1): {(df.cluster_length==1).mean()*100:.1f}%")
    print(f"  2-3: {df.cluster_length.between(2,3).mean()*100:.1f}%")
    print(f"  4+: {(df.cluster_length>=4).mean()*100:.1f}%  (max={df.cluster_length.max()})")

    print(f"\n=== C. OUTCOME BUCKETS ===")
    print(df.outcome.value_counts())
    print()
    print((df.outcome.value_counts(normalize=True) * 100).round(1))

    print(f"\n=== B. LIFECYCLE DISTRIBUTION (by outcome bucket) ===")
    for outcome in ["immediate_continuation", "consolidation_resumption", "consolidation_failure",
                    "continued_decline_no_stabilization", "unresolved_at_window_end"]:
        sub = df[df.outcome == outcome]
        if sub.empty:
            continue
        print(f"\n--- {outcome} (n={len(sub):,}) ---")
        print(f"  median a_to_peak_days: {sub.a_to_peak_days.median():.1f}")
        print(f"  median max_retracement_pct: {sub.max_retracement_pct.median():.2f}%")
        print(f"  median rearm_count: {sub.rearm_count.median():.1f}  "
              f"(% with >=1 rearm: {(sub.rearm_count>=1).mean()*100:.1f}%)")
        if "consolidation_days" in sub.columns:
            cd = sub.consolidation_days.dropna()
            if len(cd):
                print(f"  median consolidation_days: {cd.median():.1f}")
        if "range_width_pct" in sub.columns:
            rw = sub.range_width_pct.dropna()
            if len(rw):
                print(f"  median box range_width_pct: {rw.median():.2f}%")
        if "vol_ratio_box_vs_prepeak" in sub.columns:
            vr = sub.vol_ratio_box_vs_prepeak.dropna()
            if len(vr):
                print(f"  median box volume vs pre-peak volume: {vr.median():.2f}x")
        if "breached_a_day_low" in sub.columns:
            br = sub.breached_a_day_low.dropna()
            if len(br):
                print(f"  % that breached the A-day's own Low before resolution: {br.mean()*100:.1f}%")

    print(f"\n=== CLEAN vs ROUND-TRIP RESUMPTION (BAJFINANCE catch -- does 'resumed' hide a scary pullback?) ===")
    resumed_pop = df[df.outcome == "consolidation_resumption"].copy()
    resumed_pop = resumed_pop[resumed_pop.breached_a_day_low.notna()]
    print(f"n={len(resumed_pop):,}")
    print(f"  Clean (never breached A-day Low): {(~resumed_pop.breached_a_day_low).mean()*100:.1f}%")
    print(f"  Round-trip (breached A-day Low before eventually resuming): {resumed_pop.breached_a_day_low.mean()*100:.1f}%")
    near_miss = resumed_pop[~resumed_pop.breached_a_day_low]
    print(f"  Of the 'clean' ones, median closest approach to A-day Low: "
          f"{near_miss.min_low_vs_a_day_low_pct.median():.2f}% above it")

    print(f"\n=== TRIGGER STRENGTH DIAGNOSTIC (A-day vol_ratio, NOT a filter -- per user's request) ===")
    resolved = df[df.outcome.isin(["immediate_continuation", "consolidation_resumption", "consolidation_failure"])].copy()
    resolved["vol_tier"] = pd.cut(resolved.a_vol_ratio, [1.5, 2, 5, 10, np.inf],
                                   labels=["1.5-2x (marginal)", "2-5x", "5-10x", "10x+ (TATACONSUM-vs-HILTON-Dec13 scale)"])
    for tier, g in resolved.groupby("vol_tier", observed=True):
        resumed = (g.outcome == "consolidation_resumption").mean() * 100
        imm_cont = (g.outcome == "immediate_continuation").mean() * 100
        failed = (g.outcome == "consolidation_failure").mean() * 100
        print(f"  {tier:38} n={len(g):6,}  immediate_cont={imm_cont:4.1f}%  "
              f"consol_resumed={resumed:4.1f}%  consol_failed={failed:4.1f}%")

    print(f"\nWritten: {HERE}/rq_emapb08b_novolfloor.csv")


if __name__ == "__main__":
    main()
