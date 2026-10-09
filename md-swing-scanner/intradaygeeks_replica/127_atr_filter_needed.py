"""Is the ATR >= 2.56% filter still needed once the target scales with ATR? (user, 2026-10-09). Spec fixed before running.
Population: script 124's stack WITHOUT the ATR filter (liquid touch, 09:15/10:15, red, Nifty 8>34 + Nifty > 200d, stock daily
8>34, gap -0.25..+0.5). Targets: fixed 1% and 0.25 / 0.35 / 0.5 x ATR; versions with and without 'target >= 2x stop'.
Split by ATR band (yday): < 2% | 2-2.56% | 2.56-3.5% | > 3.5%, plus 'no ATR filter' and '>= 2.56' (the current filter).
Both candles together. Rs per trade at Rs1k risk, net. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
src = open(Path(__file__).resolve().parent / "124_realistic_rr.py").read().split('print("| candle')[0]
src = src.replace("(S.atrp >= 2.56) & ", "")
exec(src)
exec(open(Path(__file__).resolve().parent / "125_stop_cap_target_grid.py").read().split("res = []")[0].split('X = X.copy()')[1].split("\n", 1)[1])
import sys
if "--hour" in sys.argv: X = X[X.hour == sys.argv[sys.argv.index("--hour") + 1]]   # 2026-10-09 (user): one candle only
print(f"candles: {sorted(X.hour.unique())}, setups {len(X)}")
res = []
for t, g in X.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} {r.hour}")
        if k not in h.index: continue
        i = h.index.get_loc(k)
        for lab, tp in (("fixed 1%", 1.0), ("0.25 x ATR", 0.25 * r.atrp), ("0.35 x ATR", 0.35 * r.atrp), ("0.5 x ATR", 0.5 * r.atrp)):
            pnl, o = walk(h, i, r.entry, r.high, tp)
            res.append(dict(ix=ix, tgt=lab, tp=tp, ret=pnl / r.entry * 100, out=o))
R = pd.DataFrame(res).merge(X[["stop", "yr", "date", "hour", "atrp"]], left_on="ix", right_index=True)
R["pos"] = 1000 / (R.stop / 100); R["rs"] = R.ret / 100 * R.pos - 85 * R.pos / 1e5
BANDS = (("no ATR filter", lambda d: d.atrp > 0), (">= 2.56 (current)", lambda d: d.atrp >= 2.56), ("< 2%", lambda d: d.atrp < 2),
         ("2-2.56%", lambda d: (d.atrp >= 2) & (d.atrp < 2.56)), ("2.56-3.5%", lambda d: (d.atrp >= 2.56) & (d.atrp < 3.5)), ("> 3.5%", lambda d: d.atrp >= 3.5))
for cn, cond in (("target >= 2x stop", lambda d: d.tp >= 2 * d.stop), ("no R:R condition", lambda d: d.tp > 0)):
    print(f"\n## {cn} -- cells: Rs/trade (setups)\n| ATR band | fixed 1% | 0.25 x ATR | 0.35 x ATR | 0.5 x ATR | 0.5 x ATR by year |\n|---|---|---|---|---|---|")
    for bn, bf in BANDS:
        cells = []
        for lab in ("fixed 1%", "0.25 x ATR", "0.35 x ATR", "0.5 x ATR"):
            g = R[R.tgt == lab]; g = g[cond(g) & bf(g)]
            cells.append(f"{g.rs.mean():+.0f} ({len(g):,})" if len(g) >= 30 else f"- ({len(g)})")
        g = R[R.tgt == "0.5 x ATR"]; g = g[cond(g) & bf(g)]
        y = " / ".join(f"{g[g.yr == k].rs.mean():+.0f}" if (g.yr == k).sum() >= 20 else "-" for k in ("2024", "2025", "2026"))
        print(f"| {bn} | " + " | ".join(cells) + f" | {y} |")
