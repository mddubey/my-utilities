"""Volatility-scaled target (user, 2026-10-04). Spec fixed before running. Population: current rules, all setups
(how_low_P0.csv, with prior-day daily ATR% = atrp). Stop = candle high; exits exactly as the live system: 5h cap on the
30m set / 5 candles on the 1H set, or EOD; stop first if both in one bar.
  Baseline: fixed 1% target.   Scaled: target = max(1%, k x daily ATR%), k = 0.25 / 0.30 / 0.35 (never below 1%).
Report both sets: all setups and the one-a-day plan, Rs gross and NET of ~Rs85 charges per Rs 1 lakh, by ATR band and
by month (30m) / year (1H)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent
KS = [0.25, 0.30, 0.35]; COST = 0.085


def sim(args):
    t, g = args
    out = []; cache = {}
    for ix, r in g.iterrows():
        s = r.set
        if s not in cache:
            p = INTRADAY_5M_DIR / f"{t}.csv" if s == "a" else HERE / "h1_cache" / f"{t}.csv"
            m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            cache[s] = m
        m = cache[s]; day = pd.Timestamp(r.date)
        if s == "a":
            at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min")
            b = m[(m.index >= at) & (m.index.normalize() == day)]
            end_k = lambda k: b.index[k] >= at + pd.Timedelta("5h")
        else:
            at = day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)
            b = m[(m.index >= at) & (m.index.normalize() == day)]
            end_k = lambda k: k >= 4                       # 5 candles after entry (k = 0..4)
        if b.empty: continue
        E, SP = r.qc, r.qh; H, L, C = b.High.values, b.Low.values, b.Close.values
        rec = {"ix": ix}
        for name, T in [("fixed", 1.0)] + [(f"k{k}", max(1.0, k * r.atrp)) for k in KS]:
            tg = E * (1 - T / 100); res = (E - C[-1]) / E * 100
            for k in range(len(H)):
                if H[k] >= SP: res = -(SP - E) / E * 100; break
                if L[k] <= tg: res = T; break
                if end_k(k): res = (E - C[k]) / E * 100; break
            rec[name] = res; rec[f"T_{name}"] = T
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(sim, list(y.groupby("ticker"))), [])).set_index("ix")
    y = y.join(R, how="inner"); y.to_csv(HERE / "atr_scaled_target.csv", index=False)
    cols = ["fixed"] + [f"k{k}" for k in KS]
    bands = pd.cut(y.atrp, [2.56, 3, 3.5, 4.5, 99], labels=["2.6-3", "3-3.5", "3.5-4.5", "4.5+"])
    for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [3, 4]), ("b", "1H 3 years", 4, [10, 11])):
        z = y[y.set == s].copy(); z["band"] = bands[y.set == s]; z["p"] = z.date.str[:per]
        print(f"\n################ {nm}  (check: fixed-1% mean Rs {z.fixed.mean()*1000:+.0f} vs live-system ret {z.ret.mean()*1000:+.0f})")
        print("ALL SETUPS  target rule      : " + " | ".join(f"{c:6s} gross {z[c].mean()*1000:+4.0f} net {(z[c].mean()-COST)*1000:+4.0f}" for c in cols))
        print("  by ATR band (gross Rs; avg target used):")
        for bnd, g in z.groupby("band", observed=True):
            print(f"    {bnd:8s} n={len(g):4d}  " + "  ".join(f"{c}: {g[c].mean()*1000:+4.0f} (T {g['T_' + c].mean():.2f}%)" for c in cols))
        print("  by period (gross Rs): " + "  ".join(f"{p}: " + "/".join(f"{g[c].mean()*1000:+.0f}" for c in cols) for p, g in z.groupby("p")))
        pl = z[z.alarm.isin(al)].sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
        print(f"PLAN one/day (n={len(pl)}): " + " | ".join(f"{c}: gross {pl[c].mean()*1000:+4.0f} net {(pl[c].mean()-COST)*1000:+4.0f}" for c in cols))
        print("  plan by period: " + "  ".join(f"{p}: " + "/".join(f"{g[c].mean()*1000:+.0f}" for c in cols) for p, g in pl.groupby("p")))
