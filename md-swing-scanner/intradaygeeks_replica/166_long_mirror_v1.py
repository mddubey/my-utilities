"""LONG MIRROR of v1 for bear phases (user, 2026-10-10: 'I am not sitting out 12 months -- work on longs'). Spec fixed before running.
Liquid (prev-day >= Rs15 lakh / 5-min bar), price >= Rs100, ATR >= 2%, 2024-01..2026-09, 3-yr 1H set (h1_cache). Mirror rules:
Nifty close BELOW its 200-day SMA (yday) [above shown as contrast]; stock daily 8-EMA < 34-EMA (downtrend); gap -0.5..+0.25%;
10:15 candle GREEN, LOW <= 1H EMA34 (prev completed hour), close > EMA34; branch A' = day opened 0-0.5% ABOVE the 1H EMA34; branch
B' = day opened BELOW it and ATR >= 3%; skip a doji cut by the line (body < 25% of range and candle open <= EMA34); skip converged
lines (live daily 8-EMA within 0.25% of the 1H EMA34). Long at the 10:15 close (11:15). E1: target +1%, stop = candle low, only if
stop <= 0.5%. E2: target max(1%, 0.35 x ATR), only if stop <= half the target. Out after 5 candles / day's last candle, stop first.
Rs @1L and @1k risk, net Rs85 per lakh, by year and 2026 bear-phase month. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
n200 = (nc > nc.rolling(200).mean()).shift(1)


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d = load(t); d = d[d.index < "2026-10-01"]
    except Exception: return []
    c = d.Close; tv = d.traded_value_sma20.shift(1)
    D = pd.DataFrame({"atrp": (d.atr14 / c * 100).shift(1), "s8": c.ewm(span=8, adjust=False).mean().shift(1), "s34": c.ewm(span=34, adjust=False).mean().shift(1),
                      "gap": (d.Open / c.shift(1) - 1) * 100, "pc": c.shift(1), "tv": tv, "ca": d.corp_action_day if "corp_action_day" in d else False})
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[((h.Volume > 0) | (h.High != h.Low)) & (h.index < "2026-10-01")]
    if len(h) < 300: return []
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index
    E34 = h.Close.ewm(span=34, adjust=False).mean().shift(1).values; day = T.normalize()
    pm = (h.Volume * h.Close).where(h.Volume > 0).groupby(day).median().shift(1) / 12 / 1e5 * 0.72
    rows = []
    for i in np.where(T.strftime("%H:%M") == "10:15")[0]:
        if T[i] < pd.Timestamp("2024-01-01") or i < 200 or i + 1 >= len(C): continue
        dd = day[i]
        if dd not in D.index: continue
        r = D.loc[dd]
        if not (r.tv >= 1e8) or bool(r.ca) or pm.get(dd, 0) < 15 or r.pc < 100 or not (r.atrp >= 2): continue
        E = E34[i]
        if not (L[i] <= E < C[i] and C[i] > O[i]): continue
        if i - 1 < 0 or day[i - 1] != dd: continue
        dayopen = O[i - 1]; ov = (dayopen / E - 1) * 100
        rows.append(dict(ticker=t, date=dd.strftime("%Y-%m-%d"), yr=dd.strftime("%Y"), entry=C[i], low=L[i], high=H[i], open=O[i], ema34=E,
                         atrp=r.atrp, s8=r.s8, s34=r.s34, gap=r.gap, ov=ov, i=i))
    out = []
    for rr in rows:
        i = rr["i"]; e = rr["entry"]; stop = (e - rr["low"]) / e * 100
        for en, tp, ok in (("E1", 1.0, stop <= 0.5), ("E2", max(1.0, 0.35 * rr["atrp"]), stop <= max(1.0, 0.35 * rr["atrp"]) / 2)):
            if not ok: continue
            tgt = e * (1 + tp / 100); px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                if L[j] <= rr["low"]: px, o = rr["low"], "stop"; break
                if H[j] >= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
            if px is None: continue
            ret = (px - e) / e * 100; pos = 1000 / (stop / 100)
            out.append({**{k: v for k, v in rr.items() if k != "i"}, "ex": en, "stop": stop, "o": o, "rs1L": ret * 1000 - 85, "rs1k": ret / 100 * pos - 85 * pos / 1e5})
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); res, t0 = [], time.time()
    with Pool(6) as pl:
        for k, r in enumerate(pl.imap_unordered(gen, t1, chunksize=8), 1):
            res += r
            if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(res)} trades, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res); R["d"] = pd.to_datetime(R.date); R["n200"] = R.d.map(n200)
    R["bodyp"] = (R.entry - R.open) / (R.high - R.low).replace(0, np.nan)
    R["dd"] = abs(R.ema34 - (2 / 9 * R.entry + 7 / 9 * R.s8)) / R.entry * 100


    def row(lab, g):
        if len(g) < 15: return f"| {lab} | {len(g)} | | | | | | | |"
        parts = [f"{(g.o == o).mean()*100:.0f}% ({g[g.o == o].rs1L.mean():+,.0f})" for o in ("target", "stall", "stop")]
        y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 15 else "-" for k in ("2024", "2025", "2026"))
        return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |"


    base = R[(R.s8 < R.s34) & (R.gap >= -0.5) & (R.gap <= 0.25) & (((R.ov > 0) & (R.ov <= 0.5)) | ((R.ov <= 0) & (R.atrp >= 3)))
             & ~((R.bodyp < 0.25) & (R.open <= R.ema34)) & (R.dd >= 0.25)]
    H = "| group | trades | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
    for en in ("E1", "E2"):
        X = base[base.ex == en]
        print(f"\n## LONG MIRROR, {en}\n" + H)
        print(row("Nifty BELOW its 200-day (the mirror's market)", X[X.n200 == False])); print(row("  branch A' (opened 0-0.5% above the line)", X[(X.n200 == False) & (X.ov > 0)]))
        print(row("  branch B' (opened below, ATR >= 3%)", X[(X.n200 == False) & (X.ov <= 0)]))
        print(row("  2026-03..09 bear phase only", X[(X.n200 == False) & (X.date >= "2026-03-01")]))
        print(row("(contrast) Nifty ABOVE its 200-day", X[X.n200 == True]))
        Z = X[(X.n200 == False) & (X.date >= "2026-03-01")]
        print("| month (bear phase) | trades | Rs/trade @1L |\n|---|---|---|")
        for m, g in Z.groupby(Z.date.str[:7]): print(f"| {m} | {len(g)} | {g.rs1L.mean():+.0f} |")
    R.to_csv(HERE / "long_mirror_v1.csv", index=False)
