"""ORB + FIB PULLBACK, the Reddit 'ORB fib strategy' base version (user, 2026-10-12: 'lets try the base first'; rules read from the post +
OP's replies, made mechanical BEFORE running): opening range 09:15-09:44 (30 min); break of its high (long) / low (short) from 09:45,
first side broken = direction, one trade per stock per day. After the break track the swing (lowest low since the break for a short);
fib from the session extreme so far (day high for a short) to that swing. Setup: price pulls back to >= 50% (without trading beyond
78.6%; a deeper pullback kills the setup; a new swing extreme resets it). Entry: first STRONG candle in the trade direction (body >= 50%
of its range) closing back through the deepest level reached (61.8% if the pullback reached it, else 50%), at that close, before 15:00.
Stop = the 78.6% level. Target = the swing extreme (0%). Skip if reward:risk < 2. Exit target / stop / 15:15 open (stop first in a bar).
MACD left out (OP: optional). Universe as 175 (>= Rs100, 20d value >= Rs10 cr, ATR >= 2%, prev-day median 5-min turnover >= Rs15 lakh);
also the in-play top-20 subset (175's relvol ranks). 5-min bars 2026-06-10..10-09. Net = Rs85 per Rs1 lakh. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from orb_common import read5_official
from data.paths import INTRADAY_5M_DIR


def setup(d, s):
    """d = one day's 5-min bars with hm. s = -1 short / +1 long. Returns a trade dict or a reason string."""
    orr = d[d.hm < "09:45"]; aft = d[(d.hm >= "09:45") & (d.hm < "15:15")]
    if len(orr) < 5 or len(aft) == 0: return "no data"
    oh, ol = orr.High.max(), orr.Low.min()
    brk_dn = aft[aft.Low < ol]; brk_up = aft[aft.High > oh]
    first = None
    if len(brk_dn) and (not len(brk_up) or brk_dn.index[0] <= brk_up.index[0]): first = -1
    elif len(brk_up): first = 1
    if first != s: return "no break this side"
    k0 = (brk_dn if s < 0 else brk_up).index[0]
    ext_far = d[d.index <= k0].High.max() if s < 0 else d[d.index <= k0].Low.min()   # session extreme on the other side (fib 100%)
    swing = None; deepest = 0.0; reached = False
    bars = d[(d.index >= k0) & (d.hm < "15:15")]
    for ts, b in bars.iterrows():
        if swing is None or ((b.Low < swing) if s < 0 else (b.High > swing)):
            swing = b.Low if s < 0 else b.High; deepest = 0.0; reached = False
            if ts == k0: continue
            continue
        rngf = (ext_far - swing) if s < 0 else (swing - ext_far)
        if rngf <= 0: continue
        lv = lambda f: swing + s * -1 * f * rngf if s < 0 else swing - f * rngf
        f50, f618, f786 = lv(0.5), lv(0.618), lv(0.786)
        pull = ((b.High - swing) if s < 0 else (swing - b.Low)) / rngf
        if pull > 0.786: return "pullback too deep (> 78.6%)"
        deepest = max(deepest, pull)
        if deepest >= 0.5: reached = True
        if not reached or b.hm >= "15:00": continue
        lvl = f618 if deepest >= 0.618 else f50
        body = abs(b.Close - b.Open); rng = b.High - b.Low
        strong = rng > 0 and body / rng >= 0.5 and ((b.Close < b.Open) if s < 0 else (b.Close > b.Open))
        if strong and ((b.Close < lvl) if s < 0 else (b.Close > lvl)):
            e, stp, tgt = b.Close, f786, swing
            risk, rew = abs(stp - e), abs(e - tgt)
            if risk <= 0 or rew / risk < 2: return "reward:risk < 2"
            return dict(entry_ts=ts, et=b.hm, e=e, stp=stp, tgt=tgt, rr=rew / risk, lvl=0.618 if deepest >= 0.618 else 0.5, swing=swing, far=ext_far, oh=oh, ol=ol)
    return "no pullback to 50% / no trigger candle"


