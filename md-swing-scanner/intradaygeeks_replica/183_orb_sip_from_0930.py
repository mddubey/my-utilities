"""In-play ORB short with orders only from 09:30 (user, 2026-10-11: 'first 15 min too jumpy; if it already broke by then, skip it').
Same trades as 175 (5-min, mid rule, 74 days) and 182 (1-min, 18 days, slippage models). TAKE = first break of the 09:15 low happens
at/after 09:30; SKIP = it already broke at 09:20-09:29. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(open(HERE / "182_orb_sip_slippage.py").read().split('\nif __name__ == "__main__":')[0])
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.side < 0) & (A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy(); ND = A.date.nunique()


def rw(lab, g, sm):
    R = g[f"R{sm}mid"]; rk = g[f"r1k{sm}mid"]; w = R > 0
    byd = g.groupby("date")[f"r1k{sm}mid"].sum().sort_values(ascending=False); wo = rk[~g.date.isin(byd.head(10).index)].mean()
    mon = " / ".join(f"{rk[g.mon == k].mean():+.0f}" for k in sorted(g.mon.unique()))
    return (f"| {lab} | {len(g)} | {g.date.nunique()} | {(g[f'o{sm}mid']=='stop').mean()*100:.0f}% | {w.mean()*100:.0f}% | {R[w].mean():+.1f} / {R[~w].mean():+.2f} | "
            f"{R.mean():+.2f} | {rk.mean():+.0f} | {wo:+.0f} | {mon} |")


print(f"## 5-min, 74 days ({S.date.min()}..{S.date.max()}), in-play shorts")
for sm in ("10", "20"):
    print(f"\nstop {sm}% ATR\n| group | trades | days | stopped | win % | avg win / loss R | avg R | Rs @1k net | w/o top-10 days | Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|")
    print(rw("ALL (orders from 09:20)", S, sm)); print(rw("TAKE: break at/after 09:30", S[S.et >= "09:30"], sm)); print(rw("SKIP: broke 09:20-09:29", S[S.et < "09:30"], sm))
X = pd.read_csv(HERE / "orb_sip_1m.csv"); X = X[(X.side < 0) & (X.traded1m == True)]
days = {(t, d): load_day(t, d) for t, d in zip(X.ticker, X.date)}
X["late"] = X.et1m >= "09:30"
rp = []
for _, r in X.iterrows():
    m = days[(r.ticker, r.date)]; f = m[m.hm < "09:20"]; trig = f.Low.min(); rest = m[(m.hm >= "09:20") & (m.hm < "15:15")]; hit = rest[rest.Low < trig]
    b0 = m.loc[hit.index[0]]; rp.append(dict(late=r.late, op=b0.Open < trig, low=(trig - b0.Low) / trig * 100))
rp = pd.DataFrame(rp)
print(f"\n## 1-min, 18 days: {len(X)} trades, {X.late.sum()} break at/after 09:30")
for lab, g in (("broke 09:20-09:29", rp[~rp.late]), ("break at/after 09:30", rp[rp.late])):
    print(f"trigger minute, {lab}: opened past the trigger {g.op.mean()*100:.0f}%, low ran past it median {g.low.median():.2f}% (p90 {g.low.quantile(.9):.2f}%)")
for k in (0.10, 0.20):
    print(f"\nstop {int(k*100)}% ATR | Rs @1k net (avg R) | ideal | SL-M 0.05% both sides | stress 0.15% both sides |\n|---|---|---|---|---|")
    for lab, g in (("ALL", X), ("TAKE: at/after 09:30", X[X.late]), ("SKIP: 09:20-09:29", X[~X.late])):
        cells = []
        for em, ss in ((("ideal", 0), 0), (("slm", 0.05), 0.05), (("slm", 0.15), 0.15)):
            D = pd.DataFrame([z for z in (run(days[(r.ticker, r.date)], r.atr, k, em, ss) for _, r in g.iterrows()) if isinstance(z, dict)])
            cells.append(f"{D.rk.mean():+.0f} ({D.R.mean():+.2f})")
        print(f"| {lab} ({len(g)}) | " + " | ".join(cells) + " |")
