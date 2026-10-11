"""Filters to cut stops on 175's in-play ORB shorts (user, 2026-10-11; spec fixed before running). Population: the 573 in-play shorts
(relvol >= 1, top 20/day, red 09:15 candle, sell-stop at its low), 5-min MID entry-bar rule (176: agrees with 1-min on 99-100%).
Stops 20% of ATR (robust to the entry-bar question) and 10%. No target, out 15:15. Judged on avg R and Rs @1k net incl. w/o top-10 days,
not on the stop rate. Filters (all known at entry, cut-offs declared): F1 yday daily EMA8 < EMA34 | F2 gap <= -0.5 / -0.5..+0.5 / >= +0.5
| F3 09:15 open < yday low | F4 strong candle: body >= 60% of range and close in the bottom 25% | F5 candle range <= 0.5 x daily ATR
| F6 Nifty 09:15 5-min candle red (Nifty 5-min only from 2026-07-10 -> F6 on that subset) | F7 relvol rank <= 5 vs 6-20 | F8 entry
by 09:30. PASS = kept beats baseline (Rs @1k net) in BOTH halves (2026-06-24..08-14 / 08-17..10-08) AND w/o top-10 days. Pairs only
of passing filters. Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import INTRADAY_5M_DIR, INDEX_INTRADAY_DIR


def feats(a):
    t, g = a; d = load(t); e8 = d.Close.ewm(span=8, adjust=False).mean().shift(1); e34 = d.Close.ewm(span=34, adjust=False).mean().shift(1)
    yl = d.Low.shift(1); pc = d.Close.shift(1)
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    out = []
    for ix, r in g.iterrows():
        dd = pd.Timestamp(r.date); f = m.loc[dd + pd.Timedelta("9h15min")]; rng = f.High - f.Low
        out.append(dict(ix=ix, F1=e8[dd] < e34[dd], gap=(f.Open / pc[dd] - 1) * 100, F3=f.Open < yl[dd],
                        F4=(rng > 0) and (abs(f.Close - f.Open) / rng >= 0.6) and ((f.Close - f.Low) / rng <= 0.25),
                        F5=rng / f.Open * 100 <= 0.5 * r.atr))
    return out


def row(lab, g, sm, base=None):
    if len(g) == 0: return f"| {lab} | 0 |"
    R = g[f"R{sm}mid"]; rk = g[f"r1k{sm}mid"]; w = R > 0
    byd = g.groupby("date")[f"r1k{sm}mid"].sum().sort_values(ascending=False); wo = rk[~g.date.isin(byd.head(10).index)].mean()
    h1, h2 = rk[g.date <= "2026-08-14"].mean(), rk[g.date >= "2026-08-17"].mean()
    mon = " / ".join(f"{rk[g.mon == k].mean():+.0f}" for k in sorted(g.mon.unique()))
    return (f"| {lab} | {len(g)} | {(g[f'o{sm}mid']=='stop').mean()*100:.0f}% | {w.mean()*100:.0f}% | {R[w].mean():+.1f} / {R[~w].mean():+.2f} | "
            f"{R.mean():+.2f} | {rk.mean():+.0f} | {wo:+.0f} | {h1:+.0f} / {h2:+.0f} | {mon} |"), (rk.mean(), wo, h1, h2)


if __name__ == "__main__":
    A = pd.read_csv(HERE / "orb_sip.csv"); A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
    S = A[(A.side < 0) & (A.rv >= 1) & (A["rank"] <= 20) & A.traded].copy()
    with ThreadPoolExecutor(1) as ex: F = pd.DataFrame(sum(ex.map(feats, list(S.groupby("ticker"))), [])).set_index("ix")
    S = S.join(F)
    n = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True); n.index = n.index.tz_convert("Asia/Kolkata").tz_localize(None)
    n915 = n[n.index.strftime("%H:%M") == "09:15"]; nred = {k.strftime("%Y-%m-%d"): v for k, v in (n915.Close < n915.Open).items()}
    S["F6"] = S.date.map(nred); S["F7"] = S["rank"] <= 5; S["F8"] = S.et <= "09:30"
    S.to_csv(HERE / "orb_sip_filters.csv", index=False)
    print(f"in-play shorts {len(S)} on {S.date.nunique()} days | Nifty 09:15 known for {S.F6.notna().sum()} trades (from {S[S.F6.notna()].date.min()})")
    HD = "| trades | stopped | win % | avg win / loss (R) | avg R gross | Rs @1k net | w/o top-10 days | half 1 / half 2 | Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|"
    FL = [("F1 stock daily 8 < 34 EMA", "F1"), ("F3 opened below yday low", "F3"), ("F4 strong red candle", "F4"),
          ("F5 candle range <= 0.5 x ATR", "F5"), ("F7 relvol rank <= 5", "F7"), ("F8 entry by 09:30", "F8")]
    passed = {}
    for sm in ("20", "10"):
        print(f"\n## stop {sm}% of ATR\n| group " + HD)
        b, bs = row("BASELINE (all in-play shorts)", S, sm); print(b)
        for lab, c in FL:
            k, ks = row(f"{lab}: KEPT", S[S[c] == True], sm); r, _ = row(f"{lab}: removed", S[S[c] == False], sm); print(k); print(r)
            ok = ks[0] > bs[0] and ks[1] > bs[1] and ks[2] > bs[2] and ks[3] > bs[3]
            if sm == "20": passed[c] = ok
        for lab, msk in (("F2 gap <= -0.5%", S.gap <= -0.5), ("F2 gap -0.5..+0.5%", S.gap.between(-0.5, 0.5, inclusive="neither")), ("F2 gap >= +0.5%", S.gap >= 0.5)):
            print(row(lab, S[msk], sm)[0])
        T = S[S.F6.notna()]; print(row("F6 subset BASELINE (from 2026-07-10)", T, sm)[0])
        print(row("F6 Nifty 09:15 red: KEPT", T[T.F6 == True], sm)[0]); print(row("F6 Nifty 09:15 red: removed", T[T.F6 == False], sm)[0])
    print("\nPASS (20% stop: kept beats baseline net, w/o top-10 days, both halves): " + ", ".join(f"{c} {'PASS' if v else 'no'}" for c, v in passed.items()) + " | F2 / F6 judged by eye (groups / subset)")
    P = [c for c, v in passed.items() if v]
    if len(P) >= 2:
        for sm in ("20", "10"):
            print(f"\n## pairs of passing filters, stop {sm}% of ATR\n| group " + HD); print(row("BASELINE", S, sm)[0])
            for i in range(len(P)):
                for j in range(i + 1, len(P)): print(row(f"{P[i]} + {P[j]}", S[(S[P[i]] == True) & (S[P[j]] == True)], sm)[0])
