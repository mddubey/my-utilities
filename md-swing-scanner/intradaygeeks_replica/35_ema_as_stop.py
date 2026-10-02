"""Stop = the 1H 34-EMA instead of the wick (user, 2026-10-02). Spec fixed before running; new risk unit declared.
Setups: 33's 1H-close setups with the checklist (setup <= 12:15, daily ADX <= 25, VWAP side, wick through live daily
8-EMA), 2024-26, both sides. Entry = setup close. Target = entry -/+1%. Out at 5 candles or EOD. Stop variants:
  S0 wick      : setup candle high (as before)                      -- intrabar, stop first
  S1 EMA fixed : 1H EMA34 including the setup close (known at entry) -- intrabar touch
  S2 EMA moving: each candle's EMA34 as of the previous candle       -- intrabar touch
  S3 EMA close : exit at the close of any candle that CLOSES beyond the current EMA34 (no intrabar stop)
Risk unit (R) for each = initial distance entry -> that variant's stop at entry (S3 uses the S1 level for R)."""
import warnings; warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; SPLIT = pd.Timestamp("2025-07-01")


def read(p):
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return x[(x.Volume > 0) | (x.High != x.Low)]


def run(args):
    t, rows = args
    h = read(HERE / "h1_cache" / f"{t}.csv")
    O, H, L, C, T = h.Open.values, h.High.values, h.Low.values, h.Close.values, h.index
    ema = h.Close.ewm(span=34, adjust=False).mean().values          # EMA through bar j (known at bar j close)
    day = T.normalize(); out = []
    for r in rows.itertuples():
        if r.bar_ts not in h.index: continue
        i = h.index.get_loc(r.bar_ts); s = 1 if r.side == "long" else -1; e = C[i]; tgt = e * (1 + s * 0.01)
        lvl = {"S0": e - s * r.stop_rs, "S1": ema[i]}
        res = {}
        for v in ("S0", "S1", "S2", "S3"):
            px = None; j = i
            for j in range(i + 1, len(C)):
                if day[j] != day[i]: px = C[j - 1]; break
                stop = lvl.get(v, ema[j - 1])                       # S2/S3 level = EMA through previous candle
                if v != "S3":
                    if (H[j] >= stop) if s == -1 else (L[j] <= stop):
                        px = max(stop, O[j]) if s == -1 else min(stop, O[j]); break
                if (L[j] <= tgt) if s == -1 else (H[j] >= tgt): px = tgt; break
                if v == "S3" and ((C[j] > ema[j]) if s == -1 else (C[j] < ema[j])): px = C[j]; break
                if j - i >= 5: px = C[j]; break
            if px is None: px = C[-1]
            risk = abs(lvl.get(v, ema[i]) - e) / e * 100
            res[v] = ((px - e) / e * 100 * s, risk)
        out.append(dict(key=r.Index, **{f"{v}_ret": res[v][0] for v in res}, **{f"{v}_risk": res[v][1] for v in res}))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    X = pd.read_csv(HERE / "gap_live_entry_1h.csv", parse_dates=["date", "bar_ts"])
    K = X[(X.bar_ts.dt.strftime("%H:%M") <= "12:15") & (X.dadx <= 25) & (X.vwap_with == True) & (X.st_live <= 0)]
    with Pool(6) as p: F = sum(p.map(run, list(K.groupby("ticker"))), [])
    K = K.join(pd.DataFrame(F).set_index("key")); K.to_csv(HERE / "ema_as_stop_1h.csv", index=False)
    lab = {"S0": "wick high (as before)", "S1": "1H 34-EMA, fixed at entry", "S2": "1H 34-EMA, moving each hour", "S3": "hourly CLOSE beyond the EMA"}
    for sd in ("short", "long"):
        x = K[K.side == sd]
        print(f"\n### {sd}s (n={len(x)})\n| stop | median stop | win% | mean % 2024-26 | 2024 / 2025 / 2026 | unseen Jul25-Sep26 | mean R |\n|---|---|---|---|---|---|---|")
        for v in ("S0", "S1", "S2", "S3"):
            r = x[f"{v}_ret"]; y = r.groupby(x.date.dt.year).mean(); u = r[x.date >= SPLIT]
            R = (r / x[f"{v}_risk"]).replace([np.inf, -np.inf], np.nan)
            print(f"| {lab[v]} | {x[f'{v}_risk'].median():.2f}% | {(r>0).mean()*100:.0f} | {r.mean():+.3f} | " + " / ".join(f"{a:+.2f}" for a in y)
                  + f" | {u.mean():+.3f} | {R.clip(-5, 20).mean():+.3f} |")
