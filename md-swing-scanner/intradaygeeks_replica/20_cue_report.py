import pandas as pd, numpy as np
from pathlib import Path
HERE = Path(__file__).resolve().parent
def cats(R):
    s = np.where(R.side == "long", 1, -1)
    t = R.bar_ts.dt.strftime("%H:%M")
    C = {}
    C["nifty_with"] = pd.Series(np.where(R.nifty_so.isna(), "na", np.where(R.nifty_so * s > 0, "with", "against")), index=R.index)
    C["tod"] = pd.Series(np.select([t < "11:30", t < "13:30", t < "14:30"], ["a 10:15-11:30", "b 11:30-13:30", "c 13:30-14:30"], "d 14:30+"), index=R.index)
    C["rvol"] = pd.cut(R.rvol, [0, 1, 2, np.inf], labels=["<1", "1-2", ">=2"]).astype(str)
    C["atr_terc"] = pd.qcut(R.atrp, 3, labels=["low", "mid", "high"]).astype(str)
    C["vwap_with"] = R.vwap_with.map({True: "with", False: "against"})
    C["rs_with"] = pd.Series(np.where(((R.stock_so - R.nifty_so) * s) > 0, "with", "against"), index=R.index).where(R.nifty_so.notna(), "na")
    C["sector_with"] = pd.Series(np.where(R.sector_so * s > 0, "with", "against"), index=R.index).where(R.sector_so.notna(), "na")
    C["gap"] = pd.cut(R.gap_s, [-np.inf, -0.5, 0.5, np.inf], labels=["against<-0.5", "flat", "with>+0.5"]).astype(str)
    C["rsi_with"] = pd.Series(np.where((R.rsi1h - 50) * s >= 0, "with", "against"), index=R.index)
    return C
def line(x, lab, per):
    if len(x) < 100: return f"| {lab} | {len(x)} | too few | | | | |"
    y = x.groupby(per).ret.mean()
    return (f"| {lab} | {len(x)} | {(x.R>0).mean()*100:.0f} | {x.ret.mean():+.3f} | {x.ret.median():+.3f} | {x.R.mean():+.2f} | "
            + " / ".join(f"{v:+.2f}" for v in y) + " |")
for nm, perlab in (("5m_held", "month"), ("1h_close", "year")):
    R = pd.read_csv(HERE / f"cues_{nm}.csv", parse_dates=["date", "bar_ts"])
    per = R.date.dt.month if perlab == "month" else R.date.dt.year
    print(f"\n### {nm}  (periods by {perlab})\n| cue / group | n | win% | mean% | med% | meanR | by {perlab} mean% |\n|---|---|---|---|---|---|---|")
    print(line(R, "BASELINE", per))
    for c, ser in cats(R).items():
        for v in sorted(ser.unique()):
            if v in ("na", "nan"): continue
            m = ser == v
            print(line(R[m], f"{c}: {v}", per[m]))
