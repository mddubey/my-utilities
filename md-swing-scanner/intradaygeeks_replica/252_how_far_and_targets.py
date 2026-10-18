"""HOW FAR DO THEY GO, AND IS 1% THE RIGHT TARGET? (user, 2026-10-18). Chat only. The hourly 34 rejection as the scan trades it (245's X, 728 setups; one a
day = highest ATR). Part 1: max favourable move after the 11:15 entry until the stop or the exit (same engine: out after 5 hourly bars / the day's last bar),
in % and in ATRs. Part 2: targets 1% (now) / 1.5% / 2% / 0.3, 0.4, 0.5 x daily ATR / none (hold to the exit), same stop. Net @1L and @1k risk, by year."""
import sys, os, io, contextlib, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE); sys.path.insert(0, os.path.dirname(HERE))
import numpy as np, pandas as pd
from data.paths import INTRADAY_60M_DIR
sys.argv = ["x"]
with contextlib.redirect_stdout(io.StringIO()): G = runpy.run_path("245_hourly34_stats.py")
X = G["X"]; N = G["G"]["N"].reset_index(drop=True); cache = G["G"]["cache"]
def run(r, stop, tgt_pct):
    h = cache.get(r.ticker)
    if h is None:
        h = pd.read_csv(INTRADAY_60M_DIR / f"{r.ticker}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); h = h[~h.index.duplicated()].sort_index(); cache[r.ticker] = h
    H, L, C, T = h.High.values, h.Low.values, h.Close.values, h.index; day = T.normalize()
    i = h.index.get_loc(pd.Timestamp(f"{str(r.date)[:10]} 10:15")); tg = r.entry * (1 - tgt_pct / 100) if tgt_pct else -1; px, o = None, "stall"; lowest = r.entry
    for j in range(i + 1, len(C)):
        if day[j] != day[i]: px = C[j - 1]; break
        if H[j] >= stop: px, o = stop, "stop"; break
        lowest = min(lowest, L[j])
        if tgt_pct and L[j] <= tg: px, o = tg, "target"; break
        if j - i >= 5 or j + 1 >= len(C) or day[j + 1] != day[i]: px = C[j]; break
    ret = (r.entry - px) / r.entry * 100; risk = (stop / r.entry - 1) * 100
    return ret * 1000 - 85, (ret - 0.085) / risk * 1000, o, (r.entry / lowest - 1) * 100
rows = []
TG = {"1% (now)": lambda r: 1.0, "1.5%": lambda r: 1.5, "2%": lambda r: 2.0, "0.3 x ATR": lambda r: 0.3 * r.atrp, "0.4 x ATR": lambda r: 0.4 * r.atrp,
      "0.5 x ATR": lambda r: 0.5 * r.atrp, "no target (hold to exit)": lambda r: None}
for idx, x in X.iterrows():
    r = N.loc[idx]; stop = r.entry * (1 + x.u_risk / 100); rec = dict(date=x.date, yr=x.yr, atrp=r.atrp)
    for k, f in TG.items():
        a, b, o, mfe = run(r, stop, f(r)); rec[f"{k}|1L"], rec[f"{k}|1k"], rec[f"{k}|o"] = a, b, o
        if k.startswith("no target"): rec["mfe"] = mfe
    rows.append(rec)
R = pd.DataFrame(rows); R["mfe_atr"] = R.mfe / R.atrp
O = R.sort_values(["date", "atrp"], ascending=[True, False]).drop_duplicates("date")
assert abs(R["1% (now)|1L"].mean() - X.rs1L.mean()) < 1, "1% must reproduce 245"
for lab, S in (("ALL SETUPS", R), ("ONE A DAY", O)):
    q = S.mfe.quantile([.25, .5, .75, .9]); qa = S.mfe_atr.quantile([.25, .5, .75, .9])
    print(f"\n### {lab} ({len(S)}): best move in your favour after entry (before the stop / exit)")
    print(f"  in %:    25% of trades < {q[.25]:.2f}% | median {q[.5]:.2f}% | 75% < {q[.75]:.2f}% | 90% < {q[.9]:.2f}%  | reached 1%: {(S.mfe>=1).mean()*100:.0f}%, 1.5%: {(S.mfe>=1.5).mean()*100:.0f}%, 2%: {(S.mfe>=2).mean()*100:.0f}%")
    print(f"  in ATRs: 25% < {qa[.25]:.2f} | median {qa[.5]:.2f} | 75% < {qa[.75]:.2f} | 90% < {qa[.9]:.2f}")
    print("| target | target / stall / stop | net @1L | net @1k | @1k 2024 / 2025 / 2026 |\n|---|---|---|---|---|")
    for k in TG:
        o = S[f"{k}|o"]; print(f"| {k} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f}% | {S[f'{k}|1L'].mean():+.0f} | {S[f'{k}|1k'].mean():+.0f} | " + " / ".join(f"{S[S.yr == y][f'{k}|1k'].mean():+.0f}" for y in ("2024", "2025", "2026")) + " |")
