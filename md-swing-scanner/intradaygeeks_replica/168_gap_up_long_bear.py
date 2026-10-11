"""Pocket 2 as a setup: BEAR-PHASE GAP-UP LONG (user, 2026-10-11). Spec fixed before running. Nifty close below its 200-day SMA (yday);
stock daily 8-EMA < 34-EMA (yday); liquid (prev-day median hourly turnover /12 x 0.72 >= Rs15 lakh / 5-min bar), price >= Rs100, ATR >= 2%;
gap up >= 1% (open vs yday close). Entry at 10:15 = close of the 09:15 hourly candle. Versions: plain | held the gap (09:15 candle green).
Stop = the 09:15 candle's low. E1: target +1%, only if stop <= 0.5%; E2: target max(1%, 0.35 x ATR), only if stop <= half the target.
Exit at target / stop / 15:15 (close of the 14:15 candle); stop first if both in one candle. 2024-01..2026-09, h1_cache. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
BEAR = (nc < nc.rolling(200).mean()).shift(1)


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d = load(t); d = d[d.index < "2026-10-01"]
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"gap": (d.Open / c.shift(1) - 1) * 100, "pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "down": (c.ewm(span=8, adjust=False).mean() < c.ewm(span=34, adjust=False).mean()).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[(h.index >= "2023-12-01") & (h.index < "2026-10-01")]
    if len(h) < 100: return []
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    pm = (h.Volume * h.Close).where(h.Volume > 0).groupby(day).median().shift(1) / 12 / 1e5 * 0.72
    out = []
    for i in np.where(T.strftime("%H:%M") == "09:15")[0]:
        dd = day[i]
        if dd < pd.Timestamp("2024-01-01") or dd not in D.index or BEAR.get(dd) is not True and BEAR.get(dd) != True: continue
        x = D.loc[dd]
        if not (x.tv >= 1e8) or bool(x.ca) or not (x.pc >= 100) or not (x.atrp >= 2) or not bool(x.down) or not (x.gap >= 1) or pm.get(dd, 0) < 15: continue
        e = C[i]; lo = L[i]; stop = (e - lo) / e * 100
        if stop <= 0: continue
        green = C[i] > O[i]
        for en, tp in (("E1", 1.0), ("E2", max(1.0, 0.35 * x.atrp))):
            ok = stop <= 0.5 if en == "E1" else stop <= tp / 2
            tgt = e * (1 + tp / 100); px, o = None, "stall"
            for j in range(i + 1, len(C)):
                if day[j] != dd: px = C[j - 1]; break
                if L[j] <= lo: px, o = lo, "stop"; break
                if H[j] >= tgt: px, o = tgt, "target"; break
                if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != dd: px = C[j]; break
            if px is None: continue
            ret = (px - e) / e * 100; pos = 1000 / (stop / 100)
            out.append(dict(t=t, date=dd.strftime("%Y-%m-%d"), yr=dd.strftime("%Y"), ex=en, ok=ok, green=green, stop=stop, gap=x.gap, atrp=x.atrp,
                            entry=e, low=lo, o=o, rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); res, t0 = [], time.time()
    with Pool(6) as pl:
        for k, r in enumerate(pl.imap_unordered(gen, t1, chunksize=8), 1):
            res += r
            if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(res):,} rows, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res); R.to_csv(HERE / "gap_up_long_bear.csv", index=False)
    E1 = R[R.ex == "E1"]
    print(f"\nbear-phase gap-up (>= 1%) downtrend days: {len(E1)} | 09:15 green: {E1.green.mean()*100:.0f}% | median 09:15-low stop {E1.stop.median():.2f}% | stop <= 0.5%: {(E1.stop <= 0.5).mean()*100:.0f}%")

    def row(lab, g):
        if len(g) < 15: return f"| {lab} | {len(g)} | | | | | | | |"
        parts = [f"{(g.o == o).mean()*100:.0f}% ({g[g.o == o].rs1L.mean():+,.0f})" for o in ("target", "stall", "stop")]
        y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 15 else "-" for k in ("2024", "2025", "2026"))
        return f"| {lab} | {len(g):,} | {g.date.nunique()} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} |"

    H = "| version | trades | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
    for en in ("E1", "E2"):
        X = R[(R.ex == en)]
        print(f"\n## {en} -- stop = 09:15 low\n" + H)
        print(row("ALL gap-up days, NO stop-size filter (reference)", X))
        print(row("plain (stop-size rule applied)", X[X.ok])); print(row("held the gap: 09:15 GREEN (stop-size rule applied)", X[X.ok & X.green]))
        print(row("09:15 RED (gap fading) (stop-size rule applied)", X[X.ok & ~X.green]))
        Z = X[X.ok & (X.date >= "2026-03-01")]
        print("| bear-phase month (rule applied) | trades | Rs/trade @1L |\n|---|---|---|")
        for m, g in Z.groupby(Z.date.str[:7]): print(f"| {m} | {len(g)} | {g.rs1L.mean():+.0f} |")
