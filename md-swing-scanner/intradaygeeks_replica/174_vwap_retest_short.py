"""VWAP retest short (user, 2026-10-11; spec fixed before running, see STRATEGY section 3).
VWAP: running from 09:15; the 09:15 bar's volume = day volume - all other 5-min bars (Yahoo gives 0 there; checked: estimate /
real median 1.01, 73% within +-10%), its price = (H+L+C)/3. Day skipped if the 09:15 bar is missing or < 70 bars.
Stocks: liquid (prev-day median 5-min turnover >= Rs15 lakh), price >= Rs100, 20d traded value >= Rs10 cr, ATR >= 2%, no corp action.
Setup: BREAK = a 5-min close below VWAP; RETEST = a later bar with high >= VWAP and close < VWAP (VWAP at that bar's close);
a close at/above VWAP before a retest resets (wait for a new break). Retests count only from the 09:30 bar (split: from 09:45).
Entry = retest bar close, first retest of the day, before 13:00 (split: before 11:15). One trade per stock per day.
Stop (a) retest bar high | (b) entry + 0.4%. Target 1% | 2 x stop. Exit 15:15 bar open; stop first if both in one bar.
Groups (never pooled): gap-up >= 0.5% with the gap already FILLED before entry (day low so far <= yday close) | gap-up NOT filled |
flat open (-0.5..+0.5%) | gap-down <= -0.5%. 5-min data 2026-06-10..10-08 (all bear phase). Net = Rs85 per Rs1 lakh."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


def walk(rest, e, stp, tgt):
    for ts, b in rest.iterrows():
        if b.hm >= "15:15": return b.Open, "stall", ts
        if b.High >= stp: return stp, "stop", ts
        if b.Low <= tgt: return tgt, "target", ts
    return (rest.Close.iloc[-1], "stall", rest.index[-1]) if len(rest) else (e, "stall", None)


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    c = d.Close; raw = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    D = pd.DataFrame({"pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    m = read5_official(t)  # 2026-10-12: official 09:15 open
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index or dd not in raw.index: continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index()
        if g.hm.iloc[0] != "09:15" or len(g) < 70: continue
        v = g.Volume.values.astype(float); v[0] = raw[dd] - v[1:].sum()
        if v[0] <= 0: continue
        vw = np.cumsum(((g.High + g.Low + g.Close) / 3).values * v) / np.cumsum(v)
        gap = (g.Open.iloc[0] / x.pc - 1) * 100
        H, L, C, HM = g.High.values, g.Low.values, g.Close.values, g.hm.values
        for start in ("09:30", "09:45"):
            broken, k = False, None
            for i in range(len(g)):
                if HM[i] >= "13:00": break
                if not broken:
                    broken = C[i] < vw[i]; continue
                if C[i] >= vw[i]: broken = False; continue
                if HM[i] >= start and H[i] >= vw[i]: k = i; break
            if k is None: continue
            e = C[k]; lowsofar = L[:k + 1].min()
            cat = ("gap-up FILLED" if lowsofar <= x.pc else "gap-up NOT filled") if gap >= 0.5 else ("gap-down" if gap <= -0.5 else "flat")
            rest = g.iloc[k + 1:]; sa = (H[k] - e) / e * 100
            r = dict(ticker=t, date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), start=start, et=HM[k], e=e, vwap=vw[k], hi=H[k],
                     pc=x.pc, gap=gap, cat=cat, above_pc=e > x.pc, stop_a=sa)
            for sn, sp in (("a", sa), ("b", 0.4)):
                for tn, tp in (("1%", 1.0), ("2x", 2 * sp)):
                    px, o, ts = walk(rest, e, e * (1 + sp / 100), e * (1 - tp / 100))
                    ret = (e - px) / e * 100; pos = 1000 / (sp / 100)
                    r[f"o_{sn}{tn}"] = o; r[f"r1L_{sn}{tn}"] = ret * 1000 - 85; r[f"r1k_{sn}{tn}"] = ret / 100 * pos - 85 * pos / 1e5
                    r[f"min_{sn}{tn}"] = (ts - g.index[k]).total_seconds() / 60 if ts is not None else np.nan
            out.append(r)
    return out


def row(lab, g, ex, ND):
    o = g[f"o_{ex}"]; r1, rk = g[f"r1L_{ex}"], g[f"r1k_{ex}"]
    if len(g) == 0: return f"| {lab} | 0 |"
    byd = g.groupby("date")[f"r1L_{ex}"].sum().sort_values(ascending=False); wo = r1[~g.date.isin(byd.head(10).index)].mean()
    mon = " / ".join(f"{r1[g.mon == k].mean():+.0f}" for k in sorted(g.mon.unique()))
    avg = " / ".join(f"{r1[o == k].mean():+.0f}" if (o == k).any() else "-" for k in ("target", "stall", "stop"))
    return (f"| {lab} | {len(g):,} | {g.date.nunique()/ND*100:.0f}% | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / "
            f"{(o=='stop').mean()*100:.0f} | {avg} | {r1.mean():+.0f} | {rk.mean():+.0f} | {wo:+.0f} | {mon} |")


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); t0 = time.time()
    with Pool(6) as pl: R = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    R.to_csv(HERE / "vwap_retest.csv", index=False)
    n = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index(); ND = len(n.loc["2026-06-10":"2026-10-08"].index)
    print(f"rows {len(R):,} in {time.time()-t0:.0f}s | trading days {ND}")
    if "--check" in sys.argv:   # hand-check: 5 random 09:30 / 13:00 trades, bars + VWAP
        S = R[R.start == "09:30"].sample(5, random_state=7)
        for _, r in S.iterrows():
            print(f"\n{r.ticker} {r.date} {r['cat']} | yday close {r.pc:.2f} gap {r.gap:+.2f}% | entry {r.et} @ {r.e:.2f} (VWAP {r.vwap:.2f}, bar high {r.hi:.2f}, stop a {r.stop_a:.2f}%) | a/1%: {r['o_a1%']} b/1%: {r['o_b1%']}")
            m = pd.read_csv(INTRADAY_5M_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
            g = m[m.index.normalize() == r.date].copy(); raw = pd.read_csv(DAILY_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True).Volume[pd.Timestamp(r.date)]
            v = g.Volume.values.astype(float); v[0] = raw - v[1:].sum(); g["vwap"] = np.cumsum(((g.High + g.Low + g.Close) / 3).values * v) / np.cumsum(v)
            g["hm"] = g.index.strftime("%H:%M"); g["c<vw"] = g.Close < g.vwap
            print(g[g.hm <= r.et][["hm", "Open", "High", "Low", "Close", "vwap", "c<vw"]].round(2).to_string(index=False))
        sys.exit()
    EX = (("a1%", "stop = retest bar high, target 1%"), ("a2x", "stop = retest bar high, target 2x stop"),
          ("b1%", "stop 0.4%, target 1%"), ("b2x", "stop 0.4%, target 0.8%"))
    HD = "| trades | days w/ setup | target / stall / stop % | avg Rs: target / stall / stop | Rs/trade @1L | @1k risk | w/o top-10 days | Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|"
    CATS = ("gap-up NOT filled", "gap-up FILLED", "flat", "gap-down")
    for start, cut in (("09:30", "13:00"), ("09:30", "11:15"), ("09:45", "13:00"), ("09:45", "11:15")):
        G = R[(R.start == start) & (R.et < cut)]
        print(f"\n### retests from {start}, entry before {cut}")
        for ex, lab in EX:
            print(f"\n{lab}\n| group " + HD)
            for cat in CATS: print(row(cat, G[G.cat == cat], ex, ND))
    G = R[(R.start == "09:30")]
    print("\n### stop (a) size, 09:30 / 13:00\n| group | median | < 0.1% | 0.1-0.3% | 0.3-0.5% | > 0.5% |\n|---|---|---|---|---|---|")
    for cat in CATS:
        s = G[G.cat == cat].stop_a
        print(f"| {cat} | {s.median():.2f}% | {(s<0.1).mean()*100:.0f}% | {((s>=0.1)&(s<0.3)).mean()*100:.0f}% | {((s>=0.3)&(s<=0.5)).mean()*100:.0f}% | {(s>0.5).mean()*100:.0f}% |")
    print("\n### gap-ups, 09:30 / 13:00, stop (b) 0.4% target 1%: entry above vs below yday close\n| group " + HD)
    for cat in CATS[:2]:
        for ab in (True, False): print(row(f"{cat}, entry {'above' if ab else 'below'} yday close", G[(G.cat == cat) & (G.above_pc == ab)], "b1%", ND))
    print("\n### how fast, 09:30 / 13:00, minutes from entry to exit (cumulative %)\n| group | exit | outcome | n | <=15m | <=30m | <=60m | <=2h | median |\n|---|---|---|---|---|---|---|---|---|")
    for cat in CATS:
        for ex in ("a2x", "b1%"):
            for oc in ("stop", "target"):
                x = G[(G.cat == cat) & (G[f"o_{ex}"] == oc)][f"min_{ex}"]
                print(f"| {cat} | {ex} | {oc} | {len(x)} | " + " | ".join(f"{(x<=b).mean()*100:.0f}%" for b in (15, 30, 60, 120)) + f" | {x.median():.0f} |")
