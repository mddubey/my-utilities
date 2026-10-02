"""Re-grade every channel attempt with each day's high/low corrected to NSE's official
bhavcopy values. Hourly Yahoo candles still give the ORDER of events; only the day's extremes
are fixed: if NSE's high is above Yahoo's, the candle holding Yahoo's high is raised to it;
if NSE's high is below, every candle's high is capped at it (same for lows).
Variants re-scored (Yahoo vs NSE-corrected): first attempt to T1, first attempt to last
target, two-tranche (entry + add-more) to last target, and re-entries to T1.
"""
import warnings
warnings.filterwarnings("ignore")
import importlib.util, re
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location("m5", HERE / "05_score_telegram_calls.py")
m5 = importlib.util.module_from_spec(spec); spec.loader.exec_module(m5)

NSE = pd.read_csv(HERE / "nse_bhav_ohlc.csv", dtype={"date": str}).set_index(["date", "ticker"])


def patched_day(ticker, day):
    h = m5.load_60m(ticker)
    d = h[h.index.date == day].copy()
    if d.empty:
        return d, False
    key = (day.strftime("%Y%m%d"), ticker)
    if key not in NSE.index:
        return d, False
    if abs(NSE.loc[key, "close"] / d.Close.iloc[-1] - 1) > 0.05:
        return d, False   # Yahoo price scale broken by a later split/bonus -- unusable day
    nh, nl = NSE.loc[key, "high"], NSE.loc[key, "low"]
    if nh > d.High.max():
        d.loc[d.High.idxmax(), "High"] = nh
    else:
        d["High"] = d.High.clip(upper=nh)
    if nl < d.Low.min():
        d.loc[d.Low.idxmin(), "Low"] = nl
    else:
        d["Low"] = d.Low.clip(lower=nl)
    return d, True


def addmore(t):
    m = re.search(r"ADD\s+(?:SOME\s+)?MORE(?:\s+(?:QTY|LOT))?\s*(?:AT|@|NEAR)?\s*(\d+(?:\.\d+)?)", str(t).upper())
    return float(m.group(1)) if m else None


def two_tranche(bars, r, addp, tgt):
    s = 1 if r.direction == "long" else -1
    filled2 = False
    px = None
    for _, b in bars.iterrows():
        adv, fav = (b.Low, b.High) if s == 1 else (b.High, b.Low)
        hit_add = adv <= addp if s == 1 else adv >= addp
        hit_sl = adv <= r.sl if s == 1 else adv >= r.sl
        hit_t = fav >= tgt if s == 1 else fav <= tgt
        if hit_add and not filled2 and not (hit_t and not hit_sl):
            filled2 = True
        if hit_sl:
            px = r.sl; break
        if hit_t:
            px = tgt; break
    if px is None:
        if bars.empty:
            return None
        px = bars.Close.iloc[-1]
    legs = [r.entry] + ([addp] if filled2 else [])
    return sum(s * (px - e) / e * 100 for e in legs) * 0.5


def pct(r, res):
    return None if res is None else res[1] * abs(r.entry - r.sl) / r.entry * 100


if __name__ == "__main__":
    A = pd.read_csv(HERE / "telegram_attempts_scored.csv", parse_dates=["ts"])
    calls = pd.read_csv(HERE / "telegram_calls.csv", parse_dates=["ts"]).set_index("msg_id")
    rows, skipped = [], []
    for a in A.itertuples():
        day = a.ts.date()
        y = m5.load_60m(a.ticker); y = y[y.index.date == day]
        n, ok = patched_day(a.ticker, day)
        if y.empty or not ok:
            skipped.append((a.ticker, day)); continue
        yb, nb = y[y.index > a.ts], n[n.index > a.ts]
        row = dict(root=a.root, kind=a.kind, ticker=a.ticker, ts=a.ts, direction=a.direction)
        for tag, bars in (("y", yb), ("n", nb)):
            r1 = m5.score(bars, a)
            rl = m5.score(bars, a._replace(target1=a.target_last))
            row[f"{tag}_out_t1"] = r1[0] if r1 else None
            row[f"{tag}_pct_t1"] = pct(a, r1)
            row[f"{tag}_out_last"] = rl[0] if rl else None
            row[f"{tag}_pct_last"] = pct(a, rl)
            if a.kind == "first" and a.root in calls.index:
                ap = addmore(calls.loc[a.root, "text"])
                good = ap is not None and ((a.direction == "long" and a.sl < ap < a.entry) or
                                           (a.direction == "short" and a.entry < ap < a.sl))
                row[f"{tag}_pct_2t"] = two_tranche(bars, a, ap, a.target_last) if good else None
        rows.append(row)
    R = pd.DataFrame(rows)
    print(f"skipped {len(skipped)} attempts (no NSE row, or split/bonus-broken Yahoo scale): {sorted(set(skipped))}")
    R.to_csv(HERE / "telegram_regraded_nse.csv", index=False)

    F = R[R.kind == "first"]
    print(f"regraded {len(R)} attempts ({len(F)} first attempts) with NSE extremes\n")
    for v in ("t1", "last"):
        flips = (F[f"y_out_{v}"] != F[f"n_out_{v}"]).sum()
        print(f"first attempt -> {'first' if v=='t1' else 'last'} target: outcome changed on {flips} of {len(F)}")
        print("   ", pd.crosstab(F[f"y_out_{v}"], F[f"n_out_{v}"]).to_dict())
    print()
    def line(x, col, label):
        x = x.dropna(subset=[col]).sort_values(col)
        print(f"{label:44s} n={len(x):3d}  mean {x[col].mean():+.3f}%  median {x[col].median():+.3f}%  "
              f"excl top5 {x.iloc[:-5][col].mean():+.3f}%  after 0.05% {x[col].mean()-0.05:+.3f}%")
    for v, lab in (("t1", "first attempt, exit at first target"), ("last", "first attempt, exit at last target"),
                   ("2t", "two-tranche (add-more), last target")):
        line(F, f"y_pct_{v}", f"YAHOO  {lab}")
        line(F, f"n_pct_{v}", f"NSE    {lab}")
    RE = R[R.kind == "reentry"]
    first_out = F.set_index("root")
    for tag in ("y", "n"):
        after = RE.root.map(first_out[f"{tag}_out_t1"]).fillna("")
        x = RE[after.str.startswith("sl")]
        print(f"{'YAHOO' if tag=='y' else 'NSE  '}  re-entries after a stop-out: n={len(x)}  stopped again "
              f"{x[f'{tag}_out_t1'].str.startswith('sl').mean()*100:.0f}%  total {x[f'{tag}_pct_t1'].sum():+.2f}%")
