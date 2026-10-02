"""Enter WHILE the 1H pin forms, with the checklist applied at the moment of entry. Spec fixed 2026-10-02.
5m data Jun 10 - Sep 30 2026. Forming hour starts 10:15/11:15/12:15; 1H EMA8/EMA34 as of last completed hour; trend
EMA8<EMA34 (short); hour opened below EMA34; a 5m high touches it. Entries:
  'seen' : first 5m close back below EMA34 at/after the touch bar (same hour)
  'held' : first 5m close back below EMA34, >= 3 bars after the touch bar, no new hour high in the last 3 bars, < 1% below
Checklist at entry: day's high so far >= live daily 8-EMA (2/9*entry + 7/9*EMA8_yday); daily ADX(yday) <= 25;
entry < session VWAP (5m); liquid (tv20 >= Rs 10cr), >= 70 bars, no corp action. Stop = hour high so far; target -1%;
out at 5h or day's last 5m close; stop first. Longs mirrored. Comparison: 33's 1H-close setups, same filters (wick
through live daily 8-EMA, setup <= 12:15, ADX <= 25, VWAP side), dates >= 2026-06-10."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx
HERE = Path(__file__).resolve().parent
H1, M5 = HERE / "h1_cache", HERE.parent / "intraday_cache"
A8 = 2 / 9


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(t):
    if not (H1 / f"{t}.csv").exists() or not (M5 / f"{t}.csv").exists(): return []
    try: d = load(t)
    except Exception: return []
    d = d[d.index < pd.Timestamp("2026-10-01")]
    h1, m5 = read(H1 / f"{t}.csv"), read(M5 / f"{t}.csv")
    if len(h1) < 200 or m5.empty: return []
    lev = pd.DataFrame({"e34": h1.Close.ewm(span=34, adjust=False).mean().shift(1),
                        "e8": h1.Close.ewm(span=8, adjust=False).mean().shift(1), "ho": h1.Open}, index=h1.index)
    d8y = d.Close.ewm(span=8, adjust=False).mean().shift(1); adx = _compute_adx(d)[0].shift(1); tv = d.traded_value_sma20.shift(1)
    rows = []
    for day, g in m5.groupby(m5.index.normalize()):
        if len(g) < 70 or day not in d.index or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        if abs(g.Close.iloc[-1] / d.Close.loc[day] - 1) > 0.02: continue
        D8, AD = d8y.get(day, np.nan), adx.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25: continue
        hl = lev[(lev.index >= day) & (lev.index < day + pd.Timedelta("1D"))]
        O, H, L, C, V, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.Volume.values, g.index
        tp = (H + L + C) / 3; vw = np.cumsum(tp * V) / np.maximum(np.cumsum(V), 1)
        hi_day, lo_day = np.maximum.accumulate(H), np.minimum.accumulate(L)
        hs_of = hl.index[np.searchsorted(hl.index.values, T.values, side="right") - 1]
        busy = {"seen": -1, "held": -1}
        for hs in hl.index:
            if hs.strftime("%H:%M") not in ("10:15", "11:15", "12:15"): continue
            E, e8, ho = hl.loc[hs, ["e34", "e8", "ho"]]
            idx = np.where(hs_of == hs)[0]
            if len(idx) == 0 or np.isnan(E): continue
            if e8 < E and ho < E: s = -1
            elif e8 > E and ho > E: s = 1
            else: continue
            tb = next((k for k in idx if (H[k] >= E if s == -1 else L[k] <= E)), None)
            if tb is None: continue
            for var in ("seen", "held"):
                if idx[0] <= busy[var]: continue
                b = None
                for k in idx:
                    if k < tb or (var == "held" and k < tb + 3): continue
                    if (C[k] - E) * s <= 0: continue
                    if var == "held":
                        hh = H[idx[0]:k + 1].max() if s == -1 else L[idx[0]:k + 1].min()
                        recent = H[k - 2:k + 1].max() if s == -1 else L[k - 2:k + 1].min()
                        if (s == -1 and recent >= hh) or (s == 1 and recent <= hh): continue
                        if abs(C[k] / E - 1) >= 0.01: continue
                    b = k; break
                if b is None: continue
                entry = C[b]; stop = H[idx[0]:b + 1].max() if s == -1 else L[idx[0]:b + 1].min()
                risk = (stop - entry) * -s
                if risk <= 0: continue
                live = A8 * entry + (1 - A8) * D8
                if (entry - D8) * s < 0: continue                                       # wrong side of daily 8
                if s == -1 and hi_day[b] < live: continue                               # wick must pierce live daily 8-EMA
                if s == 1 and lo_day[b] > live: continue
                if (entry - vw[b]) * s < 0: continue                                    # VWAP side
                tgt, end = entry * (1 + s * 0.01), T[b] + pd.Timedelta("5h")
                px, why, k = None, None, b
                for k in range(b + 1, len(C)):
                    if (H[k] >= stop) if s == -1 else (L[k] <= stop): px, why = stop, "stop"; break
                    if (L[k] <= tgt) if s == -1 else (H[k] >= tgt): px, why = tgt, "target"; break
                    if T[k] >= end: px, why = C[k], "time"; break
                if px is None: px, why, k = C[-1], "eod", len(C) - 1
                rows.append(dict(variant=var, ticker=t, date=day, hour=hs.strftime("%H:%M"), entry_time=T[b].strftime("%H:%M"),
                                 side="short" if s == -1 else "long", entry=entry, stop_pct=risk / entry * 100,
                                 past_ema_pct=abs(entry / E - 1) * 100, exit=why, ret=(px - entry) / entry * 100 * s))
                busy[var] = k
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "early_entry_checklist_5m.csv", index=False)
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    W = X[(X.date >= "2026-06-10") & (X.bar_ts.dt.strftime("%H:%M") <= "12:15") & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0)]
    def line(x, lab):
        if len(x) < 30: print(f"| {lab} | {len(x)} | too few |"); return
        e = x.exit.astype(str).str.replace("_5m", "").str.replace("_ambig", "").value_counts(normalize=True)
        m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {x.stop_pct.median():.2f}% | {e.get('target',0)*100:.0f} / {e.get('stop',0)*100:.0f} | {(x.ret>0).mean()*100:.0f} | "
              f"{x.ret.mean():+.3f} | {x.ret.median():+.3f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
    print("| entry (same filters, Jun 10 - Sep 30 2026) | n | stop med | target / stop % | win% | mean% | med% | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|---|")
    for sd in ("short", "long"):
        line(W[W.side == sd], f"{sd}: 1H candle close (confirmed)")
        for v, lab in (("seen", "rejection seen (first 5m close back across)"), ("held", "rejection held 15 min")):
            line(R[(R.variant == v) & (R.side == sd)], f"{sd}: {lab}")
    s = W[W.side == "short"]
    print(f"\n1H-close shorts: entry already below the EMA by median {s.close_past_ema.abs().median():.2f}%; >0.5% below in {(s.close_past_ema.abs()>0.5).mean()*100:.0f}%, >1% in {(s.close_past_ema.abs()>1).mean()*100:.0f}%")
