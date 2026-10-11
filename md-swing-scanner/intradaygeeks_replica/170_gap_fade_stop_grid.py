"""Gap-up fade short: formalize the stop (user, 2026-10-11: '42% target rate means there is scope'). Spec fixed before running. Same
population as 169 (gap >= 0.5%, 10:15 candle red and closing below the day's open, short 11:15, liquid, >= Rs100, ATR >= 2%).
Stop placement A = day's high so far | B = the 10:15 candle's high. Caps: <= 0.5 / 0.75 / 1.0% / none. Targets: 1% fixed | max(1%, 2 x stop).
Exit target / stop / 5 candles or day's last candle. By regime (Nifty vs its 200-day): trades, % of days with a setup, t / s / s,
Rs/trade @1L and @1k risk, by year, without the top-10 days. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
src = open(HERE / "169_gap_up_fade_short.py").read()
exec(src.split("def gen(t):")[0].split('"""', 2)[2])


def gen(t):
    p = HERE / "h1_cache" / f"{t}.csv"
    if not p.exists(): return []
    try:
        d = load(t); d = d[d.index < "2026-10-01"]
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"gap": (d.Open / c.shift(1) - 1) * 100, "pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
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
        if not (C[i] < O[i] and C[i] < O[i - 1]): continue
        e = C[i]
        for pl, hi in (("A day high", max(H[i - 1], H[i])), ("B 10:15 high", H[i])):
            stop = (hi - e) / e * 100
            if stop <= 0: continue
            for tl, tp in (("1%", 1.0), (">=1:2", max(1.0, 2 * stop))):
                tgt = e * (1 - tp / 100); px, o = None, "stall"
                for j in range(i + 1, len(C)):
                    if day[j] != dd: px = C[j - 1]; break
                    if H[j] >= hi: px, o = hi, "stop"; break
                    if L[j] <= tgt: px, o = tgt, "target"; break
                    if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != dd: px = C[j]; break
                if px is None: continue
                ret = (e - px) / e * 100; pos = 1000 / (stop / 100)
                out.append(dict(date=dd.strftime("%Y-%m-%d"), yr=dd.strftime("%Y"), pl=pl, tl=tl, stop=stop, o=o, rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv")); res, t0 = [], time.time()
    with Pool(6) as plx:
        for k, r in enumerate(plx.imap_unordered(gen, t1, chunksize=8), 1):
            res += r
            if k % 500 == 0 or k == len(t1): print(f"{k}/{len(t1)} stocks, {len(res):,} rows, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res)
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
    bull = (nc > nc.rolling(200).mean()).shift(1); R["bull"] = pd.to_datetime(R.date).map(bull)
    tdays = nc.loc["2024-01-01":"2026-09-30"].index; ND = {True: sum(bull.get(d) == True for d in tdays), False: sum(bull.get(d) == False for d in tdays)}
    print("| stop placement | target | cap | regime | trades | days w/ setup | target / stall / stop % | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 | w/o top-10 days |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for pl in ("A day high", "B 10:15 high"):
        for tl in ("1%", ">=1:2"):
            for cap in (0.5, 0.75, 1.0, 99):
                for b in (True, False):
                    g = R[(R.pl == pl) & (R.tl == tl) & (R.stop <= cap) & (R.bull == b)]
                    if len(g) < 30: continue
                    o = g.o; y = " / ".join(f"{g[g.yr == k].rs1L.mean():+.0f}" if (g.yr == k).sum() >= 30 else "-" for k in ("2024", "2025", "2026"))
                    byd = g.groupby("date").rs1L.sum().sort_values(ascending=False); wo = g[~g.date.isin(byd.head(10).index)].rs1L.mean()
                    print(f"| {pl} | {tl} | {'none' if cap == 99 else f'<= {cap}%'} | {'BULL' if b else 'BEAR'} | {len(g):,} | {g.date.nunique()/ND[b]*100:.0f}% | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {y} | {wo:+.0f} |")
