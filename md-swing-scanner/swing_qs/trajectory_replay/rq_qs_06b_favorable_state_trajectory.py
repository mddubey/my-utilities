"""RQ-QS-06B -- Favorable-State Trajectory Anatomy (2026-09-29, critic-specified).

Frozen QS-A population, same entry, same S1b stop -- NO new entry, NO new filter,
NO exit rule, NO threshold optimization. RQ-06 established THAT QS-A visits
favorable territory fast (median MFE +0.80R by D5) while the median CLOSE stays
flat -- this script asks the missing question: once a trade first reaches a given
favorable state, what does the path look like AFTER that, and is the excursion a
wick-and-reverse or a persistent, confirmed move?

Reuses the exact same 46,613 frozen positions as RQ-QS-06 (same entries, same
initial_risk_pct -- read directly from rq_qs_06_envelope.csv rather than re-walking
the universe). Extends the walk to the FULL MAX_TRACK_DAYS=15 window this time
(RQ-06 capped at D5) since "15D eventual MFE/R," "return to entry," "makes a new
high" all need the complete trade, not just the first 5 days. Independently re-walks
day-by-day (does not trust walk_ticker's own cur["max_r"]/exit_i) using the SAME
stricter local 25% corp-action check RQ-06 already had to add (production's
corp_action_day column missed a real 33.04% bonus-issue move) -- kept consistent
rather than risk the same bug re-entering through a different code path.

For each of 6 R-levels [0.25, 0.5, 0.75, 1.0, 1.5, 2.0], conditional on a trade
FIRST reaching that level (High-based MFE, matching this project's raw-trigger
convention), measures:
  day_first_reached, close_r_that_day, persistent_half (close_r_that_day >= level/2
      -- the exact distinction critic's own example draws: "does it close above
      +0.25R, or does it merely wick through +0.5R"),
  giveback_by_dX+1/+2/+3 (close_r at day_first_reached+k vs the level just touched),
  returns_to_entry (Low-based R drops to <=0 at any point after this day, + when),
  returns_below_half (Low-based R drops back below level/2, + when),
  reaches_next_level (does the trade go on to ALSO touch the next level up --
      "makes a new higher peak"),
  eventual_exit_r, eventual_max_r_15d, exit_reason, days_held (trade-level, not
      level-conditional).

Archetype classification (simple, rule-based, disclosed -- NOT claimed to be
exhaustive or objectively correct, a first descriptive pass per critic's own framing
of the four possible mechanisms):
  wick_and_fail: reaches >=0.5R, closes that day below 0.25R (not persistent), AND
      is stopped out (-1R) within the following 2 days.
  burst_then_exhaustion: reaches >=1.5R at some point, but the eventual exit R is
      <=50% of that peak.
  slow_oscillation: reaches >=0.5R, later drops back below 0.25R, then reaches
      >=0.5R again -- without ever reaching 1R.
  persistent_continuation: reaches every level it touches with day_first_reached
      gaps of <=3 days between consecutive levels, and eventual exit R is >=50% of
      its own 15D peak.
  unclassified: none of the above (a trade can legitimately not fit any bucket).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
R_LEVELS = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0]
MAX_TRACK_DAYS = 15


def walk_full(rows, entry_i, entry_price, risk_pct):
    """Independent day-by-day walk to exit (stop, max_days, corp-action truncation,
    or history end) -- does not trust any externally-computed exit_i/max_r."""
    n_rows = len(rows)
    days = []  # list of dicts: day, close_r, high_r, low_r, mfe_so_far, mae_so_far
    running_mfe, running_mae = -float("inf"), float("inf")
    exit_reason, exit_day = None, None
    for d in range(1, MAX_TRACK_DAYS + 1):
        k = entry_i + d
        if k >= n_rows:
            exit_reason, exit_day = "history_end", d - 1
            break
        prev_close = rows.iloc[k - 1].Close if k > 0 else None
        real_jump = bool(prev_close and abs(rows.iloc[k].Close / prev_close - 1) > 0.25)
        if rows.iloc[k].corp_action_day or real_jump:
            exit_reason, exit_day = "corp_action_truncated", d - 1
            break
        row = rows.iloc[k]
        close_r = (row.Close / entry_price - 1) * 100 / risk_pct
        high_r = (row.High / entry_price - 1) * 100 / risk_pct
        low_r = (row.Low / entry_price - 1) * 100 / risk_pct
        running_mfe = max(running_mfe, high_r)
        running_mae = min(running_mae, low_r)
        days.append(dict(day=d, close_r=close_r, high_r=high_r, low_r=low_r,
                           mfe_so_far=running_mfe, mae_so_far=running_mae))
        if low_r <= -1.0:
            exit_reason, exit_day = "stop", d
            break
    if exit_reason is None:
        exit_reason, exit_day = "max_days", MAX_TRACK_DAYS
    return days, exit_reason, exit_day


def analyze(rows, a):
    entry_i, entry_price, risk_pct = a["entry_i"], a["entry_price"], a["initial_risk_pct"]
    days, exit_reason, exit_day = walk_full(rows, entry_i, entry_price, risk_pct)
    if not days:
        return None
    day_map = {d["day"]: d for d in days}
    eventual_max_r_15d = max(d["mfe_so_far"] for d in days)
    exit_r = days[-1]["close_r"] if exit_reason != "stop" else -1.0

    rec = dict(ticker=a["ticker"], entry_definition=a["entry_definition"], entry_date=a["entry_date"],
                exit_reason=exit_reason, exit_day=exit_day, eventual_max_r_15d=eventual_max_r_15d,
                eventual_exit_r=exit_r)

    level_first_day = {}
    for level in R_LEVELS:
        hit = next((d for d in days if d["mfe_so_far"] >= level), None)
        if hit is None:
            for suffix in ["day_first_reached", "close_r_that_day", "persistent_half",
                            "close_positive_that_day", "giveback_d1", "giveback_d2", "giveback_d3",
                            "returns_to_entry", "returns_to_entry_day", "returns_below_half",
                            "reaches_next_level"]:
                rec[f"{suffix}_{level}R"] = None
            continue
        d0 = hit["day"]
        level_first_day[level] = d0
        close0 = hit["close_r"]
        rec[f"day_first_reached_{level}R"] = d0
        rec[f"close_r_that_day_{level}R"] = close0
        rec[f"persistent_half_{level}R"] = bool(close0 >= level / 2)
        rec[f"close_positive_that_day_{level}R"] = bool(close0 > 0)

        # giveback is relative to the RUNNING PEAK as of that future day (which already
        # incorporates any further gain between d0 and d0+k), not the static level just
        # touched -- anchoring to the static level was wrong: if price kept climbing past
        # the level, (level - close)/level went strongly NEGATIVE (nonsensical "negative
        # giveback"), and if it fell hard, the same static denominator understated real
        # giveback. mfe_so_far is monotonically non-decreasing and >=level by construction
        # from d0 onward, so this is always a safe, meaningful 0%+ (or >100% if it round-
        # trips past the peak into a loss) percentage, matching RQ-06's own convention.
        after = [d for d in days if d["day"] > d0]
        for k in (1, 2, 3):
            fut = day_map.get(d0 + k)
            rec[f"giveback_d{k}_{level}R"] = ((fut["mfe_so_far"] - fut["close_r"]) / fut["mfe_so_far"] * 100) if fut else None

        ret_entry = next((d for d in after if d["low_r"] <= 0), None)
        rec[f"returns_to_entry_{level}R"] = ret_entry is not None
        rec[f"returns_to_entry_day_{level}R"] = (ret_entry["day"] - d0) if ret_entry else None

        ret_half = next((d for d in after if d["low_r"] <= level / 2), None)
        rec[f"returns_below_half_{level}R"] = ret_half is not None

    for i, level in enumerate(R_LEVELS):
        if level not in level_first_day:
            rec[f"reaches_next_level_{level}R"] = None
            continue
        if i + 1 >= len(R_LEVELS):
            rec[f"reaches_next_level_{level}R"] = None
            continue
        rec[f"reaches_next_level_{level}R"] = R_LEVELS[i + 1] in level_first_day

    # --- archetype classification (simple, disclosed, non-exhaustive) ---
    archetype = "unclassified"
    if 0.5 in level_first_day:
        d05 = level_first_day[0.5]
        closed_not_persistent = rec.get("close_r_that_day_0.5R", 0) < 0.25
        stopped_within_2 = exit_reason == "stop" and exit_day is not None and exit_day - d05 <= 2 and exit_day >= d05
        if closed_not_persistent and stopped_within_2:
            archetype = "wick_and_fail"
    if archetype == "unclassified" and 1.5 in level_first_day:
        if exit_r <= 0.5 * eventual_max_r_15d:
            archetype = "burst_then_exhaustion"
    if archetype == "unclassified" and 0.5 in level_first_day and 1.0 not in level_first_day:
        d05 = level_first_day[0.5]
        after05 = [d for d in days if d["day"] > d05]
        dropped_then_back = any(d["low_r"] <= 0.25 for d in after05) and any(d["high_r"] >= 0.5 for d in after05)
        if dropped_then_back:
            archetype = "slow_oscillation"
    if archetype == "unclassified" and len(level_first_day) >= 2:
        touched_levels = sorted(level_first_day.keys())
        gaps_ok = all(level_first_day[touched_levels[i+1]] - level_first_day[touched_levels[i]] <= 3
                       for i in range(len(touched_levels) - 1))
        if gaps_ok and exit_r >= 0.5 * eventual_max_r_15d:
            archetype = "persistent_continuation"
    rec["archetype"] = archetype
    return rec


def pstack(s, fmt="{:.2f}", suffix=""):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}{suffix}" for p in [25, 50, 75, 90]) + f"  (n={len(s)})"


if __name__ == "__main__":
    src = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06_envelope.csv", parse_dates=["entry_date"])
    cache = {}
    recs = []
    for n, r in enumerate(src.itertuples()):
        if n % 5000 == 0:
            print(f"{n}/{len(src)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        m = rows.index[rows.Date == r.entry_date]
        if len(m) == 0:
            continue
        entry_i = m[0]
        a = dict(ticker=r.ticker, entry_definition=r.entry_definition, entry_date=str(r.entry_date.date()),
                   entry_i=entry_i, entry_price=r.entry_price, initial_risk_pct=r.initial_risk_pct)
        rows_full = rows
        rec = analyze(rows_full, a)
        if rec:
            recs.append(rec)
    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq_qs_06b_state_trajectory.csv", index=False)
    print(f"\n{len(df)} positions analyzed\n")

    print("=== State table: first favorable state -> what happens after ===\n")
    hdr = f"{'level':>7} {'N':>7} {'med_day':>8} {'close+':>8} {'persist':>8} {'ret_entry':>10} {'new_high':>9} {'giveback>=50@exit':>18}"
    print(hdr)
    for level in R_LEVELS:
        n_reached = df[f"day_first_reached_{level}R"].notna().sum()
        if n_reached == 0:
            print(f"{level:>7}R {0:>7}")
            continue
        med_day = df[f"day_first_reached_{level}R"].median()
        close_pos = df[f"close_positive_that_day_{level}R"].mean() * 100
        persist = df[f"persistent_half_{level}R"].mean() * 100
        ret_entry = df[f"returns_to_entry_{level}R"].mean() * 100
        new_high_col = f"reaches_next_level_{level}R"
        new_high = df[new_high_col].dropna().mean() * 100 if df[new_high_col].notna().any() else float("nan")
        sub = df[df[f"day_first_reached_{level}R"].notna()]
        gb50 = (sub.eventual_exit_r <= 0.5 * level).mean() * 100
        print(f"{level:>7}R {n_reached:>7} {med_day:>8.0f} {close_pos:>7.1f}% {persist:>7.1f}% "
              f"{ret_entry:>9.1f}% {new_high:>8.1f}% {gb50:>17.1f}%")

    print("\n=== Giveback in the days right after first touching each level ===")
    for level in R_LEVELS:
        print(f"\n  {level}R:")
        for k in (1, 2, 3):
            print(f"    D+{k}: {pstack(df[f'giveback_d{k}_{level}R'], '{:.1f}', '%')}")

    print("\n=== Archetype breakdown (simple rule-based classification, n=%d) ===" % len(df))
    print(df.archetype.value_counts())
    print("\n  by exit outcome:")
    for arch, grp in df.groupby("archetype"):
        print(f"  {arch:24s} n={len(grp):6d}  median eventual_exit_r={grp.eventual_exit_r.median():+.2f}R  "
              f"median eventual_max_r_15d={grp.eventual_max_r_15d.median():+.2f}R")

    print("\n=== Rule #22: hand-check 2 examples ===")
    for _, r in df[df.archetype == "wick_and_fail"].head(1).iterrows():
        print(f"\nwick_and_fail example: {r.ticker} {r.entry_date}  "
              f"day_first_reached_0.5R={r['day_first_reached_0.5R']}  close_that_day={r['close_r_that_day_0.5R']:.2f}R  "
              f"exit_reason={r.exit_reason} exit_day={r.exit_day} eventual_exit_r={r.eventual_exit_r:.2f}R")
    for _, r in df[df.archetype == "persistent_continuation"].head(1).iterrows():
        print(f"\npersistent_continuation example: {r.ticker} {r.entry_date}  "
              f"eventual_exit_r={r.eventual_exit_r:.2f}R  eventual_max_r_15d={r.eventual_max_r_15d:.2f}R")
