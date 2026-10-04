"""15-minute signal + follow-through (user, 2026-10-04; Al Brooks signal bar / follow-through bar). Spec fixed before
running. 30m set only (needs 5-min bars), Jun-Sep 2026. Same checklist as today (1H EMA34 / EMA8 trend, red candle, wick
touches the EMA, close below within 0.5%, daily 8-EMA, ADX, ATR >= 2.56%, VWAP, 2:1 = stop <= 0.5%) but on 15-MINUTE
candles ending 10:30 .. 12:15.
  S15 close : short at the 15-min signal's close, stop = its high.
  S15 break : sell-stop at the 15-min signal's LOW during the next 15-min candle only; cancel if its high is hit first.
  Target 1% below the actual entry; out 5h after entry or EOD. Compared with today's 30-min close entry.
  One-a-day plans: P15 = first 15-min signal (break version) whose entry is at/after 10:45, closest to EMA;
  vs 30-min plan B (10:45 at 10:50, else 11:15, else 11:45; script 83) and today's plan A."""
import sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace('k30 = (T - base) // pd.Timedelta("30min")', 'k30 = (T - base) // pd.Timedelta("15min")', 1)
src = src.replace("for q in (2, 3, 4, 5):", "for q in range(4, 12):", 1)
src = src.replace("if len(qi) < 6: continue", "if len(qi) < 3: continue", 1)
src = src.replace("hs = base + ((q * 30) // 60)", "hs = base + ((q * 15) // 60)", 1)
src = src.replace("alarm=q,", "alarm=q, qc=qc, qh=qh, ql=L[qi].min(), tsig=T[b],", 1)
assert 'pd.Timedelta("15min")' in src and "range(4, 12)" in src and "ql=L[qi]" in src
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "84", "exec"))
COST = 0.085


def brk(args):
    t, g = args
    m = pd.read_csv(M5 / f"{t}.csv", index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date); at = pd.Timestamp(r.tsig) + pd.Timedelta("5min")
        b = m[(m.index >= at) & (m.index.normalize() == day)]
        H, L, O, C, T = b.High.values, b.Low.values, b.Open.values, b.Close.values, b.index
        hi, lo = r.qh, r.ql; st, px, k_in = "no_break", np.nan, None
        for k in range(len(H)):
            if T[k] >= at + pd.Timedelta("15min"): break
            if H[k] >= hi and L[k] <= lo: st, px = "stop", min(lo, O[k]); break
            if H[k] >= hi: st = "cancelled"; break
            if L[k] <= lo: px, k_in = min(lo, O[k]), k; break
        res = -(hi - px) / px * 100 if st == "stop" else np.nan
        if k_in is not None:
            tg = px * 0.99; st = "stall"; res = None
            for k in range(k_in + 1, len(H)):
                if H[k] >= hi: res, st = -(hi - px) / px * 100, "stop"; break
                if L[k] <= tg: res, st = 1.0, "target"; break
                if T[k] >= T[k_in] + pd.Timedelta("5h"): res = (px - C[k]) / px * 100; break
            if res is None: res = (px - C[-1]) / px * 100
        out.append(dict(ix=ix, b_status=st, b_ret=res, b_entry=px, b_time=T[k_in] if k_in is not None else pd.NaT,
                        b_risk=(hi - px) / px * 100 if px == px else np.nan))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), []))
    A["date"] = pd.to_datetime(A.date).dt.strftime("%Y-%m-%d"); A = A.reset_index(drop=True)
    with Pool(6) as p:
        Bk = pd.DataFrame(sum(p.map(brk, list(A.groupby("ticker"))), [])).set_index("ix")
    A = A.join(Bk); A.to_csv(HERE / "s15_signal_break.csv", index=False)
    A["o"] = A.why.replace({"time": "stall", "eod": "stall"}); A["p"] = A.date.str[:7]
    sp = lambda st, r: f"tgt {np.mean(st == 'target')*100:4.1f} stall {np.mean(st == 'stall')*100:4.1f} stop {np.mean(st == 'stop')*100:4.1f} | Rs gross {np.nanmean(r)*1000:+4.0f} net {(np.nanmean(r)-COST)*1000:+4.0f}"
    print(f"15-min signals: {len(A)} ({len(A)/A.date.nunique():.1f}/day) | median stop from close {A.stop.median():.2f}% | from the low {A.b_risk.median():.2f}%")
    print(f"  S15 close entry            n={len(A):4d} " + sp(A.o.values, A.ret.values))
    tr = A[A.b_status.isin(["target", "stall", "stop"])]
    print(f"  S15 break entry            n={len(tr):4d} " + sp(tr.b_status.values, tr.b_ret.values) + f"  (triggered {len(tr)/len(A)*100:.0f}%, cancelled {np.mean(A.b_status == 'cancelled')*100:.0f}%, never broke {np.mean(A.b_status == 'no_break')*100:.0f}%)")
    print("  by month, close / break: " + "  ".join(f"{k}: {g.ret.mean()*1000:+.0f} / {np.nanmean(g.b_ret)*1000:+.0f}" for k, g in A.groupby("p")))
    ref = pd.read_csv(HERE / "how_low_P0.csv"); ref = ref[ref.set == "a"]
    print(f"  30-min close entry (today) n={len(ref):4d} Rs gross {ref.ret.mean()*1000:+.0f} net {(ref.ret.mean()-COST)*1000:+.0f}")
    tr = tr.assign(bt=pd.to_datetime(tr.b_time))
    pp = tr[tr.bt.dt.strftime("%H:%M") >= "10:45"].sort_values(["date", "bt", "dist"]).groupby("date").head(1)
    print(f"  PLAN P15 (first 15-min break entry from 10:45): {len(pp)} trades | " + sp(pp.b_status.values, pp.b_ret.values) + f" | total net {(pp.b_ret - COST).sum()*1000:+.0f} | "
          + " ".join(f"{k}: {g.b_ret.mean()*1000:+.0f}" for k, g in pp.groupby("p")))
    pc = A[pd.to_datetime(A.tsig).dt.strftime("%H:%M") >= "10:40"].sort_values(["date", "tsig", "dist"]).groupby("date").head(1)
    print(f"  PLAN P15c (first 15-min close entry from 10:45): {len(pc)} trades | " + sp(pc.o.values, pc.ret.values) + f" | total net {(pc.ret - COST).sum()*1000:+.0f}")
    print("  reference: 30-min plan A (11:15 else 11:45) 63 trades net +94/trade total +5,907; plan B (10:45@10:50) 68 trades net +220 total +14,971")
