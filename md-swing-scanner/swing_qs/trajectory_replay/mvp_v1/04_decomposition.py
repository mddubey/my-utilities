"""QS Trajectory Replay -- decomposition, per critic's exact instruction (2026-09-28
late): don't threshold, don't re-define. Characterize the 6 confirmed examples on
every requested dimension (no thresholds), then compute two continuous axes -- early
expansion vs persistence -- across all 96, and see whether the six occupy a
recognizable region. No new gate, no labels.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIRMED = ["TECHM", "LODHA", "SONACOMS", "PPLPHARMA", "INDGN", "HINDZINC"]

bars = pd.read_csv(f"{OUT_DIR}/per_bar_trajectory.csv", parse_dates=["timestamp"])
events = pd.read_csv(f"{OUT_DIR}/events.csv", parse_dates=["entry_date"])
bars = bars.sort_values(["trade_id", "timestamp"])
bars["bar_seq"] = bars.groupby("trade_id").cumcount()

# ============ STEP 1: descriptive profile of the 6 confirmed examples, no thresholds ============
rows = []
for tid in events[events.ticker.isin(CONFIRMED)].trade_id:
    g = bars[bars.trade_id == tid].reset_index(drop=True)
    ev = events[events.trade_id == tid].iloc[0]

    mfe_idx = g.high_r.idxmax()
    mfe_r = g.loc[mfe_idx, "high_r"]
    time_to_mfe = g.loc[mfe_idx, "minutes_since_entry"]

    half_mfe_hit = g[g.high_r >= 0.5 * mfe_r]
    time_to_half_mfe = half_mfe_hit.minutes_since_entry.iloc[0] if len(half_mfe_hit) else None

    after_peak = g.loc[mfe_idx:]
    min_close_after_peak = after_peak.close_r.min() if len(after_peak) else g.close_r.iloc[-1]
    giveback_from_mfe = mfe_r - min_close_after_peak

    # did it recover after the deepest post-peak drawdown?
    min_after_peak_idx = after_peak.close_r.idxmin()
    after_deepest = g.loc[min_after_peak_idx:]
    recovered_r = after_deepest.close_r.iloc[-1] - min_close_after_peak if len(after_deepest) else 0

    # count distinct daily closing highs (a day-level proxy for "expansion episodes")
    day_cols = [c for c in events.columns if c.startswith("D") and c.endswith("_close_r")]
    day_vals = [ev[c] for c in sorted(day_cols, key=lambda c: int(c[1:c.index("_")]))]
    running_max = -np.inf
    new_high_days = 0
    higher_high_flags = []
    for v in day_vals:
        if pd.notna(v) and v > running_max:
            new_high_days += 1
            higher_high_flags.append(True)
            running_max = v
        else:
            higher_high_flags.append(False)

    rows.append(dict(
        ticker=ev.ticker, trade_id=tid, mfe_r=round(mfe_r, 3),
        time_to_mfe_min=round(time_to_mfe, 0), time_to_half_mfe_min=round(time_to_half_mfe, 0) if time_to_half_mfe else None,
        giveback_from_mfe_r=round(giveback_from_mfe, 3), recovered_after_deepest_giveback_r=round(recovered_r, 3),
        num_new_daily_closing_highs=new_high_days,
        daily_close_r_sequence=[round(v, 2) if pd.notna(v) else None for v in day_vals],
        higher_high_each_day=higher_high_flags,
    ))

profile = pd.DataFrame(rows)
profile.to_csv(f"{OUT_DIR}/six_examples_decomposition.csv", index=False)
print("=== Step 1: six confirmed examples, full descriptive profile (no thresholds) ===\n")
for r in rows:
    print(f"{r['ticker']:<10} mfe={r['mfe_r']}R  time_to_mfe={r['time_to_mfe_min']}min  "
          f"time_to_half_mfe={r['time_to_half_mfe_min']}min  giveback_from_mfe={r['giveback_from_mfe_r']}R  "
          f"recovered_after={r['recovered_after_deepest_giveback_r']}R  new_daily_highs={r['num_new_daily_closing_highs']}/6")
    print(f"           daily close_r D0-D5: {r['daily_close_r_sequence']}")
    print(f"           higher-high each day: {r['higher_high_each_day']}\n")

# ============ STEP 3: two continuous axes across all 96 ============
axis_rows = []
for tid in events.trade_id:
    g = bars[bars.trade_id == tid].reset_index(drop=True)
    ev = events[events.trade_id == tid].iloc[0]
    d0 = g[g.day_num == 0]
    d0_max_r = d0.high_r.max() if len(d0) else None

    mfe_idx = g.high_r.idxmax()
    mfe_r = g.loc[mfe_idx, "high_r"]
    after_peak = g.loc[mfe_idx:]
    min_close_after_peak = after_peak.close_r.min() if len(after_peak) else g.close_r.iloc[-1]
    max_giveback_r = mfe_r - min_close_after_peak

    axis_rows.append(dict(trade_id=tid, ticker=ev.ticker, d0_max_r=d0_max_r,
                           mfe_r=mfe_r, max_giveback_r=max_giveback_r,
                           is_confirmed=ev.ticker in CONFIRMED))

axes_df = pd.DataFrame(axis_rows)
axes_df.to_csv(f"{OUT_DIR}/two_axes_all_96.csv", index=False)

print("\n=== Step 3: distributions across all 96 (continuous, no thresholds) ===")
print(f"d0_max_r:      median={axes_df.d0_max_r.median():.3f}  IQR=[{axes_df.d0_max_r.quantile(.25):.3f}, {axes_df.d0_max_r.quantile(.75):.3f}]")
print(f"mfe_r:         median={axes_df.mfe_r.median():.3f}  IQR=[{axes_df.mfe_r.quantile(.25):.3f}, {axes_df.mfe_r.quantile(.75):.3f}]")
print(f"max_giveback_r: median={axes_df.max_giveback_r.median():.3f}  IQR=[{axes_df.max_giveback_r.quantile(.25):.3f}, {axes_df.max_giveback_r.quantile(.75):.3f}]")

fig, axs = plt.subplots(1, 2, figsize=(15, 6.5))
for ax, ycol, ylabel in [(axs[0], "mfe_r", "MFE (eventual peak R)"), (axs[1], "max_giveback_r", "max giveback from peak (R)")]:
    others = axes_df[~axes_df.is_confirmed]
    conf = axes_df[axes_df.is_confirmed]
    ax.scatter(others.d0_max_r, others[ycol], alpha=0.4, s=25, color="steelblue", label="other 90")
    ax.scatter(conf.d0_max_r, conf[ycol], alpha=1.0, s=90, color="red", marker="*", label="6 confirmed examples")
    for _, r in conf.iterrows():
        ax.annotate(r.ticker, (r.d0_max_r, r[ycol]), fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("d0_max_r (early expansion: max R reached on D0 alone)")
    ax.set_ylabel(ylabel)
    ax.legend(fontsize=8)
fig.suptitle("Early expansion (D0 max R) vs persistence, all 96, 6 confirmed examples highlighted")
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/plot_two_axes.png", dpi=130)
print("\nSaved plot_two_axes.png")
