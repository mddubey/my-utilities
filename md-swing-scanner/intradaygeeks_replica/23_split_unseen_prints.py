"""Split 22's 'possibly stopped by an unseen print' trades by WHERE Yahoo's own day extreme fell.
pre : Yahoo's day extreme occurred at/before entry -> NSE's extra paise most likely belong to that pre-entry wick
      (stop LEVEL understated, trade itself probably fine).  post: Yahoo's day extreme came after entry -> the unseen
      print most likely came after entry -> treat as stopped. Gives a middle estimate between the two bounds."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
N = pd.read_csv(HERE / "nse_bhav_jun_sep26.csv", dtype={"date": str}).set_index(["date", "ticker"])
R = pd.read_csv(HERE / "pin_rejection_held_results.csv", parse_dates=["date"]); R = R[R.variant == "held"].copy()
R["d"] = R.date.dt.strftime("%Y%m%d")
rows = []
for t, g in R.groupby("ticker"):
    x = pd.read_csv(HERE.parent / "intraday_cache" / f"{t}.csv", index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for r in g.itertuples():
        day = x[x.index.strftime("%Y%m%d") == r.d]
        if day.empty or (r.d, t) not in N.index: continue
        nh, nl, nc = N.loc[(r.d, t), ["high", "low", "close"]]
        if abs(day.Close.iloc[-1] / nc - 1) > 0.02: continue
        s = 1 if r.side == "long" else -1
        stop = r.entry - s * r.stop_rs
        et = pd.Timestamp(f"{r.d[:4]}-{r.d[4:6]}-{r.d[6:]} {r.entry_time}")
        if s == -1: yext, t_ext, nse_beyond = day.High.max(), day.High.idxmax(), (nh >= stop) and (nh > day.High.max())
        else:       yext, t_ext, nse_beyond = day.Low.min(), day.Low.idxmin(), (nl <= stop) and (nl < day.Low.min())
        risk = nse_beyond and r.exit != "stop"
        rows.append(dict(ret=r.ret, stop_pct=r.stop_pct, exit=r.exit, at_risk=risk, when=("post" if t_ext > et else "pre") if risk else ""))
D = pd.DataFrame(rows)
print(f"trades {len(D)} | at risk {D.at_risk.sum()} -> pre-entry extreme {int((D.when=='pre').sum())}, post-entry extreme {int((D.when=='post').sum())}")
mid = D.ret.where(D.when != "post", -D.stop_pct)
worst = D.ret.where(~D.at_risk, -D.stop_pct)
print(f"mean %: as backtested {D.ret.mean():+.3f} | middle (post-entry ones stopped) {mid.mean():+.3f} | worst case {worst.mean():+.3f}")
print("at-risk 'post' trades by original exit:", D[D.when == "post"].exit.value_counts().to_dict())
