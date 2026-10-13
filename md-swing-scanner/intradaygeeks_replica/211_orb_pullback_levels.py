"""ORB PULLBACK LEVELS -- where does a normal pullback after the break stop, and is a REJECTION at a level different from a
BREAK-THROUGH? (user, 2026-10-13: 'no trade runs directly -- what is the general pullback expectation, if not VWAP? any EMA / fib
level'; 'came back to VWAP and rejected from VWAP are two different things'). DESCRIPTIVE, no new rule. Spec fixed before running:
  Population: script 206's (in-play, relvol >= 1, top 20, official open; shorts = red 09:15, longs = green; the first break of the
  09:15 low / high from 09:20, entry = the level or the bar open if it gapped through). No stop -- the whole path to 15:15 is followed.
  Levels (short side; longs mirrored), each judged on its own:
    BREAK = the 09:15 low (retest of the level); FIB 23.6 / 38.2 / 50 / 61.8 = that far back into the 09:15 candle;
    EMA9 / EMA20 = 5-min EMAs (continuous series, value at the previous bar's close); VWAP (09:15 volume = day - other bars,
    value at the previous bar's close); OR_HIGH = the 09:15 high (full failure).
    A level already on the trade's side at entry (e.g. EMA9 below a short's entry) is 'n/a' for that break.
  Window for the pullback: bars after the break bar, before 13:00 (as 206).
  Classification at the FIRST touch (short: bar high >= level):
    REJECTED = the touch bar or one of the next two CLOSES back below the level (206's rule); decision = that close.
    BROKEN   = none of the three closes back below; decision = the third bar's close.
    NEVER    = no touch before 13:00 (known only at 13:00 -- reference, not tradeable).
  Outcomes, counted from the decision bar onward to 15:15 (stop-first ordering inside a bar):
    'already +1%' = the 1% target from the entry was hit BEFORE the decision (trade already done -- shows how many run first);
    else: TARGET = price later reaches entry -1% before the 09:15 high; FAIL = takes the 09:15 high first; NEITHER;
    and the move from the decision close to the 15:15 bar open (what a NEW entry at that point gets, % gross, no stop).
  Also: of the breaks that reached +1% at all, how many came back to each level first (outcome-conditioned, descriptive only);
  and the median deepest pullback before 13:00 in R (R = 10% ATR) and in % of the 09:15 candle.
  Hand check printed: INOXGREEN 2026-10-12."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
from data.paths import DAILY_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()
LEVELS = ["BREAK", "FIB23.6", "FIB38.2", "FIB50", "FIB61.8", "EMA9", "EMA20", "VWAP", "OR_HIGH"]

rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    m["e9"] = m.Close.ewm(span=9, adjust=False).mean().shift(1); m["e20"] = m.Close.ewm(span=20, adjust=False).mean().shift(1)
    dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd].copy()
        if len(d) < 70: continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High; opp = f.High if s < 0 else f.Low; rng = f.High - f.Low
        if rng <= 0: continue
        v = d.Volume.values.astype(float); v[0] = dv.get(dd, np.nan) - v[1:].sum()
        d["vw"] = pd.Series(np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v), index=d.index).shift(1)
        a = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        brk = a[(a.Low < lvl) if s < 0 else (a.High > lvl)]
        if not len(brk): continue
        kb = brk.index[0]; b0 = d.loc[kb]; ep = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
        R = 0.1 * r.atr / 100 * ep; tgt = ep * (1 + s * 0.01)
        after = d[(d.index > kb) & (d.hm < "15:15")]
        fav = (after.Low <= tgt) if s < 0 else (after.High >= tgt)
        k_tgt = fav[fav].index[0] if fav.any() else None
        win = d[(d.index > kb) & (d.hm < "13:00")]
        if not len(win): continue
        adv = (win.High.max() - ep) if s < 0 else (ep - win.Low.min())          # deepest pullback before 13:00 (incl. after a target)
        pre = win if k_tgt is None else win[win.index < k_tgt]
        adv_pre = ((pre.High.max() - ep) if s < 0 else (ep - pre.Low.min())) if len(pre) else 0.0
        rec = dict(t=t, date=r.date, side=s, ep=ep, reached=k_tgt is not None, depth_R=adv / R, depth_pre_R=adv_pre / R,
                   depth_pre_rng=adv_pre / rng * 100)
        fixed = {"BREAK": lvl, "OR_HIGH": opp}
        for fpc in (23.6, 38.2, 50, 61.8): fixed[f"FIB{fpc}"] = lvl - s * fpc / 100 * rng      # back into the candle
        for L in LEVELS:
            ser = (pd.Series(fixed[L], index=d.index) if L in fixed else d[{"EMA9": "e9", "EMA20": "e20", "VWAP": "vw"}[L]])
            l0 = ser.get(kb, np.nan)
            if not l0 == l0 or ((l0 < ep) if s < 0 else (l0 > ep)) and L not in ("BREAK",):   # level already on the trade's side
                rec[L] = "n/a"; continue
            wl = ser.reindex(win.index)
            tch = win[(win.High >= wl) if s < 0 else (win.Low <= wl)]
            if not len(tch): rec[L] = "NEVER"; rec[L + "_already"] = False; continue
            kt = tch.index[0]; nxt = d[d.index >= kt].head(3); nl = ser.reindex(nxt.index)
            rj = nxt[(nxt.Close < nl) if s < 0 else (nxt.Close > nl)]
            if len(rj): cls, kd = "REJECTED", rj.index[0]
            else: cls, kd = "BROKEN", nxt.index[-1]
            rec[L] = cls; rec[L + "_t"] = d.loc[kt].hm
            if k_tgt is not None and k_tgt <= kd: rec[L + "_out"] = "already +1%"; continue
            p0 = d.loc[kd].Close; out = "NEITHER"
            for b in d[(d.index > kd) & (d.hm < "15:15")].itertuples():
                if (b.High >= opp) if s < 0 else (b.Low <= opp): out = "FAIL"; break
                if (b.Low <= tgt) if s < 0 else (b.High >= tgt): out = "TARGET"; break
            e15 = d[d.hm == "15:15"]; px = e15.Open.iloc[0] if len(e15) else d.Close.iloc[-1]
            rec[L + "_out"] = out; rec[L + "_newret"] = s * (px - p0) / p0 * 100
        rows.append(rec)
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_pullback_levels.csv", index=False)

print("HAND CHECK INOXGREEN 2026-10-12:")
h = X[(X.t == "INOXGREEN") & (X.date == "2026-10-12")]
print(h[[c for c in X.columns if not c.endswith("_newret")]].T.to_string() if len(h) else "  not in population")
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    G = X[X.side == sd]
    print(f"\n## {sn}: {len(G)} breaks | reached +1% at all: {G.reached.mean()*100:.0f}% | deepest pullback before 13:00, median "
          f"{G.depth_R.median():.1f}R | before the +1% (those that got there): median {G[G.reached].depth_pre_R.median():.1f}R = "
          f"{G[G.reached].depth_pre_rng.median():.0f}% of the 09:15 candle (75th pct {G[G.reached].depth_pre_R.quantile(.75):.1f}R) | "
          f"ran to +1% with a pullback < 1R (tight stop survives): {(G[G.reached].depth_pre_R < 1).mean()*100:.0f}% of those")
    print("| level | n/a | never touched | touched | of touched: rejected / broken | REJECTED: already +1% / then target / then fail / neither | REJECTED: new entry at the rejection close, move to 15:15 | BROKEN: already +1% / then target / then fail / neither | BROKEN: new entry, move to 15:15 | of +1% winners, came back here first |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    W = G[G.reached]
    for L in LEVELS:
        c = G[L]; na = (c == "n/a").sum(); nv = (c == "NEVER").sum(); tc = c.isin(["REJECTED", "BROKEN"]).sum()
        cells = []
        for cls in ("REJECTED", "BROKEN"):
            x = G[c == cls]; o = x[L + "_out"] if L + "_out" in x else pd.Series(dtype=object)
            n = len(x)
            if n == 0: cells += ["-", "-"]; continue
            pc = lambda k: f"{(o == k).mean()*100:.0f}%"
            nr = x[L + "_newret"].dropna()
            cells += [f"{n}: {pc('already +1%')} / {pc('TARGET')} / {pc('FAIL')} / {pc('NEITHER')}",
                      f"{nr.mean():+.2f}% (n {len(nr)}, median {nr.median():+.2f}%)" if len(nr) else "-"]
        cw = W[L]; came = cw.isin(["REJECTED", "BROKEN"]) & (W.get(L + "_out") == "already +1%").eq(False)
        print(f"| {L} | {na} | {nv} | {tc} | {(c == 'REJECTED').sum()} / {(c == 'BROKEN').sum()} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | "
              f"{came.sum()}/{len(W)} ({came.mean()*100:.0f}%) |")
