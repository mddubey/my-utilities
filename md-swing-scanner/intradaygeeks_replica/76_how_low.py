"""How far do the shorts actually go? (user, 2026-10-04: the 1% target was never derived.) Spec fixed before running.
Populations (current rules incl. full hour at :15, ATR >= 2.56%, green-hour skip), both sets:
  P0 = current rules (2:1 rule + 0.5% cap)  -- reconciliation only (expect 511 / 1629)
  P1 = NO 2:1 rule, keep the 0.5% cap (close no more than 0.5% below the 1H EMA34)
  P2 = NO 2:1 rule, NO cap
Per trade, after entry until the 15:15 square-off (stop = trigger candle high):
  mfe_stop = lowest point before the stop is touched (% below entry)   mfe_eod = lowest point by 15:15 ignoring the stop
  bounce   = 15:15 close vs that low (how much of the move came back)  stop_pct = candle high vs entry
Target grid 0.5/0.75/1/1.25/1.5/2/2.5/3 %, stop = candle high, out at 15:15 (stop first if both in one bar):
  hit rate, Rs per trade on Rs 1 lakh, mean R (R = stop distance)."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
MODE = sys.argv[1] if len(sys.argv) > 1 else "P0"
cond_old = "(E - qc) / E * 100 <= 0.5 and (qh - qc) / qc * 100 <= 0.5"
cond_new = {"P0": cond_old, "P1": "(E - qc) / E * 100 <= 0.5", "P2": "True"}[MODE]
head += f'''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
assert src.count({cond_old!r}) == 2
src = src.replace({cond_old!r}, {cond_new!r})
src = src.replace("alarm=q,", "alarm=q, qc=qc, qh=qh,", 1).replace("alarm=T[i].hour,", "alarm=T[i].hour, qc=qc, qh=qh,", 1)
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "76", "exec"))
ctx70 = {"__file__": str(HERE / "70_prev_hour_context.py")}
exec(compile(open(HERE / "70_prev_hour_context.py").read().split('if __name__ == "__main__":')[0], "70", "exec"), ctx70)
GRID = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]


def paths(args):
    t, g, s = args
    if s == "a":
        m = pd.read_csv(M5 / f"{t}.csv", index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        step = pd.Timedelta("5min")
    else:
        m = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
        step = pd.Timedelta("60min")
    out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date)
        at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min") if s == "a" else day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)
        b = m[(m.index >= at) & (m.index + step <= day + pd.Timedelta("15h15min"))]
        if b.empty: continue
        E, SP = r.qc, r.qh; H, L, C = b.High.values, b.Low.values, b.Close.values
        hit = np.where(H >= SP)[0]; ks = hit[0] if len(hit) else len(H)
        pre = L[:ks] if ks > 0 else np.array([E])
        mfe_stop = (E - pre.min()) / E * 100
        lo_i = int(np.argmin(L)); mfe_eod = (E - L.min()) / E * 100
        rec = dict(ix=ix, stop_pct=(SP - E) / E * 100, mfe_stop=max(mfe_stop, 0), mfe_eod=max(mfe_eod, 0),
                   bounce=(C[-1] - L.min()) / E * 100, low_time=b.index[lo_i].strftime("%H:%M"),
                   stopped=ks < len(H), close_ret=(E - C[-1]) / E * 100)
        for T in GRID:
            tg = E * (1 - T / 100); res = (E - C[-1]) / E * 100
            for k in range(len(H)):
                if H[k] >= SP: res = -(SP - E) / E * 100; break
                if L[k] <= tg: res = T; break
            rec[f"t{T}"] = res
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    res = []
    for x, s in ((A, "a"), (B, "b")):
        x = x.reset_index(drop=True); x["date"] = pd.to_datetime(x.date).dt.strftime("%Y-%m-%d"); x["set"] = s
        ctx = pd.concat([ctx70["context"](g, s) for _, g in x.groupby("ticker")])
        x = x.join(ctx, how="left"); x["grp"] = ctx70["label"](x.fillna({"prev_above": True, "prev_green": False, "above_mid": False}))
        late = x.alarm.eq(11) if s == "b" else x.alarm.isin([4, 5])
        x = x[~(late & x.grp.str.startswith("B"))]
        with Pool(6) as p:
            pr = pd.DataFrame(sum(p.map(paths, [(t, g, s) for t, g in x.groupby("ticker")]), [])).set_index("ix")
        res.append(x.join(pr, how="inner"))
    R = pd.concat(res); R.to_csv(HERE / f"how_low_{MODE}.csv", index=False)
    print(MODE, {s: int((R.set == s).sum()) for s in "ab"}, "generator 5h-exit mean Rs:", {s: round(R[R.set == s].ret.mean() * 1000) for s in "ab"})
