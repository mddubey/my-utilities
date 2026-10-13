"""ORB STOP PLACEMENT with FIXED TARGETS (user, 2026-10-13: 'holding to EOD already seems flawed -- at some point it takes my SL out';
follows 211: winners pull back a median 0.2R first, a close back through the break level is the failure sign). Spec fixed before running:
  Population: 211's (in-play relvol >= 1 top 20, official open, first break of the 09:15 low / high from 09:20; entry = the level, or
  the bar open if it gapped through). Shorts and longs separate. 2026-06-24 .. 2026-10-09.
  Stops (all known at entry):
    ATR10  = 10% of daily ATR from the entry (the paper's / current tight stop)
    ATR20  = 20% of ATR (the wide one the user used on INOXGREEN)
    CLOSE  = exit at the close of the first 5-min bar (the entry bar included) that closes > 0.1% back through the break level,
             with a hard stop at ATR20 inside the bar; sized on the ATR20 distance
    FIB236 = the 23.6% level of the 09:15 candle (back into the candle)
    VWAP   = VWAP at entry (previous bar's value; 09:15 volume = day - other bars), fixed price
  Targets: fixed 1% / 1.5% / 2% from the entry; else out at the 15:15 bar open. Stop first if both fall in one bar. Entry bar: a fixed
  stop is hit inside it only if the bar opened through the level (gap fill) and touched the stop, or it CLOSED beyond the stop (206's rule);
  targets are counted from the next bar.
  Rs per trade at Rs1,000 risk on the sizing distance, net of Rs85 per Rs1 lakh traded. Report: n, win %, stop %, target %, Rs net,
  w/o the top-10 days, half 1 / half 2 (to 2026-08-14 / from 2026-08-17), median risk %, worst drawdown of the daily-summed P&L."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
from data.paths import DAILY_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()
STOPS = ["ATR10", "ATR20", "CLOSE", "FIB236", "VWAP"]; TGTS = [1.0, 1.5, 2.0]


def run(d, kb, b0, ep, s, lvl, stp, tgt_pct, close_exit, gapfill):
    """Returns (exit price, how)."""
    tgt = ep * (1 + s * tgt_pct / 100)
    # entry bar
    if (gapfill and ((b0.High >= stp) if s < 0 else (b0.Low <= stp))) or ((b0.Close >= stp) if s < 0 else (b0.Close <= stp)): return stp, "stop"
    if close_exit and ((b0.Close > lvl * 1.001) if s < 0 else (b0.Close < lvl * 0.999)): return b0.Close, "close-exit"
    for b in d[d.index > kb].itertuples():
        if b.hm >= "15:15": return b.Open, "time"
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp, "stop"
        if (b.Low <= tgt) if s < 0 else (b.High >= tgt): return tgt, "target"
        if close_exit and ((b.Close > lvl * 1.001) if s < 0 else (b.Close < lvl * 0.999)): return b.Close, "close-exit"
    return d.Close.iloc[-1], "time"


rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M"); dv = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).Volume
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd].copy()
        if len(d) < 70: continue
        s = int(r.side); f = d.iloc[0]; lvl = f.Low if s < 0 else f.High; rng = f.High - f.Low
        v = d.Volume.values.astype(float); v[0] = dv.get(dd, np.nan) - v[1:].sum()
        vw = pd.Series(np.cumsum(((d.High + d.Low + d.Close) / 3).values * v) / np.cumsum(v), index=d.index).shift(1)
        a = d[(d.hm >= "09:20") & (d.hm < "15:15")]
        brk = a[(a.Low < lvl) if s < 0 else (a.High > lvl)]
        if not len(brk) or rng <= 0: continue
        kb = brk.index[0]; b0 = d.loc[kb]; ep = min(lvl, b0.Open) if s < 0 else max(lvl, b0.Open)
        gapfill = (b0.Open <= lvl) if s < 0 else (b0.Open >= lvl)
        stops = {"ATR10": ep * (1 - s * 0.1 * r.atr / 100), "ATR20": ep * (1 - s * 0.2 * r.atr / 100),
                 "FIB236": lvl - s * 0.236 * rng, "VWAP": vw.get(kb, np.nan)}
        stops["CLOSE"] = stops["ATR20"]
        rec = dict(t=t, date=r.date, side=s)
        for sn in STOPS:
            stp = stops[sn]
            if not stp == stp or ((stp <= ep) if s < 0 else (stp >= ep)): continue          # stop must be on the far side
            risk = abs(stp - ep) / ep * 100; rec[f"risk_{sn}"] = risk
            for tp in TGTS:
                px, how = run(d, kb, b0, ep, s, lvl, stp, tp, sn == "CLOSE", gapfill)
                ret = s * (px - ep) / ep * 100
                rec[f"{sn}_{tp}"] = ret / risk * 1000 - 85 * (1000 / (risk / 100)) / 1e5; rec[f"{sn}_{tp}_how"] = how
        rows.append(rec)
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_stop_placement.csv", index=False)

print("HAND CHECK (3 random shorts, ATR10 / CLOSE at 1.5%):")
print(X[X.side == -1].sample(3, random_state=3)[["t", "date", "risk_ATR10", "ATR10_1.5", "ATR10_1.5_how", "risk_CLOSE", "CLOSE_1.5", "CLOSE_1.5_how", "risk_FIB236", "risk_VWAP"]].round(2).to_string(index=False))
for sd, sn_ in ((-1, "SHORTS"), (1, "LONGS")):
    G = X[X.side == sd]
    print(f"\n## {sn_}: {len(G)} breaks")
    print("| stop | target | trades | win % | stopped % | target % | Rs @1k net | w/o top-10 days | half 1 / half 2 | median risk % | worst DD (Rs) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for sn in STOPS:
        for tp in TGTS:
            c = f"{sn}_{tp}"; x = G[G[c].notna()]
            if not len(x): continue
            k = x[c]; how = x[c + "_how"]; byd = x.groupby("date")[c].sum().sort_index()
            top = byd.sort_values(ascending=False).head(10).index; eq = byd.cumsum(); dd = (eq - eq.cummax()).min()
            print(f"| {sn} | {tp}% | {len(x)} | {(k > 0).mean()*100:.0f}% | {how.isin(['stop', 'close-exit']).mean()*100:.0f}% | "
                  f"{(how == 'target').mean()*100:.0f}% | {k.mean():+.0f} | {k[~x.date.isin(top)].mean():+.0f} | "
                  f"{k[x.date <= '2026-08-14'].mean():+.0f} / {k[x.date >= '2026-08-17'].mean():+.0f} | {x['risk_' + sn].median():.2f} | {dd:,.0f} |")
