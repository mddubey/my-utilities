"""RQ-QS-04C -- 20-vs-20 trajectory replay: QS-A vs the post-breakout pause breakout B
(2026-09-29). Run at the user's explicit direction; NOTE the pre-declared decision tree
gated this step on 04B confirming a distinct structure and 04B said it did not
(see FINDINGS.md "RQ-QS-04B"). So this is a look at what the 04B population *feels*
like in trajectory terms, not a promotion step. NO expectancy, NO gate, NO ranking.

Population: holds-above-A (low basis) AND resolved (a B exists), from
rq04b_holds_above_a_anatomy.csv. Dedup ticker+a_entry_date across lookbacks. A dated
2026-06-10..2026-09-01 (intraday cache window, leaves >=5 forward bars after B).
Sample drawn BEFORE looking at any trajectory: fixed seed 42, deterministic
stratification 5 early / 5 mid / 5 late / 5 random by A date (same scheme as 05_).

B entry (raw-trigger convention, live-IOC): the intraday touch of consolidation_high on
the B day; fill = max(consolidation_high, B open) so a gap-up B fills at the open.
STOP CONVENTION DECLARED (Rule #20): S1b = prior trading day's Low as of the entry day,
for BOTH A and B -- identical to the frozen QS baseline, so A and B share one risk-unit
definition. The candidate structural lows (pre-B pause low = min Low from the pause start
through the day BEFORE B, i.e. decision-time-safe, unlike 04A's field) are reported as
reference metadata only; the structural-stop comparison is step 4, not here.

Daily-bar descriptors only (D0 entry day is excluded from stop/MFE/MAE because the
intraday order of the entry-day range is not knowable from daily bars).
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from backtest import load, daily_pivots

OUT = os.path.dirname(os.path.abspath(__file__))
SEED = 42
N_FWD = 5

h = pd.read_csv(f"{OUT}/rq04b_holds_above_a_anatomy.csv", parse_dates=["a_entry_date"])
cache_files = set(f[:-4] for f in os.listdir("intraday_cache") if f.endswith(".csv"))
pool = h[h.resolved & h.a_entry_date.between("2026-06-10", "2026-09-01") & h.ticker.isin(cache_files)]
pool = pool.sort_values(["ticker", "a_entry_date", "entry_definition"]).drop_duplicates(["ticker", "a_entry_date"]).reset_index(drop=True)
print(f"Eligible pool: {len(pool)}")

d0, d1 = pool.a_entry_date.min(), pool.a_entry_date.max()
span = (d1 - d0) / 3
c1, c2 = d0 + span, d0 + 2 * span
rng = np.random.RandomState(SEED)
picked = pd.DataFrame()
for name, sub in [("early", pool[pool.a_entry_date < c1]),
                  ("mid", pool[(pool.a_entry_date >= c1) & (pool.a_entry_date < c2)]),
                  ("late", pool[pool.a_entry_date >= c2]),
                  ("random", pool)]:
    avail = sub[~sub.index.isin(picked.index)]
    picked = pd.concat([picked, avail.sample(n=5, random_state=rng).assign(stratum=name)])
sample = picked.reset_index(drop=True)
sample["pair_id"] = sample.index
print(f"Sample n={len(sample)}")

cache, recs = {}, []
for r in sample.itertuples():
    rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
    ia = int(r.a_entry_i); ib = ia + int(r.b_day)
    cs = ia + int(r.consolidation_start_day)
    if ib >= len(rows) or ib - 1 <= ia:
        continue
    b = rows.iloc[ib]
    b_entry = max(r.consolidation_high, b.Open)
    b_stop = rows.iloc[ib - 1].Low
    a_entry, a_stop = r.a_entry_price, rows.iloc[ia - 1].Low
    if b_entry <= b_stop or a_entry <= a_stop:
        continue
    pre_b_low = rows.iloc[cs:ib].Low.min()

    def path(i0, entry, stop):
        risk = entry - stop
        fwd = rows.iloc[i0 + 1:i0 + 1 + N_FWD]
        if len(fwd) < N_FWD:
            return None
        stopped = None
        for k, (_, x) in enumerate(fwd.iterrows(), start=1):
            if x.Low <= stop:
                stopped = k; break
        return dict(risk_pct=risk / entry * 100,
                    d5_close_r=(fwd.Close.iloc[-1] - entry) / risk,
                    mfe_r=(fwd.High.max() - entry) / risk,
                    mae_r=(fwd.Low.min() - entry) / risk,
                    stopped_by_day=stopped)
    pa, pb = path(ia, a_entry, a_stop), path(ib, b_entry, b_stop)
    if pa is None or pb is None:
        continue
    atr = rows.iloc[ia].atr14
    recs.append(dict(
        pair_id=r.pair_id, stratum=r.stratum, ticker=r.ticker,
        a_date=str(r.a_entry_date.date()), b_date=str(b.Date.date()), a_to_b_days=int(r.b_day),
        pause_days=int(r.duration), b_gap_up=bool(b.Open > r.consolidation_high),
        b_entry_vs_a_pct=(b_entry / a_entry - 1) * 100,
        b_entry_vs_a_atr=(b_entry - a_entry) / atr,
        b_close_above_high=bool(b.Close > r.consolidation_high),
        pre_b_low_risk_pct=(b_entry - pre_b_low) / b_entry * 100,
        a_risk_pct=pa["risk_pct"], b_risk_pct=pb["risk_pct"],
        a_d5_close_r=pa["d5_close_r"], b_d5_close_r=pb["d5_close_r"],
        a_mfe_r=pa["mfe_r"], b_mfe_r=pb["mfe_r"], a_mae_r=pa["mae_r"], b_mae_r=pb["mae_r"],
        a_stopped_by=pa["stopped_by_day"], b_stopped_by=pb["stopped_by_day"],
        k_ia=ia, k_ib=ib, k_cs=cs, k_a_entry=a_entry, k_a_stop=a_stop, k_b_entry=b_entry,
        k_b_stop=b_stop, k_pre_b_low=pre_b_low, k_chigh=r.consolidation_high,
    ))
pairs = pd.DataFrame(recs)
pairs.drop(columns=[c for c in pairs if c.startswith("k_")]).to_csv(f"{OUT}/rq04c_pairs.csv", index=False)
sample.to_csv(f"{OUT}/rq04c_sample.csv", index=False)
print(f"Pairs with valid A and B paths: {len(pairs)}\n")

show = ["pair_id", "ticker", "a_date", "a_to_b_days", "pause_days", "b_gap_up", "b_entry_vs_a_pct",
        "b_close_above_high", "a_risk_pct", "b_risk_pct", "pre_b_low_risk_pct",
        "a_d5_close_r", "b_d5_close_r", "a_mae_r", "b_mae_r", "a_stopped_by", "b_stopped_by"]
pd.set_option("display.width", 250)
print(pairs[show].round(2).to_string(index=False))

print("\nMedians (descriptive; n=%d, NOT a comparison of expectancy):" % len(pairs))
for c in ["a_to_b_days", "pause_days", "b_entry_vs_a_pct", "b_entry_vs_a_atr", "a_risk_pct", "b_risk_pct",
          "pre_b_low_risk_pct", "a_d5_close_r", "b_d5_close_r", "a_mfe_r", "b_mfe_r", "a_mae_r", "b_mae_r"]:
    print(f"  {c:20s} {pairs[c].median():8.2f}")
print(f"  A stopped by D5: {pairs.a_stopped_by.notna().sum()}/{len(pairs)}   B stopped by D5: {pairs.b_stopped_by.notna().sum()}/{len(pairs)}")
print(f"  B gap-up fills: {pairs.b_gap_up.sum()}   B closed above consolidation high: {pairs.b_close_above_high.sum()}")

# --- visual: one panel per pair, A entry -> B + N_FWD, candles + the levels that matter ---
fig, axes = plt.subplots(5, 4, figsize=(26, 26))
for ax, p in zip(axes.ravel(), pairs.itertuples()):
    rows = cache[p.ticker]
    lo_i, hi_i = max(p.k_ia - 3, 0), min(p.k_ib + N_FWD + 1, len(rows))
    seg = rows.iloc[lo_i:hi_i]
    for x, (_, c) in zip(range(lo_i, hi_i), seg.iterrows()):
        col = "#2a9d4f" if c.Close >= c.Open else "#d1392f"
        ax.plot([x, x], [c.Low, c.High], color=col, lw=1)
        ax.add_patch(plt.Rectangle((x - 0.3, min(c.Open, c.Close)), 0.6, max(abs(c.Close - c.Open), 1e-6), color=col))
    ax.axvline(p.k_ia, color="#1f6feb", ls=":", lw=1); ax.axvline(p.k_ib, color="#9333ea", ls=":", lw=1)
    ax.axhline(p.k_a_entry, color="#1f6feb", lw=0.8, ls="--")
    ax.axhline(p.k_chigh, color="#9333ea", lw=0.8, ls="--")
    ax.axhline(p.k_pre_b_low, color="#888", lw=0.8, ls="-.")
    ax.hlines(p.k_b_stop, p.k_ib - 0.5, hi_i, color="#d1392f", lw=1.2)
    ax.hlines(p.k_a_stop, p.k_ia - 0.5, p.k_ib, color="#d1392f", lw=1.2, alpha=0.5)
    ax.set_title(f"#{p.pair_id} {p.ticker}  A {p.a_date} -> B {p.b_date} ({p.a_to_b_days}d)  "
                 f"A_D5 {p.a_d5_close_r:+.1f}R  B_D5 {p.b_d5_close_r:+.1f}R", fontsize=9)
    ax.set_xticks([])
fig.suptitle("RQ-QS-04C: blue dashed = A entry, purple dashed = consolidation high (B trigger), "
             "grey = pre-B pause low, red = S1b stops (B solid, A faded)", fontsize=12)
fig.tight_layout()
fig.savefig(f"{OUT}/plot_04c_pairs.png", dpi=70)
print("saved plot_04c_pairs.png")
