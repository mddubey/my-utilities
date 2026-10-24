"""Level poke-and-reject, the ORB fade levels across the whole day (2026-10-22, spec agreed in chat; RESULTS ONLY, nothing goes
to STRATEGY.md). Follows 255 (R1 only, green-bar bug) and the 2026-10-21 TCS / INFY R2 rejections.

Levels (only those above the 09:15 close): 09:15 high, R1, R2, daily 8 touch (yesterday's EMA8), yesterday's high, yesterday's
close. Stacked = another of these levels within 0.3%.
Event:   per level, the FIRST 5-min bar (09:20-14:55) whose High >= level*(1-0.0005) (every earlier bar's High below that; for the
         09:15 high the 09:15 bar itself is skipped) -- it must close RED (Close < Open) and back under the level, else no event.
Entry A: the poke bar's close.
Entry B: the first later 5-min close under VWAP (and under the level) within 12 bars (60 min); no trade if the poke high + 0.05%
         trades first or no such close.
Stop:    poke high + 0.05% (both entries). Exit: package (a) -- stop to entry after +2R, out at the 15:10 bar close (15:15).
Universe: 5-min cache (2026-06-10 on), price >= Rs100, prior-5-day median 5-min turnover >= Rs15 lakh. In-play tag from
         orb_list_history.csv (230; covers up to 2026-10-16, later days tagged NA).
Cost:    ~Rs85 per Rs1 lakh traded, reported per Rs1k risk. Pass bar (set before the run): net positive AND positive without the
         top 5 days.
Check:   red R1 entry A must match 255's red R1 rows (r1_poke_fade_events.csv)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

HERE = Path(__file__).resolve().parent
TOUCH, STOP_BUF, STACK, LIQ, B_WAIT = 0.0005, 0.0005, 0.003, 15e5, 12
BUCKETS = [("09:20-10:30", "09:20", "10:25"), ("10:30-12:00", "10:30", "11:55"),
           ("12:00-13:30", "12:00", "13:25"), ("13:30-15:00", "13:30", "14:55")]


def bucket(hm):
    for name, a, b in BUCKETS:
        if a <= hm <= b: return name
    return None


def simulate(day, i, stop):
    """Short at bar i's close, package (a), same as 255."""
    e = day.Close.iat[i]; risk = stop - e
    if risk <= 0: return None
    cur, be = stop, False
    for j in range(i + 1, len(day)):
        if day.High.iat[j] >= cur: return e, cur, (e - cur) / risk, "BE" if be else "stop", day.index[j]
        if not be and day.Low.iat[j] <= e - 2 * risk: cur, be = e, True
        if day.index[j].strftime("%H:%M") == "15:10": return e, day.Close.iat[j], (e - day.Close.iat[j]) / risk, "time", day.index[j]
    return e, day.Close.iat[-1], (e - day.Close.iat[-1]) / risk, "time", day.index[-1]


def one(t):
    try:
        m = read5_official(t)
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    except Exception:
        return []
    d = d[~d.index.duplicated()]
    d["e8"] = d.Close.ewm(span=8, adjust=False).mean()
    m["to"] = m.Close * m.Volume; m["day"] = m.index.normalize()
    med5 = m.groupby("day").to.median()
    out = []
    for day_ts, day in m.groupby("day"):
        if day_ts not in d.index or day.index[0].strftime("%H:%M") != "09:15": continue
        k = d.index.get_loc(day_ts)
        if k < 1: continue
        p = d.iloc[k - 1]; H, L, C = p.High, p.Low, p.Close
        PP = (H + L + C) / 3; R1 = 2 * PP - L; R2 = PP + H - L
        prior = med5[med5.index < day_ts].tail(5)
        if len(prior) < 3 or prior.median() < LIQ or day.Open.iat[0] < 100: continue
        if abs(R1 / day.Open.iat[0] - 1) > 0.10: continue          # split / bad-data guard
        hm = day.index.strftime("%H:%M")
        tp = (day.High + day.Low + day.Close) / 3
        vwap = ((tp * day.Volume).cumsum() / day.Volume.cumsum().replace(0, np.nan)).values
        c915 = day.Close.iat[0]
        levels = {"h915": day.High.iat[0], "R1": R1, "R2": R2, "d8": p.e8, "yH": H, "yC": C}
        for name, lv in levels.items():
            if not lv > c915: continue
            thr = lv * (1 - TOUCH)
            if name != "h915" and day.High.iat[0] >= thr: continue     # first touch was the 09:15 bar
            for i in range(1, len(day)):
                if hm[i] > "14:55": break
                if day.High.iat[i] >= thr:
                    if day.Close.iat[i] < lv and day.Close.iat[i] < day.Open.iat[i] and bucket(hm[i]):
                        stack = [n for n, x in levels.items() if n != name and abs(x / lv - 1) <= STACK]
                        stop = day.High.iat[i] * (1 + STOP_BUF)
                        base = dict(t=t, date=day_ts.date(), level_kind=name, poke_bar=hm[i], bucket=bucket(hm[i]),
                                    stacked=bool(stack), stack_with="+".join(stack), level=round(lv, 2),
                                    poke=day.High.iat[i], stop=round(stop, 2))
                        s = simulate(day, i, stop)
                        if s: out.append(dict(base, entry_type="A", entry_bar=hm[i], entry=s[0], exit=round(s[1], 2), R=s[2],
                                              how=s[3], exit_t=s[4].strftime("%H:%M")))
                        for j in range(i + 1, min(i + 1 + B_WAIT, len(day))):
                            if day.High.iat[j] >= stop or hm[j] > "14:55": break
                            if day.Close.iat[j] < vwap[j] and day.Close.iat[j] < lv:
                                s = simulate(day, j, stop)
                                if s: out.append(dict(base, entry_type="B", entry_bar=hm[j], entry=s[0], exit=round(s[1], 2),
                                                      R=s[2], how=s[3], exit_t=s[4].strftime("%H:%M")))
                                break
                    break
    return out


