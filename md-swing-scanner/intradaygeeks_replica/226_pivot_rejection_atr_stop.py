"""225 TRADE 1 with a WIDER STOP: level + k x daily ATR (user, 2026-10-15: 'if you sweep for ATR x 0.2 how many SLs would have been
saved and become target'). Same setups as 225 (pivot_rejection_reentry.csv: 5-min rejection at daily/weekly PP-R1-R2 or the daily 8,
first per stock-day, entry = candle close). Stop = max(candle high + 0.05%, level + k x ATR14% of yesterday), k = 0.1 / 0.2 / 0.3
(0.2 = the user's, 0.1 / 0.3 shown around it); exits: 1% target and 2R, else out at the 15:15 close, stop first on a tie.
Report: what happened to the ORIGINAL stops (now target / time / still stopped), net Rs per Rs1 lakh, mean R, by month."""
import sys, importlib.util, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR
COST = 0.085; KS = (0.1, 0.2, 0.3)


def run(args):
    t, g = args
    d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index(); d = d[~d.index.duplicated()]
    tr = pd.concat([d.High - d.Low, (d.High - d.Close.shift()).abs(), (d.Low - d.Close.shift()).abs()], axis=1).max(axis=1)
    atr = (tr.rolling(14).mean() / d.Close * 100).shift(1)
    m = read5_official(t); md = m.index.normalize(); out = []
    for _, r in g.iterrows():
        D = pd.Timestamp(r.date); x = m[md == D]; hm = x.index.strftime("%H:%M").values
        H, L, C = x.High.values, x.Low.values, x.Close.values
        i = np.where(hm == r.time)[0]; lasts = np.where(hm <= "15:10")[0]
        if not len(i) or not len(lasts): continue
        i, last = i[0], lasts[-1]; e = r.entry1; a = atr.get(D, np.nan)
        if not a == a: continue
        rec = dict(ticker=t, date=r.date, why_orig=r.why1, atr=a)
        for k in (0,) + KS:
            stop = r.stop1 if k == 0 else max(r.stop1, r.lvl * (1 + k * a / 100))
            risk = (stop - e) / e * 100
            for nm, tg in (("t1", e * 0.99), ("r2", e - 2 * (stop - e))):
                res = None
                for j in range(i + 1, last + 1):
                    if H[j] >= stop: res = (-risk, "stop"); break
                    if L[j] <= tg: res = ((e - tg) / e * 100, "target"); break
                if res is None: res = ((e - C[last]) / e * 100, "time")
                rec[f"k{k}_{nm}_ret"], rec[f"k{k}_{nm}_why"] = res
            rec[f"k{k}_risk"] = risk
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    X = pd.read_csv(HERE / "pivot_rejection_reentry.csv")
    with Pool(6) as p: R = pd.DataFrame([r for rr in p.map(run, list(X.groupby("ticker")), chunksize=10) for r in rr])
    R.to_csv(HERE / "pivot_rejection_atr_stop.csv", index=False)
    print(f"setups {len(R)} (of {len(X)} in 225; dropped = no ATR)")
    print("\n### Net Rs per Rs1 lakh, all setups\n| stop | median stop | 1% target: stopped / target / time | net | mean R | 2R target: stopped / target / time | net | mean R |\n|---|---|---|---|---|---|---|---|")
    for k in (0,) + KS:
        lab = "candle high (225)" if k == 0 else f"level + {k} x ATR"
        cells = [lab, f"{R[f'k{k}_risk'].median():.2f}%"]
        for nm in ("t1", "r2"):
            w = R[f"k{k}_{nm}_why"]; ret = R[f"k{k}_{nm}_ret"]
            cells += [f"{(w=='stop').mean()*100:.0f} / {(w=='target').mean()*100:.0f} / {(w=='time').mean()*100:.0f}%",
                      f"{(ret.mean()-COST)*1000:+.0f}", f"{(ret / R[f'k{k}_risk']).mean():+.2f}"]
        print("| " + " | ".join(cells) + " |")
    st = R[R.k0_t1_why == "stop"]
    print(f"\n### What happened to the {len(st)} ORIGINAL stops (1% target)\n| stop | still stopped | now TARGET | now out 15:15 (time) | net of these trades |\n|---|---|---|---|---|")
    for k in KS:
        w = st[f"k{k}_t1_why"]
        print(f"| level + {k} x ATR | {(w=='stop').sum()} ({(w=='stop').mean()*100:.0f}%) | {(w=='target').sum()} ({(w=='target').mean()*100:.0f}%) | "
              f"{(w=='time').sum()} ({(w=='time').mean()*100:.0f}%) | {(st[f'k{k}_t1_ret'].mean()-COST)*1000:+.0f} (was {(st.k0_t1_ret.mean()-COST)*1000:+.0f}) |")
    print("\n### By month, net Rs @1L, 1% target\n| month | n | candle high | " + " | ".join(f"+{k} ATR" for k in KS) + " |\n|---|---|---|" + "---|" * len(KS))
    for mo, g in R.groupby(R.date.str[:7]):
        print(f"| {mo} | {len(g)} | " + " | ".join(f"{(g[f'k{k}_t1_ret'].mean()-COST)*1000:+.0f}" for k in (0,) + KS) + " |")
    print("\nHAND CHECK (3 original stops that became targets at 0.2 ATR):")
    print(R[(R.k0_t1_why == "stop") & (R["k0.2_t1_why"] == "target")].sample(3, random_state=2)[["ticker", "date", "atr", "k0_risk", "k0.2_risk"]].round(2).to_string(index=False))
