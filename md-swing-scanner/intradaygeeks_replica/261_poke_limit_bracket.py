"""Level poke -> sell limit 0.2% under a bar's open, WORST / BEST case bracket (2026-10-22, user's entry; RESULTS ONLY, nothing goes
to STRATEGY.md). User: I sell once the bar trades ~0.2% under its open (first-minute red, no confirmation); every bar that opens
under the level counts, its close / colour is never looked at; a stop over ~0.5% = no trade.

Levels / poke / 60-min window / > 0.3% close-above kill: as 258 / 259.
Entry:  the first bar in the window that opens under the level AND trades down to Open*(1-0.002) -> sell there.
Stop:   highest high from the poke to the bar before the entry bar + 0.05%; skip when > 0.5% above the fill.
Order inside the entry bar (5-min OHLC cannot tell):
  clean     High <= Open*1.001 -> it went down first; filled; the rest of the bar is after the fill.
  ambiguous High > Open*1.001 and Low reaches the fill:
     WORST  filled first, then the rally (stopped if High >= stop; a bar touching stop and target = stop).
     BEST   it went up first, the user saw green and skipped this bar (keeps watching the next bars).
Exit:   1% target, out at the 15:10 bar close; a bar touching both = stop. Cost ~Rs85 per Rs1 lakh, per Rs1k risk."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

HERE = Path(__file__).resolve().parent
TOUCH, STOP_BUF, LIQ, WAIT, KILL = 0.0005, 0.0005, 15e5, 12, 0.003
DIP, OPEN_HI, MAX_STOP, TGT = 0.002, 0.001, 0.005, 0.01
EDGES = ["09:20", "09:30", "09:40", "09:50", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00",
         "14:30", "15:00"]


def bucket(hm):
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        if a <= hm < b: return f"{a}-{b}"
    return None


def walk(day, j, e, stop):
    """Filled inside bar j at e (bar j's own High / Low count as after the fill)."""
    tgt = e * (1 - TGT); risk = stop - e
    if day.High.iat[j] >= stop: return stop, -1.0, "stop"
    if day.Low.iat[j] <= tgt: return tgt, (e - tgt) / risk, "target"
    for k in range(j + 1, len(day)):
        if day.High.iat[k] >= stop: return stop, -1.0, "stop"
        if day.Low.iat[k] <= tgt: return tgt, (e - tgt) / risk, "target"
        if day.index[k].strftime("%H:%M") == "15:10": return day.Close.iat[k], (e - day.Close.iat[k]) / risk, "time"
    return day.Close.iat[-1], (e - day.Close.iat[-1]) / risk, "time"


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
        O, Hi, Lo, Cl = (day[c].values for c in ("Open", "High", "Low", "Close"))
        levels = {"h915": Hi[0], "R1": R1, "R2": R2, "d8": p.e8, "yH": H, "yC": C}
        for name, lv in levels.items():
            if not lv > Cl[0]: continue
            thr = lv * (1 - TOUCH)
            if name != "h915" and Hi[0] >= thr: continue
            i = next((x for x in range(1, len(day)) if Hi[x] >= thr), None)
            if i is None or hm[i] > "14:55": continue
            base = dict(t=t, date=day_ts.date(), level_kind=name, poke_bar=hm[i])
            done = {"worst": False, "best": False}
            for j in range(i + 1, min(i + 1 + WAIT, len(day))):
                if hm[j] > "14:55" or all(done.values()): break
                if O[j] < lv and Lo[j] <= O[j] * (1 - DIP):
                    f = O[j] * (1 - DIP); stop = Hi[i:j].max() * (1 + STOP_BUF)
                    clean = Hi[j] <= O[j] * (1 + OPEN_HI)
                    if stop > f and (stop - f) / f <= MAX_STOP:
                        for case in ("worst", "best"):
                            if done[case] or (case == "best" and not clean): continue
                            done[case] = True
                            r = walk(day, j, f, stop)
                            out.append(dict(base, case=case, clean=clean, bar=hm[j], bucket=bucket(hm[j]), entry=f, stop=stop,
                                            exit=r[0], R=r[1], how=r[2]))
                    else:
                        done = {"worst": True, "best": True}          # stop too wide on the first fill = no trade
                if Cl[j] > lv * (1 + KILL): break
    return out


def summary(g):
    cost = 85 * (1000.0 / (g.stop - g.entry)) * g.entry / 1e5
    net = 1000.0 * g.R - cost
    daily = net.groupby(g.date).sum().sort_values()
    eq = net.cumsum(); dd = (eq - eq.cummax()).min()
    streak = (g.R <= 0).astype(int).groupby((g.R > 0).cumsum()).sum().max()
    return pd.Series(dict(n=len(g), clean=f"{g.clean.mean() * 100:.0f}%", win=f"{(g.R > 0).mean() * 100:.0f}%",
                          tgt_hit=f"{(g.how == 'target').mean() * 100:.0f}%", avgR=round(g.R.mean(), 2),
                          stop_pct=round(((g.stop - g.entry) / g.entry * 100).median(), 2), net_per_trade=round(net.mean()),
                          wo_top5_days=round(daily.iloc[:-5].sum()) if len(daily) > 5 else np.nan,
                          maxDD=round(dd), worst_streak=int(streak)))


if __name__ == "__main__":
    tick = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pool:
        res = []
        for n, r in enumerate(pool.imap_unordered(one, tick, chunksize=20), 1):
            res += r
            if n % 500 == 0: print(f"{n}/{len(tick)}", flush=True)
    ev = pd.DataFrame(res).sort_values(["date", "bar"]).reset_index(drop=True)
    lst = pd.read_csv(HERE / "orb_list_history.csv", parse_dates=["date"])
    keys = set(zip(lst.date.dt.date, lst.ticker))
    ev["inplay"] = [(dt, t) in keys for dt, t in zip(ev.date, ev.t)]
    ev.to_csv(HERE / "poke_limit_bracket_events.csv", index=False)
    dd_ = ev.drop_duplicates(["t", "date", "case", "bar"])
    print("trades", len(dd_), "dates", ev.date.min(), ev.date.max())
    pd.set_option("display.width", 220)
    print("\nALL"); print(dd_.groupby("case").apply(summary).to_string())
    print("\nIN-PLAY LIST"); print(dd_[dd_.inplay].groupby("case").apply(summary).to_string())
    print("\nBY TIME (entry bar)"); print(dd_.groupby(["case", "bucket"]).apply(summary).to_string())
    print("\nIN-PLAY BY TIME"); print(dd_[dd_.inplay].groupby(["case", "bucket"]).apply(summary).to_string())
    print("\nBY MONTH"); print(dd_.groupby(["case", pd.to_datetime(dd_.date).dt.to_period("M")]).apply(summary).to_string())
    chk = ev[(ev.date == pd.Timestamp("2026-10-21").date()) & ev.t.isin(["TCS", "INFY"])]
    print("\nCHECK"); print(chk[["t", "level_kind", "case", "clean", "bar", "entry", "stop", "exit", "how", "R"]].round(2).to_string(index=False))
