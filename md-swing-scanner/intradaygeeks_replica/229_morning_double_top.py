"""MORNING 5-MIN DOUBLE TOP SHORT (user, 2026-10-16, from live RBLBANK 2026-10-13: 09:20 strong green to 396.75, 09:25 dipped and
came back up but failed at the same price (396.95, heaviest bar), 09:30 heavy red -> shorted 395.25 51s in; 'I don't really see
anything on the chart' -- a price-action read, not a level). Spec fixed before running:
  Data: 30m set (5-min bars, 2026-06..10). Universe: prev-day median 5-min turnover >= Rs15 lakh, prev close >= Rs100.
  SETUP: two bars i < j (j = i+1 or i+2), both starting 09:20..10:30, highs within 0.1% of each other (a middle bar, if any, not
    above them); top = max(H_i, H_j) >= 0.5% above the day's low so far (a real bounce). First per stock-day.
  Entries, side by side:  (a) ANTICIPATION: the open of bar j+1, only if it opens below the top.
                          (b) CONFIRMATION: sell-stop at bar j's low, triggered within the next 3 bars (fill = that low, or the bar
                              open if it gaps through).
  Stop = top + 0.05%. The entry bar can stop you (stop first: order inside a bar unknown, counted against us).
  Exits: 1% target or 2R, else out at the 15:15 close. Net Rs per Rs1 lakh = ret - 0.085%.
  Splits: bar j volume > bar i (absorption) vs not; gap <= -2% vs not; in-play top-20 (relvol = 09:15-09:25 volume / median of
    the previous 10 days'); an OLD DAILY SHELF within 0.3% of the top (swing lows K=2 and gap-up edges = gap day's low / the
    prior day's high, last 60 trading days, confirmed >= 3 days before) vs not; Nifty 20 min before entry (a); month; top-10
    days removed.  Hand check: RBLBANK 2026-10-13 -> bars 09:20 / 09:25, (a) 396.45, (b) 394.55."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
COST = 0.085; TICK = 0.0005; EQ = 0.001; SHELF = 0.003


def walk(H, L, C, i0, e, stop, last, tg):
    for k in range(i0, last + 1):
        if H[k] >= stop: return (e - stop) / e * 100, "stop"
        if L[k] <= tg: return (e - tg) / e * 100, "target"
    return (e - C[last]) / e * 100, "time"


def trade(H, L, C, i0, e, stop, last, p):
    out = {f"{p}_entry": round(e, 2), f"{p}_risk": (stop - e) / e * 100}
    for nm, tg in (("t1", e * 0.99), ("r2", e - 2 * (stop - e))):
        out[f"{p}_{nm}_ret"], out[f"{p}_{nm}_why"] = walk(H, L, C, i0, e, stop, last, tg)
    return out


def shelves(d):
    """per day: the list of old daily shelf prices known before that day (swing lows K=2, gap-up edges), last 60 sessions."""
    lo, hi = d.Low.values, d.High.values; n = len(d); pts = []   # (usable-from index, price)
    for k in range(2, n - 2):
        if lo[k] < min(lo[k - 2], lo[k - 1], lo[k + 1], lo[k + 2]): pts.append((k + 3, k, lo[k]))
        if lo[k] > hi[k - 1]: pts += [(k + 1, k, lo[k]), (k + 1, k, hi[k - 1])]
    return pts


def run(t):
    try:
        m = read5_official(t)
        d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()].dropna(subset=["Close"])
    except Exception: return []
    pts = shelves(d); didx = {D: k for k, D in enumerate(d.index)}
    md = m.index.normalize(); days = sorted(set(md)); out = []
    early = m.index.strftime("%H:%M") <= "09:25"; first = m.Volume[early].groupby(md[early]).sum()
    for a in range(1, len(days)):
        D, P = days[a], days[a - 1]
        if D not in didx or didx[D] < 1: continue
        kD = didx[D]; pc = d.Close.iloc[kD - 1]
        if pc < 100: continue
        pv = m[(md == P) & (m.Volume > 0)]
        if not len(pv) or (pv.Volume * pv.Close).median() < 15e5: continue
        g = m[md == D]; hm = g.index.strftime("%H:%M").values
        if len(g) < 60 and not (t == "RBLBANK" and D == pd.Timestamp("2026-10-13")): continue
        O, H, L, C, V = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values
        lasts = np.where(hm <= "15:10")[0]
        if not len(lasts): continue
        last = lasts[-1]
        pf = first[first.index < D].tail(10)
        relvol = first.get(D, np.nan) / pf.median() if len(pf) >= 5 and pf.median() > 0 else np.nan
        sh = [p for (u, k, p) in pts if u <= kD and k >= kD - 60]
        for i in range(1, last - 2):
            if hm[i] < "09:20" or hm[i] > "10:30": continue
            found = None
            for j in (i + 1, i + 2):
                if j >= last - 1 or hm[j] > "10:30": break
                if abs(H[j] / H[i] - 1) > EQ: continue
                top = max(H[i], H[j])
                if j == i + 2 and H[i + 1] > top: continue
                if top < L[:j + 1].min() * 1.005: continue
                found = (j, top); break
            if not found: continue
            j, top = found; stop = top * (1 + TICK)
            rec = dict(ticker=t, date=D.strftime("%Y-%m-%d"), t1=hm[i], t2=hm[j], top=round(top, 2), low2=round(L[j], 2), absorb=V[j] > V[i],
                       gap=(O[0] / pc - 1) * 100, relvol=relvol, shelf=any(abs(p / top - 1) <= SHELF for p in sh), stop=round(stop, 2),
                       t_entry=g.index[j + 1])
            if O[j + 1] < top: rec.update(trade(H, L, C, j + 1, O[j + 1], stop, last, "a"))
            for k in range(j + 1, min(j + 4, last)):
                if L[k] <= L[j]:
                    e = min(L[j], O[k]); rec.update(trade(H, L, C, k, e, stop, last, "b")); rec["b_time"] = hm[k]; break
            out.append(rec); break
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: X = pd.DataFrame([r for rr in p.map(run, uni, chunksize=20) for r in rr])
    NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True)
    if NF.index.tz is not None: NF.index = NF.index.tz_convert("Asia/Kolkata").tz_localize(None)
    NC = NF.Close[~NF.index.duplicated()].sort_index()
    def n20(T):
        a, b = T - pd.Timedelta("25min"), T - pd.Timedelta("5min")
        return (NC[b] / NC[a] - 1) * 100 if a in NC.index and b in NC.index else np.nan
    X["nifty20"] = [n20(T) for T in X.t_entry]
    X["inplay"] = (X.groupby("date").relvol.rank(ascending=False) <= 20).astype(bool)
    X["absorb"] = X.absorb.astype(bool); X["shelf"] = X.shelf.astype(bool)
    X.drop(columns="t_entry").to_csv(HERE / "morning_double_top.csv", index=False)

    def cells(x, v, tg):
        x = x[x[f"{v}_{tg}_ret"].notna()]
        if not len(x): return ["0", "", "", ""]
        w = x[f"{v}_{tg}_why"]
        return [str(len(x)), f"{(w=='stop').mean()*100:.0f} / {(w=='target').mean()*100:.0f} / {(w=='time').mean()*100:.0f}%",
                f"{x[f'{v}_risk'].median():.2f}%", f"{(x[f'{v}_{tg}_ret'].mean()-COST)*1000:+.0f} ({(x[f'{v}_{tg}_ret']/x[f'{v}_risk']).mean():+.2f}R)"]
    def table(title, groups, tg):
        print(f"\n### {title}\n| group | (a) n | (a) stop/target/time | (a) med stop | (a) net Rs@1L (mean R) | (b) n | (b) stop/target/time | (b) med stop | (b) net (R) |\n|---|---|---|---|---|---|---|---|---|")
        for lab, x in groups:
            a = cells(x, "a", tg); b = cells(x, "b", tg); print(f"| {lab} | " + " | ".join(a + b) + " |")
    print(f"double tops {len(X)} on {X.date.nunique()} days, {X.ticker.nunique()} stocks ({X.date.min()} .. {X.date.max()})")
    top10 = X.groupby("date").a_t1_ret.sum().nlargest(10).index
    base = [("ALL", X), ("top-10 days removed", X[~X.date.isin(top10)])] + [(f"month {mo}", g) for mo, g in X.groupby(X.date.str[:7])]
    table("1% target: (a) next-bar open vs (b) sell-stop under bar 2's low; stop = top + 0.05%", base, "t1")
    table("2R target", base, "r2")
    table("Splits, 1% target", [("bar 2 heavier (absorption)", X[X.absorb]), ("bar 2 lighter", X[~X.absorb]),
          ("gap <= -2%", X[X.gap <= -2]), ("gap > -2%", X[X.gap > -2]), ("in-play top-20", X[X.inplay]), ("not in-play", X[~X.inplay]),
          ("in-play AND absorption", X[X.inplay & X.absorb]), ("in-play AND gap <= -2%", X[X.inplay & (X.gap <= -2)]),
          ("old daily shelf within 0.3%", X[X.shelf]), ("no shelf", X[~X.shelf]),
          ("Nifty up > +0.1% (20m)", X[X.nifty20 > 0.1]), ("Nifty flat", X[X.nifty20.between(-0.1, 0.1)]), ("Nifty down < -0.1%", X[X.nifty20 < -0.1]),
          ("bars 1-2 adjacent", X[X.t2 == pd.to_datetime(X.t1, format="%H:%M").add(pd.Timedelta("5min")).dt.strftime("%H:%M")]),
          ("entry 09:25-09:45", X[X.t2 <= "09:40"]), ("entry 09:50-10:40", X[X.t2 > "09:40"])], "t1")
    print("\nHAND CHECK RBLBANK 2026-10-13:")
    cols = ["ticker", "date", "t1", "t2", "top", "low2", "stop", "absorb", "gap", "inplay", "shelf", "a_entry", "a_t1_why", "a_r2_why", "b_time", "b_entry", "b_t1_why", "b_r2_why"]
    h = X[(X.ticker == "RBLBANK") & (X.date == "2026-10-13")]
    print(h[[c for c in cols if c in h]].round(2).to_string(index=False) if len(h) else "  NOT CAUGHT")
    print("\n4 random:"); print(X.sample(4, random_state=3)[[c for c in cols if c in X]].round(2).to_string(index=False))
