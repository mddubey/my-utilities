"""Does the user's READ add what the candle alone lacks? (user, 2026-10-12, after 208 failed: 'all three trades showed the
symptoms of going down -- all flukes?'). Two things the user saw on INOXINDIA / TIMEX that 208 ignored. Spec fixed before running:
  Population: 208's setups (half_candle_above.csv), same exits (1% target / hold to 15:15), same net (Rs @1L, -85).
  MARKET: Nifty below its own day open (official daily open) at entry -- 30m set: Nifty 5-min close of the 10:40 bar
    (entry 10:45; Nifty 5-min exists from 2026-07-10, June days dropped from this split); 1H set: Nifty hourly 10:15 bar close
    (entry 11:15).
  LEVEL: the candle high within 0.2% of yesterday's high OR the daily pivot (yesterday's (H+L+C)/3), either side.
  Report per group (RED_BELOW = current rule, ABOVE_WICK = the user's shape): baseline / market yes-no / level yes-no / both,
  n, net for both exits, w/o top-10, by month (30m) and year (1H).
  Pass for either condition = ABOVE_WICK with the condition positive in BOTH sets and both exits, better than without it,
  not carried by the top 10."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import DAILY_DIR

A = pd.read_csv(HERE / "half_candle_above.csv", parse_dates=["day"])
ND = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index()
ix = HERE.parent / "data" / "index_intraday"
def idx(f):
    x = pd.read_csv(ix / f, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); return x
n5 = idx("_NIFTY_5m_60d.csv"); n1 = idx("_NIFTY_1h.csv")
n5c = n5[n5.index.strftime("%H:%M") == "10:40"].Close; n5c.index = n5c.index.normalize()
n1c = n1[n1.index.strftime("%H:%M") == "10:15"].Close; n1c.index = n1c.index.normalize()
nop = ND.Open
A["nifty_at_entry"] = np.where(A.set == "30m", A.day.map(n5c), A.day.map(n1c))
A["mkt"] = np.where(A.nifty_at_entry.isna(), np.nan, (A.nifty_at_entry < A.day.map(nop)).astype(float))

# yesterday's high and pivot per ticker
lv = {}
for t in A.t.unique():
    d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index()
    lv[t] = pd.DataFrame({"yh": d.High.shift(1), "pp": ((d.High + d.Low + d.Close) / 3).shift(1)})
yh = np.array([lv[t].yh.get(d, np.nan) for t, d in zip(A.t, A.day)]); pp = np.array([lv[t].pp.get(d, np.nan) for t, d in zip(A.t, A.day)])
A["lvl"] = ((np.abs(A.hi / yh - 1) <= 0.002) | (np.abs(A.hi / pp - 1) <= 0.002)).astype(float)
A.loc[np.isnan(yh) & np.isnan(pp), "lvl"] = np.nan
A["month"] = A.day.dt.strftime("%Y-%m"); A["year"] = A.day.dt.year


def st(x, col):
    net = (x.c - x[col]) / x.c * 100 * 1000 - 85
    return len(x), net.mean(), (net.sort_values(ascending=False).iloc[10:].mean() if len(x) > 20 else np.nan)


print("HAND CHECK 2026-10-12:"); print(A[(A.day == "2026-10-12") & A.t.isin(["INOXINDIA", "TIMEX"])][["set", "t", "grp", "hi", "nifty_at_entry", "mkt", "lvl"]].to_string(index=False))
print("Nifty open 2026-10-12:", nop.get(pd.Timestamp("2026-10-12")))
for s in ("30m", "1H"):
    S = A[A.set == s]
    if s == "30m": S = S[S.mkt.notna()]
    print(f"\n===== {s} set {S.day.min():%Y-%m-%d} .. {S.day.max():%Y-%m-%d} | share of setup days with Nifty below its open: {S.groupby('day').mkt.first().mean():.0%} =====")
    rows = []
    for g in ("RED_BELOW", "ABOVE_WICK"):
        G = S[S.grp == g]
        for lab, x in (("baseline", G), ("Nifty below open", G[G.mkt == 1]), ("Nifty NOT below open", G[G.mkt == 0]),
                       ("high at yday high / pivot", G[G.lvl == 1]), ("high NOT at a level", G[G.lvl == 0]),
                       ("BOTH", G[(G.mkt == 1) & (G.lvl == 1)])):
            n, tn, tw = st(x, "xt"); _, hn, hw = st(x, "xh")
            rows.append(dict(group=g, cut=lab, n=n, target_net=round(tn), target_wo_top10=round(tw) if tw == tw else None,
                             hold_net=round(hn), hold_wo_top10=round(hw) if hw == hw else None))
    print(pd.DataFrame(rows).to_string(index=False))
    per = "month" if s == "30m" else "year"
    for g in ("RED_BELOW", "ABOVE_WICK"):
        G = S[S.grp == g]; out = []
        for lab, x in (("baseline", G), ("Nifty below open", G[G.mkt == 1]), ("Nifty NOT below", G[G.mkt == 0]), ("at level", G[G.lvl == 1]), ("not at level", G[G.lvl == 0])):
            d = {"cut": lab}
            for k, y in x.groupby(per): n, tn, _ = st(y, "xt"); d[str(k)] = f"{tn:+.0f} ({n})"
            out.append(d)
        print(f"\n{g}, 1% target net by {per}:"); print(pd.DataFrame(out).to_string(index=False))
