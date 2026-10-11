"""Settle 175's entry-bar ambiguity with Yahoo 1-MINUTE bars (user, 2026-10-11). Yahoo keeps ~30 days of 1-min history, so: every
in-play trade of 175 (relvol >= 1, top 20/day, traded) dated >= 2026-09-11 (18 days; shorts 158, longs 142). Same rules re-run on 1-min
bars: level = the 09:15-09:19 low (short) / high (long) from the 1-min bars; entry = first 1-min bar from 09:20 crossing it, fill at
the level (or that bar's open if it opened beyond); stop 10% / 20% of daily ATR; out at the 15:15 bar's open. The 1-min entry bar
still has a tiny ambiguity: reported pessimistic (any touch = stop) and mid (as 175). Compared trade by trade with 175's 5-min
pess / mid / opt. 1-min bars cached in m1_cache/ (Yahoo can't re-serve them later). Sequential fetch (yfinance is not thread-safe: a 4-thread first run cross-wrote tickers), each file checked against the 5-min 09:15 bar."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd, yfinance as yf
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; CACHE = HERE / "m1_cache"; CACHE.mkdir(exist_ok=True)


def fetch(td):
    t, d = td; p = CACHE / f"{t}_{d}.csv"
    if p.exists(): return td, True
    for k in range(3):
        try:
            x = yf.Ticker(f"{t}.NS").history(start=d, end=(pd.Timestamp(d) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"), interval="1m", auto_adjust=False)
            if len(x):
                # sanity vs our 5-min file: the 09:15-09:19 1-min range must match the 5-min 09:15 bar within 1%, else reject
                m5 = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m5.index = m5.index.tz_convert("Asia/Kolkata").tz_localize(None)
                b5 = m5[m5.index == pd.Timestamp(d) + pd.Timedelta("9h15min")]
                xi = x.copy(); xi.index = xi.index.tz_convert("Asia/Kolkata").tz_localize(None); f1 = xi[xi.index < pd.Timestamp(d) + pd.Timedelta("9h20min")]
                if len(b5) == 0 or len(f1) == 0 or abs(f1.High.max() / b5.High.iloc[0] - 1) > 0.01 or abs(f1.Low.min() / b5.Low.iloc[0] - 1) > 0.01: return td, False
                x[["Open", "High", "Low", "Close", "Volume"]].to_csv(p); return td, True
        except Exception: pass
        time.sleep(2 + 3 * k)
    return td, False


def sim(r):
    m = pd.read_csv(CACHE / f"{r.ticker}_{r.date}.csv", index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None); m["hm"] = m.index.strftime("%H:%M")
    side = r.side; first = m[m.hm < "09:20"]; rest = m[(m.hm >= "09:20") & (m.hm < "15:15")]
    if len(first) == 0: return None
    lvl = first.Low.min() if side < 0 else first.High.max()
    hit = rest[(rest.Low < lvl) if side < 0 else (rest.High > lvl)]
    out = dict(lvl1m=lvl, traded1m=len(hit) > 0)
    if not len(hit): return out
    k = hit.index[0]; b0 = m.loc[k]; e = min(lvl, b0.Open) if side < 0 else max(lvl, b0.Open); after = m[m.index > k]
    out.update(e1m=e, et1m=b0.hm)
    for sm in (0.1, 0.2):
        sp = sm * r.atr; stp = e * (1 - side * sp / 100)
        for mode in ("pess", "mid"):
            touched = (b0.High >= stp) if side < 0 else (b0.Low <= stp); fo = (b0.Open <= lvl) if side < 0 else (b0.Open >= lvl)
            cb = (b0.Close >= stp) if side < 0 else (b0.Close <= stp); px, o = None, "close"
            if (mode == "pess" and touched) or (mode == "mid" and ((fo and touched) or cb)): px, o = stp, "stop"
            if px is None:
                for ts, b in after.iterrows():
                    if b.hm >= "15:15": px = b.Open; break
                    if (b.High >= stp) if side < 0 else (b.Low <= stp): px, o = stp, "stop"; break
            if px is None: px = after.Close.iloc[-1] if len(after) else e
            ret = side * (px - e) / e * 100; pos = 1000 / (sp / 100); key = f"{int(sm*100)}m1{mode}"
            out[f"o{key}"] = o; out[f"R{key}"] = ret / sp; out[f"r1k{key}"] = ret / 100 * pos - 85 * pos / 1e5
    return out


if __name__ == "__main__":
    A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
    S = A[(A.rv >= 1) & (A["rank"] <= 20) & A.traded & (A.date >= "2026-09-11")].copy()
    todo = list(zip(S.ticker, S.date)); print(f"{len(todo)} trades to fetch ({S.date.min()} .. {S.date.max()})", flush=True)
    ok, t0 = {}, time.time()
    with ThreadPoolExecutor(1) as ex:   # 2026-10-11: yf.download in 4 threads cross-wrote tickers (72% price mismatch) -> sequential + Ticker.history + 5-min sanity check
        for i, (td, good) in enumerate(ex.map(fetch, todo), 1):
            ok[td] = good
            if i % 50 == 0 or i == len(todo): print(f"  fetched {i}/{len(todo)}, missing {sum(not v for v in ok.values())}, {time.time()-t0:.0f}s", flush=True)
    S = S[[ok[(t, d)] for t, d in zip(S.ticker, S.date)]]
    X = S.join(pd.DataFrame([sim(r) or {} for _, r in S.iterrows()], index=S.index))
    X.to_csv(HERE / "orb_sip_1m.csv", index=False)
    X = X[X.traded1m == True]
    lv = (X.e1m / X.e - 1).abs() * 100
    print(f"\ntrades with 1-min data and a 1-min entry: {len(X)} | entry price 1m vs 5m: median diff {lv.median():.3f}%, same minute-bucket {(X.et1m.str[:4] == X.et.str[:4]).mean()*100:.0f}%")
    for sd, nm in ((-1, "SHORTS"), (1, "LONGS (info)")):
        G = X[X.side == sd]
        for sm in ("10", "20"):
            print(f"\n## {nm}, stop {sm}% ATR, same {len(G)} trades\n| version | stopped | win % | avg R (gross) | Rs/trade @1k risk (net) | w/o top-3 trades avg R |\n|---|---|---|---|---|---|")
            for lab, key in (("5-min PESSIMISTIC", f"{sm}pess"), ("5-min MID (used in 175)", f"{sm}mid"), ("5-min OPTIMISTIC", f"{sm}opt"),
                             ("1-MIN pessimistic", f"{sm}m1pess"), ("1-MIN mid", f"{sm}m1mid")):
                R = G[f"R{key}"]; rk = G[f"r1k{key}"] if f"r1k{key}" in G else None
                print(f"| {lab} | {(G[f'o{key}']=='stop').mean()*100:.0f}% | {(R>0).mean()*100:.0f}% | {R.mean():+.3f} | {rk.mean():+.0f} | {R.sort_values(ascending=False).iloc[3:].mean():+.3f} |")
            a = G[f"o{sm}mid"]; b = G[f"o{sm}m1mid"]
            print(f"outcome agreement 5-min MID vs 1-MIN mid: {(a == b).mean()*100:.0f}% | 5m said close but 1m stop: {((a=='close')&(b=='stop')).sum()} | 5m stop but 1m close: {((a=='stop')&(b=='close')).sum()}")
