"""GAP-UP FADE SHORT, universal test (user, 2026-10-11: one intraday short that has a trade ~9 of 10 days in any regime). Spec fixed
before running. Liquid (prev-day median hourly turnover / 12 x 0.72 >= Rs15 lakh / 5-min bar), ADTV >= Rs10 cr, price >= Rs100, ATR >= 2%.
Gap bands (open vs yday close): +0.5..+1% | >= +1%. Trigger: the 10:15 hourly candle is RED and closes BELOW the day's open (the gap is
being given back). Short at its close (11:15). Stop = the day's high so far (09:15 + 10:15 candles), UNBOUNDED (no size cap).
Target 1%. Exit target / stop / 5 candles or the day's last candle, stop first. Splits: Nifty above / below its 200-day SMA (yday), the
stock's daily trend (8 vs 34 EMA), gap band, year. Availability = % of trading days with >= 1 setup. Top-10-days concentration.
2024-01..2026-09, h1_cache. Results only."""
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
    D = pd.DataFrame({"gap": (d.Open / c.shift(1) - 1) * 100, "pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "up": (c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean()).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    h = pd.read_csv(p, index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    h = h[(h.index >= "2023-12-01") & (h.index < "2026-10-01")]
    if len(h) < 100: return []
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize(); hm = T.strftime("%H:%M")
    pm = (h.Volume * h.Close).where(h.Volume > 0).groupby(day).median().shift(1) / 12 / 1e5 * 0.72
    out = []
    for i in np.where(hm == "10:15")[0]:
        dd = day[i]
        if dd < pd.Timestamp("2024-01-01") or dd not in D.index or i < 1 or day[i - 1] != dd or hm[i - 1] != "09:15": continue
        x = D.loc[dd]
        if not (x.tv >= 1e8) or bool(x.ca) or not (x.pc >= 100) or not (x.atrp >= 2) or not (x.gap >= 0.5) or pm.get(dd, 0) < 15: continue
        dopen = O[i - 1]
        if not (C[i] < O[i] and C[i] < dopen): continue
        e = C[i]; hi = max(H[i - 1], H[i]); stop = (hi - e) / e * 100; tgt = e * 0.99; px, o = None, "stall"
        for j in range(i + 1, len(C)):
            if day[j] != dd: px = C[j - 1]; break
            if H[j] >= hi: px, o = hi, "stop"; break
            if L[j] <= tgt: px, o = tgt, "target"; break
            if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != dd: px = C[j]; break
        if px is None: continue
        ret = (e - px) / e * 100; pos = 1000 / (stop / 100)
        out.append(dict(t=t, date=dd.strftime("%Y-%m-%d"), yr=dd.strftime("%Y"), gap=x.gap, up=bool(x.up), stop=stop, o=o, rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); res, t0 = [], time.time()
    with Pool(6) as pl:
        for k, r in enumerate(pl.imap_unordered(gen, t1, chunksize=8), 1):
            res += r
            if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(res):,} trades, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res)
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
    bull = (nc > nc.rolling(200).mean()).shift(1); R["bull"] = pd.to_datetime(R.date).map(bull)
    R["band"] = np.where(R.gap >= 1, "gap >= 1%", "gap 0.5-1%"); R.to_csv(HERE / "gap_up_fade_short.csv", index=False)
    tdays = nc.loc["2024-01-01":"2026-09-30"].index; bulld = set(d.strftime("%Y-%m-%d") for d in tdays if bull.get(d) == True); beard = set(d.strftime("%Y-%m-%d") for d in tdays if bull.get(d) == False)
    print(f"\ntrading days 2024-01..2026-09: {len(tdays)} (bull {len(bulld)}, bear {len(beard)}) | median stop (day's high) {R.stop.median():.2f}%")

    def row(lab, g, dset=None):
        if len(g) < 30: return f"| {lab} | {len(g)} | | | | | | | | |"
        parts = [f"{(g.o == o).mean()*100:.0f}% ({g[g.o == o].rs1L.mean():+,.0f})" for o in ("target", "stall", "stop")]
        y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 30 else "-" for k in ("2024", "2025", "2026"))
        byd = g.groupby("date").rs1L.sum().sort_values(ascending=False); wo = g[~g.date.isin(byd.head(10).index)].rs1L.mean()
        av = f"{g.date.nunique()/len(dset)*100:.0f}%" if dset else "-"
        return f"| {lab} | {len(g):,} | {av} | " + " | ".join(parts) + f" | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} | {wo:+.0f} |"

    H = "| group | trades | days with a setup | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 | without top-10 days |\n|---|---|---|---|---|---|---|---|---|---|"
    print(H)
    alld = bulld | beard
    print(row("ALL (any regime)", R, alld))
    for b, bl, ds in ((True, "Nifty ABOVE 200d", bulld), (False, "Nifty BELOW 200d", beard)):
        X = R[R.bull == b]; print(row(bl, X, ds))
        for band in ("gap 0.5-1%", "gap >= 1%"):
            for u, ul in ((True, "stock UPtrend"), (False, "stock DOWNtrend")):
                print(row(f"  {bl}, {band}, {ul}", X[(X.band == band) & (X.up == u)], ds))
