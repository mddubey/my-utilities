"""Sweep of 'skip if the 1H close is already more than X% beyond the EMA', plus one-trade-at-a-time simulation.
Spec fixed 2026-10-02 before running. Set: checklist shorts (setup <= 12:15, daily ADX <= 25, VWAP side, wick through
live daily 8-EMA), 1H close entry, stop = candle high, 1% target, out at 5 candles/EOD (15's stored outcome).
X = 0.1 .. 1.0 step 0.1, and no cap. Threshold chosen on TRAIN (< 2025-07-01): best mean/trade with >= 2 setups/day.
Policies: ALL setups (every one taken); ONE-AT-A-TIME (first setup of the day, tie -> closest to EMA; next eligible
setup must start after the previous exit); ONE-PER-DAY (first setup only). Equal size per trade; drawdown = peak-to-
trough of cumulative % (sum of per-trade %); worst streak = longest run of losing trades."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent; SPLIT = pd.Timestamp("2025-07-01")
X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
days = pd.Index(sorted(X.date.unique())); ndays = {"train": (days < SPLIT).sum(), "test": (days >= SPLIT).sum()}
K = X[(X.bar_ts.dt.strftime("%H:%M") <= "12:15") & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0) & (X.side == "short")].copy()
K["t_in"] = K.bar_ts + pd.Timedelta("60min"); K["t_out"] = K.bar_ts + pd.to_timedelta(K.bars + 1, unit="h")
K = K.sort_values(["date", "t_in", "entry_past_ema_pct"])

def policy(x, mode):
    if mode == "all": return x
    keep = []
    for d, g in x.groupby("date"):
        free = pd.Timestamp.min
        for r in g.itertuples():
            if r.t_in >= free:
                keep.append(r.Index); free = r.t_out
                if mode == "one_per_day": break
    return x.loc[keep]

def stats(x, per):
    if len(x) == 0: return dict(n=0)
    r = x.sort_values("t_in").ret.values; cum = np.cumsum(r); dd = (cum - np.maximum.accumulate(cum)).min()
    streak = m = 0
    for v in r: m = m + 1 if v <= 0 else 0; streak = max(streak, m)
    return dict(n=len(x), per_day=len(x) / ndays[per], win=(r > 0).mean() * 100, mean=r.mean(), per_day_ret=r.sum() / ndays[per],
                maxdd=dd, streak=streak)

caps = [round(c, 1) for c in np.arange(0.1, 1.01, 0.1)] + [None]
rows = []
for cap in caps:
    x = K if cap is None else K[K.entry_past_ema_pct <= cap]
    for per, sub in (("train", x[x.date < SPLIT]), ("test", x[x.date >= SPLIT])):
        for mode in ("all", "one_at_a_time", "one_per_day"):
            rows.append(dict(cap="none" if cap is None else cap, period=per, mode=mode, **stats(policy(sub, mode), per)))
S = pd.DataFrame(rows); S.to_csv(HERE / "threshold_sweep.csv", index=False)
A = S[S["mode"] == "all"].pivot(index="cap", columns="period", values=["n", "per_day", "mean"])
print("SWEEP, all setups taken: setups/day and mean % per trade\n| cap: skip if close > X% beyond EMA | train setups/day | train mean % | unseen setups/day | unseen mean % |\n|---|---|---|---|---|")
for c in A.index: print(f"| {c} | {A.loc[c, ('per_day','train')]:.1f} | {A.loc[c, ('mean','train')]:+.3f} | {A.loc[c, ('per_day','test')]:.1f} | {A.loc[c, ('mean','test')]:+.3f} |")
tr = S[(S.period == "train") & (S["mode"] == "all") & (S.per_day >= 2)]
best = tr.sort_values("mean", ascending=False).iloc[0].cap
print(f"\nchosen on TRAIN only: cap = {best}")
print("\nONE TRADE AT A TIME vs ONE PER DAY (chosen cap, and 0.5 / none for reference)")
print("| cap | period | policy | trades | per day | win% | mean % | avg % per day | max drawdown (sum %) | worst losing streak |\n|---|---|---|---|---|---|---|---|---|---|")
for c in dict.fromkeys([best, 0.5, "none"]):
    for per in ("train", "test"):
        for mode in ("one_at_a_time", "one_per_day"):
            r = S[(S.cap == c) & (S.period == per) & (S["mode"] == mode)].iloc[0]
            print(f"| {c} | {'unseen' if per=='test' else 'train'} | {mode.replace('_',' ')} | {r.n:.0f} | {r.per_day:.2f} | {r.win:.0f} | {r['mean']:+.3f} | {r.per_day_ret:+.3f} | {r.maxdd:+.2f} | {r.streak:.0f} |")