def walk(d, tr, s):
    for ts, b in d[d.index > tr["entry_ts"]].iterrows():
        if b.hm >= "15:15": return b.Open, "close"
        if (b.High >= tr["stp"]) if s < 0 else (b.Low <= tr["stp"]): return tr["stp"], "stop"
        if (b.Low <= tr["tgt"]) if s < 0 else (b.High >= tr["tgt"]): return tr["tgt"], "target"
    return d.Close.iloc[-1], "close"


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d0 = load(t)
    except Exception: return []
    c = d0.Close
    D = pd.DataFrame({"pc": c.shift(1), "tv": d0.traded_value_sma20.shift(1), "atrp": (d0.atr14 / c * 100).shift(1),
                      "ca": d0.corp_action_day if "corp_action_day" in d0 else False})
    m = read5_official(t)  # 2026-10-12: official 09:15 open
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1); out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index: continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index()
        if g.hm.iloc[0] != "09:15" or len(g) < 70: continue
        for s in (-1, 1):
            tr = setup(g, s)
            if isinstance(tr, str):
                out.append(dict(ticker=t, date=dd.strftime("%Y-%m-%d"), side=s, status=tr)); continue
            px, o = walk(g, tr, s); ret = s * (px - tr["e"]) / tr["e"] * 100; risk = abs(tr["stp"] - tr["e"]) / tr["e"] * 100; pos = 1000 / (risk / 100)
            out.append(dict(ticker=t, date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), side=s, status="TRADE", et=tr["et"], e=tr["e"], stp=tr["stp"],
                            tgt=tr["tgt"], rr=tr["rr"], lvl=tr["lvl"], risk=risk, o=o, R=ret / risk, r1L=ret * 1000 - 85, r1k=ret / 100 * pos - 85 * pos / 1e5,
                            swing=tr["swing"], far=tr["far"], oh=tr["oh"], ol=tr["ol"]))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); t0 = time.time()
    with Pool(6) as pl: X = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    X.to_csv(HERE / "orb_fib.csv", index=False); ND = X.date.nunique()
    A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
    inplay = set(zip(A[(A.rv >= 1) & (A["rank"] <= 20)].ticker, A[(A.rv >= 1) & (A["rank"] <= 20)].date))
    X["inplay"] = [(t, d) in inplay for t, d in zip(X.ticker, X.date)]
    print(f"stock-day-sides {len(X):,} on {ND} days in {time.time()-t0:.0f}s")
    T = X[X.status == "TRADE"]
    if "--check" in sys.argv:
        for _, r in T.sample(4, random_state=5).iterrows():
            m = pd.read_csv(INTRADAY_5M_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
            g = m[m.index.normalize() == pd.Timestamp(r.date)]; g = g.assign(hm=g.index.strftime("%H:%M"))
            print(f"\n{r.ticker} {r.date} {'SHORT' if r.side < 0 else 'LONG'} | OR {r.ol:.2f}-{r.oh:.2f} | fib 100% {r.far:.2f} -> 0% (swing) {r.swing:.2f} | entry {r.e:.2f} at {r.et} (closed through the {r.lvl} level) | stop {r.stp:.2f} target {r.tgt:.2f} (R:R {r.rr:.1f}) -> {r.o} {r.R:+.2f}R")
            print(g[(g.hm >= "09:40") & (g.hm <= r.et)][["hm", "Open", "High", "Low", "Close"]].round(2).to_string(index=False))
        sys.exit()
    print("\nfunnel (stock-day-sides): " + " | ".join(f"{k}: {v:,}" for k, v in X.status.value_counts().items()))
    HD = "| group | trades | days with a trade | target / stop / close % | win % | avg win / avg loss (R) | avg R | Rs @1k net | w/o top-10 days | half 1 / half 2 | Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|---|"
    def row(lab, g):
        if len(g) == 0: return f"| {lab} | 0 |"
        k = g.r1k; R = g.R; w = R > 0; byd = g.groupby("date").r1k.sum().sort_values(ascending=False); wo = k[~g.date.isin(byd.head(10).index)].mean()
        mon = " / ".join(f"{k[g.mon == mm].mean():+.0f}" for mm in sorted(g.mon.unique()))
        return (f"| {lab} | {len(g)} | {g.date.nunique()} ({g.date.nunique()/ND*100:.0f}%) | {(g.o=='target').mean()*100:.0f} / {(g.o=='stop').mean()*100:.0f} / {(g.o=='close').mean()*100:.0f} | "
                f"{w.mean()*100:.0f}% | {R[w].mean():+.2f} / {R[~w].mean():+.2f} | {R.mean():+.2f} | {k.mean():+.0f} | {wo:+.0f} | {k[g.date <= '2026-08-14'].mean():+.0f} / {k[g.date >= '2026-08-17'].mean():+.0f} | {mon} |")
    print("\n" + HD)
    for sd, sn in ((-1, "SHORTS"), (1, "LONGS")):
        print(row(f"{sn}, all liquid", T[T.side == sd])); print(row(f"{sn}, in-play top 20", T[(T.side == sd) & T.inplay]))
    print(f"\nmedian risk {T.risk.median():.2f}%, median R:R at entry {T.rr.median():.1f}, entry at the 61.8% level {(T.lvl == 0.618).mean()*100:.0f}% of trades, entry time median {sorted(T.et)[len(T)//2]}")
