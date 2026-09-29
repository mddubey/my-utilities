"""QS Trajectory Replay -- Minimum Viable Replay, Step 3: normalized trajectory plots
+ D0/D1/D2/D3/D5 state table (critic-approved spec, section B's remaining two
deliverables). Pure visualization/reshaping of what 02_replay.py already computed --
no new computation, no labels, no thresholds chosen here.
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

bars = pd.read_csv(f"{OUT_DIR}/per_bar_trajectory.csv", parse_dates=["timestamp"])
events = pd.read_csv(f"{OUT_DIR}/events.csv", parse_dates=["entry_date"])

# sequential bar index per trade (avoids wall-clock/weekend-gap distortion in the plot)
bars = bars.sort_values(["trade_id", "timestamp"])
bars["bar_seq"] = bars.groupby("trade_id").cumcount()

# --- Plot 1: overlay of all trajectories (close_r vs bar_seq) ---
fig, ax = plt.subplots(figsize=(11, 7))
for tid, g in bars.groupby("trade_id"):
    ax.plot(g.bar_seq, g.close_r, color="steelblue", alpha=0.15, linewidth=0.8)
ax.axhline(0, color="black", linewidth=0.6)
ax.axhline(0.25, color="green", linewidth=0.5, linestyle="--", alpha=0.5)
ax.axhline(1.0, color="green", linewidth=0.5, linestyle="--", alpha=0.5)
ax.axhline(-1.0, color="red", linewidth=0.5, linestyle="--", alpha=0.5)
ax.set_xlabel("5-min bar sequence since entry (D0..D5)")
ax.set_ylabel("close_r (R multiples, S1b)")
ax.set_title(f"QS Trajectory Replay -- all {bars.trade_id.nunique()} sampled trades, D0-D5 (5-min bars)")
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/plot_overlay_all.png", dpi=130)
print("Saved plot_overlay_all.png")

# --- Plot 2: small multiples, a fixed random subset for closer visual inspection ---
rng = np.random.RandomState(7)
sample_ids = rng.choice(bars.trade_id.unique(), size=min(12, bars.trade_id.nunique()), replace=False)
fig, axes = plt.subplots(3, 4, figsize=(16, 10), sharex=False)
for ax, tid in zip(axes.flat, sample_ids):
    g = bars[bars.trade_id == tid]
    ev = events[events.trade_id == tid].iloc[0]
    ax.plot(g.bar_seq, g.close_r, color="steelblue", linewidth=1)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_title(f"{ev.ticker} {ev.entry_date.date()} ({ev.entry_definition}D)", fontsize=9)
    ax.tick_params(labelsize=7)
fig.suptitle("QS Trajectory Replay -- 12 randomly selected individual trades")
fig.tight_layout()
fig.savefig(f"{OUT_DIR}/plot_small_multiples.png", dpi=130)
print("Saved plot_small_multiples.png")

# --- D0/D1/D2/D3/D5 state table (reshape events.csv's wide daily columns into a
# clean, readable table -- D4 intentionally included too even though critic's list
# said D0/D1/D2/D3/D5, since it's already computed and free) ---
state_cols = ["trade_id", "ticker", "entry_date", "entry_definition"]
for d in range(6):
    state_cols += [f"D{d}_close_r", f"D{d}_close_vs_trigger", f"D{d}_close_vs_prev_close_pct",
                   f"D{d}_daily_range_pct", f"D{d}_new_high"]
state_table = events[[c for c in state_cols if c in events.columns]]
state_table.to_csv(f"{OUT_DIR}/state_table_D0_D5.csv", index=False)
print(f"Saved state_table_D0_D5.csv, n={len(state_table)}")

# --- quick, purely descriptive summary (no labels, no thresholds -- just counting) ---
print(f"\n=== Descriptive summary, n={len(events)} ===")
print(f"MAE distribution: median={events.mae_r.median():.3f}R  10th pct={events.mae_r.quantile(0.1):.3f}R  90th pct={events.mae_r.quantile(0.9):.3f}R")
print(f"MFE distribution: median={events.mfe_r.median():.3f}R  10th pct={events.mfe_r.quantile(0.1):.3f}R  90th pct={events.mfe_r.quantile(0.9):.3f}R")
print(f"D0 close vs trigger: {events.D0_close_vs_trigger.value_counts(normalize=True).mul(100).round(1).to_dict()}")
print(f"D5 close vs trigger: {events.D5_close_vs_trigger.value_counts(normalize=True).mul(100).round(1).to_dict()}")
print(f"Ever returned to trigger after moving away: {events.first_return_to_trigger_min.notna().mean()*100:.1f}%")
print(f"Reclaimed after a return: {(events.first_reclaim_after_return_min.notna() & events.first_return_to_trigger_min.notna()).sum()} / {events.first_return_to_trigger_min.notna().sum()} of those that returned")
