"""Nifty SMA trend rules vs the checklist setups, both sides (user, 2026-10-02). Spec fixed before running.
Rules from Nifty daily closes as of the PRIOR day: R1 close > SMA50 = uptrend; R2 SMA50 > SMA50 20 days earlier = rising;
R3 SMA50 > SMA200 = golden-cross regime. Setups: 1H-close checklist both sides (as 48), 2024-01 .. 2026-09,
with and without the 2:1 rule. Switch = longs in uptrend, shorts in downtrend."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = pd.read_csv(HERE.parent / "data_cache" / "_NIFTY.csv", parse_dates=["Date"]).set_index("Date").Close.sort_index()
s50, s200 = N.rolling(50).mean(), N.rolling(200).mean()
REG = pd.DataFrame({"R1 close>SMA50": N > s50, "R2 SMA50 rising": s50 > s50.shift(20), "R3 SMA50>SMA200": s50 > s200}).astype(float).shift(1)
print("share of days in UPTREND by year:"); print(REG.loc["2024":"2026-09"].groupby(REG.loc["2024":"2026-09"].index.year).mean().round(2).to_string())
X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
K = X[X.bar_ts.dt.strftime("%H:%M").isin(["10:15", "11:15"]) & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0)
      & (X.close_past_ema > 0) & (X.close_past_ema <= 0.5)].join(REG, on="date")
def cell(x): return f"{x.ret.mean():+.3f} (n {len(x)})" if len(x) >= 20 else f"n {len(x)}"
for rr in (False, True):
    D = K[K.stop_pct <= 0.5] if rr else K
    print(f"\n### {'WITH 2:1 RULE' if rr else 'ALL (0.5% cap)'}\n| rule | side | regime | 2024 | 2025 | 2026 | all |\n|---|---|---|---|---|---|---|")
    for r in REG.columns:
        for sd in ("short", "long"):
            for up, nm in ((1.0, "UP"), (0.0, "DOWN")):
                x = D[(D.side == sd) & (D[r] == up)]
                print(f"| {r} | {sd} | {nm} | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) + f" | {cell(x)} |")
    print("\n| strategy | 2024 | 2025 | 2026 | all |\n|---|---|---|---|---|")
    print("| shorts only (current) | " + " | ".join(cell(D[(D.side == 'short') & (D.date.dt.year == y)]) for y in (2024, 2025, 2026)) + f" | {cell(D[D.side == 'short'])} |")
    for r in REG.columns:
        m = ((D.side == "long") & (D[r] == 1)) | ((D.side == "short") & (D[r] == 0))
        x = D[m]; print(f"| switch by {r}: long in UP, short in DOWN | " + " | ".join(cell(x[x.date.dt.year == y]) for y in (2024, 2025, 2026)) + f" | {cell(x)} |")
