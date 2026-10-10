"""Faster market-regime definitions than Nifty > 200-day (user, 2026-10-10: 'the 200-day takes too long to turn'). Spec fixed before
running. v1 trades WITHOUT any Nifty filter (script 164's V), E1 and E2. Definitions (yesterday's Nifty close): > SMA20 | > SMA50 |
> SMA100 | > SMA200 (current) | EMA8 > EMA34 | EMA21 > EMA50. For each: share of days ON (2024-01..2026-09 and in 2026-03..09), v1 when
ON vs OFF (Rs/trade, trades, stops), by year, and inside the 2026-03..09 bear phase. Results only; pick by logic, not by best number."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "164_v1_without_nifty200.py").read().split("\nH = ")[0])
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); c = n["Close"]
DEF = {"Nifty > SMA20": c > c.rolling(20).mean(), "Nifty > SMA50": c > c.rolling(50).mean(), "Nifty > SMA100": c > c.rolling(100).mean(),
       "Nifty > SMA200 (current)": c > c.rolling(200).mean(), "EMA8 > EMA34": c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean(),
       "EMA21 > EMA50": c.ewm(span=21, adjust=False).mean() > c.ewm(span=50, adjust=False).mean()}
DEF = {k: v.shift(1) for k, v in DEF.items()}
days = c.loc["2024-01-01":"2026-09-30"].index; bear = c.loc["2026-03-01":"2026-09-30"].index
V["d"] = pd.to_datetime(V.date)
for en in EX:
    X = V[V.ex == en].copy()
    print(f"\n## {en} (v1 without a Nifty filter: {len(X)} trades)")
    print("| definition | days ON 2024-26 | days ON in 2026-03..09 | ON: trades / Rs per trade / stop % | OFF: trades / Rs per trade | ON by year 2024 / 2025 / 2026 | ON inside the 2026-03..09 bear phase: trades / Rs |\n|---|---|---|---|---|---|---|")
    for nm, s in DEF.items():
        on = X.d.map(s).fillna(False).astype(bool); Y = X[on]; N = X[~on]; Zb = Y[Y.d >= "2026-03-01"]
        y = " / ".join(f"{Y[Y.yr == k].rs1L.mean():+.0f}" if (Y.yr == k).sum() >= 10 else "-" for k in ("2024", "2025", "2026"))
        print(f"| {nm} | {s.reindex(days).mean()*100:.0f}% | {s.reindex(bear).mean()*100:.0f}% | {len(Y)} / {Y.rs1L.mean():+.0f} / {(Y.o=='stop').mean()*100:.0f}% | {len(N)} / {N.rs1L.mean():+.0f} | {y} | {len(Zb)} / " + (f"{Zb.rs1L.mean():+.0f}" if len(Zb) else "-") + " |")
