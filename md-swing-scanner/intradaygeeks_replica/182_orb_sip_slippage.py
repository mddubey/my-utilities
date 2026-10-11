"""Slippage on the in-play ORB SHORT, on Yahoo 1-min bars (user, 2026-10-11; models declared before running). Trades: 176's in-play
shorts with 1-min data (2026-09-12..10-08). Trigger = the 09:15-09:19 1-min low; protective stop price fixed in advance at trigger x
(1 + k x ATR%), k = 0.10 / 0.20. Entry models: IDEAL fill at the trigger (as 175/176) | SL-M small = trigger - 0.05% | SL-M stress =
trigger - 0.15% (if the trigger minute OPENED below the trigger: that open minus the same slip) | SL-LIMIT buffer 0.1% / 0.2% = fill at
the limit (trigger - buffer, worst allowed), MISSED if the trigger minute opened below the limit (gapped past it). Stop exit: stop price
+ 0 / 0.05% / 0.15% (if the minute opened above the stop: that open + slip). 15:15 exit at that minute's open. Entry minute: stop only if
that 1-min bar CLOSED above the stop (176's mid rule). R and Rs @1k use the PLANNED risk (trigger -> stop price). Also descriptive: how
far price ran past the trigger in the trigger minute, and how often stops gapped. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; CACHE = HERE / "m1_cache"


def load_day(t, d):
    m = pd.read_csv(CACHE / f"{t}_{d}.csv", index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m["hm"] = m.index.strftime("%H:%M"); return m


def run(m, atr, k, entry_model, stop_slip):
    first = m[m.hm < "09:20"]; rest = m[(m.hm >= "09:20") & (m.hm < "15:15")]
    trig = first.Low.min(); hit = rest[rest.Low < trig]
    if not len(hit): return None
    i = hit.index[0]; b0 = m.loc[i]; base = min(trig, b0.Open)
    kind, x = entry_model
    if kind == "ideal": e = base
    elif kind == "slm": e = base * (1 - x / 100)
    else:
        lim = trig * (1 - x / 100)
        if b0.Open < lim: return "missed"
        e = lim
    sp = k * atr; stp = trig * (1 + sp / 100); px, o = None, "close"
    if b0.Close >= stp: px, o = stp * (1 + stop_slip / 100), "stop"
    if px is None:
        for ts, b in m[m.index > i].iterrows():
            if b.hm >= "15:15": px = b.Open; break
            if b.High >= stp: px, o = max(stp, b.Open) * (1 + stop_slip / 100), "stop"; break
    if px is None: px = m.Close.iloc[-1]
    ret = (e - px) / e * 100; risk = (stp - trig) / trig * 100; pos = 1000 / (risk / 100)
    return dict(o=o, R=ret / risk, rk=ret / 100 * pos - 85 * pos / 1e5)


if __name__ == "__main__":
    X = pd.read_csv(HERE / "orb_sip_1m.csv"); X = X[(X.side < 0) & (X.traded1m == True)]
    days = {(t, d): load_day(t, d) for t, d in zip(X.ticker, X.date)}
    # descriptive: run past the trigger in the trigger minute, and stop gaps
    run_past, gap_stop = [], []
    for (t, d), m in days.items():
        f = m[m.hm < "09:20"]; rest = m[(m.hm >= "09:20") & (m.hm < "15:15")]; trig = f.Low.min(); hit = rest[rest.Low < trig]
        if len(hit): b0 = m.loc[hit.index[0]]; run_past.append(dict(low=(trig - b0.Low) / trig * 100, close=(trig - b0.Close) / trig * 100, opened_below=b0.Open < trig))
    rp = pd.DataFrame(run_past)
    print(f"in-play shorts with 1-min data: {len(X)} ({X.date.min()}..{X.date.max()})")
    print(f"trigger minute: opened already below the trigger {rp.opened_below.mean()*100:.0f}% | low went past the trigger by median {rp.low.median():.2f}% (p75 {rp.low.quantile(.75):.2f}%, p90 {rp.low.quantile(.9):.2f}%) | closed below it by median {rp.close.median():.2f}%")
    EM = [("IDEAL (fill at trigger)", ("ideal", 0)), ("SL-M, 0.05% slip", ("slm", 0.05)), ("SL-M, 0.15% slip (stress)", ("slm", 0.15)),
          ("SL-LIMIT, 0.1% buffer", ("lim", 0.1)), ("SL-LIMIT, 0.2% buffer", ("lim", 0.2))]
    for k in (0.10, 0.20):
        print(f"\n## stop {int(k*100)}% of ATR (planned risk median {(X.atr * k).median():.2f}%)\n| entry | stop slip | filled | missed | stopped | win % | avg R | Rs/trade @1k net | missed trades' IDEAL avg R |\n|---|---|---|---|---|---|---|---|---|")
        for el, em in EM:
            for ss in (0, 0.05, 0.15):
                res, miss_ideal = [], []
                for _, r in X.iterrows():
                    m = days[(r.ticker, r.date)]; z = run(m, r.atr, k, em, ss)
                    if z == "missed": miss_ideal.append(run(m, r.atr, k, ("ideal", 0), ss)["R"]); continue
                    if z: res.append(z)
                D = pd.DataFrame(res)
                mi = f"{np.mean(miss_ideal):+.2f}" if miss_ideal else "-"
                print(f"| {el} | {ss:.2f}% | {len(D)} | {len(miss_ideal)} | {(D.o=='stop').mean()*100:.0f}% | {(D.R>0).mean()*100:.0f}% | {D.R.mean():+.2f} | {D.rk.mean():+.0f} | {mi} |")
