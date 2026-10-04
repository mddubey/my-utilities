"""Confirmation entry (user, 2026-10-04): don't short at the signal candle's close; place a sell-stop at its LOW and enter
only if the next candle breaks it. Spec fixed before running. Signals = current rules, all setups (how_low_P0.csv).
  Entry: signal low (or the bar open if it gaps below). Window: the NEXT candle only (30 min on set a, 1 hour on set b);
         neighbour: next 2 candles. CANCEL (no trade) if the signal high (= stop) is touched before the low breaks.
  Stop: signal candle high (unchanged). Target: 1% below the actual entry. Exit: 5h after entry (a) / 5 candles (b) / EOD.
  Ambiguous bars (stop and entry, or entry and target, in the same bar): resolved AGAINST us (1H set has no 5-min data).
  Versions: V1 same signals as today; V2 also require stop from the new entry (high - low)/low <= 0.5% (2:1 kept).
  Compared on the same signals with today's close entry; also what the never-triggered signals did with a close entry.
  Rs gross and net of ~Rs85; outcome split target / stall / stop; both sets; one-a-day plan; by month / year."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085


def sim(args):
    t, g = args
    cache = {}; out = []
    for ix, r in g.iterrows():
        s = r.set
        if s not in cache:
            p = INTRADAY_5M_DIR / f"{t}.csv" if s == "a" else HERE / "h1_cache" / f"{t}.csv"
            m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
            cache[s] = m
        m = cache[s]; day = pd.Timestamp(r.date)
        if s == "a":
            at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min"); cand = pd.Timedelta("30min"); cap = pd.Timedelta("5h")
        else:
            at = day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15); cand = pd.Timedelta("60min"); cap = None
        b = m[(m.index >= at) & (m.index.normalize() == day) & (m.index < day + pd.Timedelta("15h15min"))]
        if b.empty: continue
        hi, cl, pos = r.qh, r.qc, r.pos
        lo = (cl - pos * hi) / (1 - pos) if pos < 1 else cl
        H, L, O, C, T = b.High.values, b.Low.values, b.Open.values, b.Close.values, b.index
        rec = {"ix": ix, "sig_low": lo, "range_pct": (hi - lo) / lo * 100}
        for wn, nc in (("w1", 1), ("w2", 2)):
            last_t = at + nc * cand; k_in = None; px = None; res = np.nan; status = "no_break"
            for k in range(len(H)):
                if T[k] >= last_t: break
                if H[k] >= hi and L[k] <= lo:                    # both in one bar: against us -> entered then stopped
                    k_in, px = k, min(lo, O[k]); res = -(hi - px) / px * 100; status = "stop"; break
                if H[k] >= hi: status = "cancelled"; break
                if L[k] <= lo: k_in, px = k, min(lo, O[k]); break
            if k_in is not None and status != "stop":
                tg = px * 0.99; res = None; status = "stall"
                end_k = None
                for k in range(k_in + 1, len(H)):
                    if H[k] >= hi: res = -(hi - px) / px * 100; status = "stop"; break
                    if L[k] <= tg: res = 1.0; status = "target"; break
                    if (cap is not None and T[k] >= T[k_in] + cap) or (cap is None and k - k_in >= 5): res = (px - C[k]) / px * 100; break
                if res is None: res = (px - C[-1]) / px * 100
            rec[f"{wn}_status"] = status; rec[f"{wn}_ret"] = res; rec[f"{wn}_entry"] = px; rec[f"{wn}_risk"] = (hi - px) / px * 100 if px else np.nan
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    with Pool(6) as p:
        R = pd.DataFrame(sum(p.map(sim, list(y.groupby("ticker"))), [])).set_index("ix")
    y = y.join(R, how="inner"); y.to_csv(HERE / "break_of_low_entry.csv", index=False)
    y["close_out"] = y.why.replace({"time": "stall", "eod": "stall"})

    def split(st, ret):
        return f"tgt {np.mean(st == 'target')*100:4.1f} stall {np.mean(st == 'stall')*100:4.1f} stop {np.mean(st == 'stop')*100:4.1f} | Rs gross {np.nanmean(ret)*1000:+4.0f} net {(np.nanmean(ret)-COST)*1000:+4.0f}"
    for s, nm, per, al in (("a", "30m Jun-Sep 2026", 7, [3, 4]), ("b", "1H 3 years", 4, [10, 11])):
        z = y[y.set == s].copy(); z["p"] = z.date.str[:per]
        print(f"\n################ {nm}: {len(z)} signals | median signal range {z.range_pct.median():.2f}% vs close-entry stop {z.stop_pct.median():.2f}%")
        print(f"  CLOSE entry (today)      n={len(z):4d} " + split(z.close_out.values, z.ret.values))
        for wn in ("w1", "w2"):
            st = z[f"{wn}_status"]; tr = z[st.isin(["target", "stall", "stop"])]
            print(f"\n  BREAK-OF-LOW, window {wn}: triggered {len(tr)/len(z)*100:.0f}% | cancelled (stop hit first) {np.mean(st == 'cancelled')*100:.0f}% | never broke {np.mean(st == 'no_break')*100:.0f}%")
            print(f"    V1 all triggered      n={len(tr):4d} " + split(tr[f"{wn}_status"].values, tr[f"{wn}_ret"].values) + f" | median risk {tr[f'{wn}_risk'].median():.2f}%")
            v2 = tr[tr.range_pct <= 0.5]
            print(f"    V2 + new stop <=0.5%  n={len(v2):4d} " + split(v2[f"{wn}_status"].values, v2[f"{wn}_ret"].values))
            for lab, grp in (("cancelled", z[st == "cancelled"]), ("never broke", z[st == "no_break"]), ("triggered", tr)):
                print(f"    same signals with CLOSE entry -- {lab:11s} n={len(grp):4d} " + split(grp.close_out.values, grp.ret.values))
            if wn == "w1":
                print("    by period Rs gross, close entry / V1: " + "  ".join(f"{k}: {g.ret.mean()*1000:+.0f} / {np.nanmean(g[g[wn+'_status'].isin(['target','stall','stop'])][wn+'_ret'])*1000:+.0f}" for k, g in z.groupby("p")))
                c = z[z.alarm.isin(al)]
                pc = c.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
                cb = c[c[f"{wn}_status"].isin(["target", "stall", "stop"])]
                pb = cb.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
                print(f"    PLAN one/day: close entry {len(pc)} trades net {(pc.ret.mean()-COST)*1000:+.0f}/trade, total net {(pc.ret-COST).sum()*1000:+.0f} | "
                      f"break-of-low {len(pb)} trades net {(pb[wn+'_ret'].mean()-COST)*1000:+.0f}/trade, total net {(pb[wn+'_ret']-COST).sum()*1000:+.0f}")
