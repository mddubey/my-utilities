"""5-min EMA8 REJECTIONS on in-play ORB stocks (user, 2026-10-13, after the RBLBANK live trades: 'look at 5-min 8EMA rejections, how
good / bad they are'). Spec declared in chat before running:
  Stocks / days: the in-play ORB list (relvol >= 1, top 20, official open), 2026-06-24 .. 2026-10-09. Shorts on red 09:15 candles,
  longs mirrored on green.
  Rejection (short): a 5-min bar from 09:30 to 12:55 whose HIGH >= the 5-min EMA8 (value at the previous bar), closes RED and BELOW that
  EMA8, with EMA8 < EMA20 (previous bar; short-term trend down). Longs mirrored (low <= EMA8, green, close above, EMA8 > EMA20).
  Entry at the rejection bar's close. Stops: (A) the rejection bar's high; (B) the wider of the bar high and 10% ATR.
  Exits: fixed 1% / 1.5% target or 2R, else out at the 15:15 bar open; stop first if both in one bar; walk starts at the next bar.
  Which: FIRST rejection of the day only | EVERY rejection, a new trade only after the previous one closed.
  Rs per trade @ Rs1,000 risk, net Rs85 per Rs1 lakh. Report win %, Rs, w/o top-10 days, half 1 / half 2, median stop %, baseline =
  the plain ORB break (212, 10% ATR, same targets). 3 trades printed for a hand check."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from orb_common import read5_official
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
P = A[(A.rv >= 1) & (A["rank"] <= 20)].copy()
EX = [("1%", 1.0, None), ("1.5%", 1.5, None), ("2R", None, 2.0)]


def walk(d, k, e, s, stp, tp, rr):
    tgt = e * (1 + s * tp / 100) if tp else e + s * rr * abs(stp - e)
    for b in d[d.index > k].itertuples():
        if b.hm >= "15:15": return b.Open, b.Index, "time"
        if (b.High >= stp) if s < 0 else (b.Low <= stp): return stp, b.Index, "stop"
        if (b.Low <= tgt) if s < 0 else (b.High >= tgt): return tgt, b.Index, "target"
    return d.Close.iloc[-1], d.index[-1], "time"


rows = []
for t, g in P.groupby("ticker"):
    m = read5_official(t); m["hm"] = m.index.strftime("%H:%M")
    m["e8"] = m.Close.ewm(span=8, adjust=False).mean().shift(1); m["e20"] = m.Close.ewm(span=20, adjust=False).mean().shift(1)
    for _, r in g.iterrows():
        dd = pd.Timestamp(r.date); d = m[m.index.normalize() == dd]
        if len(d) < 70: continue
        s = int(r.side)
        w = d[(d.hm >= "09:30") & (d.hm <= "12:55")]
        if s < 0: rj = w[(w.High >= w.e8) & (w.Close < w.Open) & (w.Close < w.e8) & (w.e8 < w.e20)]
        else: rj = w[(w.Low <= w.e8) & (w.Close > w.Open) & (w.Close > w.e8) & (w.e8 > w.e20)]
        for sv in ("A", "B"):
            busy_until = None; n = 0
            for k, b in rj.iterrows():
                if busy_until is not None and k <= busy_until: continue
                e = b.Close; stA = b.High if s < 0 else b.Low
                stp = stA if sv == "A" else ((max(stA, e * (1 + 0.1 * r.atr / 100))) if s < 0 else min(stA, e * (1 - 0.1 * r.atr / 100)))
                risk = abs(stp - e) / e * 100
                if risk <= 0: continue
                n += 1; rec = dict(t=t, date=r.date, side=s, stopv=sv, nth=n, hm=b.hm, e=e, stp=stp, risk=risk)
                last = None
                for lab, tp, rr in EX:
                    px, kx, how = walk(d, k, e, s, stp, tp, rr); ret = s * (px - e) / e * 100
                    rec[lab] = ret / risk * 1000 - 85 * (1000 / (risk / 100)) / 1e5; rec[lab + "_how"] = how
                    if lab == "1.5%": last = kx
                rows.append(rec); busy_until = last
X = pd.DataFrame(rows); X.to_csv(HERE / "orb_ema8_rejection.csv", index=False)
B = pd.read_csv(HERE / "orb_stop_placement.csv")

print("HAND CHECK (3 random first-rejection shorts, stop A):")
for _, r in X[(X.side == -1) & (X.stopv == "A") & (X.nth == 1)].sample(3, random_state=11).iterrows():
    m = read5_official(r.t); m["e8"] = m.Close.ewm(span=8, adjust=False).mean().shift(1); m["e20"] = m.Close.ewm(span=20, adjust=False).mean().shift(1)
    d = m[m.index.normalize() == pd.Timestamp(r.date)]; k = d.index[d.index.strftime("%H:%M") == r.hm][0]; i = d.index.get_loc(k)
    print(f"\n{r.t} {r.date} rejection {r.hm}: entry {r.e:.2f} stop {r.stp:.2f} ({r.risk:.2f}%) -> 1.5%: {r['1.5%_how']} {r['1.5%']:+.0f}")
    print(d.iloc[max(i - 2, 0):i + 4][["Open", "High", "Low", "Close", "e8", "e20"]].round(2).to_string())


def line(lab, x, c):
    if not len(x): return f"| {lab} | 0 |"
    v = x[c]; top = x.groupby("date")[c].sum().sort_values(ascending=False).head(10).index
    return (f"| {lab} | {len(x)} | {(v > 0).mean()*100:.0f}% | {v.mean():+.0f} | {v[~x.date.isin(top)].mean():+.0f} | "
            f"{v[x.date <= '2026-08-14'].mean():+.0f} / {v[x.date >= '2026-08-17'].mean():+.0f} |")


for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    G = X[X.side == sd]; Bs = B[B.side == sd]
    print(f"\n## {sn}: baseline breaks {len(Bs)} | stock-days with a first rejection (any day in the in-play list, broken or not) {G[(G.stopv == 'A') & (G.nth == 1)].date.size} | "
          f"median stop A {G[G.stopv == 'A'].risk.median():.2f}%, B {G[G.stopv == 'B'].risk.median():.2f}%")
    for lab, _, _ in EX:
        print(f"\n{lab} exit\n| version | trades | win % | Rs @1k net | w/o top-10 days | half 1 / half 2 |\n|---|---|---|---|---|---|")
        bc = {"1%": "ATR10_1.0", "1.5%": "ATR10_1.5"}.get(lab)
        if bc: print(line("BASELINE plain ORB break, 10% ATR", Bs, bc))
        for sv, svn in (("A", "stop = bar high"), ("B", "stop = max(bar high, 10% ATR)")):
            print(line(f"FIRST rejection, {svn}", G[(G.stopv == sv) & (G.nth == 1)], lab))
            print(line(f"EVERY rejection, {svn}", G[G.stopv == sv], lab))
