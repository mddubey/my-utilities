"""How often a poke of a level is followed by a red bar going down, and how far it goes -- by time of day (2026-10-22, user;
DESCRIPTIVE ONLY, no entries / costs; nothing goes to STRATEGY.md). User's idea: the morning is the unstable session where the
big drops happen; the afternoon is calmer / choppier.

Levels / poke: as 258 (09:15 high, R1, R2, daily 8, yesterday's high / close, above the 09:15 close; first touch from 09:20).
Stacked levels poked by the same bar count once (one row per stock-day-poke bar).
Window: the 12 bars (60 min) after the poke bar.
Red bar: first bar in the window with Close < Open and Close under the level ('any red').
Overwhelming red: as 258 (red from its open: High <= Open*1.001; body >= 60% of range; range >= the day's average from 09:20).
How far: from the red bar's OPEN to the lowest Low before price trades above the highest high so far + 0.05% (or 15:10).
Buckets by poke time: 10 min from 09:20 to 10:00, then 30 min. Pokes after ~14:10 have less than a full hour / day left."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

HERE = Path(__file__).resolve().parent
TOUCH, STOP_BUF, LIQ, WAIT, OPEN_HI, BODY = 0.0005, 0.0005, 15e5, 12, 0.001, 0.60
EDGES = ["09:20", "09:30", "09:40", "09:50", "10:00", "10:30", "11:00", "11:30", "12:00", "12:30", "13:00", "13:30", "14:00",
         "14:30", "15:00"]


def bucket(hm):
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        if a <= hm < b: return f"{a}-{b}"
    return None


def run_down(day, j, stop):
    """From bar j's open: lowest low before a High >= stop (or 15:10). Returns (drop %, minutes to the low)."""
    o = day.Open.iat[j]; lo, lo_k = day.Low.iat[j], j
    if day.High.iat[j] >= stop: return (o - lo) / o * 100, 0      # stopped inside the bar; order unknown, low counted
    for k in range(j + 1, len(day)):
        if day.High.iat[k] >= stop: break
        if day.Low.iat[k] < lo: lo, lo_k = day.Low.iat[k], k
        if day.index[k].strftime("%H:%M") == "15:10": break
    return (o - lo) / o * 100, (lo_k - j) * 5


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
        rng = Hi - Lo
        levels = {"h915": Hi[0], "R1": R1, "R2": R2, "d8": p.e8, "yH": H, "yC": C}
        seen = set()
        for name, lv in sorted(levels.items(), key=lambda x: x[1]):
            if not lv > Cl[0]: continue
            thr = lv * (1 - TOUCH)
            if name != "h915" and Hi[0] >= thr: continue
            i = next((x for x in range(1, len(day)) if Hi[x] >= thr), None)
            if i is None or not bucket(hm[i]) or i in seen: continue
            seen.add(i)                                            # stacked levels poked by one bar = one row
            row = dict(t=t, date=day_ts.date(), level_kind=name, poke_bar=hm[i], bucket=bucket(hm[i]))
            hh = Hi[i]
            for j in range(i + 1, min(i + 1 + WAIT, len(day))):
                hh = max(hh, Hi[j]) if "any_bar" in row else hh
                if Cl[j] < O[j] and Cl[j] < lv:
                    if "any_bar" not in row:
                        hh_any = max(Hi[i:j + 1]); dp, mins = run_down(day, j, hh_any * (1 + STOP_BUF))
                        row.update(any_bar=hm[j], any_drop=dp, any_mins=mins)
                    if Hi[j] <= O[j] * (1 + OPEN_HI) and (O[j] - Cl[j]) >= BODY * rng[j] and rng[j] >= rng[1:j].mean():
                        hh_ow = max(Hi[i:j + 1]); dp, mins = run_down(day, j, hh_ow * (1 + STOP_BUF))
                        row.update(ow_bar=hm[j], ow_drop=dp, ow_mins=mins)
                        break
            out.append(row)
    return out


def table(ev, kind):
    rows = []
    for b, g in ev.groupby("bucket"):
        x = g[f"{kind}_drop"].dropna()
        rows.append(dict(poke_time=b, pokes=len(g), red_bar=f"{len(x) / len(g) * 100:.0f}%",
                         median_drop=f"{x.median():.2f}%", **{f">={c}%": f"{(x >= c).mean() * 100:.0f}%" for c in (0.5, 1, 1.5, 2)},
                         med_mins_to_low=int(g[f"{kind}_mins"].dropna().median())))
    return pd.DataFrame(rows).to_string(index=False)


if __name__ == "__main__":
    tick = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pool:
        res = []
        for n, r in enumerate(pool.imap_unordered(one, tick, chunksize=20), 1):
            res += r
            if n % 500 == 0: print(f"{n}/{len(tick)}", flush=True)
    ev = pd.DataFrame(res).sort_values(["date", "poke_bar"]).reset_index(drop=True)
    lst = pd.read_csv(HERE / "orb_list_history.csv", parse_dates=["date"])
    keys = set(zip(lst.date.dt.date, lst.ticker))
    ev["inplay"] = [(dt, t) in keys for dt, t in zip(ev.date, ev.t)]
    ev.to_csv(HERE / "poke_redbar_frequency_events.csv", index=False)
    print("pokes", len(ev), "dates", ev.date.min(), ev.date.max())
    print("\nOVERWHELMING RED BAR (drop from its open)"); print(table(ev, "ow"))
    print("\nANY RED BAR closing under the level (drop from its open)"); print(table(ev, "any"))
    print("\nOVERWHELMING, IN-PLAY LIST ONLY"); print(table(ev[ev.inplay], "ow"))
    for t_, dt in (("INFY", "2026-10-21"), ("TCS", "2026-10-21")):
        print(ev[(ev.t == t_) & (ev.date == pd.Timestamp(dt).date())].to_string(index=False))
