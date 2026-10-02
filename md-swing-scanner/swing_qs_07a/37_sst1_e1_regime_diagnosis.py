"""RQ-QS-07A-SST1-E1-R1 -- Frozen-path regime diagnosis (2026-10-02,
critic-specified, exact next action after SST1-E1's 2025/2026 weakness).

QUESTION: did the trades become harder to monetize in 2025-26 even though
the underlying opportunity (freshness' MFE edge) remained intact? Or did
the fresh-transition idea itself quietly stop working, with the "regime"
story just a convenient excuse?

EVERYTHING FROZEN, NOTHING CHANGED (critic's explicit instruction) -- same
fresh-transition population (run_age=1), same T0-close entry, same 1.5x
ATR14 stop, same 3-day horizon, same 3x-risk target. Only the PERIOD SPLIT
(2022-2024 vs 2025-2026) and the DIAGNOSTIC LENS change. Compared against
`established` (run_age>=8) under the IDENTICAL frozen mechanics, as a
control population -- if established shows the same period-over-period
shape change, that points to a broad regime effect; if only fresh degrades,
that points to a candidate-specific problem.

NOT ALLOWED (critic's explicit list): no new ATR multiplier, no 2-day/5-day
horizon, no regime-specific stop or target, no early exit, no 2025-specific
filter, no liquidity filter, no parameter optimization. This is diagnosis,
not a fix.

DIAGNOSTICS COMPUTED PER (population, period) CELL:
  - MFE (max_return_d3), MAE (adverse_d3) -- the raw opportunity/risk,
    independent of the frozen stop/target.
  - day_of_max -- which day (1/2/3) the 3-day High peak actually occurs.
  - outcome/R under the frozen 1.5x-ATR-stop / 3x-risk-target mechanics
    (identical walk to script 36).
  - gap_through_stop / gap_through_target -- did the triggering day's own
    OPEN already sit beyond the level (a gap doing the damage/the work),
    vs. an intraday High/Low crossing during the day.
  - was_green_before_stop -- for STOP-outcome trades only: did price ever
    trade above entry on an earlier day before the stop day (a real
    unrealized profit that was given back), vs. going straight down.
  - giveback = max_return_d3 - close_ret_d3 (the simple, already-familiar
    opportunity-vs-sustained gap used throughout this chain).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = "swing_qs_07a"
STOP_MULT = 1.5
TARGET_MULT = 3.0  # frozen, the middle of the 3 tested in script 36 -- not re-tuned here

print("Loading fresh (run_age=1) and established (run_age>=8) populations...", flush=True)
feats_b = pd.read_csv(f"{OUT_DIR}/sst1_freshness_features.csv", parse_dates=["date"])
target_pop = feats_b[(feats_b.run_age == 1) | (feats_b.run_age >= 8)].copy()
target_pop["bucket"] = np.where(target_pop.run_age == 1, "fresh", "established")
target_pop["period"] = np.where(target_pop.date.dt.year <= 2024, "2022-2024", "2025-2026")
print(target_pop.groupby(["bucket", "period"]).size().to_string())

grouped = dict(tuple(target_pop.groupby("ticker")))
rows_out = []
for n, t in enumerate(grouped):
    if n % 300 == 0:
        print(f"  {n}/{len(grouped)} tickers", flush=True)
    idf = load(t, daily_pivots)
    close, open_, high, low, atr14 = idf.Close, idf.Open, idf.High, idf.Low, idf.atr14
    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        pos = idf.index.get_loc(r.date)
        if pos + 3 >= len(idf) or pd.isna(atr14.iloc[pos]) or atr14.iloc[pos] <= 0:
            continue
        entry = close.iloc[pos]
        risk = STOP_MULT * atr14.iloc[pos]
        stop_level = entry - risk
        target_level = entry + TARGET_MULT * risk

        h1, h2, h3 = high.iloc[pos+1], high.iloc[pos+2], high.iloc[pos+3]
        l1, l2, l3 = low.iloc[pos+1], low.iloc[pos+2], low.iloc[pos+3]
        c3 = close.iloc[pos+3]
        max_h = max(h1, h2, h3)
        min_l = min(l1, l2, l3)
        mfe = (max_h / entry - 1) * 100
        mae = (min_l / entry - 1) * 100
        day_of_max = 1 if h1 >= max_h else (2 if h2 >= max_h else 3)
        close_ret_d3 = (c3 / entry - 1) * 100

        outcome, day_hit, gap_through, was_green_before = None, None, False, False
        seen_green = False
        for d, (o, h, l) in enumerate([(open_.iloc[pos+1], h1, l1), (open_.iloc[pos+2], h2, l2), (open_.iloc[pos+3], h3, l3)], start=1):
            if l <= stop_level:
                outcome, day_hit = "stop", d
                gap_through = o <= stop_level
                was_green_before = seen_green
                break
            if h >= target_level:
                outcome, day_hit = "target", d
                gap_through = o >= target_level
                break
            if h > entry:
                seen_green = True
        if outcome is None:
            outcome, day_hit = "neither", 3
            r_mult = (c3 - entry) / risk
        elif outcome == "stop":
            r_mult = -1.0
        else:
            r_mult = TARGET_MULT

        rows_out.append(dict(ticker=t, date=r.date, bucket=r.bucket, period=r.period,
                               mfe=mfe, mae=mae, day_of_max=day_of_max, close_ret_d3=close_ret_d3,
                               outcome=outcome, day_hit=day_hit, r_mult=r_mult,
                               gap_through=gap_through, was_green_before_stop=was_green_before,
                               giveback=mfe - close_ret_d3))

diag = pd.DataFrame(rows_out)
diag.to_csv(f"{OUT_DIR}/sst1_e1_regime_diagnosis.csv", index=False)
print(f"\n{len(diag):,} rows, saved sst1_e1_regime_diagnosis.csv")


def summarize(label, grp):
    n = len(grp)
    if n == 0:
        print(f"  {label}: n=0")
        return
    target_rate = (grp.outcome == "target").mean() * 100
    stop_rate = (grp.outcome == "stop").mean() * 100
    neither_rate = (grp.outcome == "neither").mean() * 100
    gap_stop_rate = grp[grp.outcome == "stop"].gap_through.mean() * 100 if (grp.outcome == "stop").any() else float("nan")
    gap_target_rate = grp[grp.outcome == "target"].gap_through.mean() * 100 if (grp.outcome == "target").any() else float("nan")
    green_before_rate = grp[grp.outcome == "stop"].was_green_before_stop.mean() * 100 if (grp.outcome == "stop").any() else float("nan")
    print(f"  {label:28s} n={n:6,}  MFE_med={grp.mfe.median():+6.2f}%  MAE_med={grp.mae.median():+6.2f}%  "
          f"day_of_max_mode={grp.day_of_max.mode().iloc[0]}  giveback_med={grp.giveback.median():+6.2f}%")
    print(f"  {'':28s} target%={target_rate:5.1f}  stop%={stop_rate:5.1f}  neither%={neither_rate:5.1f}  "
          f"mean_R={grp.r_mult.mean():+.3f}  median_R={grp.r_mult.median():+.3f}")
    print(f"  {'':28s} of stop-outs: gapped-through-stop={gap_stop_rate:5.1f}%  was-green-before-stopping={green_before_rate:5.1f}%  "
          f"of target-hits: gapped-through-target={gap_target_rate:5.1f}%")


print(f"\n{'='*120}\nFRESH -- 2022-2024 vs 2025-2026 (frozen mechanics)\n{'='*120}")
summarize("fresh, 2022-2024", diag[(diag.bucket=="fresh") & (diag.period=="2022-2024")])
print()
summarize("fresh, 2025-2026", diag[(diag.bucket=="fresh") & (diag.period=="2025-2026")])

print(f"\n{'='*120}\nESTABLISHED (control) -- 2022-2024 vs 2025-2026 (same frozen mechanics)\n{'='*120}")
summarize("established, 2022-2024", diag[(diag.bucket=="established") & (diag.period=="2022-2024")])
print()
summarize("established, 2025-2026", diag[(diag.bucket=="established") & (diag.period=="2025-2026")])

print("\nDONE")
