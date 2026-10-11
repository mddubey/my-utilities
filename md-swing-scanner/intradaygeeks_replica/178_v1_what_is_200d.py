"""What is the Nifty > 200-day gate standing in for? (user, 2026-10-11: 'a blunt gate for some other things'; spec fixed before
running.) Population: v1 WITHOUT the Nifty filter (= script 164), 1H set 2024-01..2026-09, E1 and E2, split Nifty above / below its
200-day. Variables (known when the 10:15 candle closes, bands declared): V1 India VIX yday close < 13 / 13-16 / > 16 (Yahoo ^INDIAVIX)
| V2 Nifty ATR14 % yday < 0.8 / 0.8-1.1 / > 1.1 | V3 Nifty 10-day avg of daily body / range (yday back) -> terciles over 2024-01..2026-09,
set without outcomes | V4 Nifty move today, 09:15 open -> 11:15 (close of the 10:15 hourly bar): up / 0..-0.3 / < -0.3 | V5 stock 20d
return - Nifty 20d return (yday) < 0 / 0-5 / > 5% | V6 stock ATR5 / ATR20 (yday) < 0.9 / 0.9-1.2 / > 1.2 | V7 Nifty distance from its
200-day (yday) < -5 / -5..0 / 0..5 / > 5%. A candidate must (1) separate in BOTH regimes the same way, (2) its good band turns
below-200 positive, (3) its bad band explains above-200 losses. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
src = open(HERE / "164_v1_without_nifty200.py").read()
exec(src.split('\nH = "')[0])
import numpy as np, pandas as pd, yfinance as yf
from backtest import load
from data.paths import DAILY_DIR, INDEX_INTRADAY_DIR

N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index()
tr = pd.concat([N.High - N.Low, (N.High - N.Close.shift()).abs(), (N.Low - N.Close.shift()).abs()], axis=1).max(axis=1)
natr = (tr.rolling(14).mean() / N.Close * 100).shift(1)
br = ((N.Close - N.Open).abs() / (N.High - N.Low).replace(0, np.nan)).rolling(10).mean().shift(1)
q = br["2024-01-01":"2026-09-30"].quantile([1 / 3, 2 / 3]).values
dist200 = ((N.Close / N.Close.rolling(200).mean() - 1) * 100).shift(1); nret20 = (N.Close / N.Close.shift(20) - 1).shift(1) * 100
vix = yf.Ticker("^INDIAVIX").history(start="2023-06-01", interval="1d").Close; vix.index = vix.index.tz_localize(None).normalize(); vix = vix.shift(1)
h = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0, parse_dates=True); h.index = h.index.tz_convert("Asia/Kolkata").tz_localize(None)
hd = h.groupby(h.index.normalize()); nopen = hd.Open.first(); n1115 = h[h.index.strftime("%H:%M") == "10:15"].Close; n1115.index = n1115.index.normalize()
nmove = (n1115 / nopen - 1) * 100

V["ticker"] = V.ix.map(B.ticker); D = {}
for t in V.ticker.unique():
    d = load(t); trs = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    D[t] = pd.DataFrame({"r20": (d.Close / d.Close.shift(20) - 1).shift(1) * 100, "ax": (trs.rolling(5).mean() / trs.rolling(20).mean()).shift(1)})
dt = pd.to_datetime(V.date)
V["V1"] = [vix.get(x, np.nan) for x in dt]; V["V2"] = [natr.get(x, np.nan) for x in dt]; V["V3"] = [br.get(x, np.nan) for x in dt]
V["V4"] = [nmove.get(x, np.nan) for x in dt]; V["V7"] = [dist200.get(x, np.nan) for x in dt]
V["V5"] = [D[t].r20.get(x, np.nan) - nret20.get(x, np.nan) for t, x in zip(V.ticker, dt)]; V["V6"] = [D[t].ax.get(x, np.nan) for t, x in zip(V.ticker, dt)]
VB = {"V1 India VIX (yday)": ("V1", [0, 13, 16, 99], ["< 13", "13-16", "> 16"]),
      "V2 Nifty ATR % (yday)": ("V2", [0, 0.8, 1.1, 99], ["< 0.8", "0.8-1.1", "> 1.1"]),
      "V3 Nifty 10d body/range (follow-through)": ("V3", [0, q[0], q[1], 9], [f"low < {q[0]:.2f} (reversal-ish)", f"mid", f"high > {q[1]:.2f} (trend-ish)"]),
      "V4 Nifty today 09:15 -> 11:15": ("V4", [-99, -0.3, 0, 99], ["< -0.3% (falling)", "0 to -0.3%", "up"]),
      "V5 stock 20d vs Nifty": ("V5", [-999, 0, 5, 999], ["< 0 (laggard)", "0-5%", "> 5% (leader)"]),
      "V6 stock ATR5 / ATR20": ("V6", [0, 0.9, 1.2, 99], ["< 0.9 (calming)", "0.9-1.2", "> 1.2 (expanding)"]),
      "V7 Nifty vs 200-day": ("V7", [-99, -5, 0, 5, 99], ["< -5%", "-5..0%", "0..5%", "> 5%"])}


def r(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | | |"
    o = g.o; sm = "*" if len(g) < 20 else ""
    av = " / ".join(f"{g[o == k].rs1L.mean():+.0f}" if (o == k).any() else "-" for k in ("target", "stall", "stop"))
    return f"| {lab} | {len(g)}{sm} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {av} | {g.rs1L.mean():+.0f} |"


print(f"V3 terciles: {q[0]:.3f} / {q[1]:.3f} | VIX known {V.V1.notna().mean()*100:.0f}% | Nifty 11:15 move known {V.V4.notna().mean()*100:.0f}% (* = under 20 trades)")
HD = "| band | trades | target / stall / stop % | avg Rs t / s / s | Rs/trade @1L |\n|---|---|---|---|---|"
for en in EX:
    X = V[V.ex == en]
    for nm, (c, bins, labs) in VB.items():
        print(f"\n### {en} -- {nm}")
        for reg, rl in ((True, "Nifty ABOVE 200d"), (False, "Nifty BELOW 200d")):
            G = X[X.n200 == reg]; print(f"\n{rl}\n{HD}"); print(r("ALL", G))
            for k, g in G.groupby(pd.cut(G[c], bins, labels=labs), observed=False): print(r(str(k), g))
