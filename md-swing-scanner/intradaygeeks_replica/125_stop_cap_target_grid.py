"""Stop cap x target grid on the realistic stack (user, 2026-10-09: 'are we filtering out good trades with the 0.5% cap?').
Spec fixed before running. Population: script 124's X (stack + Nifty > 200d + gap -0.25..+0.5), 10:15 candle only.
Stop = candle high, cap 0.5 / 0.75 / 1.0 / 1.5 / none. Target A = 1% fixed; target B = max(1%, 2 x stop) (always >= 1:2).
Exit after 5 candles / day's last candle, stop first if both in one candle (re-walked on h1_cache). Fixed Rs1,000 risk,
charges Rs85 per Rs1 lakh of position. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "124_realistic_rr.py").read().split('print("| candle')[0])
X = X[X.hour == "10:15"].copy()


def walk(h, i, entry, stop, tpct):
    day = h.index[i].normalize(); tgt = entry * (1 - tpct / 100)
    for j in range(i + 1, len(h)):
        r = h.iloc[j]
        if h.index[j].normalize() != day: return entry - h.Close.iloc[j - 1], "stall"
        if r.High >= stop: return entry - stop, "stop"
        if r.Low <= tgt: return entry - tgt, "target"
        last = j + 1 >= len(h) or h.index[j + 1].normalize() != day
        if j - i >= 5 or last: return entry - r.Close, "stall"
    return 0.0, "stall"


res = []
for t, g in X.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 10:15")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for tl, tp in (("A", 1.0), ("B", max(1.0, 2 * r.stop))):
            pnl, o = walk(h, i, r.entry, r.high, tp)
            res.append(dict(ix=ix, tgt=tl, ret=pnl / r.entry * 100, out=o))
R = pd.DataFrame(res).merge(X[["stop", "yr", "date"]], left_on="ix", right_index=True)
R["pos"] = 1000 / (R.stop / 100); R["rs"] = R.ret / 100 * R.pos - 85 * R.pos / 1e5; R["Rm"] = R.ret / R.stop
chk = R[(R.tgt == "A") & (R.stop <= 0.5)]
print(f"check vs 124 (10:15, <=0.5%, 1%): n {len(chk)}, avg R {chk.Rm.mean():+.2f}\n")
print("| stop cap | target | setups | days | target / stall / stop % | avg R | Rs/trade @ Rs1k risk | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|")
for lab, cap in (("<= 0.5%", 0.5), ("<= 0.75%", 0.75), ("<= 1.0%", 1.0), ("<= 1.5%", 1.5), ("no cap", 100)):
    for tl, tn in (("A", "1% fixed"), ("B", "max(1%, 2x stop)")):
        g = R[(R.tgt == tl) & (R.stop <= cap)]; o = g.out
        y = " / ".join(f"{g[g.yr == k].rs.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
        print(f"| {lab} | {tn} | {len(g):,} | {g.date.nunique()} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.Rm.mean():+.2f} | {g.rs.mean():+.0f} | {y} |")
