"""How to pick ONE trade per day from many candidates. Spec fixed 2026-10-03 before running.
Act at the first alarm of the day with any candidate; within it pick by: closest to EMA | tightest stop | most liquid
(prior-day tv20) | weakest on the day (entry / yesterday's close, most negative) | random (mean of 200 draws).
Sets: (a) 30m-trigger shorts, 2:1 rule, alarms 10:45-12:15, Jun 10 - Sep 30 2026 (43's output);
      (b) 1H-close checklist shorts, 2:1 rule, 0.5% cap, alarms 11:15/12:15, 2024-26 (33's output).
A rule counts only if it beats random in most periods (months for a, years for b)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent; M5 = HERE.parent / "intraday_cache"


def daily_feats(args):
    t, g = args
    try: d = load(t)
    except Exception: return []
    tv, pc = d.traded_value_sma20.shift(1), d.Close.shift(1)
    return [(i, tv.get(dt, np.nan), pc.get(dt, np.nan)) for i, dt in zip(g.index, g.date)]


def entry_px(args):
    t, g = args
    x = pd.read_csv(M5 / f"{t}.csv", index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return [(i, x.Close.get(ti - pd.Timedelta("5min"), np.nan)) for i, ti in zip(g.index, g.t_in)]


def evaluate(D, per, title, rng):
    first = D.groupby("date").t_in.transform("min"); F = D[D.t_in == first].copy()
    rules = {"closest to EMA": ("dist", True), "tightest stop": ("stop_pct", True),
             "most liquid": ("tv", False), "weakest on the day": ("day_move", True)}
    out = {}
    for nm, (c, asc) in rules.items():
        out[nm] = F.sort_values(["date", c], ascending=[True, asc]).groupby("date").head(1)
    draws = [F.groupby("date", group_keys=False).apply(lambda g: g.sample(1, random_state=int(rng.integers(1e9)))) for _ in range(200)]
    rnd_mean = np.mean([d.ret.mean() for d in draws])
    rnd_per = pd.concat([d.groupby(per(d)).ret.mean() for d in draws], axis=1).mean(axis=1)
    print(f"\n### {title}: {D.date.nunique()} days, {len(D)/D.date.nunique():.1f} candidates/day, {len(F)/F.date.nunique():.1f} at the first alarm")
    print(f"| pick rule | mean % per trade | win% | by period | beats random in |\n|---|---|---|---|---|")
    print(f"| random (200 draws) | {rnd_mean:+.3f} | | " + " / ".join(f"{v:+.2f}" for v in rnd_per) + " | -- |")
    for nm, x in out.items():
        p = x.groupby(per(x)).ret.mean(); beats = int((p > rnd_per.reindex(p.index)).sum())
        print(f"| {nm} | {x.ret.mean():+.3f} | {(x.ret>0).mean()*100:.0f} | " + " / ".join(f"{v:+.2f}" for v in p) + f" | {beats} of {len(p)} |")
    print(f"| (all candidates, no pick) | {D.ret.mean():+.3f} | {(D.ret>0).mean()*100:.0f} | " + " / ".join(f"{v:+.2f}" for v in D.groupby(per(D)).ret.mean()) + " | |")


if __name__ == "__main__":
    from multiprocessing import Pool
    rng = np.random.default_rng(7)
    A = pd.read_csv(HERE / "alarm_times_30m.csv", parse_dates=["date", "t_in"])
    A = A[A.alarm.isin(["10:45", "11:15", "11:45", "12:15"])].copy().rename(columns={"below_ema": "dist"})
    with Pool(6) as p:
        F1 = sum(p.map(daily_feats, list(A.groupby("ticker"))), []); F2 = sum(p.map(entry_px, list(A.groupby("ticker"))), [])
    A = A.join(pd.DataFrame(F1, columns=["i", "tv", "pc"]).set_index("i")).join(pd.DataFrame(F2, columns=["i", "px"]).set_index("i"))
    A["day_move"] = A.px / A.pc - 1
    evaluate(A, lambda x: x.date.dt.month, "(a) 30-min trigger shorts, 2:1", rng)
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    B = X[(X.side == "short") & X.bar_ts.dt.strftime("%H:%M").isin(["10:15", "11:15"]) & (X.dadx <= 25) & (X.vwap_with == True)
          & (X.st_live <= 0) & (X.close_past_ema > 0) & (X.close_past_ema <= 0.5) & (X.stop_pct <= 0.5)].copy()
    B["t_in"] = B.bar_ts + pd.Timedelta("60min"); B["dist"] = B.close_past_ema
    with Pool(6) as p: F1 = sum(p.map(daily_feats, list(B.groupby("ticker"))), [])
    B = B.join(pd.DataFrame(F1, columns=["i", "tv", "pc"]).set_index("i")); B["day_move"] = B.price / B.pc - 1
    evaluate(B, lambda x: x.date.dt.year, "(b) 1H-close checklist shorts, 2:1, 2024-26", rng)
