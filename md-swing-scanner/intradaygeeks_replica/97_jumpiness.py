"""Jumpiness / thin-stock execution risk (user, 2026-10-08, after IPCALAB: a ~Rs31L buy burst spiked through the stop
in a stock trading Rs1-2L a minute; "it's not about win %, it's whether jumps / fluctuations happen"). Spec fixed before
running:
  Population: 30m set, current rules, RED setups (green_rejection.csv set a, 511 -- reconciles with 76 P0). 5-min bars.
  The 1H 3-year set is out (hourly bars cannot see a single burst).
  OUTCOME (execution risk, NOT win rate), fixed window per setup independent of the result: entry (alarm candle close)
  to min(entry + 5h, 15:15):
    jumps_ph  = 5-min bars with |close-to-close| > 0.2% per hour      maxbar = largest single 5-min bar range, % of price
    max_vs_stop = maxbar / stop distance (>= 1: one bar can span the whole stop); same three for the first hour (sub-view)
  PREDICTORS (known at entry), 12 bars before the alarm: amihud = mean(|bar return %| / Rs crore traded); liq_L =
  median Rs lakh per bar (the live THIN flag, < 25); pre_jumps_ph / pre_maxbar (persistence baseline); ATR14 % (control).
  Groups: terciles of each predictor (cut points from the predictor only), each outcome by tercile and by month.
  Real = worst tercile clearly jumpier in >= 3 of 4 months, Spearman permutation p < 0.05 (5,000), AND it survives the
  ATR control (rank correlation of ATR-residualised predictor vs ATR-residualised outcome)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR as M5, DAILY_DIR
HERE = Path(__file__).resolve().parent
JUMP = 0.2


def one(args):
    t, g = args
    try:
        m = pd.read_csv(M5 / f"{t}.csv", index_col=0, parse_dates=True)
        m.index = (m.index.tz_localize("UTC") if m.index.tz is None else m.index).tz_convert("Asia/Kolkata").tz_localize(None)
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    except Exception:
        return []
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    atrp = (tr.ewm(alpha=1 / 14, adjust=False).mean() / d.Close * 100)
    out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); ent = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min")
        end = min(ent + pd.Timedelta("5h"), day + pd.Timedelta("15h15min"))
        dm = m[m.index.normalize() == day]
        pre = dm[dm.index < ent].tail(12); post = dm[(dm.index >= ent) & (dm.index < end)]
        if len(pre) < 10 or len(post) < 6: continue
        prev_c = pre.Close.iloc[-1]
        def stats(b, p0):
            c = pd.concat([pd.Series([p0]), b.Close.reset_index(drop=True)])
            rr = (c.pct_change().dropna() * 100).abs().values
            rng = ((b.High - b.Low) / b.Close * 100).values
            return (rr > JUMP).sum() / (len(b) / 12), rng.max()
        pre_rr = (pre.Close.pct_change() * 100).abs().iloc[1:]; pre_rs = (pre.Volume * pre.Close).iloc[1:]
        ok = pre_rs > 0
        amihud = (pre_rr[ok] / (pre_rs[ok] / 1e7)).mean() if ok.any() else np.nan
        pj, pm = stats(pre.iloc[1:], pre.Close.iloc[0])
        jp, mb = stats(post, prev_c); jp1, mb1 = stats(post.head(12), prev_c)
        sp = r["stop"]
        a = atrp[atrp.index < day]
        out.append(dict(ix=ix, ticker=t, date=r.date, month=r.date[:7], stop_pct=sp, amihud=amihud,
                        liq_L=float((pre.Volume * pre.Close).median() / 1e5), pre_jumps_ph=pj, pre_maxbar=pm,
                        atrp=a.iloc[-1] if len(a) else np.nan, jumps_ph=jp, maxbar=mb, max_vs_stop=mb / sp if sp > 0 else np.nan,
                        jumps_ph_1h=jp1, maxbar_1h=mb1, max_vs_stop_1h=mb1 / sp if sp > 0 else np.nan))
    return out


def rank_resid(y, x):
    ry, rx = pd.Series(y).rank().values, pd.Series(x).rank().values
    b = np.polyfit(rx, ry, 1); return ry - np.polyval(b, rx)


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "green_rejection.csv"); y = y[(y.set == "a") & (~y.green)]
    with Pool(6) as p:
        J = pd.DataFrame(sum(p.map(one, list(y.groupby("ticker"))), []))
    J.to_csv(HERE / "jumpiness.csv", index=False)
    print(f"setups measured: {len(J)} of {len(y)} | THIN (liq_L < 25): {(J.liq_L < 25).mean()*100:.0f}%")
    rng = np.random.default_rng(97)
    OUT = ["jumps_ph", "maxbar", "max_vs_stop", "jumps_ph_1h", "maxbar_1h", "max_vs_stop_1h"]
    print("\nbaseline (all):", " | ".join(f"{o} {J[o].mean():.2f}" for o in OUT))
    for pred, worst_high in (("amihud", True), ("liq_L", False), ("pre_jumps_ph", True), ("pre_maxbar", True), ("atrp", True)):
        z = J.dropna(subset=[pred]).copy()
        z["t"] = pd.qcut(z[pred], 3, labels=["T1 low", "T2 mid", "T3 high"])
        print(f"\n## {pred} (worst tercile = {'T3 high' if worst_high else 'T1 low'})  cuts: {np.round(z[pred].quantile([1/3, 2/3]).values, 3).tolist()}")
        tab = z.groupby("t")[OUT].mean().round(2); tab.insert(0, "n", z.groupby("t").size()); print(tab.to_string())
        worst = "T3 high" if worst_high else "T1 low"; best = "T1 low" if worst_high else "T3 high"
        mm = z.groupby(["month", "t"]).jumps_ph.mean().unstack()
        print("jumps_ph by month: " + " ".join(f"{k}: worst {r[worst]:.2f} vs best {r[best]:.2f}" for k, r in mm.iterrows()))
        mv = z.groupby(["month", "t"]).max_vs_stop.mean().unstack()
        print("max_vs_stop by month: " + " ".join(f"{k}: {r[worst]:.2f} vs {r[best]:.2f}" for k, r in mv.iterrows()))
        for o in ("jumps_ph", "max_vs_stop"):
            zz = z.dropna(subset=[o, "atrp"]); xs, ys = zz[pred].rank().values, zz[o].rank().values
            rho = np.corrcoef(xs, ys)[0, 1]
            sh = np.array([np.corrcoef(rng.permutation(xs), ys)[0, 1] for _ in range(5000)])
            line = f"  {o}: Spearman {rho:+.3f}, p {np.mean(np.abs(sh) >= abs(rho)):.4f}"
            if pred != "atrp":
                rx, ry = rank_resid(zz[pred].values, zz.atrp.values), rank_resid(zz[o].values, zz.atrp.values)
                rp = np.corrcoef(rx, ry)[0, 1]; shp = np.array([np.corrcoef(rng.permutation(rx), ry)[0, 1] for _ in range(5000)])
                line += f" | after ATR control {rp:+.3f}, p {np.mean(np.abs(shp) >= abs(rp)):.4f}"
            print(line)
