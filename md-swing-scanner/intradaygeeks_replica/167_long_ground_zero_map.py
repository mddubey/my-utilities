"""INTRADAY LONGS, ground zero (user, 2026-10-11: 'start longs from scratch'). Spec fixed before running. No setup, no stop: buy at a
fixed time, sell at 15:15. Liquid (prev-day median hourly turnover / 12 x 0.72 >= Rs15 lakh / 5-min bar), price >= Rs100, every
stock-day 2024-01..2026-09 (h1_cache; corp-action days skipped). Entries: 10:15 (close of the 09:15 hourly candle) and 11:15 (close of
the 10:15 candle); exit at 15:15 (close of the 14:15 candle). Splits: Nifty below / above its 200-day SMA (yday); the stock's gap
(open vs yday close): <= -2 | -2..-1 | -1..-0.5 | -0.5..+0.5 | +0.5..+1 | > +1; the stock's daily trend (8-EMA vs 34-EMA, yday).
Report mean return after Rs85 charges (Rs per Rs1 lakh), % of stock-days positive, stock-days, by year. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d = load(t); d = d[d.index < "2026-10-01"]
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"gap": (d.Open / c.shift(1) - 1) * 100, "pc": c.shift(1), "tv": d.traded_value_sma20.shift(1),
                      "up": (c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean()).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[(h.index >= "2023-12-01") & (h.index < "2026-10-01")]
    if len(h) < 100: return []
    day = h.index.normalize(); hm = h.index.strftime("%H:%M")
    pm = (h.Volume * h.Close).where(h.Volume > 0).groupby(day).median().shift(1) / 12 / 1e5 * 0.72
    cl = pd.DataFrame({"day": day, "hm": hm, "c": h.Close.values}).pivot_table(index="day", columns="hm", values="c", aggfunc="last")
    need = {"09:15", "10:15", "14:15"}
    if not need.issubset(cl.columns): return []
    out = []
    for dd, r in cl.iterrows():
        if dd < pd.Timestamp("2024-01-01") or dd not in D.index: continue
        x = D.loc[dd]
        if not (x.tv >= 1e8) or bool(x.ca) or not (x.pc >= 100) or pm.get(dd, 0) < 15 or r[list(need)].isna().any(): continue
        out.append(dict(t=t, date=dd, gap=x.gap, up=bool(x.up), r10=(r["14:15"] / r["09:15"] - 1) * 100, r11=(r["14:15"] / r["10:15"] - 1) * 100))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); res, t0 = [], time.time()
    with Pool(6) as pl:
        for k, r in enumerate(pl.imap_unordered(gen, t1, chunksize=8), 1):
            res += r
            if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(res):,} stock-days, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res)
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
    R["bull"] = R.date.map((nc > nc.rolling(200).mean()).shift(1)); R["yr"] = R.date.dt.year
    R["gb"] = pd.cut(R.gap, [-99, -2, -1, -0.5, 0.5, 1, 99], labels=["gap down 2%+", "gap down 1-2%", "gap down 0.5-1%", "flat (+/-0.5%)", "gap up 0.5-1%", "gap up 1%+"])
    R.to_csv(HERE / "long_ground_zero.csv", index=False)

    def cell(g, col):
        if len(g) < 100: return f"n {len(g)}"
        net = g[col] * 1000 - 85; y = "/".join(f"{(g[g.yr == k][col] * 1000 - 85).mean():+.0f}" if (g.yr == k).sum() >= 100 else "-" for k in (2024, 2025, 2026))
        return f"{net.mean():+.0f} ({(g[col] > 0).mean()*100:.0f}% up, n {len(g):,}; {y})"

    for col, lab in (("r10", "BUY 10:15 -> SELL 15:15"), ("r11", "BUY 11:15 -> SELL 15:15")):
        print(f"\n## {lab} -- cells: net Rs per Rs1 lakh (% of stock-days up, n; 2024/2025/2026)")
        print("| stock's gap | NIFTY BELOW 200d, stock in daily DOWNtrend | below 200d, stock UPtrend | NIFTY ABOVE 200d, stock DOWNtrend | above 200d, stock UPtrend |\n|---|---|---|---|---|")
        for gb in R.gb.cat.categories:
            G = R[R.gb == gb]
            print(f"| {gb} | " + " | ".join(cell(G[(G.bull == b) & (G.up == u)], col) for b, u in ((False, False), (False, True), (True, False), (True, True))) + " |")
        print(f"| ALL gaps | " + " | ".join(cell(R[(R.bull == b) & (R.up == u)], col) for b, u in ((False, False), (False, True), (True, False), (True, True))) + " |")
