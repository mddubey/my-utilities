"""TRUE 15-MIN in-play ORB (user, 2026-10-12: 'we watch the first 15 min anyway'; the paper's 15-min variant). Everything from the first
15 min (09:15-09:29): relative volume = first-15-min volume (09:15 bar = day volume - other bars) / its 14-day average (>= 10 days),
in play = >= 1 and top 20 of the day; direction = the 15-min candle's colour (09:15 open -> 09:25 bar close); level = the 15-min low
(short) / high (long); stop order live from 09:30 (= the user's 09:30 rule built in), fill at the level or the bar's open if it gapped
past (mid entry-bar rule as 175). Stop 10% / 20% of ATR from the entry; hold to 15:15 (14:15 also); shorts also with the gap-fill skip
(yesterday's close within 1% below the entry). Universe as 175. 5-min bars; same days as 175 (2026-06-24..10-08) for the side-by-side
with the 5-min version from 09:30 (183 / 191). Results only."""
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
    try: d0 = load(t)
    except Exception: return []
    c = d0.Close; raw = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    D = pd.DataFrame({"pc": c.shift(1), "tv": d0.traded_value_sma20.shift(1), "atrp": (d0.atr14 / c * 100).shift(1),
                      "ca": d0.corp_action_day if "corp_action_day" in d0 else False})
    m = pd.read_csv(p, index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    v15 = {}
    for dd, g in m.groupby("day"):
        if g.hm.iloc[0] == "09:15" and len(g) >= 70 and dd in raw.index:
            v0 = raw[dd] - g.Volume.iloc[1:].sum()
            if v0 > 0: v15[dd] = v0 + g[(g.hm > "09:15") & (g.hm < "09:30")].Volume.sum()
    v15 = pd.Series(v15).sort_index(); avg = v15.rolling(14, min_periods=10).mean().shift(1); out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-24") or dd > pd.Timestamp("2026-10-08") or dd not in D.index or dd not in v15.index or not (avg.get(dd, 0) > 0): continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index(); r15 = g[g.hm < "09:30"]
        if len(r15) < 3: continue
        o15, c15 = r15.Open.iloc[0], r15.Close.iloc[-1]
        if c15 == o15: continue
        s = -1 if c15 < o15 else 1; lvl = r15.Low.min() if s < 0 else r15.High.max()
        aft = g[(g.hm >= "09:30") & (g.hm < "15:15")]; hit = aft[(aft.Low < lvl) if s < 0 else (aft.High > lvl)]
        rec = dict(ticker=t, date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), side=s, rv=v15[dd] / avg[dd], traded=len(hit) > 0)
        if len(hit):
            k = hit.index[0]; b0 = g.loc[k]; e = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
            rec.update(et=b0.hm, e=e, gapfill=((e - x.pc) / e * 100 if (s < 0 and x.pc < e) else np.nan))
            for sm in (0.1, 0.2):
                sp = sm * x.atrp; stp = e * (1 - s * sp / 100); pos = 1000 / (sp / 100)
                fo = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl); tc = (b0.High >= stp) if s < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if s < 0 else (b0.Close <= stp)
                for xh in ("14:15", "15:15"):
                    px, o = None, "close"
                    if (fo and tc) or cb: px, o = stp, "stop"
                    elif b0.hm >= xh: continue
                    else:
                        for ts, b in g[g.index > k].iterrows():
                            if b.hm >= xh: px = b.Open; break
                            if (b.High >= stp) if s < 0 else (b.Low <= stp): px, o = stp, "stop"; break
                    if px is None: px = g.Close.iloc[-1]
                    ret = s * (px - e) / e * 100; key = f"{int(sm*100)}_{xh[:2]}"
                    rec[f"R{key}"] = ret / sp; rec[f"k{key}"] = ret / 100 * pos - 85 * pos / 1e5; rec[f"o{key}"] = o
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); t0 = time.time()
    with Pool(6) as pl: A = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first"); A.to_csv(HERE / "orb15_sip.csv", index=False)
    S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded]; ND = A.date.nunique()
    print(f"stock-days {len(A):,} on {ND} days in {time.time()-t0:.0f}s | in-play traded {len(S)}")
    F5 = pd.read_csv(HERE / "orb_sip.csv"); F5["rank"] = F5.groupby("date").rv.rank(ascending=False, method="first")
    F5 = F5[(F5.rv >= 1) & (F5["rank"] <= 20) & F5.traded & (F5.et >= "09:30")]

    def row(lab, g, k, R, o):
        if len(g) == 0: return f"| {lab} | 0 |"
        g = g[g[k].notna()]; kk = g[k]; RR = g[R]; byd = g.groupby("date")[k].sum().sort_values(ascending=False)
        wo = kk[~g.date.isin(byd.head(10).index)].mean(); mon = " / ".join(f"{kk[g.mon == mm].mean():+.0f}" for mm in sorted(g.mon.unique())) if "mon" in g else ""
        return (f"| {lab} | {len(g)} | {g.date.nunique()} | {(g[o] == 'stop').mean()*100:.0f}% | {(RR > 0).mean()*100:.0f}% | {RR.mean():+.2f} | {kk.mean():+.0f} | {wo:+.0f} | "
                f"{kk[g.date <= '2026-08-14'].mean():+.0f} / {kk[g.date >= '2026-08-17'].mean():+.0f} |")
    F5["mon"] = F5.date.str[:7]
    for sm in ("10", "20"):
        print(f"\n## stop {sm}% ATR, hold to 15:15 -- Rs @1k net per trade\n| version | trades | days | stopped | win % | avg R | Rs @1k | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|---|---|---|")
        for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
            print(row(f"{sn} 5-min version, from 09:30 (183)", F5[F5.side == sd], f"r1k{sm}mid", f"R{sm}mid", f"o{sm}mid"))
            print(row(f"{sn} TRUE 15-min version", S[S.side == sd], f"k{sm}_15", f"R{sm}_15", f"o{sm}_15"))
            if sd < 0: print(row("SHORTS 15-min, gap fill within 1% skipped", S[(S.side < 0) & ~(S.gapfill <= 1)], f"k{sm}_15", f"R{sm}_15", f"o{sm}_15"))
            print(row(f"{sn} 15-min, exit 14:15", S[S.side == sd], f"k{sm}_14", f"R{sm}_14", f"o{sm}_14"))
    print(f"\n15-min: entries by 10:00 {(S.et < '10:00').mean()*100:.0f}%, median entry {sorted(S.et)[len(S)//2]}; in-play per day {A[(A.rv >= 1) & (A['rank'] <= 20)].groupby('date').size().median():.0f}")