def summary(g):
    risk_rs = 1000.0
    cost = 85 * (risk_rs / (g.stop - g.entry)) * g.entry / 1e5
    net = risk_rs * g.R - cost
    daily = net.groupby(g.date).sum().sort_values()
    eq = net.cumsum(); dd = (eq - eq.cummax()).min()
    streak = (g.R <= 0).astype(int).groupby((g.R > 0).cumsum()).sum().max()
    return pd.Series(dict(n=len(g), win=f"{(g.R > 0).mean() * 100:.0f}%", avgR=round(g.R.mean(), 2),
                          net_per_trade=round(net.mean()), net_total=round(net.sum()),
                          wo_top5_days=round(daily.iloc[:-5].sum()) if len(daily) > 5 else np.nan,
                          maxDD=round(dd), worst_streak=int(streak)))


if __name__ == "__main__":
    tick = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pool:
        res = []
        for n, r in enumerate(pool.imap_unordered(one, tick, chunksize=20), 1):
            res += r
            if n % 300 == 0: print(f"{n}/{len(tick)}", flush=True)
    ev = pd.DataFrame(res).sort_values(["date", "entry_bar"]).reset_index(drop=True)
    lst = pd.read_csv(HERE / "orb_list_history.csv", parse_dates=["date"])
    last_list = lst.date.max().date()
    keys = set(zip(lst.date.dt.date, lst.ticker))
    ev["inplay"] = [("NA" if dt > last_list else ("Y" if (dt, t) in keys else "N")) for dt, t in zip(ev.date, ev.t)]
    ev.to_csv(HERE / "level_poke_reject_events.csv", index=False)
    print("events", len(ev), "dates", ev.date.min(), ev.date.max(), "in-play list up to", last_list)
    pd.set_option("display.width", 220)
    # dedup: one trade per stock-day-entry bar (stacked pokes hit several levels with the same bar)
    dd_ = ev.drop_duplicates(["t", "date", "entry_type", "entry_bar"])
    print("\nALL (deduped by stock-bar)"); print(dd_.groupby("entry_type").apply(summary).to_string())
    print("\nBY LEVEL x ENTRY"); print(ev.groupby(["entry_type", "level_kind"]).apply(summary).to_string())
    print("\nSTACKED vs SINGLE (deduped)"); print(dd_.groupby(["entry_type", "stacked"]).apply(summary).to_string())
    print("\nBY TIME BUCKET (deduped)"); print(dd_.groupby(["entry_type", "bucket"]).apply(summary).to_string())
    print("\nIN-PLAY LIST (deduped)"); print(dd_.groupby(["entry_type", "inplay"]).apply(summary).to_string())
    print("\nBY MONTH (deduped)"); print(dd_.groupby(["entry_type", pd.to_datetime(dd_.date).dt.to_period("M")]).apply(summary).to_string())
    # check vs 255
    old = HERE / "r1_poke_fade_events.csv"
    if old.exists():
        o = pd.read_csv(old); o = o[(o.kind == "R1") & (o.entry < o.bar_open)]
        n = ev[(ev.level_kind == "R1") & (ev.entry_type == "A")]
        print(f"\nCHECK vs 255 red R1: 255 n={len(o)} avgR={o.R.mean():.3f} | 257 n={len(n)} avgR={n.R.mean():.3f}")
