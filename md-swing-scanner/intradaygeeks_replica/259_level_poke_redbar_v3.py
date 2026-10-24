"""Level poke -> overwhelming red bar, v3 (2026-10-22, user's entry / stop / target; RESULTS ONLY, nothing goes to STRATEGY.md).
User: I sell near the top of the red bar while it forms (limit; no fill = no trade), so the body middle is already the worse fill;
a stop wider than ~0.5% means I would not have entered there (INFY 10-21: R2 1169.4 is the line, 8 rupees under it is a miss).

Levels / poke / 60-min window / > 0.3% close-above kill / overwhelming red bar: as 258.
Entry A: the signal bar's body middle (Open + Close) / 2.
Entry B (honesty check, no look at the close): any bar in the window that opens under the level fills a sell limit at
         Open - half the day's average 5-min range (from 09:20) when its Low reaches it; one fill per level.
Stop S1: highest high since the poke + 0.05% (for B, the high before the fill bar; if the fill bar's High also reaches the stop,
         counted filled-then-stopped). Skip when the stop is > 0.5% above the entry.
Entry C (2026-10-22, user: "I enter in the first minute, no confirmation"): sell at the OPEN of the first bar in the window that
         opens under the level; nothing about that bar is looked at. Stop S1 (high before that bar + 0.05%, skip > 0.5%); everything
         inside the entry bar happens after the fill, so its High reaching the stop is a real stop. A bar touching both = stop.
Stop S2 (entry A only): entry + 0.5%, valid when the highest high + 0.05% is under it.
Exit:    1% target, out at the 15:10 bar close; a bar touching both stop and target counts the stop.
One a day: the first signal bar of the day across all stocks; ties on that bar averaged (= picking one at random).
Cost: ~Rs85 per Rs1 lakh, per Rs1k risk. Pass bar: net > 0 and > 0 without the top 5 days."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
from orb_common import read5_official

HERE = Path(__file__).resolve().parent
TOUCH, STOP_BUF, STACK, LIQ, WAIT = 0.0005, 0.0005, 0.003, 15e5, 12
KILL, OPEN_HI, BODY, MAX_STOP, TGT = 0.003, 0.001, 0.60, 0.005, 0.01
BUCKETS = [("09:20-09:45", "09:20", "09:40"), ("09:45-10:30", "09:45", "10:25"), ("10:30-12:00", "10:30", "11:55"),
           ("12:00-13:30", "12:00", "13:25"), ("13:30-15:00", "13:30", "14:55")]


def bucket(hm):
    for name, a, b in BUCKETS:
        if a <= hm <= b: return name
    return None


def walk(day, j, e, stop, in_bar_low):
    """Short filled inside bar j at e. 1% target, stop, out at 15:10. Returns (exit, R, how, time)."""
    tgt = e * (1 - TGT); risk = stop - e
    if in_bar_low <= tgt: return tgt, (e - tgt) / risk, "target", day.index[j]
    for k in range(j + 1, len(day)):
        if day.High.iat[k] >= stop: return stop, -1.0, "stop", day.index[k]
        if day.Low.iat[k] <= tgt: return tgt, (e - tgt) / risk, "target", day.index[k]
        if day.index[k].strftime("%H:%M") == "15:10": return day.Close.iat[k], (e - day.Close.iat[k]) / risk, "time", day.index[k]
    return day.Close.iat[-1], (e - day.Close.iat[-1]) / risk, "time", day.index[-1]


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
        for name, lv in levels.items():
            if not lv > Cl[0]: continue
            thr = lv * (1 - TOUCH)
            if name != "h915" and Hi[0] >= thr: continue
            i = next((x for x in range(1, len(day)) if Hi[x] >= thr), None)
            if i is None or hm[i] > "14:55": continue
            stack = [n for n, x in levels.items() if n != name and abs(x / lv - 1) <= STACK]
            base = dict(t=t, date=day_ts.date(), level_kind=name, poke_bar=hm[i], stacked=bool(stack), level=round(lv, 2))
            hh, got_a, got_b, got_c = Hi[i], False, False, False
            for j in range(i + 1, min(i + 1 + WAIT, len(day))):
                if hm[j] > "14:55" or (got_a and got_b and got_c): break
                hh_before = hh; hh = max(hh, Hi[j])
                avg = rng[1:j].mean()
                # C: sell the open of the first bar opening under the level
                if not got_c and O[j] < lv:
                    got_c = True; e = O[j]; stop = hh_before * (1 + STOP_BUF)
                    if stop > e and (stop - e) / e <= MAX_STOP:
                        if Hi[j] >= stop: r = (stop, -1.0, "stop", day.index[j])
                        else: r = walk(day, j, e, stop, Lo[j])
                        out.append(dict(base, entry_type="C", stop_kind="S1", bar=hm[j], bucket=bucket(hm[j]), entry=e,
                                        stop=stop, exit=r[0], R=r[1], how=r[2], exit_t=r[3].strftime("%H:%M")))
                # B: blind limit, no look at the bar's close
                if not got_b and O[j] < lv and avg > 0:
                    f = O[j] - 0.5 * avg; stop = hh_before * (1 + STOP_BUF)
                    if Lo[j] <= f and (stop - f) / f <= MAX_STOP and stop > f:
                        got_b = True
                        if Hi[j] >= stop: r = (f, -1.0, "stop", day.index[j])
                        else: r = walk(day, j, f, stop, Lo[j])
                        out.append(dict(base, entry_type="B", stop_kind="S1", bar=hm[j], bucket=bucket(hm[j]), entry=f,
                                        stop=stop, exit=r[0], R=r[1], how=r[2], exit_t=r[3].strftime("%H:%M")))
                if Cl[j] > lv * (1 + KILL): break
                # A: the overwhelming red bar, filled at its body middle
                if (not got_a and Cl[j] < O[j] and Hi[j] <= O[j] * (1 + OPEN_HI) and Cl[j] < lv and rng[j] > 0
                        and (O[j] - Cl[j]) >= BODY * rng[j] and rng[j] >= avg):
                    got_a = True; e = (O[j] + Cl[j]) / 2
                    for sk, stop in (("S1", hh * (1 + STOP_BUF)), ("S2", e * (1 + MAX_STOP))):
                        if (stop - e) / e > MAX_STOP + 1e-9 or hh * (1 + STOP_BUF) > stop + 1e-9: continue
                        r = walk(day, j, e, stop, Lo[j])
                        out.append(dict(base, entry_type="A", stop_kind=sk, bar=hm[j], bucket=bucket(hm[j]), entry=e,
                                        stop=stop, exit=r[0], R=r[1], how=r[2], exit_t=r[3].strftime("%H:%M")))
    return out


def net_of(g):
    cost = 85 * (1000.0 / (g.stop - g.entry)) * g.entry / 1e5
    return 1000.0 * g.R - cost


def summary(g, net=None):
    net = net_of(g) if net is None else net
    daily = net.groupby(g.date).sum().sort_values()
    eq = net.cumsum(); dd = (eq - eq.cummax()).min()
    streak = (g.R <= 0).astype(int).groupby((g.R > 0).cumsum()).sum().max()
    return pd.Series(dict(n=len(g), win=f"{(g.R > 0).mean() * 100:.0f}%", tgt_hit=f"{(g.how == 'target').mean() * 100:.0f}%",
                          avgR=round(g.R.mean(), 2), stop_pct=round(((g.stop - g.entry) / g.entry * 100).median(), 2),
                          net_per_trade=round(net.mean()), net_total=round(net.sum()),
                          wo_top5_days=round(daily.iloc[:-5].sum()) if len(daily) > 5 else np.nan,
                          maxDD=round(dd), worst_streak=int(streak)))


def one_a_day(g):
    g = g.assign(net=net_of(g))
    first = g[g.bar == g.groupby("date").bar.transform("min")]
    x = first.groupby("date").agg(R=("R", "mean"), net=("net", "mean"), stop=("stop", "first"), entry=("entry", "first"),
                                  how=("how", lambda s: s.mode().iat[0]), ties=("t", "size")).reset_index()
    return summary(x, x.net)


if __name__ == "__main__":
    tick = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as pool:
        res = []
        for n, r in enumerate(pool.imap_unordered(one, tick, chunksize=20), 1):
            res += r
            if n % 300 == 0: print(f"{n}/{len(tick)}", flush=True)
    ev = pd.DataFrame(res).sort_values(["date", "bar"]).reset_index(drop=True)
    ev["ver"] = ev.entry_type + "-" + ev.stop_kind
    lst = pd.read_csv(HERE / "orb_list_history.csv", parse_dates=["date"])
    keys = set(zip(lst.date.dt.date, lst.ticker)); last_list = lst.date.max().date()
    ev["inplay"] = [("NA" if dt > last_list else ("Y" if (dt, t) in keys else "N")) for dt, t in zip(ev.date, ev.t)]
    ev.to_csv(HERE / "level_poke_redbar_v3_events.csv", index=False)
    print("events", len(ev), "dates", ev.date.min(), ev.date.max())
    chk = ev[(ev.date == pd.Timestamp("2026-10-21").date()) & ev.t.isin(["TCS", "INFY"]) & (ev.level_kind == "R2")]
    print("\nCHECK TCS / INFY 2026-10-21 R2"); print(chk[["t", "ver", "bar", "entry", "stop", "exit", "exit_t", "how", "R"]].round(2).to_string(index=False))
    pd.set_option("display.width", 220)
    dd_ = ev.drop_duplicates(["t", "date", "ver", "bar"])
    recent = pd.to_datetime(dd_.date) >= "2026-10-17"
    hist = dd_[~recent]
    print("\nALL (deduped), to 10-16"); print(hist.groupby("ver").apply(summary).to_string())
    print("\nALL (deduped), 10-19..10-21"); print(dd_[recent].groupby("ver").apply(summary).to_string())
    print("\nONE A DAY, to 10-16"); print(hist.groupby("ver").apply(one_a_day).to_string())
    print("\nONE A DAY, 10-19..10-21"); print(dd_[recent].groupby("ver").apply(one_a_day).to_string())
    h = ev[pd.to_datetime(ev.date) < "2026-10-17"]
    print("\nBY LEVEL, to 10-16"); print(h.groupby(["ver", "level_kind"]).apply(summary).to_string())
    print("\nBY TIME, to 10-16 (deduped)"); print(hist.groupby(["ver", "bucket"]).apply(summary).to_string())
    print("\nIN-PLAY LIST, all dates (deduped)"); print(dd_.groupby(["ver", "inplay"]).apply(summary).to_string())
    print("\nIN-PLAY x TIME, entry C (deduped)"); print(dd_[dd_.entry_type == "C"].groupby(["inplay", "bucket"]).apply(summary).to_string())
    print("\nBY MONTH (deduped)"); print(dd_.groupby(["ver", pd.to_datetime(dd_.date).dt.to_period("M")]).apply(summary).to_string())
