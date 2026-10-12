"""DOUBLE TOP inside the half-hour candle (user, 2026-10-12, from live TIMEX: the 10:15-10:45 candle hit 724.00 at 10:25 AND 10:30,
723.70 at 10:35, then fell to 715.05 by 11:10). Spec fixed before running:
  Population: script 208's 30m setups (half_candle_above.csv: the 10:15-10:45 candle crosses the 1H EMA34; liquid, >= Rs100,
  ATR >= 2%), all four candle groups; same trade (short at the candle close, stop = candle high), same exits (1% target / hold
  to 15:15), same net (Rs @1L, -85).
  DOUBLE TOP (main) = at least 2 of the candle's six 5-min bars have a high within 0.05% of the candle high.
    Tolerance robustness, declared now: 0.03% and 0.10%.
    SEPARATED variant (a real dip between the touches): two touching bars with a bar between them whose high is >= 0.10% below
    the candle high.
  Pre-check (by hand, before running): TIMEX 724.00 / 724.00 / 723.70 -> double top (3 touches; separated: no, the bar between
  is 724.00); INOXINDIA 2082.8 / 2083.2 -> double top at 0.05% too (adjacent bars of a rising push, not a rejection), separated: no.
  ONLY the 30-min set can test this: the 3-year set has no 5-min bars, so the usual both-sets rule cannot be met -- at best a lead.
  Pass (as a lead) = double top better than no double top in the user's group and in all groups, positive in both exits,
  not carried by the top 10, not one month, shuffle p < 0.05."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR

A = pd.read_csv(HERE / "half_candle_above.csv", parse_dates=["day"]); A = A[A.set == "30m"].reset_index(drop=True)
feat = {}
for k, (t, g) in enumerate(A.groupby("t"), 1):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m = m[~m.index.duplicated()]
    for i, r in g.iterrows():
        b = m[(m.index >= r.day + pd.Timedelta("10h15min")) & (m.index < r.day + pd.Timedelta("10h45min"))].High.values
        H = b.max(); d = (H - b) / H * 100
        f = {f"dt{tol}": int((d <= tol).sum() >= 2) for tol in (0.03, 0.05, 0.10)}
        touch = np.where(d <= 0.05)[0]
        f["sep"] = int(any(((d[a + 1:c] >= 0.10).any()) for a in touch for c in touch if c > a + 1))
        f["touches"] = int((d <= 0.05).sum()); feat[i] = f
    if k % 200 == 0: print(f"  {k} tickers", flush=True)
A = A.join(pd.DataFrame.from_dict(feat, orient="index"))
A["month"] = A.day.dt.strftime("%Y-%m")


def st(x, col):
    net = (x.c - x[col]) / x.c * 100 * 1000 - 85
    return len(x), net.mean(), (net.sort_values(ascending=False).iloc[10:].mean() if len(x) > 20 else np.nan), (x[col] == x.hi).mean() * 100


print("HAND CHECK 2026-10-12:"); print(A[(A.day == "2026-10-12") & A.t.isin(["INOXINDIA", "TIMEX"])][["t", "grp", "hi", "touches", "dt0.03", "dt0.05", "dt0.1", "sep"]].to_string(index=False))
pd.set_option("display.width", 250)
rows = []
for g in ("ALL", "RED_BELOW", "GREEN_BELOW", "ABOVE_WICK", "ABOVE_NOWICK"):
    G = A if g == "ALL" else A[A.grp == g]
    for lab, x in (("baseline", G), ("double top 0.05%", G[G["dt0.05"] == 1]), ("no double top", G[G["dt0.05"] == 0]),
                   ("double top 0.03%", G[G["dt0.03"] == 1]), ("double top 0.10%", G[G["dt0.1"] == 1]), ("separated", G[G.sep == 1])):
        n, tn, tw, sp = st(x, "xt"); _, hn, hw, _ = st(x, "xh")
        rows.append(dict(group=g, cut=lab, n=n, stopped=round(sp), target_net=round(tn), t_wo_top10=None if tw != tw else round(tw),
                         hold_net=round(hn), h_wo_top10=None if hw != hw else round(hw)))
print(pd.DataFrame(rows).to_string(index=False))
for g in ("ALL", "ABOVE_WICK"):
    G = A if g == "ALL" else A[A.grp == g]; out = []
    for lab, x in (("baseline", G), ("double top 0.05%", G[G["dt0.05"] == 1]), ("no double top", G[G["dt0.05"] == 0])):
        d = {"cut": lab}
        for k, y in x.groupby("month"): n, tn, _, _ = st(y, "xt"); d[k] = f"{tn:+.0f} ({n})"
        out.append(d)
    print(f"\n{g}, 1% target net by month:"); print(pd.DataFrame(out).to_string(index=False))
for g in ("ALL", "ABOVE_WICK"):
    G = A if g == "ALL" else A[A.grp == g]
    net = ((G.c - G.xt) / G.c * 100 * 1000 - 85).values; lab = (G["dt0.05"] == 1).values
    obs = net[lab].mean() - net[~lab].mean(); rng = np.random.default_rng(0)
    sh = np.array([net[p].mean() - net[~p].mean() for p in (rng.permutation(lab) for _ in range(5000))])
    print(f"shuffle {g} double top - none (1% target): {obs:+.0f}, p = {np.mean(np.abs(sh) >= abs(obs)):.3f}")
