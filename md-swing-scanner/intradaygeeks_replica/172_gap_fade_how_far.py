"""How far does a faded gap actually go? (user, 2026-10-11: 'does it stop at the gap fill or go further -- day close, support, EMA?').
Spec fixed before running. Same entries as 171 (OR15 break, gap >= 0.5%, 5-min data, 84 bear days). Ignoring any stop, from entry to
15:15: lowest price reached (MFE) and highest (MAE); does the low reach yday's close (gap fill)? how far beyond it, in % and as a multiple
of the gap; what time the day's low came; is the low near yday's low / the 1H EMA34-ish (skip: hourly EMA not in 5-min file) -> only
yday close and yday low used. Descriptive only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import INTRADAY_5M_DIR


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    c = d.Close
    D = pd.DataFrame({"pc": c.shift(1), "pl": d.Low.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    m = pd.read_csv(p, index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index: continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index()
        if g.hm.iloc[0] != "09:15": continue
        gap = (g.Open.iloc[0] / x.pc - 1) * 100
        if gap < 0.5: continue
        rg = g[g.hm < "09:30"]; after = g[g.hm >= "09:30"]
        orh, orl = rg.High.max(), rg.Low.min(); brk = after[(after.Close < orl) & (after.hm < "11:15")]
        if len(brk) == 0: continue
        k = brk.index[0]; e = brk.Close.iloc[0]
        if e <= x.pc: continue
        rest = g[(g.index > k) & (g.hm < "15:15")]
        if len(rest) == 0: continue
        lo = rest.Low.min(); lo_t = rest.Low.idxmin().strftime("%H:%M"); hi_before_lo = rest.loc[:rest.Low.idxmin()].High.max()
        out.append(dict(gap=gap, e=e, pc=x.pc, pl=x.pl, mfe=(e - lo) / e * 100, mae_before=(hi_before_lo - e) / e * 100, stop=(orh - e) / e * 100,
                        filled=lo <= x.pc, beyond=(x.pc - lo) / x.pc * 100, beyond_gaps=(x.pc - lo) / (g.Open.iloc[0] - x.pc), lo_t=lo_t,
                        near_pl=abs(lo - x.pl) / x.pl * 100 <= 0.3, stop_first=hi_before_lo >= orh, close_vs_e=(e - rest.Close.iloc[-1]) / e * 100))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pl: R = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    print(f"entries: {len(R)} | median gap {R.gap.median():.2f}% | median stop (range high) {R.stop.median():.2f}%")
    print(f"\nreached the GAP FILL (yday close) before 15:15: {R.filled.mean()*100:.0f}%")
    f = R[R.filled]
    print(f"of those, went BEYOND the fill: median {f.beyond.median():.2f}% further ({f.beyond_gaps.median():.2f}x the gap); went >= 0.5% beyond: {(f.beyond >= 0.5).mean()*100:.0f}%, >= 1%: {(f.beyond >= 1).mean()*100:.0f}%")
    print(f"low of the day near yday's LOW (within 0.3%): {R.near_pl.mean()*100:.0f}%")
    print(f"\nMFE from entry (no stop): median {R.mfe.median():.2f}% | 25th {R.mfe.quantile(.25):.2f}% | 75th {R.mfe.quantile(.75):.2f}% | share reaching 1%: {(R.mfe >= 1).mean()*100:.0f}%, 2%: {(R.mfe >= 2).mean()*100:.0f}%")
    print(f"before reaching that low, price first went UP by: median {R.mae_before.median():.2f}% | it hit the range-high stop first in {R.stop_first.mean()*100:.0f}% of trades")
    print(f"position at 15:15 vs entry (short P&L, no stop): median {R.close_vs_e.median():+.2f}% | mean {R.close_vs_e.mean():+.2f}% | positive {(R.close_vs_e > 0).mean()*100:.0f}%")
    tb = pd.cut(pd.to_datetime(R.lo_t, format="%H:%M").dt.hour + pd.to_datetime(R.lo_t, format="%H:%M").dt.minute / 60, [9, 10, 11, 12, 13, 14, 15.3], labels=["before 10", "10-11", "11-12", "12-13", "13-14", "14-15:15"])
    print("\nwhen the low after entry came:", (tb.value_counts(normalize=True).sort_index() * 100).round(0).to_dict())
