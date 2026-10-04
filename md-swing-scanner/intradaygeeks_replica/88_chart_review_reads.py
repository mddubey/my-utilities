"""User's chart reads on 10 plan-B trades (2026-10-04), checked on all trades -- descriptive, nothing forced.
Pre-declared measures (known at entry):
 (a) 1H EMA8 'channel': gap = (EMA34 - EMA8) / price, and whether the EMA8 sits BELOW the entry (support in the path).
     Groups: EMA8 above entry | EMA8 below entry, gap < 0.3% (hugging) | EMA8 below entry, gap >= 0.3% (channel).
 (b) The stock's DAILY trend (yesterday): daily EMA8 vs daily EMA34 (uptrend = short is a pullback inside an uptrend).
 (c) Daily 34-EMA rejection today: day's high so far >= the daily EMA34 (yesterday's) and entry below it.
Population: how_low_P0.csv (current rules, all setups, both sets) and plan B's 68 trades (plan_b_trades.csv)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085


def daily(args):
    t, g = args
    D = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Close.dropna()
    e8, e34 = D.ewm(span=8, adjust=False).mean(), D.ewm(span=34, adjust=False).mean()
    cache = {}; out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); k = D.index < day
        if k.sum() < 40: continue
        s = r.set
        if s not in cache:
            p = INTRADAY_5M_DIR / f"{t}.csv" if s == "a" else HERE / "h1_cache" / f"{t}.csv"
            m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); cache[s] = m
        m = cache[s]
        at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min") if s == "a" else day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15)
        step = pd.Timedelta("5min") if s == "a" else pd.Timedelta("60min")
        dh = m[(m.index.normalize() == day) & (m.index + step <= at)].High.max()
        out.append(dict(ix=ix, d_up=bool(e8[k].iloc[-1] > e34[k].iloc[-1]), d34=e34[k].iloc[-1], day_hi=dh))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(daily, list(y.groupby("ticker"))), [])).set_index("ix")
    y = y.join(R, how="inner")
    y["o"] = y.why.replace({"time": "stall", "eod": "stall"})
    E34 = y.qc / (1 - y.dist / 100); E8 = y.qc * (1 - y.d8 / 100)
    y["gap"] = (E34 - E8) / y.qc * 100
    y["chan"] = np.where(E8 >= y.qc, "EMA8 above entry", np.where(y.gap < 0.3, "EMA8 below, hugging (<0.3%)", "EMA8 below, CHANNEL (>=0.3%)"))
    y["d34_rej"] = (y.day_hi >= y.d34) & (y.qc < y.d34)
    pb = pd.read_csv(HERE / "plan_b_trades.csv")[["ticker", "date", "alarm", "st"]]
    sp = lambda g: f"n={len(g):4d} | tgt {(g.o == 'target').mean()*100:4.1f} stall {(g.o == 'stall').mean()*100:4.1f} stop {(g.o == 'stop').mean()*100:4.1f} | Rs net {(g.ret.mean()-COST)*1000:+4.0f}"
    for col, nm in (("chan", "(a) 1H EMA8 channel"), ("d_up", "(b) stock's DAILY trend up (daily 8 > 34)"), ("d34_rej", "(c) daily 34-EMA rejection today")):
        print(f"\n===== {nm}")
        for s, lab, per in (("a", "30m", 7), ("b", "1H 3y", 4)):
            z = y[y.set == s]
            for k, g in z.groupby(col):
                by = " ".join(f"{q}:{gg.ret.mean()*1000:+.0f}" for q, gg in g.groupby(g.date.str[:per]))
                print(f"  {lab:5s} {str(k):30s} {sp(g)} | {by}")
        b = y[y.set == "a"].merge(pb, on=["ticker", "date", "alarm"])
        print("  plan B trades (outcome counts): " + "; ".join(f"{k}: " + ", ".join(f"{o} {n}" for o, n in g.st.value_counts().items()) for k, g in b.groupby(col)))
    y.to_csv(HERE / "chart_review_reads.csv", index=False)
    for t, d in (("IGL", "2026-06-12"), ("YATHARTH", "2026-08-21"), ("VAIBHAVGBL", "2026-08-26"), ("GMDCLTD", "2026-08-28"), ("SURYAROSNI", "2026-09-09"),
                 ("JPPOWER", "2026-06-18"), ("BERGEPAINT", "2026-07-06"), ("KFINTECH", "2026-07-08"), ("INDUSTOWER", "2026-09-03"), ("ONESOURCE", "2026-09-28")):
        r = y[(y.set == "a") & (y.ticker == t) & (y.date == d)].merge(pb, on=["ticker", "date", "alarm"])
        if len(r): r = r.iloc[0]; print(f"  {t:11s} {d} {r.st:6s} | {r.chan:30s} gap {r.gap:+.2f}% | daily uptrend {r.d_up} | daily-34 rejection {r.d34_rej}")
