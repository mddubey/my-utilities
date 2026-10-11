"""GAP-FADE SHORT built properly, opening-range trigger, 5-min data (user, 2026-10-11, option b: no VWAP because Yahoo's 09:15 5-min
bar has zero volume). Spec fixed before running. 5-min cache, 2026-06-10 .. latest (Nifty below its 200-day throughout -> checked
per day). Universe: price >= Rs100, ADTV >= Rs10 cr, previous day's median 5-min turnover >= Rs15 lakh, ATR >= 2%. Gap = 09:15 open vs
yday close >= +0.5% (bands 0.5-1 / 1-2 / 2+). Weak vs strong gap = volume of the 09:20 + 09:25 bars vs the same bars' 20-day average:
< 2x weak / >= 2x strong. Opening range OR15 (09:15-09:30) and OR30 (09:15-09:45). Entry: short at the close of the first 5-min bar
after the range that closes BELOW the range low, bar starting before 11:15; skip if the entry is already at/below yday's close (gap
already filled). Stop = range high (unbounded). Target = yday's close (gap fill) | 1% (reference). Exit target / stop / 15:15, stop
first. Report trades, % of trading days with a setup, t / s / s, Rs @1L and @1k risk, by month, weak/strong, gap band, top-10-days.
Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    m = pd.read_csv(p, index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    v15 = m[m.hm.isin(["09:20", "09:25"])].groupby("day").Volume.sum(); v15n = v15.rolling(20, min_periods=10).mean().shift(1)
    out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index: continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index()
        if g.hm.iloc[0] != "09:15": continue
        dop = g.Open.iloc[0]; gap = (dop / x.pc - 1) * 100
        if gap < 0.5: continue
        vr = v15.get(dd, np.nan) / v15n.get(dd, np.nan) if v15n.get(dd, 0) > 0 else np.nan
        for orn, orend in (("OR15", "09:30"), ("OR30", "09:45")):
            rg = g[g.hm < orend]; after = g[g.hm >= orend]
            if len(rg) < 2 or len(after) == 0: continue
            orh, orl = rg.High.max(), rg.Low.min()
            brk = after[(after.Close < orl) & (after.hm < "11:15")]
            if len(brk) == 0: continue
            k = brk.index[0]; e = brk.Close.iloc[0]
            if e <= x.pc: continue
            stop = (orh - e) / e * 100; rest = g[g.index > k]
            for tn, tgt in (("gap fill", x.pc), ("1%", e * 0.99)):
                px, o = None, "stall"
                for ts, b in rest.iterrows():
                    if b.hm >= "15:15": px = b.Open; break
                    if b.High >= orh: px, o = orh, "stop"; break
                    if b.Low <= tgt: px, o = tgt, "target"; break
                if px is None: px = rest.Close.iloc[-1] if len(rest) else e
                ret = (e - px) / e * 100; pos = 1000 / (stop / 100) if stop > 0 else np.nan
                out.append(dict(t=t, date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), orn=orn, tn=tn, gap=gap, vr=vr, stop=stop,
                                tgt_pct=(e - tgt) / e * 100, entry_hm=brk.hm.iloc[0], o=o, rs1L=ret * 1000 - 85, rs1k=ret / 100 * pos - 85 * pos / 1e5))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); res, t0 = [], time.time()
    with Pool(6) as pl:
        for k, r in enumerate(pl.imap_unordered(gen, tk, chunksize=8), 1):
            res += r
            if k % 400 == 0 or k == len(tk): print(f"{k}/{len(tk)} stocks, {len(res):,} rows, {time.time()-t0:.0f}s", flush=True)
    R = pd.DataFrame(res); R.to_csv(HERE / "gap_fade_orb_5m.csv", index=False)
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); nc = n["Close"]
    bull = (nc > nc.rolling(200).mean()).shift(1); R["bull"] = pd.to_datetime(R.date).map(bull)
    tdays = [d for d in nc.loc["2026-06-10":].index]
    print(f"\ntrading days in the 5-min period: {len(tdays)} | Nifty above 200d on {sum(bull.get(d) == True for d in tdays)} of them")

    def row(lab, g):
        if len(g) < 30: return f"| {lab} | {len(g)} | | | | | | | | |"
        parts = [f"{(g.o == o).mean()*100:.0f}% ({g[g.o == o].rs1L.mean():+,.0f})" for o in ("target", "stall", "stop")]
        byd = g.groupby("date").rs1L.sum().sort_values(ascending=False); wo = g[~g.date.isin(byd.head(10).index)].rs1L.mean()
        mon = " / ".join(f"{g[g.mon == k].rs1L.mean():+.0f}" for k in sorted(g.mon.unique()))
        return (f"| {lab} | {len(g):,} | {g.date.nunique()/len(tdays)*100:.0f}% | " + " | ".join(parts) +
                f" | {g.stop.median():.2f}% / {g.tgt_pct.median():.2f}% | {g.rs1L.mean():+.0f} | {g.rs1k.mean():+.0f} | {wo:+.0f} | {mon} |")

    H = "| group | trades | days w/ setup | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | median stop / target dist | Rs/trade @1L | @1k risk | w/o top-10 days | by month (Jun..Oct) |\n|---|---|---|---|---|---|---|---|---|---|---|"
    for orn in ("OR15", "OR30"):
        for tn in ("gap fill", "1%"):
            X = R[(R.orn == orn) & (R.tn == tn)]
            print(f"\n## {orn}, target = {tn}\n" + H)
            print(row("ALL gap-ups that broke the range low", X))
            print(row("WEAK gap (first-15-min volume < 2x normal)", X[X.vr < 2])); print(row("STRONG gap (>= 2x normal)", X[X.vr >= 2]))
            for lab, lo, hi in (("gap 0.5-1%", 0.5, 1), ("gap 1-2%", 1, 2), ("gap 2%+", 2, 99)):
                print(row(f"weak, {lab}", X[(X.vr < 2) & (X.gap >= lo) & (X.gap < hi)]))
