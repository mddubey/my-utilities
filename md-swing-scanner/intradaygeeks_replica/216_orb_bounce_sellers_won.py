"""ORB BOUNCE -> 'SELLERS WON' bar -> back to the 09:15 close (user, 2026-10-13, from the live RBLBANK short: red in-play ORB candle,
bounce took back ~68% of its body, a heavy stall bar, short, exit at the 09:15 close area). User: 'not obsessed with one candle -- any candle
that says sellers won'; 'a watch-out sort of thing, mechanical'. Spec declared in chat before running:
  Stocks: in-play red ORB candles (relvol >= 1, top 20, official open), 2026-06-24 .. 2026-10-09.
  Setup: from 09:20 the running high takes back >= 50% of the red body by 10:30 and never goes above the 09:15 OPEN before the signal
  (above the open = a different story: 59% took the 09:15 high first).
  SELLERS-WON bar (any 5-min bar from the one that completed the 50% bounce, starting no later than 10:55):
    A red, close in the lower half of its range | B shooting star, upper wick >= half the range | C bearish engulfing, red body covering
    the previous bar's body | D stall, volume >= 1.5x the prior 3 bars' average and body < 25% of the range.
  Entry: the NEXT bar breaks the signal bar's low (sell-stop at the low; gap-through fills at that bar's open); otherwise wait for the next signal.
  Stop: signal bar high + 0.05%. Entry bar: stopped if it opened through the low and touched the stop, or closed beyond the stop.
  Targets: the 09:15 candle's CLOSE (skip if the entry is already at / below it) | fixed 1.5%; else out at the 15:15 open.
  One trade per stock-day per definition (its first filled signal); ANY = first filled signal of any type (main result).
  Baseline: same setups, short at the 10:30 open, stop = the bounce high so far + 0.05%, same targets.
  Rs @1k risk net (Rs85 per Rs1 lakh); win %, R, w/o top-10 days, half 1 / half 2 (to 2026-08-14 / from 2026-08-17); 3 hand checks.
  Counts only if ANY holds w/o the top-10 days and in both halves."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20) & (A.side == -1)]


def walk(d, k, e, stp, tgt):
    for b in d[d.index > k].itertuples():
        if b.hm >= "15:15": return b.Open, "time"
        if b.High >= stp: return stp, "stop"
        if b.Low <= tgt: return tgt, "target"
    return d.Close.iloc[-1], "time"


def trade(d, kb, e, stp, gapfill, C915):
    b0 = d.loc[kb]; out = {}
    for lab, tgt in (("close", C915), ("1.5%", e * 0.985)):
        if lab == "close" and e <= C915 * 1.0005: out[lab] = (None, "no room"); continue
        if (gapfill and b0.High >= stp) or b0.Close >= stp: px, how = stp, "stop"
        elif b0.Low <= tgt and lab == "1.5%" and False: px, how = tgt, "target"
        else: px, how = walk(d, kb, e, stp, tgt)
        risk = (stp - e) / e * 100
        out[lab] = ((e - px) / e * 100 / risk * 1000 - 85 * (1000 / (risk / 100)) / 1e5, how, (e - px) / (stp - e))
    return out


rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]
        if len(d) < 70: continue
        f = d.iloc[0]; O, H, L, C = f.Open, f.High, f.Low, f.Close; body = O - C
        if body <= 0: continue
        lvl50 = C + 0.5 * body
        w = d[(d.hm >= "09:20") & (d.hm <= "10:55")].copy()
        w["runhi"] = w.High.cummax()
        reach = w[(w.runhi >= lvl50) & (w.hm <= "10:30")]
        if not len(reach): continue
        k50 = reach.index[0]
        if w.loc[:k50].High.max() > O: continue                         # went above the open before the setup completed
        base = dict(t=t, date=r.date)
        # baseline: short at the 10:30 open if still valid
        b1030 = d[d.hm == "10:30"]
        if len(b1030) and w.loc[:b1030.index[0]].High.max() <= O and k50 <= b1030.index[0]:
            kb = b1030.index[0]; e = b1030.Open.iloc[0]; stp = w.loc[:kb].High.max() * 1.0005
            if stp > e:
                rows.append(dict(base, typ="BASELINE 10:30", **{f"{k}_{x}": v for k, (vv) in trade(d, kb, e, stp, False, C).items() for x, v in zip(("rs", "how", "R"), vv if vv[0] is not None else (None, vv[1], None))}))
        sig = w.loc[k50:]
        idx = list(d.index); first = {}
        for k, b in sig.iterrows():
            if w.loc[:k].High.max() > O: break                           # bounce went above the open -> setup void
            i = idx.index(k)
            if i + 1 >= len(idx): break
            p = d.iloc[i - 1]; rng = b.High - b.Low
            if rng <= 0: continue
            v3 = d.Volume.iloc[max(i - 3, 0):i].mean()
            types = []
            if b.Close < b.Open and (b.Close - b.Low) / rng <= 0.5: types.append("A red lower half")
            if (b.High - max(b.Open, b.Close)) / rng >= 0.5: types.append("B shooting star")
            if b.Close < b.Open and b.Open >= max(p.Open, p.Close) and b.Close <= min(p.Open, p.Close): types.append("C bearish engulfing")
            if v3 > 0 and b.Volume >= 1.5 * v3 and abs(b.Close - b.Open) < 0.25 * rng: types.append("D stall")
            if not types: continue
            nb = d.iloc[i + 1]
            if nb.hm >= "15:15" or not nb.Low < b.Low: continue          # next bar must break the signal low
            gap = nb.Open <= b.Low; e = min(b.Low, nb.Open); stp = b.High * 1.0005
            res = trade(d, d.index[i + 1], e, stp, gap, C)
            for ty in types + ["ANY"]:
                if ty in first: continue
                first[ty] = 1
                rows.append(dict(base, typ=ty, sig=b.hm, e=e, stp=stp, **{f"{k}_{x}": v for k, vv in res.items() for x, v in zip(("rs", "how", "R"), vv if vv[0] is not None else (None, vv[1], None))}))
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_bounce_sellers_won.csv", index=False)

print("HAND CHECK (3 random ANY trades):")
for _, r in X[X.typ == "ANY"].dropna(subset=["close_rs"]).sample(3, random_state=8).iterrows():
    m = read5_official(r.t); d = m[m.index.normalize() == pd.Timestamp(r.date)]; f = d.iloc[0]
    k = d.index[d.index.strftime("%H:%M") == r.sig][0]; i = d.index.get_loc(k)
    print(f"\n{r.t} {r.date} 09:15 O {f.Open:.2f} H {f.High:.2f} L {f.Low:.2f} C {f.Close:.2f} (50% = {f.Close + 0.5*(f.Open-f.Close):.2f}) | signal {r.sig} "
          f"entry {r.e:.2f} stop {r.stp:.2f} -> to-close: {r.close_how} {r.close_R:+.2f}R | 1.5%: {r['1.5%_how']} {r['1.5%_R']:+.2f}R")
    print(d.iloc[max(i - 2, 1):i + 3][["Open", "High", "Low", "Close", "Volume"]].round(2).to_string())

print(f"\nsetups (red in-play, bounce 50-100% by 10:30): {X[X.typ == 'BASELINE 10:30'].shape[0]} with a 10:30 baseline; stock-days with a filled ANY signal: {(X.typ == 'ANY').sum()}")
for tg in ("close", "1.5%"):
    print(f"\nTARGET = {'the 09:15 CLOSE' if tg == 'close' else 'fixed 1.5%'}\n| entry | trades | win % | target / stop / time | R per trade | Rs @1k net | w/o top-10 days | half 1 / half 2 | median risk % |\n|---|---|---|---|---|---|---|---|---|")
    for ty in ["ANY", "A red lower half", "B shooting star", "C bearish engulfing", "D stall", "BASELINE 10:30"]:
        x = X[(X.typ == ty) & X[f"{tg}_rs"].notna()]
        if not len(x): print(f"| {ty} | 0 |"); continue
        v = x[f"{tg}_rs"].astype(float); top = x.groupby("date")[f"{tg}_rs"].sum().sort_values(ascending=False).head(10).index; h = x[f"{tg}_how"]
        risk = ((x.stp - x.e) / x.e * 100) if "e" in x and x.e.notna().all() else pd.Series(dtype=float)
        print(f"| {ty} | {len(x)} | {(v > 0).mean()*100:.0f}% | {(h == 'target').mean()*100:.0f} / {(h == 'stop').mean()*100:.0f} / {(h == 'time').mean()*100:.0f}% | "
              f"{x[f'{tg}_R'].astype(float).mean():+.2f} | {v.mean():+.0f} | {v[~x.date.isin(top)].mean():+.0f} | "
              f"{v[x.date <= '2026-08-14'].mean():+.0f} / {v[x.date >= '2026-08-17'].mean():+.0f} | {risk.median() if len(risk) else float('nan'):.2f} |")
    nr = X[(X.typ == "ANY") & (X[f"{tg}_how"] == "no room")].shape[0]
    if nr: print(f"(ANY signals skipped for no room -- entry already at / below the 09:15 close: {nr})")
