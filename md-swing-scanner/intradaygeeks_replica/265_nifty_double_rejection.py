"""Nifty DOUBLE rejection (2026-10-23, user's own level list; RESULTS ONLY). Levels (user): EMA 8 / 34 on hourly (previous bar),
daily (yesterday's value) and weekly (last completed week's value), + daily pivots PP / R1 / R2 / S1 / S2.
Zone:   an hourly candle that OPENS under level L1 (the nearest of the user's levels above the open) and whose high goes
        through L1 AND reaches a second level L2 within 0.4% above L1 ("reached" = within 0.1%). First such candle per day.
Entry A (blind at the upper level): sell at L2 - 0.1% the moment it trades; stop L2 + 0.2%.
Entry B (confirmed, late): the same candle closes RED back under L1 -> sell at its close; stop = candle high + 0.05%.
Target: in front (0.05%) of the next user level at least 0.2% under the entry. Entry bar: stop first; target only if the bar
closes at / under it. Later bars: gaps exit at the open, both touched = stop; up to the close of the 5th trading day."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from data.paths import DAILY_DIR, INDEX_INTRADAY_DIR

ZONE, REACH, GAP, FRONT, MAXD = 0.004, 0.001, 0.002, 0.0005, 5
h = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv", index_col=0)
h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
h = h[~h.index.duplicated()].sort_index()
h["h8"] = h.Close.ewm(span=8, adjust=False).mean().shift(1)
h["h34"] = h.Close.ewm(span=34, adjust=False).mean().shift(1)
d = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True)
d = d[~d.index.duplicated()].sort_index()
for s in (8, 34): d[f"d{s}"] = d.Close.ewm(span=s, adjust=False).mean().shift(1)
wk = d.Close.resample("W-FRI").last().dropna()
for s in (8, 34):
    we = wk.ewm(span=s, adjust=False).mean()
    d[f"w{s}"] = [we[we.index < day - pd.Timedelta(days=day.weekday())].iloc[-1] if (we.index < day - pd.Timedelta(days=day.weekday())).any() else np.nan for day in d.index]
yH, yL, yC = d.High.shift(1), d.Low.shift(1), d.Close.shift(1); PP = (yH + yL + yC) / 3
d["PP"], d["R1"], d["R2"], d["S1"], d["S2"] = PP, 2 * PP - yL, PP + (yH - yL), 2 * PP - yH, PP - (yH - yL)
d["above200"] = (d.Close > d.Close.rolling(200).mean()).shift(1)
days = sorted(set(h.index.normalize())); pos = {dd: i for i, dd in enumerate(days)}
H = h.reset_index(); H = H.rename(columns={H.columns[0]: "ts"}); H["day"] = H.ts.dt.normalize()
DL = ["d8", "d34", "w8", "w34", "PP", "R1", "R2", "S1", "S2"]


def walk(ri, e, stop, tgt, last_day, b, entry_bar):
    if entry_bar:
        if b.High >= stop: return stop, "stop", b.day
        if b.Close <= tgt: return tgt, "target", b.day
    ww = H[(H.index > ri) & (H.day <= last_day)]
    for _, w in ww.iterrows():
        if w.Open >= stop: return w.Open, "stop-gap", w.day
        if w.Open <= tgt: return w.Open, "target-gap", w.day
        if w.High >= stop: return stop, "stop", w.day
        if w.Low <= tgt: return tgt, "target", w.day
    return (ww.Close.iat[-1], "time", ww.day.iat[-1]) if len(ww) else None


ev = []
for day, g in H.groupby("day"):
    if day not in d.index or len(g) < 6: continue
    dr = d.loc[day]
    if dr[DL].isna().any() or pd.isna(dr.above200): continue
    k = pos[day]; last_day = days[min(k + MAXD, len(days) - 1)]
    for ri in g.index.tolist()[:-1]:
        b = H.loc[ri]
        lv = {n: dr[n] for n in DL}; lv["h8"], lv["h34"] = b.h8, b.h34
        above = sorted((v, n) for n, v in lv.items() if v > b.Open)
        if len(above) < 2: continue
        L1, n1 = above[0]
        if b.High < L1: continue
        cand = [(v, n) for v, n in above[1:] if v <= L1 * (1 + ZONE) and b.High >= v * (1 - REACH)]
        if not cand: continue
        L2, n2 = max(cand)
        base = dict(date=day.date(), year=day.year, above200=bool(dr.above200), hour=b.ts.strftime("%H:%M"),
                    pair=f"{n1}+{n2}", weekly=("w" in n1 + n2), zone_pct=(L2 / L1 - 1) * 100)
        allv = [v for v in lv.values()]
        for ver, e, stop in (("A_blind_upper", L2 * (1 - REACH), L2 * 1.002),
                             ("B_red_close", b.Close, b.High * 1.0005)):
            if ver == "B_red_close" and not (b.Close < L1 and b.Close < b.Open): continue
            sup = [v for v in allv if v <= e * (1 - GAP)]
            if not sup: continue
            tgt = max(sup) * (1 + FRONT)
            r = walk(ri, e, stop, tgt, last_day, b, entry_bar=(ver == "A_blind_upper"))
            if r is None: continue
            px, how, xd = r
            ev.append(dict(base, ver=ver, entry=e, stop=stop, target=tgt, risk_pct=(stop / e - 1) * 100,
                           tgt_pct=(e / tgt - 1) * 100, exit=px, how=how, days_held=pos[xd] - k,
                           pct=(e / px - 1) * 100, R=(e - px) / (stop - e)))
        break                                              # first double-reach candle of the day only
E = pd.DataFrame(ev); E.to_csv(Path(__file__).resolve().parent / "nifty_double_rejection_events.csv", index=False)


def S(x):
    return pd.Series(dict(n=len(x), stop_pct=x.risk_pct.median(), tgt_pct=x.tgt_pct.median(),
                          win=(x.R > 0).mean() * 100, avg_pct=x.pct.mean(), avgR=x.R.mean(),
                          avg_win_R=x.R[x.R > 0].mean(), overnight=(x.days_held > 0).mean() * 100)).round(2)


pd.set_option("display.width", 250)
print("days with a double reach:", E.date.nunique(), "|", E.date.min(), "..", E.date.max())
for col in (None, "above200", "year", "weekly", "hour"):
    print(f"\n{'ALL' if col is None else 'BY ' + col}")
    print((E.groupby("ver") if col is None else E.groupby(["ver", col])).apply(S).to_string())
print("\nTOP PAIRS (A)"); print(E[E.ver == "A_blind_upper"].groupby("pair").apply(S).sort_values("n", ascending=False).head(8).to_string())
print("\n2026-10-19 / 10-21 / 10-22 / 10-23"); print(E[E.date.astype(str).isin(["2026-10-19", "2026-10-21", "2026-10-22", "2026-10-23"])][["date", "hour", "pair", "ver", "entry", "stop", "target", "how", "exit", "pct", "R"]].round(2).to_string(index=False))
