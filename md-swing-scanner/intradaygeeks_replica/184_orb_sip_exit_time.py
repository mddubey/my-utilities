"""When does the in-play ORB short stop paying? (user, 2026-10-11: 'do we need to wait till 15:15?'; time exits declared before
running.) 175's in-play shorts (5-min, mid entry-bar rule, 74 days), all and the 09:30-onward version (183). Stop 10% / 20% of ATR live
all the time; exit at the OPEN of the 10:30 / 11:15 / 12:15 / 13:15 / 14:15 / 15:15 bar if not stopped. Also: time of the day's low after
entry on trades that ended positive at 15:15, and the average open (unrealised) R of still-open trades by clock time. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR
EXITS = ["10:30", "11:15", "12:15", "13:15", "14:15", "15:15"]
A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
S = A[(A.side < 0) & (A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy()
rows = []
for t, g in S.groupby("ticker"):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m["hm"] = m.index.strftime("%H:%M")
    for _, r in g.iterrows():
        d = m[m.index.normalize() == pd.Timestamp(r.date)]; f = d.iloc[0]; lvl = f.Low
        b0 = d[d.hm == r.et].iloc[0]; e = r.e; after = d[d.hm > r.et]
        rec = dict(date=r.date, mon=r.date[:7], late=r.et >= "09:30")
        for sm in (0.1, 0.2):
            sp = sm * r.atr; stp = e * (1 + sp / 100); pos = 1000 / (sp / 100)
            stopped_at = None
            if (b0.Open <= lvl and b0.High >= stp) or b0.Close >= stp: stopped_at = r.et
            else:
                for _, b in after.iterrows():
                    if b.hm >= "15:15": break
                    if b.High >= stp: stopped_at = b.hm; break
            for x in EXITS:
                if r.et >= x:   # entered at/after this exit time -> not a trade under 'out by x' (fix 2026-10-11: first run priced exits before entry)
                    rec[f"R{int(sm*100)}_{x}"] = np.nan; rec[f"k{int(sm*100)}_{x}"] = np.nan; continue
                if stopped_at is not None and stopped_at < x: px = stp
                else:
                    bx = d[d.hm == x]; px = bx.Open.iloc[0] if len(bx) else d.Close.iloc[-1]
                ret = (e - px) / e * 100
                rec[f"R{int(sm*100)}_{x}"] = ret / sp; rec[f"k{int(sm*100)}_{x}"] = ret / 100 * pos - 85 * pos / 1e5
            rec[f"stopat{int(sm*100)}"] = stopped_at
        w = d[(d.hm > r.et) & (d.hm < "15:15")]
        rec["low_time"] = w.Low.idxmin().strftime("%H:%M") if len(w) else None
        rows.append(rec)
R = pd.DataFrame(rows)
for sm in ("10", "20"):
    for lab, G in (("ALL in-play shorts", R), ("orders from 09:30 only", R[R.late])):
        print(f"\n## stop {sm}% ATR, {lab} ({len(G)} trades)\n| exit at | trades | avg R | Rs @1k net | win % | w/o top-10 days | Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|")
        for x in EXITS:
            GG = G[G[f"k{sm}_{x}"].notna()]; k = GG[f"k{sm}_{x}"]; Rr = GG[f"R{sm}_{x}"]; byd = GG.groupby("date")[f"k{sm}_{x}"].sum().sort_values(ascending=False)
            wo = k[~GG.date.isin(byd.head(10).index)].mean(); mon = " / ".join(f"{k[GG.mon == mm].mean():+.0f}" for mm in sorted(GG.mon.unique()))
            print(f"| {x} | {len(GG)} | {Rr.mean():+.2f} | {k.mean():+.0f} | {(Rr > 0).mean()*100:.0f}% | {wo:+.0f} | {mon} |")
W = R[R["R20_15:15"] > 0]
print(f"\ntime of the day's low after entry, trades positive at 15:15 (20% ATR stop; {len(W)} trades): " +
      " | ".join(f"by {x}: {(W.low_time < x).mean()*100:.0f}%" for x in ("10:30", "11:15", "12:15", "13:15", "14:15", "15:15")))
