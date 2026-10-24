"""Level poke, then an OVERWHELMING RED bar (2026-10-22, v2 of 257, spec agreed in chat; RESULTS ONLY, nothing goes to STRATEGY.md).
User: the poke candle can be any colour -- the sign is a later candle that starts red and keeps going (the TCS / INFY 2026-10-21 R2
rejections, which 257's 'first touch must be a red bar' rule missed).

Levels (only those above the 09:15 close): 09:15 high, R1, R2, daily 8 touch, yesterday's high, yesterday's close.
Poke:    first 5-min bar from 09:20 whose High >= level*(1-0.0005), any colour (for levels other than the 09:15 high: no event if
         the 09:15 bar already touched it).
Window:  the 12 bars (60 min) after the poke; repeat pokes allowed; dead if a bar closes > 0.3% above the level.
Signal:  first bar in the window that is red from its open (High <= Open*1.001), closes under the level, body >= 60% of its range,
         range >= the day's average 5-min range so far from 09:20 (the 09:15 bar left out -- with it, neither TCS nor INFY 10-21
         qualified; fixed before any results were looked at).
Entry:   the signal bar's close (the user enters intrabar, so this is later / conservative). Stop: highest high since the poke
         + 0.05%. Exit: package (a) -- stop to entry after +2R, out at the 15:10 bar close.
Universe / cost / pass bar: as 257 (>= Rs100, >= Rs15 lakh per 5-min bar, ~Rs85 per Rs1 lakh, net > 0 and > 0 without the top 5 days).
Check:   TCS 2026-10-21 (signal 09:50) and INFY 2026-10-21 (signal 09:25) must come out as R2 events."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

HERE = Path(__file__).resolve().parent
TOUCH, STOP_BUF, STACK, LIQ, WAIT = 0.0005, 0.0005, 0.003, 15e5, 12
KILL, OPEN_HI, BODY = 0.003, 0.001, 0.60
BUCKETS = [("09:20-09:45", "09:20", "09:40"), ("09:45-10:30", "09:45", "10:25"), ("10:30-12:00", "10:30", "11:55"),
           ("12:00-13:30", "12:00", "13:25"), ("13:30-15:00", "13:30", "14:55")]


def bucket(hm):
    for name, a, b in BUCKETS:
        if a <= hm <= b: return name
    return None


def simulate(day, i, stop):
    """Short at bar i's close, package (a), same as 255 / 257."""
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
        O, Hi, Lo, Cl, V = (day[c].values for c in ("Open", "High", "Low", "Close", "Volume"))
        rng = Hi - Lo
        c915 = Cl[0]
        levels = {"h915": Hi[0], "R1": R1, "R2": R2, "d8": p.e8, "yH": H, "yC": C}
        for name, lv in levels.items():
            if not lv > c915: continue
            thr = lv * (1 - TOUCH)
            if name != "h915" and Hi[0] >= thr: continue
            i = next((x for x in range(1, len(day)) if Hi[x] >= thr), None)
            if i is None or hm[i] > "14:55": continue
            hh = Hi[i]
            for j in range(i + 1, min(i + 1 + WAIT, len(day))):
                if hm[j] > "14:55": break
                hh = max(hh, Hi[j])
                if Cl[j] > lv * (1 + KILL): break
                if (Cl[j] < O[j] and Hi[j] <= O[j] * (1 + OPEN_HI) and Cl[j] < lv and rng[j] > 0
                        and (O[j] - Cl[j]) >= BODY * rng[j] and rng[j] >= rng[1:j].mean()):
                    stop = hh * (1 + STOP_BUF)
                    s = simulate(day, j, stop)
                    if s:
                        stack = [n for n, x in levels.items() if n != name and abs(x / lv - 1) <= STACK]
                        out.append(dict(t=t, date=day_ts.date(), level_kind=name, poke_bar=hm[i], sig_bar=hm[j],
                                        wait_bars=j - i, bucket=bucket(hm[j]), stacked=bool(stack), stack_with="+".join(stack),
                                        level=round(lv, 2), high_since=hh, stop=round(stop, 2), entry=s[0],
                                        vol_x=round(V[j] / max(V[1:j].mean(), 1), 2), exit=round(s[1], 2), R=s[2], how=s[3],
                                        exit_t=s[4].strftime("%H:%M")))
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
                          stop_pct=round(((g.stop - g.entry) / g.entry * 100).median(), 2),
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
    ev = pd.DataFrame(res).sort_values(["date", "sig_bar"]).reset_index(drop=True)
    lst = pd.read_csv(HERE / "orb_list_history.csv", parse_dates=["date"])
    last_list = lst.date.max().date()
    keys = set(zip(lst.date.dt.date, lst.ticker))
    ev["inplay"] = [("NA" if dt > last_list else ("Y" if (dt, t) in keys else "N")) for dt, t in zip(ev.date, ev.t)]
    ev.to_csv(HERE / "level_poke_redbar_events.csv", index=False)
    print("events", len(ev), "dates", ev.date.min(), ev.date.max(), "in-play list up to", last_list)
    chk = ev[(ev.date == pd.Timestamp("2026-10-21").date()) & ev.t.isin(["TCS", "INFY"])]
    print("\nCHECK TCS / INFY 2026-10-21"); print(chk[["t", "level_kind", "poke_bar", "sig_bar", "entry", "stop", "exit", "exit_t", "how", "R"]].to_string(index=False))
    pd.set_option("display.width", 220)
    dd_ = ev.drop_duplicates(["t", "date", "sig_bar"])
    recent = pd.to_datetime(dd_.date) >= "2026-10-17"
    print("\nALL (deduped by stock-bar), up to 2026-10-16 / last 3 sessions")
    print(dd_.groupby(recent.map({False: "to 10-16", True: "10-19..10-21"})).apply(summary).to_string())
    print("\nBY LEVEL"); print(ev.groupby("level_kind").apply(summary).to_string())
    print("\nBY TIME BUCKET (deduped)"); print(dd_.groupby("bucket").apply(summary).to_string())
    print("\nLEVEL x TIME (R1 / R2 / yH)"); print(ev[ev.level_kind.isin(["R1", "R2", "yH"])].groupby(["level_kind", "bucket"]).apply(summary).to_string())
    print("\nSTACKED vs SINGLE (deduped)"); print(dd_.groupby("stacked").apply(summary).to_string())
    print("\nIN-PLAY LIST (deduped)"); print(dd_.groupby("inplay").apply(summary).to_string())
    print("\nBY MONTH (deduped)"); print(dd_.groupby(pd.to_datetime(dd_.date).dt.to_period("M")).apply(summary).to_string())
