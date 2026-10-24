"""Nifty EMA level BLIND TOUCH short, held to the next support, can run over days (2026-10-23, user; RESULTS ONLY).
263 only counted touches that had ALREADY rejected for a full hour (red close under the level) -- a confirmed population that
drops every touch that broke through. Here EVERY first touch from below counts, entry at the level the moment it trades:
  levels: daily 8 / daily 34 (yesterday's values), 1H EMA8 / 1H EMA34 (previous hourly bar's value);
  touch : first hourly bar of the day per level that OPENS under the level and whose high reaches it -> sell AT the level.
  stop  : level + 0.3% (no candle high exists yet at entry).
  target: nearest support >= 0.2% under the level, booked 0.05% in front (supports as 263, minus today's low before the touch
          bar is included, the touch bar's own low is not).
Entry bar (5-min order unknown): high >= stop -> stopped (worst case); else target only if the bar CLOSES at/under it (then it
must have traded after the touch); else walk on. Later bars as 263: opens through stop / target exit at the open, a bar
touching both = stop, up to the close of the 5th trading day."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INDEX_INTRADAY_DIR

STOPP, GAP, FRONT, STACK, MAXD = 0.003, 0.002, 0.0005, 0.0015, 5
h = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0)
h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
h = h[~h.index.duplicated()].sort_index()
h["h8"] = h.Close.ewm(span=8, adjust=False).mean().shift(1)
h["h34"] = h.Close.ewm(span=34, adjust=False).mean().shift(1)
d = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True)
d = d[~d.index.duplicated()].sort_index()
for s in (8, 21, 34, 50): d[f"d{s}"] = d.Close.ewm(span=s, adjust=False).mean().shift(1)
d["yH"], d["yL"], d["yC"] = d.High.shift(1), d.Low.shift(1), d.Close.shift(1)
d["low5"] = d.Low.shift(1).rolling(5).min()
d["above200"] = (d.Close > d.Close.rolling(200).mean()).shift(1)
e20 = d.Close.ewm(span=20, adjust=False).mean(); d["up20"] = (e20 > e20.shift(5)).shift(1)
days = sorted(set(h.index.normalize())); pos = {dd: i for i, dd in enumerate(days)}
H = h.reset_index(); H = H.rename(columns={H.columns[0]: "ts"}); H["day"] = H.ts.dt.normalize()


def run(STOPP=STOPP, GAP=GAP):
    ev = []
    for day, g in H.groupby("day"):
        if day not in d.index or len(g) < 6: continue
        dr = d.loc[day]
        if pd.isna(dr.d50) or pd.isna(dr.above200) or pd.isna(dr.low5): continue
        PP = (dr.yH + dr.yL + dr.yC) / 3
        fixed = [dr.yL, dr.yC, PP, 2 * PP - dr.yH, PP - (dr.yH - dr.yL), dr.d8, dr.d21, dr.d34, dr.d50, dr.low5]
        k = pos[day]; last_day = days[min(k + MAXD, len(days) - 1)]
        rows = g.index.tolist()
        for kind in ("d8", "d34", "h8", "h34"):
            for ii, ri in enumerate(rows[:-1]):
                b = H.loc[ri]
                L = dr[kind] if kind[0] == "d" else b[kind]
                if not (b.Open < L and b.High >= L): continue
                e = L; stop = L * (1 + STOPP); risk = stop - e
                stacked = sum(abs(x / L - 1) <= STACK for x in [dr.d8, dr.d34, b.h8, b.h34]) >= 2
                lowsofar = H.loc[rows[:ii]].Low.min() if ii else np.nan
                sup = [x for x in fixed + [b.h8, b.h34, lowsofar] if x == x and x <= e * (1 - GAP)]
                if not sup: break
                tgt = max(sup) * (1 + FRONT)
                if b.High >= stop: res = (stop, "stop", day)
                elif b.Close <= tgt: res = (tgt, "target", day)
                else:
                    res = None
                    for _, w in H[(H.index > ri) & (H.day <= last_day)].iterrows():
                        if w.Open >= stop: res = (w.Open, "stop-gap", w.day); break
                        if w.Open <= tgt: res = (w.Open, "target-gap", w.day); break
                        if w.High >= stop: res = (stop, "stop", w.day); break
                        if w.Low <= tgt: res = (tgt, "target", w.day); break
                    if res is None:
                        ww = H[(H.index > ri) & (H.day <= last_day)]
                        if not len(ww): break
                        res = (ww.Close.iat[-1], "time", ww.day.iat[-1])
                px, how, xd = res
                ev.append(dict(date=day.date(), year=day.year, above200=bool(dr.above200), up20=bool(dr.up20), level=kind,
                               hour=b.ts.strftime("%H:%M"), stacked=stacked, entry=e, stop=stop, target=tgt,
                               tgt_dist_pct=(e / tgt - 1) * 100, exit=px, how=how, days_held=pos[xd] - k,
                               red_close=bool(b.Close < L and b.Close < b.Open), pct=(e / px - 1) * 100, R=(e - px) / risk))
                break
    return pd.DataFrame(ev)


def S(x):
    return pd.Series(dict(n=len(x), tgt_dist=x.tgt_dist_pct.median(), target=x.how.str.startswith("target").mean() * 100,
                          stop=x.how.str.startswith("stop").mean() * 100, time=(x.how == "time").mean() * 100,
                          win=(x.R > 0).mean() * 100, avg_pct=x.pct.mean(), avgR=x.R.mean(),
                          overnight=(x.days_held > 0).mean() * 100)).round(2)


pd.set_option("display.width", 250)
E = run(); E.to_csv(Path(__file__).resolve().parent / "nifty_ema_blind_touch_events.csv", index=False)
print("BLIND TOUCH | stop 0.3%, target gap 0.2% | events", len(E), E.date.min(), "..", E.date.max())
print("touch candle later closed red under the level (= 263's population):", f"{E.red_close.mean() * 100:.0f}%")
print("\nALL"); print(S(E).to_frame().T.to_string(index=False))
for col in ("above200", "year", "up20", "level", "stacked", "hour", "red_close"):
    print(f"\nBY {col}"); print(E.groupby(col).apply(S).to_string())
print("\nLEVEL x 200d"); print(E.groupby(["level", "above200"]).apply(S).to_string())
for sp in (0.002, 0.005):
    X = run(STOPP=sp); print(f"\nROBUSTNESS stop {sp*100:.1f}% -- by 200d"); print(X.groupby("above200").apply(S).to_string())
print("\nLAST 12"); print(E.tail(12)[["date", "level", "hour", "entry", "stop", "target", "how", "exit", "days_held", "pct", "R"]].round(2).to_string(index=False))
