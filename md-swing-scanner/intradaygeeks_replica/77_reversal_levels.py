"""Where do the shorts reverse? Placebo check (user, 2026-10-04). Spec fixed before running.
Population: how_low_P0.csv (current rules, all setups; 511 30m / 1629 1H).
Two definitions of the turning point (price after entry until the 15:15 square-off):
  REV  = lowest low after entry, counted only if price then rose >= 0.3% (of entry) before 15:15  (a real reversal)
  STOP = for stopped trades: lowest low between entry and the bar that hit the stop (the turn that killed the trade)
Candidate levels, all known at entry, used only when BELOW entry and within 2%:
  1H EMA8 (last completed hour) | day's low so far (before entry) | previous day low | previous day close |
  daily pivot PP, S1 (yesterday H/L/C) | weekly pivot PP, S1 (last completed week) | daily EMA20 (yesterday)
Test: share of turning points within +-0.15% of the level (in % of entry) vs a placebo where the level's distance
below entry is shuffled across trades (1,000 shuffles, same eligible trades). Real >> placebo = price respects it."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent
LEVELS = ["h1_ema8", "day_low_so_far", "prev_low", "prev_close", "d_PP", "d_S1", "w_PP", "w_S1", "d_ema20"]


def one(args):
    t, g = args
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)[["High", "Low", "Close"]].dropna()
    e20 = D.Close.ewm(span=20, adjust=False).mean()
    W = D.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    bars = {}
    out = []
    for ix, r in g.iterrows():
        s = r.set
        if s not in bars:
            if s == "a":
                m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0); step = pd.Timedelta("5min")
            else:
                m = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); step = pd.Timedelta("60min")
            m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); bars[s] = (m, step)
        m, step = bars[s]
        day = pd.Timestamp(r.date)
        at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min") if s == "a" else day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)
        dm = m[m.index.normalize() == day]
        before, after = dm[dm.index + step <= at], dm[(dm.index >= at) & (dm.index + step <= day + pd.Timedelta("15h15min"))]
        prev = D[D.index < day]
        if after.empty or before.empty or len(prev) < 25: continue
        E, SP = r.qc, r.qh
        H, L = after.High.values, after.Low.values
        i_lo = int(np.argmin(L)); rev = None
        if i_lo + 1 < len(H) and (H[i_lo + 1:].max() - L[i_lo]) / E * 100 >= 0.3: rev = L[i_lo]
        hit = np.where(H >= SP)[0]; stp = None
        if len(hit) and hit[0] > 0: stp = L[:hit[0]].min()
        elif len(hit) and hit[0] == 0: stp = None
        y = prev.iloc[-1]; pp = (y.High + y.Low + y.Close) / 3
        wk = W[W.index < day - pd.Timedelta(days=day.weekday())].iloc[-1]; wpp = (wk.High + wk.Low + wk.Close) / 3
        lv = dict(h1_ema8=E * (1 - r.d8 / 100), day_low_so_far=before.Low.min(), prev_low=y.Low, prev_close=y.Close,
                  d_PP=pp, d_S1=2 * pp - y.High, w_PP=wpp, w_S1=2 * wpp - wk.High, d_ema20=e20[e20.index < day].iloc[-1])
        rec = dict(set=s, rev=(E - rev) / E * 100 if rev is not None else np.nan, stp=(E - stp) / E * 100 if stp is not None else np.nan)
        for k, v in lv.items():
            d = (E - v) / E * 100
            rec[k] = d if 0 < d <= 2 else np.nan          # level below entry, within 2%
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        X = pd.DataFrame(sum(p.map(one, list(y.groupby("ticker"))), []))
    X.to_csv(HERE / "reversal_levels.csv", index=False)
    rng = np.random.default_rng(77)
    for s, nm in (("a", "30m Jun-Sep 2026"), ("b", "1H 3 years")):
        for pt, pn in (("rev", "REV: low followed by a >=0.3% bounce"), ("stp", "STOP: lowest point before the stop hit")):
            z = X[(X.set == s) & X[pt].notna()]
            print(f"\n===== {nm} | {pn} | {len(z)} turning points =====")
            print(f"{'level':16s} {'n':>5s} {'real %':>7s} {'placebo %':>9s} {'ratio':>6s} {'p':>6s}   median level dist")
            for k in LEVELS:
                w = z[z[k].notna()]
                if len(w) < 30: continue
                lo, lvd = w[pt].values, w[k].values
                real = (np.abs(lo - lvd) <= 0.15).mean()
                sims = np.array([(np.abs(lo - rng.permutation(lvd)) <= 0.15).mean() for _ in range(1000)])
                print(f"{k:16s} {len(w):5d} {real*100:7.1f} {sims.mean()*100:9.1f} {real/sims.mean():6.2f} {np.mean(sims >= real):6.3f}   {np.median(lvd):.2f}%")
