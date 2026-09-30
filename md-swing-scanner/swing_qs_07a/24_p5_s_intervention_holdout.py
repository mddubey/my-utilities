"""RQ-QS-07A-P5 -- S-State Intervention Chronological OOS Validation
(2026-09-30, critic-specified). Does P4's intervention (S(T-1) eligibility
on top of frozen QS-A) survive on QS-A trades chronologically AFTER a
pre-registered cutoff, using the exact same frozen rule -- not "is S real"
(already validated, CG1/CG3-H), but "does the INTERVENTION's advantage
generalize to a later period."

FROZEN, no exceptions, per critic's explicit prohibition list: same CG1 S
specification (composite, percentile mapping, P90 boundary, T-1 decision-
time evaluation), same QS-A entry machinery, same S1b stop, same 15-day
horizon, same realized-R convention (exit at exactly -1.0R if stopped
within 15 days, else the D15 close -- reused directly from P4's own
already-computed `final_r`/`exit_date`, not recomputed). No new S
percentile, no threshold change, no T-instead-of-T-1, no capacity
optimization, no new stop/exit, no changing the 15-day horizon, no
selecting a "favorable" cutoff after looking at results.

CUTOFF, PRE-REGISTERED BEFORE LOOKING AT ANY COMPARISON RESULT: 2025-01-01.
Chosen for three disclosed reasons, checked before this script computed a
single trajectory comparison: (1) a clean calendar-year boundary, not
cherry-picked; (2) deliberately DIFFERENT from CG3-H's 2026-03-31 cutoff --
critic's explicit instruction not to "repeat CG3-H's holdout and call it
independent," since that exact window has already been extensively
analyzed; (3) the holdout (2025-01-01 to 2026-09-25) coincides with the
ALREADY-ESTABLISHED tougher 2025-26 regime (07R, CG3-H's own April finding)
-- testing S's intervention advantage specifically through a known-harder
stretch is a MORE rigorous test than picking an easy period, not a softer
one. S-filtered coverage in this holdout is 1,323 events (checked before
building the comparison logic, to confirm adequate statistical power).

LABELING DISCIPLINE (same as CG3-H, critic's explicit instruction): this is
a CHRONOLOGICAL OOS VALIDATION of the frozen intervention, NOT "fully
independent blind validation" -- the S specification itself was already
derived from data spanning this same period (CG1's reference population
runs through 2026-09-24), so researcher-conditioning still applies exactly
as it did for CG3-H. Reported as such throughout.

CAPACITY: reported as SECONDARY sensitivity only, explicitly NOT a
production capacity decision -- per critic's exact instruction, deferred to
a separate product-engineering question, not resolved by this research
thread. No max_concurrent is "selected" here.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from risk_of_ruin import capacity_constrained_backtest

OUT_DIR = "swing_qs_07a"
CUTOFF = pd.Timestamp("2025-01-01")
CAPACITY_SWEEP = (3, 5, 10, 20, 50)

print("Loading P4's already-computed population (realized R + exit dates already resolved)...", flush=True)
env = pd.read_csv(f"{OUT_DIR}/p4_baseline_positions.csv", parse_dates=["entry_date", "exit_date"])
print(f"Full population: {len(env):,} positions, {env.entry_date.min().date()} to {env.entry_date.max().date()}")

discovery = env[env.entry_date < CUTOFF].copy()
holdout = env[env.entry_date >= CUTOFF].copy()
print(f"\nDiscovery (pre-cutoff): {len(discovery):,} positions, {discovery.entry_date.min().date()} to "
      f"{discovery.entry_date.max().date()}")
print(f"Holdout (post-cutoff, chronologically OOS relative to this comparison): {len(holdout):,} positions, "
      f"{holdout.entry_date.min().date()} to {holdout.entry_date.max().date()}")


def win_rate_stack(r):
    r = r.dropna()
    winners_meaningful = r[r >= 0.25]
    return dict(
        n=len(r), mean_r=r.mean(), median_r=r.median(),
        pct_gross_positive=(r > 0).mean() * 100, pct_meaningful=(r >= 0.25).mean() * 100,
        pct_quality=(r >= 0.5).mean() * 100, pct_full_r=(r >= 1.0).mean() * 100,
        payoff_ratio=(winners_meaningful.mean() / abs(r[r < 0].mean())) if (r < 0).any() and len(winners_meaningful) else np.nan,
    )


def episodes(sub):
    count = 0
    for t, g in sub.sort_values("entry_date").groupby("ticker"):
        dates = g.entry_date.tolist()
        if not dates:
            continue
        count += 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days > 10:
                count += 1
    return count


all_rows = []
for seg_label, seg in [("DISCOVERY (pre-2025-01-01)", discovery), ("HOLDOUT (2025-01-01 onward, chronological OOS)", holdout)]:
    print(f"\n{'='*115}\n{seg_label}\n{'='*115}")
    baseline_seg = seg[seg.final_r.notna()]
    s_seg = baseline_seg[baseline_seg.is_S]
    n_tickers = s_seg.ticker.nunique()
    n_episodes = episodes(s_seg)
    coverage_pct = len(s_seg) / len(baseline_seg) * 100 if len(baseline_seg) else np.nan
    print(f"  Baseline n={len(baseline_seg):,}   S-filtered n={len(s_seg):,} ({coverage_pct:.1f}% coverage, "
          f"{n_tickers} tickers, {n_episodes} episodes)")

    for label, df in [("Baseline", baseline_seg), ("S-filtered", s_seg)]:
        stats = win_rate_stack(df.final_r)
        all_rows.append(dict(segment=seg_label, group=label, coverage_pct=coverage_pct if label == "S-filtered" else 100.0, **stats))
        print(f"\n  -- {label} -- n={stats['n']:,}  mean_R={stats['mean_r']:+.4f}  median_R={stats['median_r']:+.4f}")
        print(f"     win-rate stack: gross>0={stats['pct_gross_positive']:.1f}%  >=0.25R={stats['pct_meaningful']:.1f}%  "
              f">=0.5R={stats['pct_quality']:.1f}%  >=1.0R={stats['pct_full_r']:.1f}%  payoff={stats['payoff_ratio']:.2f}")
        for d in [3, 5, 10, 15]:
            print(f"     close_r D{d}: median={df[f'close_r_D{d}'].median():+.3f}R", end="  ")
        print()
        gb = df.giveback_from_mfe_pct.dropna()
        print(f"     giveback median={gb.median():.1f}%  (n={len(gb):,})")

    print(f"\n  -- Year-by-year within this segment (never pooled) --")
    seg["year"] = seg.entry_date.dt.year
    for y in sorted(seg.year.unique()):
        yr = seg[(seg.year == y) & seg.final_r.notna()]
        yr_s = yr[yr.is_S]
        if len(yr) < 30:
            print(f"    {y}: n={len(yr)} -- too thin, skipped")
            continue
        b_mean = yr.final_r.mean()
        s_mean = yr_s.final_r.mean() if len(yr_s) >= 10 else np.nan
        print(f"    {y}: baseline n={len(yr):,} mean_R={b_mean:+.3f}   "
              f"S-filtered n={len(yr_s):,} mean_R={s_mean:+.3f}" if pd.notna(s_mean) else
              f"    {y}: baseline n={len(yr):,} mean_R={b_mean:+.3f}   S-filtered n={len(yr_s)} -- too thin")

    print(f"\n  -- Capacity sensitivity (SECONDARY, illustrative FCFS only -- not a production capacity decision) --")
    for label, df in [("Baseline", baseline_seg), ("S-filtered", s_seg)]:
        trades = df[["entry_date", "exit_date", "final_r"]].dropna().rename(columns={"final_r": "r_multiple"})
        for n_slots in CAPACITY_SWEEP:
            res = capacity_constrained_backtest(trades, n_slots)
            print(f"    {label} max_concurrent={n_slots:3d}: n_admitted={res['n_admitted']:,}/{res['n_total']:,}  "
                  f"cumulative_R={res['cumulative_r']:+.1f}  max_DD={res['max_drawdown_r']:.1f}")

pd.DataFrame(all_rows).to_csv(f"{OUT_DIR}/p5_discovery_vs_holdout.csv", index=False)
print(f"\n\nRESEARCHER-CONDITIONING CAVEAT (same discipline as CG3-H): this is a chronological OOS validation of "
      f"the frozen intervention at the numerical level, NOT fully independent blind validation -- CG1's S "
      f"specification was derived from a reference population spanning through 2026-09-24, which includes this "
      f"holdout window. The research team has already examined this general period (2025-2026) extensively "
      f"across multiple prior RQs (07R, CG3-H). Report accordingly.")
print("\nDONE")
