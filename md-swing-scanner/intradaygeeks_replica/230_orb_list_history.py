"""REBUILD THE ORB SCAN LIST (185's top-20 in-play) FOR EVERY PAST DAY, in one pass, and re-score 228 / 229 on it (user, 2026-10-16:
'why on 450? I am only working with the 2-3 first which you short list and then the rest 8-10 listed by you as part of ORB scan').
Same rules as 185 (prep_row + the replay relvol): yesterday's close >= Rs100, 20-day traded value >= Rs10 cr, daily ATR14 >= 2%,
previous day's median 5-min turnover >= Rs15 lakh, >= 10 days of first-bar history; relvol = first-bar volume (day volume - the 5-min
bars from 09:20 on) / its 14-day average, >= 1, top 20 of the day; side = 09:15 candle colour with the OFFICIAL open (daily Open).
Output orb_list_history.csv (date, ticker, rank, relvol, side). Checked against the saved live scans orb_scans/orb_scan_202610*.csv.
Then: 228 (A / C / D) and 229 ((a) / (b)) setups restricted to stock-days on the list; splits rank 1-3 vs 4-20 and red vs green 09:15."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from backtest import load
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
COST = 0.085


def per_ticker(t):
    try:
        d = load(t); raw = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True); raw = raw[~raw.index.duplicated()]
        x = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0)
    except Exception: return []
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    x = x.assign(day=x.index.normalize(), hm=x.index.strftime("%H:%M"))
    v0, f915, liq = {}, {}, {}
    for dd, g in x.groupby("day"):
        if g.hm.iloc[0] != "09:15": continue
        f915[dd] = g.iloc[0]
        gv = g[g.Volume > 0]
        if len(gv): liq[dd] = (gv.Volume * gv.Close).median() / 1e5
        if len(g) >= 70 and dd in raw.index:
            v = raw.Volume[dd] - g.Volume.iloc[1:].sum()
            if v > 0: v0[dd] = v
    v0 = pd.Series(v0).sort_index(); liq = pd.Series(liq).sort_index()
    out = []
    days = sorted(f915)
    for k in range(1, len(days)):
        D, P = days[k], days[k - 1]
        dp = d[d.index < D]
        if len(dp) < 60 or D not in raw.index or dp.index[-1] != P: continue
        if dp.Close.iloc[-1] < 100 or dp.traded_value_sma20.iloc[-1] < 1e8 or dp.atr14.iloc[-1] / dp.Close.iloc[-1] * 100 < 2: continue
        if liq.get(P, 0) < 15: continue
        hist = v0[v0.index < D].tail(14)
        if len(hist) < 10 or D not in v0.index: continue
        f = f915[D]; oo = raw.Open[D]; c = f.Close
        side = "SHORT" if c < oo else ("long" if c > oo else "doji")
        out.append(dict(date=D.strftime("%Y-%m-%d"), ticker=t, relvol=v0[D] / hist.mean(), side=side))
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
    with Pool(6) as p: A = pd.DataFrame([r for rr in p.map(per_ticker, uni, chunksize=20) for r in rr])
    A = A[(A.relvol >= 1) & (A.side != "doji")].sort_values(["date", "relvol"], ascending=[True, False])
    A["rank"] = A.groupby("date").cumcount() + 1; L = A[A["rank"] <= 20].copy()
    L.to_csv(HERE / "orb_list_history.csv", index=False)
    print(f"list: {len(L)} stock-days on {L.date.nunique()} days ({L.date.min()} .. {L.date.max()})")
    print("\n### Check vs the saved live scans (top-20 overlap)\n| day | live file | live tickers | rebuilt | overlap | live top-3 in rebuilt top-3 |\n|---|---|---|---|---|---|")
    for f in sorted((HERE / "orb_scans").glob("orb_scan_202610*_09[23]?.csv")):
        day = f.name.split("_")[2]; dd = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        S = pd.read_csv(f); live = list(S.ticker); reb = list(L[L.date == dd].ticker)
        print(f"| {dd} | {f.name} | {len(live)} | {len(reb)} | {len(set(live) & set(reb))} | {len(set(live[:3]) & set(reb[:3]))}/3 |")

    key = L.set_index(["ticker", "date"])
    def on_list(X):
        X = X.merge(L[["ticker", "date", "rank", "side"]], on=["ticker", "date"], how="inner"); return X
    def cells(x, v, tg):
        x = x[x[f"{v}_{tg}_ret"].notna()] if f"{v}_{tg}_ret" in x else x.iloc[0:0]
        if not len(x): return ["0", "", "", ""]
        w = x[f"{v}_{tg}_why"]
        return [str(len(x)), f"{(w=='stop').mean()*100:.0f} / {(w=='target').mean()*100:.0f} / {(w=='time').mean()*100:.0f}%",
                f"{x[f'{v}_risk'].median():.2f}%", f"{(x[f'{v}_{tg}_ret'].mean()-COST)*1000:+.0f} ({(x[f'{v}_{tg}_ret']/x[f'{v}_risk']).mean():+.2f}R)"]
    def groups(X, rk="t1"):
        top10 = X.groupby("date")[rk].sum().nlargest(10).index if rk in X else []
        g = [("ALL on the list", X), ("rank 1-3", X[X["rank"] <= 3]), ("rank 4-20", X[X["rank"] > 3]),
             ("red 09:15 (SHORT side)", X[X.side == "SHORT"]), ("green 09:15", X[X.side == "long"])]
        if len(top10): g.append(("top-10 days removed", X[~X.date.isin(top10)]))
        return g + [(f"month {mo}", gg) for mo, gg in X.groupby(X.date.str[:7])]
    def table(title, X, vs, tg):
        X = X.assign(t1=X[f"{vs[0]}_{tg}_ret"])
        print(f"\n### {title}\n| group | " + " | ".join(f"{v} n | {v} stop/target/time | {v} med stop | {v} net Rs@1L (R)" for v in vs) + " |")
        print("|---|" + "---|" * (4 * len(vs)))
        for lab, x in groups(X): print(f"| {lab} | " + " | ".join(" | ".join(cells(x, v, tg)) for v in vs) + " |")
    P = on_list(pd.read_csv(HERE / "morning_pop_rejection.csv")); F = on_list(pd.read_csv(HERE / "morning_failed_breakout.csv"))
    T = on_list(pd.read_csv(HERE / "morning_double_top.csv"))
    print(f"\non the list: 228 rejection setups {len(P)}, 228 failed breakouts {len(F)}, 229 double tops {len(T)}")
    for tg, nm in (("t1", "1% target"), ("r2", "2R target")):
        table(f"228 pop-into-level rejection, {nm}: A bar-close / C spike-fail", P, ["A", "C"], tg)
        table(f"228 D failed breakout, {nm}", F, ["D"], tg)
        table(f"229 double top, {nm}: (a) next-bar open / (b) sell-stop under bar 2", T, ["a", "b"], tg)
    for nm, X in (("228 A", P), ("228 D", F), ("229", T)):
        for t, d in (("RBLBANK", "2026-10-13"), ("JSWSTEEL", "2026-10-14"), ("CEATLTD", "2026-10-15"), ("GRANULES", "2026-10-15"), ("ORIENTELEC", "2026-10-16")):
            h = X[(X.ticker == t) & (X.date == d)]
            print(f"  {nm} {t} {d}: " + ("on the list, rank " + str(int(h['rank'].iloc[0])) if len(h) else "-"))
    for t, d in (("RBLBANK", "2026-10-13"), ("JSWSTEEL", "2026-10-14"), ("CEATLTD", "2026-10-15"), ("GRANULES", "2026-10-15"), ("ORIENTELEC", "2026-10-16")):
        h = L[(L.ticker == t) & (L.date == d)]; print(f"  list {t} {d}: " + (f"rank {int(h['rank'].iloc[0])} relvol {h.relvol.iloc[0]:.1f} {h.side.iloc[0]}" if len(h) else "NOT on the rebuilt list"))
