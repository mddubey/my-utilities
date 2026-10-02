"""User's three refinements to the 1H setup (2026-10-02). Spec fixed before running. Base: 31's feature file
(1H-close setup, 2024-26, both sides). 'Checklist' here = stretch + setup <= 12:15 + daily ADX <= 25 + VWAP side
(gap rule removed so gaps can be studied). Stretch cut = train (< 2025-07-01) 2/3 quantile of its own metric.
(1) GAP split, both directions: gap in trade direction > 0.5% / flat / gap AGAINST trade > 0.5% (e.g. gap-up for a short).
(2) LIVE daily 8-EMA: chart value = a*P + (1-a)*EMA8_yesterday, a = 2/9, P = entry price. Price-vs-EMA side is
    mathematically unchanged; the WICK-vs-live-EMA distance changes. Stretch_live = day's extreme so far vs live EMA.
(3) ENTRY at the 1H 34-EMA: after the setup candle closes, a limit at the current 1H EMA34 (re-set every hour to that
    hour's value), valid for the next 2 hourly candles. Short: fills if a candle's high >= EMA; fill = max(EMA, open).
    Cancelled if a candle opens at/above the stop. Stop = setup wick, target = fill -/+1%, out after 5 candles or EOD,
    stop first if a candle hits both (no 5m resolution here = conservative). Variants per trigger:
      a) close entry (as before)   b) EMA limit only (unfilled = 0)   c) half at close + half at EMA limit."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
SPLIT, A8 = pd.Timestamp("2025-07-01"), 2 / 9


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def sim(args):
    t, rows = args
    h = read(HERE / "h1_cache" / f"{t}.csv")
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index
    E = h.Close.ewm(span=34, adjust=False).mean().shift(1).values
    day = T.normalize()
    d = load(t); d = d[d.index < pd.Timestamp("2026-10-01")]
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1)
    out = []
    for r in rows.itertuples():
        if r.bar_ts not in h.index: continue
        i = h.index.get_loc(r.bar_ts); s = 1 if r.side == "long" else -1
        stop = r.price - s * r.stop_rs
        D8 = d8y.get(r.date, np.nan)
        ext = D8 * (1 + s * r.d8_ext_vs_d8_pct / 100) if not np.isnan(D8) else np.nan   # day's extreme so far (inverse of 15's formula)
        live = A8 * r.price + (1 - A8) * D8
        st_live = ((live - ext) / live * 100) if s == -1 else ((ext - live) / live * 100)   # >0: extreme stayed short of live EMA
        fill = fk = None
        for j in range(i + 1, min(i + 3, len(C))):
            if day[j] != day[i]: break
            if (O[j] >= stop) if s == -1 else (O[j] <= stop): break
            if (H[j] >= E[j]) if s == -1 else (L[j] <= E[j]):
                fill = max(E[j], O[j]) if s == -1 else min(E[j], O[j]); fk = j; break
        lim_ret = np.nan
        if fill is not None and (fill - stop) * s > 0:
            tgt = fill * (1 + s * 0.01); px = None
            if (H[fk] >= stop) if s == -1 else (L[fk] <= stop): px = stop
            else:
                for j in range(fk + 1, len(C)):
                    if day[j] != day[fk]: px = C[j - 1]; break
                    if (H[j] >= stop) if s == -1 else (L[j] <= stop): px = stop; break
                    if (L[j] <= tgt) if s == -1 else (H[j] >= tgt): px = tgt; break
                    if j - fk >= 5: px = C[j]; break
                if px is None: px = C[-1]
            lim_ret = (px - fill) / fill * 100 * s
        if t == "SKYGOLD" and str(r.bar_ts) == "2025-07-09 12:15:00":
            assert abs(ext - 323.60) < 0.05, ext; print(f"  check SKYGOLD: day high recovered {ext:.2f}, live EMA {live:.2f}, st_live {st_live:+.2f}", flush=True)
        out.append(dict(key=r.Index, st_live=st_live, lim_filled=fill is not None and not np.isnan(lim_ret), lim_ret=lim_ret,
                        lim_stop_pct=abs(stop - fill) / fill * 100 if fill else np.nan))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    X = pd.read_csv(HERE / "winners_losers_features_1h.csv", parse_dates=["date", "bar_ts"])
    with Pool(6) as p: F = sum(p.map(sim, list(X.groupby("ticker"))), [])
    X = X.join(pd.DataFrame(F).set_index("key")); X.to_csv(HERE / "gap_live_entry_1h.csv", index=False)
    tr = X.date < SPLIT
    cut_s, cut_l = X[tr].d8_ext_vs_d8_pct.quantile(2 / 3), X[tr].st_live.quantile(2 / 3)
    base = (X.bar_ts.dt.strftime("%H:%M") <= "12:15") & (X.dadx <= 25) & (X.vwap_with == True)
    CK = base & (X.d8_ext_vs_d8_pct <= cut_s)
    X["gapb"] = np.select([X.gap_s > 0.5, X.gap_s < -0.5], ["gap WITH trade >0.5%", "gap AGAINST trade >0.5%"], "flat")
    def line(x, lab, col="ret"):
        if len(x) < 50: print(f"| {lab} | {len(x)} | too few | | | |"); return
        y = x.groupby(x.date.dt.year)[col].mean(); te = x[x.date >= SPLIT][col]
        print(f"| {lab} | {len(x)} | {x[col].mean():+.3f} | " + " / ".join(f"{v:+.2f}" for v in y) + f" | {te.mean():+.3f} (n {len(te)}) |")
    H = "| group | n | mean % 2024-26 | 2024 / 2025 / 2026 | unseen period Jul25-Sep26 |\n|---|---|---|---|---|"
    print(f"stretch cut static {cut_s:.3f}% | live {cut_l:.3f}%")
    print("\n(1) GAP, within checklist (no gap rule), close entry\n" + H)
    for sd in ("short", "long"):
        for g in ("gap WITH trade >0.5%", "flat", "gap AGAINST trade >0.5%"): line(X[CK & (X.side == sd) & (X.gapb == g)], f"{sd}: {g}")
    print("\n(2) DAILY 8-EMA stretch: static (yesterday's EMA) vs LIVE (chart) EMA, shorts, checklist otherwise same\n" + H)
    S = X.side == "short"
    line(X[base & S & (X.d8_ext_vs_d8_pct <= cut_s)], "static stretch rule (as before)")
    line(X[base & S & (X.st_live <= cut_l)], "live-EMA stretch rule")
    chg = (X.d8_ext_vs_d8_pct <= cut_s) != (X.st_live <= cut_l)
    print(f"  trades whose keep/skip decision changes: {chg[base & S].mean()*100:.1f}%")
    print("  wick through the LIVE EMA (st_live <= 0) vs not, shorts:")
    line(X[base & S & (X.st_live <= 0)], "  wick through live daily 8-EMA"); line(X[base & S & (X.st_live > 0)], "  wick short of live daily 8-EMA")
    print("\n(3) ENTRY: close vs limit at 1H 34-EMA vs half/half, per TRIGGER (unfilled limit = 0), checklist shorts (static, no gap rule)\n" + H)
    K = X[CK & S].copy()
    K["a_close"] = K.ret; K["b_limit"] = K.lim_ret.fillna(0); K["c_half"] = 0.5 * K.ret + 0.5 * K.lim_ret.fillna(0)
    for c, lab in (("a_close", "a) enter at setup close"), ("b_limit", "b) limit at 1H 34-EMA only"), ("c_half", "c) half close + half EMA")): line(K, lab, c)
    f = K[K.lim_filled]
    print(f"  limit fill rate {K.lim_filled.mean()*100:.0f}% | filled: limit result {f.lim_ret.mean():+.3f}% (stop med {f.lim_stop_pct.median():.2f}%), "
          f"close-entry result on same trades {f.ret.mean():+.3f}% | NOT filled: close-entry result {K[~K.lim_filled].ret.mean():+.3f}%")
    print("  limit entry, filled trades by gap:")
    for g in ("gap WITH trade >0.5%", "flat", "gap AGAINST trade >0.5%"): line(f[f.gapb == g], f"  {g}", "lim_ret")
