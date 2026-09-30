"""RQ-QS-07A-P4 -- S-State Entry Intervention (2026-09-30, critic-specified).

Pre-registered per critic's exact design. The only intervention: S(T-1)
eligibility. Everything else stays frozen -- same universe, same 10/20/40
breakout definitions, same frozen v0.1 gate, same intraday breach, same
entry price, same S1b stop, same MAX_HOLD_DAYS=15, same walk_ticker()
mechanics. No threshold search, no S-coverage optimization (CG1's S
definition is frozen; this tests whether the ALREADY-DISCOVERED state has
product value, not whether a different one would).

PRE-INTERVENTION INTEGRITY AUDIT (done first, per critic's instruction --
result: PASS, D15 close_r gap survives in all three, giveback lower in S
for all three -- proceeding to the intervention):
  10D: S median D15 close_r=+0.284R vs non-S +0.119R, giveback 58.4% vs 63.8%
  20D: S median D15 close_r=+0.291R vs non-S +0.099R, giveback 57.4% vs 62.6%
  40D: S median D15 close_r=+0.277R vs non-S +0.089R, giveback 58.6% vs 62.1%

BASELINE vs S-FILTERED vs EXCLUDED (critic's exact three-way comparison --
filtering out ~85% of the population is not free, must be shown, not
assumed away):
  Baseline: all 46,613 original QS-A positions.
  S-filtered: baseline AND S(T-1) -- the intervention.
  Excluded: baseline MINUS S-filtered (everything the filter would give up,
  including the 7,975 T-1-unclassifiable positions -- correctly landing
  here since S eligibility cannot be verified for them).

PER-TRADE REALIZED R (production-consistent, NOT close_r_D15 alone): a real
QS-A position exits at exactly STOP_R=-1.0 if stopped within the 15-day
window (confirmed via `qs_dashboard.py`'s own STOP_R/MAX_TRACK_DAYS
constants), or at the D15 close if never stopped. Using `close_r_D15`
directly for stopped positions would silently assume the trade kept riding
past its own stop -- `envelope()`'s trajectory columns deliberately keep
tracking post-stop for OPPORTUNITY measurement (RQ-06's own purpose), but
that is NOT the realized outcome of an actual production trade.

WIN-RATE STACK, per this project's own standing Reporting Convention
(adopted 2026-09-26): r_multiple>0 (gross), >=0.25R (Meaningful Win),
>=0.5R (quality), >=1.0R (full-R), plus Payoff Ratio -- never a single win
rate number.

CAPACITY-CONSTRAINED COMPARISON: reuses `risk_of_ruin.py`'s standing
methodology (FCFS by entry_date, no ranking) -- this project's own default
for comparing two differently-sized populations. IMPORTANT DISCLOSURE: no
`max_concurrent` portfolio-capacity parameter has ever been established for
QS-A specifically in this codebase (checked directly, no hits). Reported at
an explicitly-labeled ILLUSTRATIVE capacity (20 concurrent positions, a
round retail-scale assumption), not a validated production parameter --
flagged for the critic to confirm or replace, not silently treated as
settled.

No S-coverage tuning. No threshold change. No combining with W (W is
CLOSED for QS-A integration, structurally incompatible, per P3).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots
from risk_of_ruin import capacity_constrained_backtest

OUT_DIR = "swing_qs_07a"
STOP_R = -1.0
MAX_TRACK_DAYS = 15
CAPACITY_SWEEP = (3, 5, 10, 20, 50)  # sensitivity sweep, not a single arbitrary pick --
                                       # no max_concurrent has ever been established for
                                       # QS-A specifically in this codebase

print("Loading P3's overlay (W/S-tagged QS-A population)...", flush=True)
env = pd.read_csv(f"{OUT_DIR}/p3_qsa_wstate_overlay.csv", parse_dates=["entry_date", "t_minus_1"])
print(f"Baseline QS-A: {len(env):,} positions")

print("\nComputing production-consistent realized R and exit_date per position...", flush=True)
cache = {}
exit_dates = []
final_rs = []
for r in env.itertuples():
    if r.ticker not in cache:
        try:
            cache[r.ticker] = load(r.ticker, daily_pivots).index
        except FileNotFoundError:
            cache[r.ticker] = None
    idx = cache[r.ticker]
    exit_offset = int(r.stopped_by_D15) if pd.notna(r.stopped_by_D15) else MAX_TRACK_DAYS
    final_r = STOP_R if pd.notna(r.stopped_by_D15) else r.close_r_D15
    if idx is None or r.entry_date not in idx:
        exit_dates.append(pd.NaT)
        final_rs.append(final_r if pd.notna(final_r) else np.nan)
        continue
    pos = idx.get_loc(r.entry_date)
    exit_i = min(pos + exit_offset, len(idx) - 1)
    exit_dates.append(idx[exit_i])
    final_rs.append(final_r if pd.notna(final_r) else np.nan)
env["exit_date"] = exit_dates
env["final_r"] = final_rs
print(f"final_r resolved for {env.final_r.notna().sum():,} of {len(env):,} positions")

baseline = env[env.final_r.notna()].copy()
s_filtered = baseline[baseline.is_S].copy()
excluded = baseline[~baseline.is_S].copy()
print(f"\nBaseline (resolved): {len(baseline):,}   S-filtered: {len(s_filtered):,} "
      f"({len(s_filtered)/len(baseline)*100:.1f}% coverage)   Excluded: {len(excluded):,}")


def win_rate_stack(r):
    r = r.dropna()
    winners_meaningful = r[r >= 0.25]
    losers = r[r < 0.25]
    payoff = winners_meaningful.mean() / abs(r[r < 0].mean()) if (r < 0).any() and len(winners_meaningful) else np.nan
    return dict(
        n=len(r), mean_r=r.mean(), median_r=r.median(),
        pct_gross_positive=(r > 0).mean() * 100, pct_meaningful=(r >= 0.25).mean() * 100,
        pct_quality=(r >= 0.5).mean() * 100, pct_full_r=(r >= 1.0).mean() * 100,
        payoff_ratio=payoff,
    )


print(f"\n{'='*115}\nPRIMARY COMPARISON -- win-rate stack (per this project's standing Reporting Convention)\n{'='*115}")
rows = []
for label, df in [("Baseline (all QS-A)", baseline), ("S-filtered (intervention)", s_filtered), ("Excluded", excluded)]:
    stats = win_rate_stack(df.final_r)
    rows.append(dict(group=label, **stats))
    print(f"\n-- {label} --")
    print(f"  n={stats['n']:,}  mean_R={stats['mean_r']:+.4f}  median_R={stats['median_r']:+.4f}")
    print(f"  win-rate stack: gross>0={stats['pct_gross_positive']:.1f}%  >=0.25R(meaningful)={stats['pct_meaningful']:.1f}%  "
          f"  >=0.5R(quality)={stats['pct_quality']:.1f}%  >=1.0R(full)={stats['pct_full_r']:.1f}%")
    print(f"  payoff ratio (avg meaningful-winner R / |avg loser R|): {stats['payoff_ratio']:.2f}")
pd.DataFrame(rows).to_csv(f"{OUT_DIR}/p4_winrate_stack.csv", index=False)

print(f"\n{'='*115}\nSECONDARY -- D3/D5/D10/D15 close_r, MFE/MAE (already-established P3 comparison, repeated here for context)\n{'='*115}")
for label, df in [("Baseline", baseline), ("S-filtered", s_filtered), ("Excluded", excluded)]:
    print(f"\n-- {label} --")
    for d in [3, 5, 10, 15]:
        print(f"  close_r D{d}: median={df[f'close_r_D{d}'].median():+.3f}R")
    for d in [1, 3, 5]:
        print(f"  mfe D{d}: median={df[f'mfe_D{d}'].median():+.3f}R")
    print(f"  mae D15: median={df.mae_D15.median():+.3f}R")

print(f"\n{'='*115}\nCAPACITY-CONSTRAINED COMPARISON (risk_of_ruin.py, FCFS by entry_date, no ranking) -- "
      f"SENSITIVITY SWEEP across {CAPACITY_SWEEP}, since no max_concurrent has ever been established as an "
      f"actual QS-A production parameter in this codebase (checked directly, no hits)\n{'='*115}")
for label, df in [("Baseline", baseline), ("S-filtered", s_filtered)]:
    print(f"\n-- {label} --")
    trades = df[["entry_date", "exit_date", "final_r"]].dropna().rename(columns={"final_r": "r_multiple"})
    for n_slots in CAPACITY_SWEEP:
        result = capacity_constrained_backtest(trades, n_slots)
        print(f"  max_concurrent={n_slots:3d}: n_admitted={result['n_admitted']:,}/{result['n_total']:,}  "
              f"cumulative_R={result['cumulative_r']:+.1f}  max_drawdown_R={result['max_drawdown_r']:.2f}  "
              f"worst_streak_R={result['worst_streak_r']:.2f} (n={result['worst_streak_n']})")

baseline.to_csv(f"{OUT_DIR}/p4_baseline_positions.csv", index=False)
print("\nDONE")
