"""In-play ORB by 30-min entry window, and WHAT MOVE a late break is (user, 2026-10-12: 'if the first 5-min candle isn't broken for 1
hour or more, what type of move am I getting into?'). DESCRIPTIVE. 175's in-play trades, paper rules (10% ATR stop, hold to 15:15,
5-min mid rule), shorts + longs. Per 30-min entry window: trades, stopped, win %, avg R, Rs @1k net. Move type before entry (shorts;
mirrored for longs): did price first take out the OTHER side of the 09:15 candle (= the opening direction failed, a reversal day),
how far it had gone the other way (max excursion beyond the 09:15 high, in ATR units), and the range traded from 09:20 to entry
in ATR units (a quiet drift vs a big swing). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy(); rows = []
for t, g in S.groupby("ticker"):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m["hm"] = m.index.strftime("%H:%M")
    for ix, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]; f = d.iloc[0]; s = int(r.side)
        pre = d[(d.hm >= "09:20") & (d.hm < r.et)]; atr_px = r.atr / 100 * f.Open
        other = f.High if s < 0 else f.Low   # the opposite side of the 09:15 candle
        if len(pre):
            took_other = (pre.High.max() > other) if s < 0 else (pre.Low.min() < other)
            beyond = max(0.0, (pre.High.max() - other) if s < 0 else (other - pre.Low.min())) / atr_px
            rng = (pre.High.max() - pre.Low.min()) / atr_px
        else: took_other, beyond, rng = False, 0.0, 0.0
        rows.append(dict(ix=ix, took_other=took_other, beyond=beyond, rng=rng))
X = S.join(pd.DataFrame(rows).set_index("ix"))
W = [("09:20-09:29", "09:20", "09:30"), ("09:30-09:59", "09:30", "10:00"), ("10:00-10:29", "10:00", "10:30"), ("10:30-10:59", "10:30", "11:00"),
     ("11:00-11:59", "11:00", "12:00"), ("12:00-13:29", "12:00", "13:30"), ("13:30-15:10", "13:30", "15:15")]
for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
    print(f"\n## {sn}, entry window (all in-play trades; the 09:30 rule = the rows from 09:30)\n| entry window | trades | stopped | win % | avg R | Rs @1k net | +5R trades | price first broke the OTHER side of the 09:15 candle | how far beyond it (median, x ATR) | range traded before entry (median, x ATR) |\n|---|---|---|---|---|---|---|---|---|---|")
    for lab, a, b in W:
        g = X[(X.side == sd) & (X.et >= a) & (X.et < b)]
        if len(g) == 0: continue
        print(f"| {lab} | {len(g)} | {(g.o10mid == 'stop').mean()*100:.0f}% | {(g.R10mid > 0).mean()*100:.0f}% | {g.R10mid.mean():+.2f} | {g.r1k10mid.mean():+.0f} | {(g.R10mid >= 5).sum()} | "
              f"{g.took_other.mean()*100:.0f}% | {g.beyond[g.took_other].median() if g.took_other.any() else 0:.2f} | {g.rng.median():.2f} |")
    for lab, msk in (("from 09:30, opposite side NOT broken first", (X.et >= "09:30") & ~X.took_other), ("from 09:30, opposite side broken first (opening move failed)", (X.et >= "09:30") & X.took_other)):
        g = X[(X.side == sd) & msk]
        print(f"| **{lab}** | {len(g)} | {(g.o10mid == 'stop').mean()*100:.0f}% | {(g.R10mid > 0).mean()*100:.0f}% | {g.R10mid.mean():+.2f} | {g.r1k10mid.mean():+.0f} | {(g.R10mid >= 5).sum()} | | | |")
