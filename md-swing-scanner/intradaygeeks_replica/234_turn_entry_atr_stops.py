"""ATR STOPS on the user's turn entry (user, 2026-10-17: 'can we look at some ATR related stops'). Spec fixed before running:
  Trades: 233's FAIR group, unchanged -- v1's stock-days (liquid, >= Rs100, ATR >= 2, gap -0.25..+0.5, uptrend, branch A / B), daily 8
    not in the path, turn 0.1% below the touch high (same 891 entries, same times and prices). Only the stop and target change.
  Stops: FIXED 0.5% (233's) | entry + k x daily ATR% | touch high + k x ATR, k = 0.10 / 0.15 / 0.20 / 0.25.
  Targets: T1 = 1% (E1) | T2 = max(1%, 0.35 x ATR) (E2). Else out at the 15:15 close; stop first on a tie; walk from the bar after entry.
  Report net Rs per Rs1 lakh and per Rs1k risk, target / stall / stop, median stop; by month; top-10 days removed; ATR 2-3% vs >= 3%;
  stop map: the FIXED-0.5% stops that survive each ATR stop and reach the target."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
COST = 0.085; KS = (0.10, 0.15, 0.20, 0.25)


def stops(r):
    s = {"fixed0.5": r.entry * 1.005}
    for k in KS:
        s[f"e+{k:.2f}atr"] = r.entry * (1 + k * r.atr / 100); s[f"hi+{k:.2f}atr"] = r.hi * (1 + k * r.atr / 100)
    return s


def run(args):
    t, g = args
    m = read5_official(t); md = m.index.normalize(); out = []
    for _, r in g.iterrows():
        x = m[md == pd.Timestamp(r.date)]; hm = x.index.strftime("%H:%M").values
        H, L, C = x.High.values, x.Low.values, x.Close.values
        j = np.where(hm == r.t_entry)[0]; lasts = np.where(hm <= "15:10")[0]
        if not len(j) or not len(lasts): continue
        j, last = j[0], lasts[-1]; rec = dict(ticker=t, date=r.date, atr=r.atr, entry=r.entry)
        for sn, s in stops(r).items():
            for tn, tp in (("T1", 1.0), ("T2", max(1.0, 0.35 * r.atr))):
                tg = r.entry * (1 - tp / 100); res = None
                for k in range(j + 1, last + 1):
                    if H[k] >= s: res = ((r.entry - s) / r.entry * 100, "stop"); break
                    if L[k] <= tg: res = (tp, "target"); break
                if res is None: res = ((r.entry - C[last]) / r.entry * 100, "stall")
                rec[f"{sn}|{tn}|ret"], rec[f"{sn}|{tn}|why"] = res
            rec[f"{sn}|risk"] = (s - r.entry) / r.entry * 100
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    A = pd.read_csv(HERE / "v1_turn_entry.csv")
    F = A[(A.liq >= 15) & (A.pc >= 100) & (A.atr >= 2) & (A.gap > -0.25) & (A.gap <= 0.5) & (A.X == 0.001)]
    V = F[F.up & (((F.ov >= -0.5) & (F.ov < 0)) | ((F.ov >= 0) & (F.atr >= 3))) & ~F.in_path]
    with Pool(6) as p: R = pd.DataFrame([r for rr in p.map(run, list(V.groupby("ticker")), chunksize=5) for r in rr])
    R.to_csv(HERE / "turn_entry_atr_stops.csv", index=False)
    print(f"trades {len(R)} (233 fair group {len(V)}); median ATR {R.atr.median():.2f}%")
    SN = ["fixed0.5"] + [f"e+{k:.2f}atr" for k in KS] + [f"hi+{k:.2f}atr" for k in KS]

    def cell(x, sn, tn):
        if not len(x): return "0 | | | |"
        r = x[f"{sn}|{tn}|ret"]; w = x[f"{sn}|{tn}|why"]; rk = x[f"{sn}|risk"]
        return f"{len(x)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f}% | {rk.median():.2f}% | {(r.mean()-COST)*1000:+.0f} | {((r-COST)/rk).mean()*1000:+.0f}"
    for tn, tl in (("T1", "1% target"), ("T2", "max(1%, 0.35 x ATR) target")):
        top10 = R.groupby("date")[f"fixed0.5|{tn}|ret"].sum().nlargest(10).index
        print(f"\n### {tl}\n| stop | n | target / stall / stop | med stop | net Rs @1L | Rs @1k | top-10 days removed @1L | ATR 2-3% @1L (n) | ATR >= 3% @1L (n) | months 06 / 07 / 08 / 09 / 10 @1L |\n|---|---|---|---|---|---|---|---|---|---|")
        for sn in SN:
            r = R[f"{sn}|{tn}|ret"]; lo = R.atr < 3
            mo = " / ".join(f"{(g[f'{sn}|{tn}|ret'].mean()-COST)*1000:+.0f}" for _, g in R.groupby(R.date.str[:7]))
            print(f"| {sn} | {cell(R, sn, tn)} | {(R[~R.date.isin(top10)][f'{sn}|{tn}|ret'].mean()-COST)*1000:+.0f} | "
                  f"{(r[lo].mean()-COST)*1000:+.0f} ({lo.sum()}) | {(r[~lo].mean()-COST)*1000:+.0f} ({(~lo).sum()}) | {mo} |")
    st = R[R["fixed0.5|T1|why"] == "stop"]
    print(f"\n### Stop map: the {len(st)} trades stopped at FIXED 0.5% (1% target)\n| ATR stop | still stopped | now TARGET | now stall | net of these trades @1L (was {(st['fixed0.5|T1|ret'].mean()-COST)*1000:+.0f}) |\n|---|---|---|---|---|")
    for sn in SN[1:]:
        w = st[f"{sn}|T1|why"]
        print(f"| {sn} | {(w=='stop').mean()*100:.0f}% | {(w=='target').mean()*100:.0f}% | {(w=='stall').mean()*100:.0f}% | {(st[f'{sn}|T1|ret'].mean()-COST)*1000:+.0f} |")
    print("\n3 random trades (stop prices):"); s = R.sample(3, random_state=4)
    for _, r in s.iterrows(): print(f"  {r.ticker} {r.date} entry {r.entry:.2f} ATR {r.atr:.2f}% -> e+0.15atr risk {r['e+0.15atr|risk']:.2f}% {r['e+0.15atr|T1|why']}, fixed {r['fixed0.5|T1|why']}")
