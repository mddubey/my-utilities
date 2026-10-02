"""Two more entry timings for the 1H 34-EMA rejection (user + my proposal, 2026-10-02). Spec fixed before running.
Same filters/window as 34 (5m Jun 10 - Sep 30 2026; hour 10:15/11:15/12:15; 1H trend; wick through live daily 8-EMA;
daily ADX <= 25; VWAP side; liquid). Target 1%, out at 5h or day's last 5m close, stop first. Longs mirrored.
  cross : hour opened below EMA (short); after the first 5m touch of EMA, sell-stop AT the EMA. Fills on a later 5m bar
          trading back through it (at the open if it opens beyond). Stop = hour high BEFORE the fill bar; if the fill
          bar also reaches the stop -> stopped (conservative).
  m15   : 15-min candles (from 5m, :15/:30/:45/:00 grid) inside the hour. First red 15m candle with high >= EMA and close
          < EMA -> enter at its close, stop = that 15m candle's high (short)."""
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


def walk(H, L, C, T, b, s, entry, stop):
    tgt, end = entry * (1 + s * 0.01), T[b] + pd.Timedelta("5h")
    for k in range(b + 1, len(C)):
        if (H[k] >= stop) if s == -1 else (L[k] <= stop): return stop, "stop"
        if (L[k] <= tgt) if s == -1 else (H[k] >= tgt): return tgt, "target"
        if T[k] >= end: return C[k], "time"
    return C[-1], "eod"


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
        vw = np.cumsum((H + L + C) / 3 * V) / np.maximum(np.cumsum(V), 1)
        hi_day, lo_day = np.maximum.accumulate(H), np.minimum.accumulate(L)
        hs_of = hl.index[np.searchsorted(hl.index.values, T.values, side="right") - 1]
        busy = {"cross": -1, "m15": -1}

        def ok(b, s, entry):
            live = A8 * entry + (1 - A8) * D8
            if (entry - D8) * s < 0: return False
            if s == -1 and hi_day[b] < live: return False
            if s == 1 and lo_day[b] > live: return False
            return (entry - vw[b]) * s >= 0

        for hs in hl.index:
            if hs.strftime("%H:%M") not in ("10:15", "11:15", "12:15"): continue
            E, e8, ho = hl.loc[hs, ["e34", "e8", "ho"]]
            idx = np.where(hs_of == hs)[0]
            if len(idx) == 0 or np.isnan(E): continue
            s = -1 if e8 < E else 1
            # cross
            if idx[0] > busy["cross"] and ((s == -1 and ho < E) or (s == 1 and ho > E)):
                tb = next((k for k in idx if (H[k] >= E if s == -1 else L[k] <= E)), None)
                if tb is not None:
                    for k in idx[idx > tb]:
                        if (L[k] <= E) if s == -1 else (H[k] >= E):
                            fill = min(E, O[k]) if s == -1 else max(E, O[k])
                            stop = H[idx[0]:k].max() if s == -1 else L[idx[0]:k].min()
                            if (stop - fill) * -s <= 0 or not ok(k, s, fill): break
                            if (H[k] >= stop) if s == -1 else (L[k] <= stop): px, why = stop, "stop"
                            else: px, why = walk(H, L, C, T, k, s, fill, stop)
                            rows.append(dict(variant="cross", side="short" if s == -1 else "long", date=day, entry=fill,
                                             stop_pct=abs(stop - fill) / fill * 100, exit=why, ret=(px - fill) / fill * 100 * s))
                            busy["cross"] = idx[-1]; break
            # 15-min confirmation
            if idx[0] > busy["m15"]:
                for q0 in range(0, len(idx), 3):
                    qi = idx[q0:q0 + 3]
                    if len(qi) < 3: break
                    qo, qh, ql, qc = O[qi[0]], H[qi].max(), L[qi].min(), C[qi[-1]]
                    if s == -1 and qh >= E and qc < E and qc < qo: entry, stop = qc, qh
                    elif s == 1 and ql <= E and qc > E and qc > qo: entry, stop = qc, ql
                    else: continue
                    b = qi[-1]
                    if (stop - entry) * -s <= 0 or not ok(b, s, entry): break
                    px, why = walk(H, L, C, T, b, s, entry, stop)
                    rows.append(dict(variant="m15", side="short" if s == -1 else "long", date=day, entry=entry,
                                     stop_pct=abs(stop - entry) / entry * 100, exit=why, ret=(px - entry) / entry * 100 * s))
                    busy["m15"] = idx[-1]; break
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tick = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p: R = pd.DataFrame(sum(p.map(run, tick, chunksize=8), []))
    R.to_csv(HERE / "cross_15m_entry_5m.csv", index=False)
    P = pd.read_csv(HERE / "early_entry_checklist_5m.csv", parse_dates=["date"])
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    W = X[(X.date >= "2026-06-10") & (X.bar_ts.dt.strftime("%H:%M") <= "12:15") & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0)]
    def line(x, lab):
        if len(x) < 30: print(f"| {lab} | {len(x)} | too few |"); return
        e = x.exit.astype(str).str.replace("_5m", "").str.replace("_ambig", "").value_counts(normalize=True)
        m = x.groupby(pd.to_datetime(x.date).dt.month).ret.mean()
        print(f"| {lab} | {len(x)} | {x.stop_pct.median():.2f}% | {e.get('target',0)*100:.0f}% / {e.get('stop',0)*100:.0f}% | {(x.ret>0).mean()*100:.0f} | {x.ret.mean():+.3f} | " + " / ".join(f"{v:+.2f}" for v in m) + " |")
    print("| entry, same filters, Jun 10 - Sep 30 2026 | n | median stop | target / stopped | win% | mean% | Jun / Jul / Aug / Sep |\n|---|---|---|---|---|---|---|")
    for sd in ("short", "long"):
        line(R[(R.variant == "cross") & (R.side == sd)], f"{sd}: sell-stop at the EMA as price comes back (cross)")
        line(P[(P.variant == "seen") & (P.side == sd)], f"{sd}: first 5m close back below (seen)")
        line(P[(P.variant == "held") & (P.side == sd)], f"{sd}: rejection held 15 min")
        line(R[(R.variant == "m15") & (R.side == sd)], f"{sd}: 15-min candle rejection close")
        line(W[W.side == sd], f"{sd}: 1H candle close")
