"""SHORT JUST UNDER THE DAILY 8, STOP AT THE DAILY 8 -- how often is the stop safe? (user, 2026-10-15, from live CEATLTD: 'I saw it
at 3280 [d8 touch 3301.79, 0.65% under] but then it spiked to 3290 -- if I keep the 8 EMA as SL, how likely is that safe?').
Spec fixed before running. 30m set (5-min bars 2026-06..10), liquid (prev-day median 5-min turnover >= Rs15 lakh), prev close >= Rs100.
  Level = yesterday's daily EMA8 (= the price where price meets the live daily 8 today). Distances under it d = 0.3 / 0.65 / 1.0%.
  Event: the day OPENS below level x (1 - d); the first 5-min bar (09:15..13:00) whose high reaches level x (1 - d) -> short there
  (fill = that price, or the bar open if it opened above). Stop = level + 0.05%. Target = entry - 1%, else out at the 15:15 close.
  The entry bar can stop you too (its high >= stop = stopped; the order inside the bar is unknown, counted against us).
  'Safe' = the stop was never hit that day. Splits: gap <= -2% vs not (CEAT gapped -4%); daily trend down (D8 < D34) vs up;
  entry time 09:15-09:45 vs later; by month. Also how far past the level the day's high went when the stop WAS hit."""
import sys, importlib.util, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
COST = 0.085; DS = (0.3, 0.65, 1.0)


def run(t):
    try:
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
        m = read5_official(t)
    except Exception: return []
    s8 = d.Close.ewm(span=8, adjust=False).mean().shift(1); s34 = d.Close.ewm(span=34, adjust=False).mean().shift(1); pc = d.Close.shift(1)
    md = m.index.normalize(); days = sorted(set(md)); out = []
    for a in range(1, len(days)):
        D, P = days[a], days[a - 1]
        if D not in d.index or not s8.get(D, np.nan) == s8.get(D, np.nan) or pc[D] < 100: continue
        pv = m[(md == P) & (m.Volume > 0)]
        if not len(pv) or (pv.Volume * pv.Close).median() < 15e5: continue
        g = m[md == D]; hm = g.index.strftime("%H:%M").values
        if len(g) < 60: continue
        O, H, L, C = g.Open.values, g.High.values, g.Low.values, g.Close.values
        last = np.where(hm <= "15:10")[0][-1]; lvl = s8[D]; stop = lvl * 1.0005
        for dd in DS:
            px = lvl * (1 - dd / 100)
            if O[0] >= px: continue
            hit = np.where((H[:last] >= px) & (hm[:last] <= "13:00"))[0]
            if not len(hit): continue
            i = hit[0]; e = max(px, O[i]); tg = e * 0.99; res = None
            for k in range(i, last + 1):
                if H[k] >= stop: res = ((e - stop) / e * 100, "stop", k); break
                if k > i and L[k] <= tg: res = (1.0, "target", k); break
            if res is None: res = ((e - C[last]) / e * 100, "time", last)
            out.append(dict(ticker=t, date=D.strftime("%Y-%m-%d"), d=dd, time=hm[i], entry=e, lvl=lvl, risk=(stop - e) / e * 100, ret=res[0], why=res[1],
                            gap=(O[0] / pc[D] - 1) * 100, trend=("down" if s8[D] < s34[D] else "up"),
                            day_high_past=(H[i:last + 1].max() / lvl - 1) * 100))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: X = pd.DataFrame([r for rr in p.map(run, uni, chunksize=20) for r in rr])
    X.to_csv(HERE / "short_below_d8.csv", index=False)
    HDR = "| group | trades | SAFE (stop not hit) | stopped | 1% target | out 15:15 | median stop | net Rs @1L |\n|---|---|---|---|---|---|---|---|"
    def row(lab, x):
        if not len(x): return f"| {lab} | 0 | | | | | | |"
        w = x.why
        return (f"| {lab} | {len(x)} | {(w != 'stop').mean()*100:.0f}% | {(w == 'stop').mean()*100:.0f}% | {(w == 'target').mean()*100:.0f}% | "
                f"{(w == 'time').mean()*100:.0f}% | {x.risk.median():.2f}% | {(x.ret.mean() - COST)*1000:+.0f} |")
    for dd in DS:
        x = X[X.d == dd]
        print(f"\n### Short {dd}% under yesterday's daily 8, stop = the daily 8 + 0.05%\n{HDR}")
        print(row("ALL", x))
        print(row("gap <= -2% (CEAT-like)", x[x.gap <= -2])); print(row("gap > -2%", x[x.gap > -2]))
        print(row("daily trend DOWN", x[x.trend == "down"])); print(row("daily trend UP", x[x.trend == "up"]))
        print(row("gap <= -2% AND trend down", x[(x.gap <= -2) & (x.trend == "down")]))
        print(row("entry 09:15-09:45", x[x.time <= "09:45"])); print(row("entry after 09:45", x[x.time > "09:45"]))
        for mo, gm in x.groupby(x.date.str[:7]): print(row(f"month {mo}", gm))
        s = x[x.why == "stop"].day_high_past
        print(f"when stopped, the day's high went past the daily 8 by: median {s.median():.2f}%, p75 {s.quantile(.75):.2f}%, p90 {s.quantile(.9):.2f}%")
    print("\n3 random (0.65%):"); print(X[X.d == 0.65].sample(3, random_state=4).round(2).to_string(index=False))
