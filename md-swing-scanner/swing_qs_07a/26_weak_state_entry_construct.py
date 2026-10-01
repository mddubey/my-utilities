"""RQ-QS-07A-E1 -- Weak-State Recovery: First Independent Entry Construct
(2026-10-01, critic+user-directed). Phase 3-5 of the reset research posture
(`swing_qs_07a/CLAUDE.md`): "if I encountered W at time T, can I define an
executable entry trigger at T or T+1 that captures the subsequent
exceptional-move distribution?" ONE focused entry-design pass, per the
breadth-before-depth rule -- not a marathon, not a threshold search.

NOT an overlay on QS-A. This is W's OWN, independent entry/stop/exit,
measured the same way QS-A was (win-rate stack, capacity-constrained
sweep) purely so the two are directly comparable -- QS-A's own numbers are
cited as context, never modified, never combined with this.

RESEARCH PREFLIGHT (this project's own 5-question discipline, answered
before any line of simulation code ran):
  1. Population: the already-frozen 22,462 historical W events (CG1 W
     definition: D0 AND decline_from_high10d_pct<=frozen median AND T's own
     ret_1d>=0) -- reused exactly, not re-derived. 1,769 distinct tickers,
     2022-09-05 to 2026-09-24.
  2. Entry clock: T+1's OPEN. T is confirmed using T's own EOD close
     (decision-time-safe, matches every W computation this whole line has
     used) -- the earliest a real order could act on that confirmation is
     the next trading session's open, not T's own close.
  3. Stop definition (Rule #20, declared before any R-multiple is computed):
     T's own Low -- the S1b convention, reused from this project's
     established swing-trading practice (QS-A/BC both use "prior day's
     low" as the structural invalidation level), not invented fresh. T is
     literally "the day before entry" once entry moves to T+1, so this is
     the direct analogue of QS-A's own S1b, not a new convention.
  4. Exit engine: mirrors QS-A's own realized-R mechanics exactly (reused
     conceptually, not imported, since this is a different entry/stop
     pair) -- STOP_R=-1.0, MAX_TRACK_DAYS=15, running MFE/MAE from
     High/Low, corp-action-day truncation, exit at stop or the D15 close.
  5. Comparison unit: this construct's OWN realized-R distribution,
     reported with the identical win-rate-stack/capacity-constrained
     methodology already used for QS-A (P4), so the two numbers sit
     side-by-side for comparison -- never an intervention on QS-A itself.

No threshold search. No new W definition. No combination with S. No
multiple stop/entry variants tested against each other -- one pre-declared
construct, reported honestly, then stop (even if a different stop/entry
choice might look better -- that would be the dangerous "maybe tweak it"
fork the critic has explicitly warned against twice already this session).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import json
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from risk_of_ruin import capacity_constrained_backtest

OUT_DIR = "swing_qs_07a"
STOP_R = -1.0
MAX_TRACK_DAYS = 15
CAPACITY_SWEEP = (3, 5, 10, 20, 50)
MIN_RISK_PCT = 1.0  # DATA-INTEGRITY floor, not a tuned threshold -- caught via Rule #22: the first run's
                      # top trade (GLOBAL, 2024-08-16) had initial_risk_pct=0.0059%, an entry/stop gap of
                      # Rs0.004, producing a mathematically meaningless 3399R "return" from dividing by a
                      # near-zero denominator. 10.4% of all 21,399 trades had risk_pct<1.0%, and the top 20
                      # trades in 2024 alone (of 2,553) contributed 91% of that year's entire R-sum --
                      # this stop convention (T's own low) can coincide almost exactly with T+1's open
                      # whenever a stock gaps flat, which is common right after a stabilization day by
                      # construction. 1.0% is a round, pre-declared floor excluding degenerate near-entry
                      # stops (same category of exclusion as QS-A's own `initial_risk_pct<=0` check, just
                      # extended to near-zero, not just non-positive) -- NOT a profitability threshold
                      # search, and not revisited after seeing results a second time.

print("Loading the frozen W population (reused classification, not re-derived)...", flush=True)
mech = pd.read_csv(f"{OUT_DIR}/weak_state_mechanism_features.csv", parse_dates=["date"])
state = pd.read_csv(f"{OUT_DIR}/trend_state_anatomy.csv", parse_dates=["date"])[["ticker", "date", "decile"]]
with open(f"{OUT_DIR}/frozen_candidate_spec.json") as f:
    DECLINE_MEDIAN = json.load(f)["decline_from_high10d_pct_median_weak_state"]

d0 = mech.merge(state, on=["ticker", "date"])
w_events = d0[(d0.decile == 0) & (d0.decline_from_high10d_pct <= DECLINE_MEDIAN) & (d0.ret_1d >= 0)].copy()
print(f"W population: {len(w_events):,} events, {w_events.ticker.nunique():,} tickers, "
      f"{w_events.date.min().date()} to {w_events.date.max().date()}")

print("\nWalking forward from T+1's open with T's low as the stop (per-ticker, decision-time-safe)...", flush=True)
cache = {}
recs = []
for n, (t, sub) in enumerate(w_events.groupby("ticker", sort=False)):
    if n % 300 == 0:
        print(f"  {n}/{w_events.ticker.nunique()}", flush=True)
    if t not in cache:
        try:
            cache[t] = load(t, daily_pivots)
        except FileNotFoundError:
            cache[t] = None
    idf = cache[t]
    if idf is None:
        continue
    idx = idf.index
    for r in sub.itertuples():
        if r.date not in idx:
            continue
        pos_t = idx.get_loc(r.date)
        pos_entry = pos_t + 1  # T+1
        if pos_entry >= len(idx):
            continue  # no next trading day in cache yet
        entry_row = idf.iloc[pos_entry]
        t_row = idf.iloc[pos_t]
        entry_price = entry_row.Open
        stop_price = t_row.Low
        if pd.isna(entry_price) or pd.isna(stop_price) or entry_price <= stop_price:
            continue  # stop must be below entry for a long
        initial_risk_pct = (entry_price - stop_price) / entry_price * 100
        if initial_risk_pct < MIN_RISK_PCT:
            continue  # data-integrity floor, see MIN_RISK_PCT comment above -- excludes degenerate
                       # near-zero-risk gaps, not a profitability threshold

        running_mfe, running_mae = -float("inf"), float("inf")
        stopped_by_day = None
        truncated = False
        day_vals = {}
        for d in range(1, MAX_TRACK_DAYS + 1):
            k = pos_entry + (d - 1)  # d=1 is the entry day itself (T+1)
            if k >= len(idx) or (hasattr(idf.iloc[k], "corp_action_day") and idf.iloc[k].corp_action_day) or truncated:
                truncated = True
                day_vals[d] = (None, running_mfe if running_mfe != -float("inf") else None,
                                 running_mae if running_mae != float("inf") else None)
                continue
            row = idf.iloc[k]
            close_r = (row.Close / entry_price - 1) * 100 / initial_risk_pct
            high_r = (row.High / entry_price - 1) * 100 / initial_risk_pct
            low_r = (row.Low / entry_price - 1) * 100 / initial_risk_pct
            running_mfe = max(running_mfe, high_r)
            running_mae = min(running_mae, low_r)
            if stopped_by_day is None and low_r <= STOP_R:
                stopped_by_day = d
            day_vals[d] = (close_r, running_mfe, running_mae)

        close15, mfe15, mae15 = day_vals[MAX_TRACK_DAYS]
        final_r = STOP_R if stopped_by_day is not None else close15
        if final_r is None:
            continue
        gb = ((mfe15 - close15) / mfe15 * 100) if (mfe15 is not None and close15 is not None and mfe15 > 0) else None
        exit_i = min(pos_entry + (stopped_by_day - 1 if stopped_by_day else MAX_TRACK_DAYS - 1), len(idx) - 1)
        recs.append(dict(
            ticker=t, trigger_date=r.date, entry_date=idx[pos_entry], exit_date=idx[exit_i],
            entry_price=entry_price, stop_price=stop_price, initial_risk_pct=initial_risk_pct,
            stopped_by_day=stopped_by_day, final_r=final_r,
            close_r_d3=day_vals[3][0], close_r_d5=day_vals[5][0], close_r_d10=day_vals[10][0], close_r_d15=close15,
            mfe_d1=day_vals[1][1], mfe_d3=day_vals[3][1], mfe_d5=day_vals[5][1],
            mae_d15=mae15, giveback_pct=gb,
        ))

trades = pd.DataFrame(recs)
trades.to_csv(f"{OUT_DIR}/e1_weak_state_entry_trades.csv", index=False)
print(f"\n{len(trades):,} trades resolved (of {len(w_events):,} W events) -- "
      f"{len(w_events)-len(trades):,} dropped (no next trading day yet, or entry<=stop)")


def win_rate_stack(r):
    r = r.dropna()
    winners_meaningful = r[r >= 0.25]
    payoff = winners_meaningful.mean() / abs(r[r < 0].mean()) if (r < 0).any() and len(winners_meaningful) else np.nan
    return dict(n=len(r), mean_r=r.mean(), median_r=r.median(),
                 pct_gross_positive=(r > 0).mean() * 100, pct_meaningful=(r >= 0.25).mean() * 100,
                 pct_quality=(r >= 0.5).mean() * 100, pct_full_r=(r >= 1.0).mean() * 100, payoff_ratio=payoff)


print(f"\n{'='*110}\nWIN-RATE STACK -- W's own independent entry construct\n{'='*110}")
stats = win_rate_stack(trades.final_r)
print(f"n={stats['n']:,}  mean_R={stats['mean_r']:+.4f}  median_R={stats['median_r']:+.4f}")
print(f"win-rate stack: gross>0={stats['pct_gross_positive']:.1f}%  >=0.25R={stats['pct_meaningful']:.1f}%  "
      f">=0.5R={stats['pct_quality']:.1f}%  >=1.0R={stats['pct_full_r']:.1f}%  payoff={stats['payoff_ratio']:.2f}")
print(f"\n-- for context only, QS-A baseline (P4, same win-rate-stack methodology) --")
print("n=46,601  mean_R=+0.174  gross>0=35.9%  >=0.25R=32.8%  >=0.5R=29.8%  >=1.0R=24.0%  payoff=2.51")

print(f"\n{'='*110}\nSECONDARY -- D3/D5/D10/D15 close, MFE, giveback\n{'='*110}")
for d in [3, 5, 10, 15]:
    print(f"  close_r D{d}: median={trades[f'close_r_d{d}'].median():+.3f}R")
for d in [1, 3, 5]:
    print(f"  mfe D{d}: median={trades[f'mfe_d{d}'].median():+.3f}R")
print(f"  mae D15: median={trades.mae_d15.median():+.3f}R")
gb = trades.giveback_pct.dropna()
print(f"  giveback: median={gb.median():.1f}%  (n={len(gb):,})  %100%-giveback={(gb>=100).mean()*100:.1f}%")
print(f"  stop rate: {trades.stopped_by_day.notna().mean()*100:.1f}%")
print(f"  median initial_risk_pct (stop distance): {trades.initial_risk_pct.median():.2f}%")

print(f"\n{'='*110}\nYEAR-BY-YEAR (never pooled)\n{'='*110}")
trades["year"] = trades.trigger_date.dt.year
for y in sorted(trades.year.unique()):
    yr = trades[trades.year == y]
    if len(yr) < 30:
        print(f"  {y}: n={len(yr)} -- too thin, skipped")
        continue
    print(f"  {y}: n={len(yr):,}  mean_R={yr.final_r.mean():+.3f}  median_R={yr.final_r.median():+.3f}  "
          f"gross>0={100*(yr.final_r>0).mean():.1f}%")

print(f"\n{'='*110}\nCAPACITY-CONSTRAINED (risk_of_ruin.py, FCFS, no ranking) -- sweep across {CAPACITY_SWEEP}\n{'='*110}")
cc_trades = trades[["entry_date", "exit_date", "final_r"]].dropna().rename(columns={"final_r": "r_multiple"})
for n_slots in CAPACITY_SWEEP:
    res = capacity_constrained_backtest(cc_trades, n_slots)
    print(f"  max_concurrent={n_slots:3d}: n_admitted={res['n_admitted']:,}/{res['n_total']:,}  "
          f"cumulative_R={res['cumulative_r']:+.1f}  max_DD={res['max_drawdown_r']:.1f}")
print(f"\n  -- for context only, QS-A baseline at the same capacities (P4) --")
print("  max_concurrent=  5: cumulative_R=-25.9  max_DD=-90.5")
print("  max_concurrent= 10: cumulative_R=-59.0  max_DD=-135.9")

print("\nDONE")
