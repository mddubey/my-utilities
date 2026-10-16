"""MORNING POP-INTO-LEVEL REJECTION SHORT, three stops side by side (user, 2026-10-16: 'this morning day high short looks more
working than anything else ... but that spike thing needs to be controlled'). From the live log: RBLBANK / JSWSTEEL 1182 / CEAT /
ORIENTELEC worked, GRANULES' tight stop was spiked. Spec fixed before running:
  Data: 30m set (5-min bars, 2026-06..10). Universe: prev-day median 5-min turnover >= Rs15 lakh, prev close >= Rs100.
  Levels known at the open: daily PP/R1/R2, weekly PP/R1/R2, daily EMA8 (through yesterday), yesterday's high, and the DAY HIGH
    SO FAR (max high of the earlier bars today, live).
  SETUP (the rejection bar): a 5-min bar starting 09:20..10:30, previous close below the level (came from below), high >= level
    x (1 - 0.1%) (a near-touch counts), close < level, upper wick >= 1/3 of the range, and the bar's high >= 0.5% above the day's
    low so far (a pop, not a drift at the top). First setup per stock-day; several levels -> the one nearest the bar high.
    Stacked = another level within 0.3% of it.
  A  TIGHT:  short at the bar close, stop = bar high + 0.05%.
  B  ROOM:   same entry, stop = max(A's stop, level + 0.2 x daily ATR14%) (226's spike room, user's 0.2 ATR).
  C  SPIKE-FAIL: no entry on the rejection bar. Only if, by 11:00 and within 6 bars, price spikes ABOVE the rejection bar's high
     and a later bar closes back under the level -> short at that close, stop = highest high since the rejection bar + 0.05%.
  D  FAILED BREAKOUT (added after the hand check: ORIENTELEC 2026-10-16 closed ABOVE R1 / the day high at 09:30, so A-C, which
     need a close under the level, cannot see it): a bar 09:20..10:30 closes above a level (previous close below), and within the
     next 3 bars a bar closes back under it -> short at that close, stop = highest high since the breakout bar + 0.05%. First per
     stock-day, independent of A.
  Exits for all: 1% target, or 2R target (both shown), else out at the 15:15 close; stop first on a tie; no trailing.
  Report net Rs per Rs1 lakh (ret - 0.085%) and mean R. Splits: level type, stacked, in-play (top-20 by relvol = 09:15-09:25 volume / median
    of the previous 10 days' same window; Yahoo's 09:15 bar volume is 0, so the 09:15 bar alone cannot be used), gap (<= -2 / between / >= +2%), stock up > 3% from the open at the
    rejection bar (trend day), Nifty 20 min before entry, month, top-10 days removed.
  Hand checks: RBLBANK 2026-10-13, JSWSTEEL 2026-10-14, CEATLTD + GRANULES 2026-10-15, ORIENTELEC 2026-10-16."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
COST = 0.085; TICK = 0.0005; NEAR = 0.001; STACK = 0.003; KATR = 0.2
CHECKS = {("RBLBANK", "2026-10-13"), ("JSWSTEEL", "2026-10-14"), ("CEATLTD", "2026-10-15"), ("GRANULES", "2026-10-15"), ("ORIENTELEC", "2026-10-16")}


def daily_levels(t):
    d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index()
    d = d[~d.index.duplicated()].dropna(subset=["Close"])
    pp = (d.High + d.Low + d.Close) / 3
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    dl = pd.DataFrame({"dPP": pp, "dR1": 2 * pp - d.Low, "dR2": pp + d.High - d.Low, "D8": d.Close.ewm(span=8, adjust=False).mean(),
                       "yH": d.High, "pc": d.Close, "atr": tr.rolling(14).mean() / d.Close * 100}).shift(1)
    w = d.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    wp = (w.High + w.Low + w.Close) / 3
    wl = pd.DataFrame({"wPP": wp, "wR1": 2 * wp - w.Low, "wR2": wp + w.High - w.Low}); wl.index = wl.index + pd.Timedelta(days=1)
    return dl.join(wl.reindex(d.index, method="ffill"))


def walk(H, L, C, i0, e, stop, last, tg):
    for k in range(i0, last + 1):
        if H[k] >= stop: return (e - stop) / e * 100, "stop"
        if L[k] <= tg: return (e - tg) / e * 100, "target"
    return (e - C[last]) / e * 100, "time"


def trade(H, L, C, i0, e, stop, last):
    risk = (stop - e) / e * 100; out = {"risk": risk}
    for nm, tg in (("t1", e * 0.99), ("r2", e - 2 * (stop - e))):
        out[f"{nm}_ret"], out[f"{nm}_why"] = walk(H, L, C, i0, e, stop, last, tg)
    return out


def run(t):
    try: m = read5_official(t); lv = daily_levels(t)
    except Exception: return []
    md = m.index.normalize(); days = sorted(set(md)); out = []
    first = m[m.index.strftime("%H:%M") <= "09:25"].Volume.groupby(md[m.index.strftime("%H:%M") <= "09:25"]).sum()
    for a in range(1, len(days)):
        D, P = days[a], days[a - 1]
        if D not in lv.index: continue
        L0 = lv.loc[D]
        if not L0.pc == L0.pc or L0.pc < 100 or not L0.atr == L0.atr: continue
        pv = m[(md == P) & (m.Volume > 0)]
        if not len(pv) or (pv.Volume * pv.Close).median() < 15e5: continue
        g = m[md == D]; hm = g.index.strftime("%H:%M").values
        if len(g) < 60 and (t, D.strftime("%Y-%m-%d")) not in CHECKS: continue
        O, H, L, C = g.Open.values, g.High.values, g.Low.values, g.Close.values
        lasts = np.where(hm <= "15:10")[0]
        if not len(lasts): continue
        last = lasts[-1]
        prev_first = first[(first.index < D)].tail(10)
        relvol = first.get(D, np.nan) / prev_first.median() if len(prev_first) >= 5 and prev_first.median() > 0 else np.nan
        fixed = {k: L0[k] for k in ("dPP", "dR1", "dR2", "wPP", "wR1", "wR2", "D8", "yH") if L0[k] == L0[k]}
        dfb = None
        for i in range(1, last):   # D: failed breakout
            if hm[i] < "09:20" or hm[i] > "10:30": continue
            levels = dict(fixed); levels["dayH"] = H[:i].max()
            br = [(k, v) for k, v in levels.items() if C[i] > v and C[i - 1] < v]
            if not br: continue
            for j in range(i + 1, min(i + 4, last)):
                fl = [(abs(C[i] - v), k, v) for k, v in br if C[j] < v]
                if fl:
                    _, lk, lvl = min(fl); sD = H[i:j + 1].max() * (1 + TICK)
                    dfb = dict(D_level=lk, D_lvl=round(lvl, 2), D_time=hm[j], D_entry=round(C[j], 2), D_stop=round(sD, 2), t_entryD=g.index[j] + pd.Timedelta("5min"))
                    dfb.update({f"D_{k}": v for k, v in trade(H, L, C, j + 1, C[j], sD, last).items()})
                    break
            if dfb: break
        if dfb: out.append(dict(ticker=t, date=D.strftime("%Y-%m-%d"), kind="D", relvol=relvol, gap=(O[0] / L0.pc - 1) * 100, **dfb))
        for i in range(1, last):
            if hm[i] < "09:20" or hm[i] > "10:30": continue
            rg = H[i] - L[i]
            if rg <= 0 or (H[i] - max(O[i], C[i])) < rg / 3 or H[i] < L[:i + 1].min() * 1.005: continue
            levels = dict(fixed); levels["dayH"] = H[:i].max()
            cand = [(abs(H[i] - v), k, v) for k, v in levels.items() if H[i] >= v * (1 - NEAR) and C[i] < v and C[i - 1] < v]
            if not cand: continue
            _, lk, lvl = min(cand)
            stacked = any(k != lk and abs(v / lvl - 1) <= STACK for k, v in levels.items())
            e = C[i]; sA = H[i] * (1 + TICK); sB = max(sA, lvl * (1 + KATR * L0.atr / 100))
            rec = dict(ticker=t, date=D.strftime("%Y-%m-%d"), kind="A", time=hm[i], level=lk, lvl=round(lvl, 2), stacked=stacked, entry=round(e, 2),
                       barH=round(H[i], 2), relvol=relvol, gap=(O[0] / L0.pc - 1) * 100, up_open=(C[i] / O[0] - 1) * 100, atr=L0.atr,
                       t_entry=g.index[i] + pd.Timedelta("5min"))
            for nm, s in (("A", sA), ("B", sB)):
                rec.update({f"{nm}_{k}": v for k, v in trade(H, L, C, i + 1, e, s, last).items()}); rec[f"{nm}_stop"] = round(s, 2)
            # C: spike above the rejection bar's high, then a close back under the level, within 6 bars and by 11:00
            spiked = False
            for j in range(i + 1, min(i + 7, last)):
                if hm[j] > "11:00": break
                if H[j] > H[i]: spiked = True
                if spiked and C[j] < lvl:
                    sC = H[i:j + 1].max() * (1 + TICK)
                    rec.update({f"C_{k}": v for k, v in trade(H, L, C, j + 1, C[j], sC, last).items()})
                    rec.update(C_entry=round(C[j], 2), C_stop=round(sC, 2), C_time=hm[j], t_entryC=g.index[j] + pd.Timedelta("5min"))
                    break
            out.append(rec)
            break
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: X = pd.DataFrame([r for rr in p.map(run, uni, chunksize=20) for r in rr])
    NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True)
    if NF.index.tz is not None: NF.index = NF.index.tz_convert("Asia/Kolkata").tz_localize(None)
    NC = NF.Close[~NF.index.duplicated()].sort_index()
    def n20(T):
        if not isinstance(T, pd.Timestamp): return np.nan
        a, b = T - pd.Timedelta("25min"), T - pd.Timedelta("5min")
        return (NC[b] / NC[a] - 1) * 100 if a in NC.index and b in NC.index else np.nan
    ALLX = X; X = ALLX[ALLX.kind == "A"].copy(); Y = ALLX[ALLX.kind == "D"].copy()
    X["nifty20"] = [n20(T) for T in X.t_entry]; Y["nifty20"] = [n20(T) for T in Y.t_entryD]
    rv = pd.concat([X[["ticker", "date", "relvol"]], Y[["ticker", "date", "relvol"]]]).drop_duplicates(["ticker", "date"])
    rv["inplay"] = rv.groupby("date").relvol.rank(ascending=False) <= 20
    X = X.merge(rv[["ticker", "date", "inplay"]], on=["ticker", "date"], how="left"); Y = Y.merge(rv[["ticker", "date", "inplay"]], on=["ticker", "date"], how="left")
    X["stacked"] = X.stacked.astype(bool); X["inplay"] = X.inplay.fillna(False).astype(bool); Y["inplay"] = Y.inplay.fillna(False).astype(bool)
    X.drop(columns=[c for c in X if c.startswith("t_entry") or c.startswith("D_")]).to_csv(HERE / "morning_pop_rejection.csv", index=False)
    Y.drop(columns=[c for c in Y if c.startswith("t_entry")]).dropna(axis=1, how="all").to_csv(HERE / "morning_failed_breakout.csv", index=False)

    def cells(x, v, tg):
        x = x[x[f"{v}_{tg}_ret"].notna()]
        if not len(x): return ["0", "", "", ""]
        w = x[f"{v}_{tg}_why"]
        return [str(len(x)), f"{(w=='stop').mean()*100:.0f} / {(w=='target').mean()*100:.0f} / {(w=='time').mean()*100:.0f}%",
                f"{x[f'{v}_risk'].median():.2f}%", f"{(x[f'{v}_{tg}_ret'].mean()-COST)*1000:+.0f} ({(x[f'{v}_{tg}_ret']/x[f'{v}_risk']).mean():+.2f}R)"]
    def table(title, groups, tg="t1"):
        print(f"\n### {title}\n| group | A n | A stop/target/time | A med stop | A net Rs@1L (mean R) | B stop/target/time | B med stop | B net (R) | C n | C stop/target/time | C med stop | C net (R) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for lab, x in groups:
            a = cells(x, "A", tg); b = cells(x, "B", tg); c = cells(x, "C", tg)
            print(f"| {lab} | {a[0]} | {a[1]} | {a[2]} | {a[3]} | {b[1]} | {b[2]} | {b[3]} | {c[0]} | {c[1]} | {c[2]} | {c[3]} |")
    print(f"A setups {len(X)} on {X.date.nunique()} days, {X.ticker.nunique()} stocks ({X.date.min()} .. {X.date.max()}); C taken on {X.C_entry.notna().sum()}")
    print(f"in-play top-20 rejection setups: {X.inplay.sum()}")
    top10 = X.groupby("date").A_t1_ret.sum().nlargest(10).index
    base = [("ALL", X), ("top-10 days removed", X[~X.date.isin(top10)])]
    for tg, nm in (("t1", "1% target"), ("r2", "2R target")):
        table(f"{nm}: A tight (bar high) vs B room (level + 0.2 ATR) vs C spike-fail", base + [(f"month {mo}", g) for mo, g in X.groupby(X.date.str[:7])], tg)
    table("Splits, 1% target", [(f"level {k}", g) for k, g in X.groupby("level")] +
          [("stacked", X[X.stacked]), ("single level", X[~X.stacked]), ("in-play top-20", X[X.inplay]), ("not in-play", X[~X.inplay]),
           ("gap <= -2%", X[X.gap <= -2]), ("gap -2..+2%", X[X.gap.between(-2, 2)]), ("gap >= +2%", X[X.gap >= 2]),
           ("up > 3% from open (trend day)", X[X.up_open > 3]), ("up <= 3%", X[X.up_open <= 3]),
           ("Nifty up > +0.1% (20m)", X[X.nifty20 > 0.1]), ("Nifty flat", X[X.nifty20.between(-0.1, 0.1)]), ("Nifty down < -0.1%", X[X.nifty20 < -0.1]),
           ("Nifty n/a (before 2026-07-10)", X[X.nifty20.isna()]),
           ("entry 09:20-09:45", X[X.time <= "09:45"]), ("entry 09:50-10:30", X[X.time > "09:45"])])
    def dtab(title, groups):
        print(f"\n### {title}\n| group | n | 1%: stop/target/time | med stop | 1% net Rs@1L (mean R) | 2R: stop/target/time | 2R net (R) |\n|---|---|---|---|---|---|---|")
        for lab, x in groups:
            a = cells(x, "D", "t1"); b = cells(x, "D", "r2"); print(f"| {lab} | {a[0]} | {a[1]} | {a[2]} | {a[3]} | {b[1]} | {b[3]} |")
    top10D = Y.groupby("date").D_t1_ret.sum().nlargest(10).index
    print(f"\nD failed breakouts: {len(Y)} on {Y.date.nunique()} days")
    dtab("D FAILED BREAKOUT (close above a level, close back under within 3 bars; stop above the spike high)",
         [("ALL", Y), ("top-10 days removed", Y[~Y.date.isin(top10D)])] + [(f"month {mo}", g) for mo, g in Y.groupby(Y.date.str[:7])] +
         [(f"level {k}", g) for k, g in Y.groupby("D_level")] + [("in-play top-20", Y[Y.inplay]), ("not in-play", Y[~Y.inplay]),
          ("gap <= -2%", Y[Y.gap <= -2]), ("gap -2..+2%", Y[Y.gap.between(-2, 2)]), ("gap >= +2%", Y[Y.gap >= 2]),
          ("Nifty up > +0.1% (20m)", Y[Y.nifty20 > 0.1]), ("Nifty flat", Y[Y.nifty20.between(-0.1, 0.1)]), ("Nifty down < -0.1%", Y[Y.nifty20 < -0.1])])
    stA = X[X.A_t1_why == "stop"]
    print(f"\nA's {len(stA)} stops (1% target): under B -> still stop {(stA.B_t1_why=='stop').mean()*100:.0f}% / target {(stA.B_t1_why=='target').mean()*100:.0f}% / time {(stA.B_t1_why=='time').mean()*100:.0f}%")
    print("\nHAND CHECKS:")
    cols = ["ticker", "date", "time", "level", "lvl", "stacked", "entry", "barH", "A_stop", "A_t1_why", "B_stop", "B_t1_why", "C_time", "C_entry", "C_stop", "C_t1_why", "inplay"]
    for t, d in sorted(CHECKS):
        h = X[(X.ticker == t) & (X.date == d)]
        print(h[[c for c in cols if c in h]].round(2).to_string(index=False, header=False) if len(h) else f"  {t} {d}: A NOT CAUGHT")
        h = Y[(Y.ticker == t) & (Y.date == d)]
        print("   D: " + (h[["D_level", "D_lvl", "D_time", "D_entry", "D_stop", "D_t1_why", "D_r2_why", "inplay"]].round(2).to_string(index=False, header=False) if len(h) else "not caught"))
    print("\n3 random setups:"); print(X.sample(3, random_state=7)[[c for c in cols if c in X]].round(2).to_string(index=False))
