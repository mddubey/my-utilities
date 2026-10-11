"""CONFIRMATION entries for the in-play ORB, SHORTS and LONGS (user, 2026-10-11: 'very immature entry -- any confirmation?'; spec
fixed before running). Population: 175's in-play stock-days (relvol >= 1, top 20/day), side from the 09:15 candle (red -> short below
its low, green -> long above its high), 5-min bars 2026-06-24..10-08. Entries:
  C0 stop order at the level (touch; 175's mid entry-bar rule) | C1 first 5-min CLOSE beyond the level, enter at that close |
  C2 TWO consecutive closes beyond, enter at the 2nd | C3 = C1 and that breakout candle's volume >= 1.5x the stock's median 5-min
  volume yesterday (else no trade) | C4 = C1 and the entry is on the right side of VWAP (09:15 volume = day - other bars) (else no
  trade) | C5 15-min range (09:15-09:29), stop order at its low/high from 09:30.
  Each also with the user's 09:30 RULE: skip the stock if the level was first touched before 09:30 (C5 is from 09:30 by design).
Stops 10% / 20% of daily ATR from the actual entry; no target; out at the 15:15 bar's open (14:15 also). Close-based entries are walked
from the next bar. PASS = beats C0 (same side, same 09:30 setting) on Rs @1k net in BOTH halves (2026-06-24..08-14 / 08-17..10-08)
AND w/o the top-10 days. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR, DAILY_DIR

A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()


def walk(d, k_after, e, side, sp, exit_hm, entry_bar=None, lvl=None):
    stp = e * (1 - side * sp / 100)
    if entry_bar is not None:   # touch entry: 175's mid rule for the entry bar
        b0 = entry_bar; fo = (b0.Open <= lvl) if side < 0 else (b0.Open >= lvl)
        touch = (b0.High >= stp) if side < 0 else (b0.Low <= stp); cb = (b0.Close >= stp) if side < 0 else (b0.Close <= stp)
        if (fo and touch) or cb: return stp, "stop"
    for _, b in d[d.index > k_after].iterrows():
        if b.hm >= exit_hm: return b.Open, "close"
        if (b.High >= stp) if side < 0 else (b.Low <= stp): return stp, "stop"
    return d.Close.iloc[-1], "close"


rows, t0 = [], time.time()
for n, (t, g) in enumerate(P.groupby("ticker"), 1):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m["hm"] = m.index.strftime("%H:%M"); m["day"] = m.index.normalize()
    dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    medv = m[m.Volume > 0].groupby("day").Volume.median().shift(1)
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.day == dd]
        if len(d) < 70 or d.hm.iloc[0] != "09:15": continue
        side = int(r.side); f = d.iloc[0]; lvl = f.Low if side < 0 else f.High
        v = d.Volume.values.astype(float); v[0] = dv.get(dd, np.nan) - v[1:].sum()
        vw = pd.Series(np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v), index=d.index)
        after = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        beyond_low = (after.Low < lvl) if side < 0 else (after.High > lvl)
        beyond_close = (after.Close < lvl) if side < 0 else (after.Close > lvl)
        touch_hm = after[beyond_low].hm.iloc[0] if beyond_low.any() else None
        late = touch_hm is not None and touch_hm >= "09:30"
        ent = {}
        if touch_hm:
            k = after[beyond_low].index[0]; b0 = d.loc[k]; ent["C0"] = (k, min(lvl, b0.Open) if side < 0 else max(lvl, b0.Open), b0)
        if beyond_close.any():
            k = after[beyond_close].index[0]; c = d.loc[k]; ent["C1"] = (k, c.Close, None)
            if c.Volume >= 1.5 * medv.get(dd, np.inf): ent["C3"] = (k, c.Close, None)
            if (c.Close < vw[k]) if side < 0 else (c.Close > vw[k]): ent["C4"] = (k, c.Close, None)
            bc = beyond_close.values
            for i in range(1, len(bc)):
                if bc[i] and bc[i - 1]: k2 = after.index[i]; ent["C2"] = (k2, d.loc[k2].Close, None); break
        r15 = d[d.hm < "09:30"]; l15 = r15.Low.min() if side < 0 else r15.High.max(); a15 = d[(d.hm >= "09:30") & (d.hm < "15:15")]
        h15 = a15[(a15.Low < l15) if side < 0 else (a15.High > l15)]
        if len(h15): k = h15.index[0]; b0 = d.loc[k]; ent["C5"] = (k, min(l15, b0.Open) if side < 0 else max(l15, b0.Open), b0, l15)
        for c, val in ent.items():
            k, e, b0 = val[0], val[1], val[2]; lv = val[3] if c == "C5" else lvl
            rec = dict(ticker=t, date=r.date, mon=r.date[:7], side=side, ver=c, late=late if c != "C5" else True, et=d.loc[k].hm)
            for sm in (0.1, 0.2):
                sp = sm * r.atr; pos = 1000 / (sp / 100)
                for xh in ("14:15", "15:15"):
                    if d.loc[k].hm >= xh: rec[f"R{int(sm*100)}_{xh}"] = np.nan; rec[f"k{int(sm*100)}_{xh}"] = np.nan; continue
                    px, o = walk(d, k, e, side, sp, xh, b0, lv)
                    ret = side * (px - e) / e * 100; rec[f"R{int(sm*100)}_{xh}"] = ret / sp; rec[f"k{int(sm*100)}_{xh}"] = ret / 100 * pos - 85 * pos / 1e5
                    rec[f"o{int(sm*100)}_{xh}"] = o
            rows.append(rec)
    if n % 100 == 0: print(f"  {n} stocks, {len(rows)} entries, {time.time()-t0:.0f}s", flush=True)
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_confirm.csv", index=False)
ND = P.date.nunique()


def stats(g, sm, xh):
    g = g[g[f"k{sm}_{xh}"].notna()]; k = g[f"k{sm}_{xh}"]; R = g[f"R{sm}_{xh}"]; w = R > 0
    byd = g.groupby("date")[f"k{sm}_{xh}"].sum().sort_values(ascending=False); wo = k[~g.date.isin(byd.head(10).index)].mean()
    h1, h2 = k[g.date <= "2026-08-14"].mean(), k[g.date >= "2026-08-17"].mean()
    return dict(n=len(g), days=g.date.nunique(), st=(g[f"o{sm}_{xh}"] == "stop").mean() * 100, win=w.mean() * 100, aw=R[w].mean(), al=R[~w].mean(),
                R=R.mean(), k=k.mean(), wo=wo, h1=h1, h2=h2)


NAMES = {"C0": "C0 touch (stop order)", "C1": "C1 5-min close beyond", "C2": "C2 two closes beyond", "C3": "C3 close + volume >= 1.5x",
         "C4": "C4 close + right side of VWAP", "C5": "C5 15-min range, from 09:30"}
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    for sm in ("10", "20"):
        for rule in (False, True):
            G = X[X.side == sd]
            if rule: G = G[G.late]
            print(f"\n## {sn}, stop {sm}% ATR, {'09:30 RULE (skip if touched before 09:30)' if rule else 'no 09:30 rule'}, exit 15:15 (14:15 in brackets)")
            print("| entry | trades | days | stopped | win % | avg win / loss R | avg R | Rs @1k net (14:15) | w/o top-10 days | half 1 / half 2 | PASS vs C0 |\n|---|---|---|---|---|---|---|---|---|---|---|")
            base = stats(G[G.ver == "C0"], sm, "15:15")
            for c in ("C0", "C1", "C2", "C3", "C4", "C5"):
                if rule and c == "C5": continue
                gg = G[G.ver == c]
                if len(gg) == 0: continue
                s = stats(gg, sm, "15:15"); s14 = stats(gg, sm, "14:15")
                ok = "" if c == "C0" else ("PASS" if (s["h1"] > base["h1"] and s["h2"] > base["h2"] and s["wo"] > base["wo"]) else "no")
                print(f"| {NAMES[c]} | {s['n']} | {s['days']} | {s['st']:.0f}% | {s['win']:.0f}% | {s['aw']:+.1f} / {s['al']:+.2f} | {s['R']:+.2f} | {s['k']:+.0f} ({s14['k']:+.0f}) | {s['wo']:+.0f} | {s['h1']:+.0f} / {s['h2']:+.0f} | {ok} |")
