"""Opening-range breakout on STOCKS IN PLAY, the Zarattini-Barbon-Aziz (2024) rules on NSE 5-min data (user, 2026-10-11; spec fixed
before running). Stocks: liquid (prev-day median 5-min turnover >= Rs15 lakh), price >= Rs100, 20d traded value >= Rs10 cr, ATR >= 2%,
no corp action, 09:15 bar present, >= 70 bars. Relative volume = 09:15 bar volume (estimated: day volume - other bars) / its 14-day
average (>= 10 days needed). In play = relvol >= 1 AND top 20 of the day by relvol. Direction = the 09:15 candle: red -> short a break
of its low, green -> long a break of its high (long reported for information). Entry = stop order at the level from 09:20 (a bar opening
beyond it fills at its open). Stop = 10% of daily ATR (also 20%). No target, out at the 15:15 bar's open. The entry bar is ambiguous
(high/low after the fill is unknown): PESSIMISTIC = stopped if the entry bar reaches the stop; OPTIMISTIC = stop checked from the next
bar. Comparison: same trade on every red / green open (no relvol pick), and relvol >= 1 without the top-20 cut.
5-min data 2026-06-10..10-08, all bear phase. Net = Rs85 per Rs1 lakh. Results only."""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR, INTRADAY_5M_DIR


OFFICIAL_OPEN = "--official-open" in sys.argv


def gen(t):
    p = INTRADAY_5M_DIR / f"{t}.csv"
    if not p.exists(): return []
    try: d = load(t)
    except Exception: return []
    c = d.Close; rawdf = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True); raw = rawdf.Volume
    D = pd.DataFrame({"pc": c.shift(1), "tv": d.traded_value_sma20.shift(1), "atrp": (d.atr14 / c * 100).shift(1),
                      "ca": d.corp_action_day if "corp_action_day" in d else False})
    m = pd.read_csv(p, index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    m = m[m.index >= "2026-05-01"]
    if len(m) < 500: return []
    m["day"] = m.index.normalize(); m["hm"] = m.index.strftime("%H:%M"); m["to"] = m.Volume * m.Close
    medto = m[m.Volume > 0].groupby("day").to.median().shift(1)
    v0 = {}
    for dd, g in m.groupby("day"):
        if g.hm.iloc[0] == "09:15" and len(g) >= 70 and dd in raw.index:
            x = raw[dd] - g.Volume.iloc[1:].sum()
            if x > 0: v0[dd] = x
    v0 = pd.Series(v0).sort_index(); avg = v0.rolling(14, min_periods=10).mean().shift(1)
    out = []
    for dd, g in m.groupby("day"):
        if dd < pd.Timestamp("2026-06-10") or dd not in D.index or dd not in v0.index or not (avg.get(dd, 0) > 0): continue
        x = D.loc[dd]
        if not (x.pc >= 100) or not (x.tv >= 1e8) or bool(x.ca) or not (x.atrp >= 2) or medto.get(dd, 0) < 15e5: continue
        g = g.sort_index(); f = g.iloc[0].copy()
        if OFFICIAL_OPEN:   # 2026-10-12: Yahoo's 5-min 09:15 'Open' is not the official NSE open (equal only 11% of days; daily
            oo = rawdf.Open.get(dd, np.nan)   # Yahoo open == NSE bhavcopy open 100%) -> colour flipped on 8% of in-play days.
            if oo == oo: f["Open"] = oo; f["High"] = max(f.High, oo); f["Low"] = min(f.Low, oo)   # candle as charts draw it
        if f.Close == f.Open: continue
        side = -1 if f.Close < f.Open else 1; lvl = f.Low if side < 0 else f.High
        rest = g.iloc[1:]; rest = rest[rest.hm < "15:15"]
        hit = rest[(rest.Low < lvl) if side < 0 else (rest.High > lvl)]
        r = dict(ticker=t, date=dd.strftime("%Y-%m-%d"), mon=dd.strftime("%Y-%m"), side=side, rv=v0[dd] / avg[dd], atr=x.atrp, traded=len(hit) > 0)
        if len(hit):
            k = hit.index[0]; b0 = g.loc[k]
            e = min(lvl, b0.Open) if side < 0 else max(lvl, b0.Open)
            after = g[g.index > k]; r.update(et=b0.hm, e=e)
            for sm in (0.1, 0.2):
                sp = sm * x.atrp; stp = e * (1 - side * sp / 100)
                for mode in ("pess", "mid", "opt"):
                    px, o = None, "close"; touched = (b0.High >= stp) if side < 0 else (b0.Low <= stp)
                    filled_at_open = (b0.Open <= lvl) if side < 0 else (b0.Open >= lvl)
                    closed_beyond = (b0.Close >= stp) if side < 0 else (b0.Close <= stp)
                    if mode == "pess" and touched: px, o = stp, "stop"
                    if mode == "mid" and ((filled_at_open and touched) or closed_beyond): px, o = stp, "stop"
                    if px is None:
                        for ts, b in after.iterrows():
                            if b.hm >= "15:15": px = b.Open; break
                            if (b.High >= stp) if side < 0 else (b.Low <= stp): px, o = stp, "stop"; break
                    if px is None: px = after.Close.iloc[-1] if len(after) else e
                    ret = side * (px - e) / e * 100; pos = 1000 / (sp / 100); key = f"{int(sm*100)}{mode}"
                    r[f"o{key}"] = o; r[f"R{key}"] = ret / sp; r[f"r1L{key}"] = ret * 1000 - 85; r[f"r1k{key}"] = ret / 100 * pos - 85 * pos / 1e5
                    r[f"sp{int(sm*100)}"] = sp
        out.append(r)
    return out


def row(lab, g, key, ND):
    g = g[g.traded]
    if len(g) == 0: return f"| {lab} | 0 |"
    R = g[f"R{key}"]; r1, rk = g[f"r1L{key}"], g[f"r1k{key}"]; win = R > 0
    byd = g.groupby("date")[f"r1k{key}"].sum().sort_values(ascending=False); wo = rk[~g.date.isin(byd.head(10).index)].mean()
    mon = " / ".join(f"{rk[g.mon == k].mean():+.0f}" for k in sorted(g.mon.unique()))
    return (f"| {lab} | {len(g):,} | {g.date.nunique()/ND*100:.0f}% | {(g[f'o{key}']=='stop').mean()*100:.0f}% | {win.mean()*100:.0f}% | "
            f"{R[win].mean():+.2f} / {R[~win].mean():+.2f} | {R.mean():+.3f} | {r1.mean():+.0f} | {rk.mean():+.0f} | {wo:+.0f} | {mon} |")


if __name__ == "__main__":
    from multiprocessing import Pool
    tk = sorted(p.stem for p in INTRADAY_5M_DIR.glob("*.csv") if not p.stem.startswith("_")); t0 = time.time()
    with Pool(6) as pl: A = pd.DataFrame(sum(pl.map(gen, tk, chunksize=8), []))
    A.to_csv(HERE / ("orb_sip_off.csv" if OFFICIAL_OPEN else "orb_sip.csv"), index=False)
    A["rank"] = A.groupby("date").rv.rank(ascending=False, method="first")
    ND = A.date.nunique()
    print(f"stock-days {len(A):,} on {ND} days ({A.date.min()} .. {A.date.max()}; relvol needs 10 days of history) in {time.time()-t0:.0f}s")
    T = A[A.traded]
    if "--check" in sys.argv:
        for _, r in T[(T.rv >= 1) & (T["rank"] <= 20) & (T.side < 0)].sample(3, random_state=3).iterrows():
            m = pd.read_csv(INTRADAY_5M_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True); m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
            g = m[m.index.normalize() == r.date]; g = g.assign(hm=g.index.strftime("%H:%M"))
            print(f"\n{r.ticker} {r.date} relvol {r.rv:.1f} rank {r['rank']:.0f} ATR {r.atr:.2f}% | short at {r.e:.2f} ({r.et}), stop 10% ATR = {r.sp10:.2f}% -> {r.e*(1+r.sp10/100):.2f} | pess {r.o10pess} {r.R10pess:+.2f}R, opt {r.o10opt} {r.R10opt:+.2f}R")
            print(g[(g.hm <= "10:30") | (g.hm >= "15:10")][["hm", "Open", "High", "Low", "Close"]].round(2).to_string(index=False))
        sys.exit()
    HD = "| trades | days | stopped | win % | avg win / avg loss (R) | avg R | Rs/trade @1L | @1k risk | @1k w/o top-10 days | @1k Jun / Jul / Aug / Sep / Oct |\n|---|---|---|---|---|---|---|---|---|---|---|"
    for sd, nm in ((-1, "SHORTS (red 09:15 candle, sell the break of its low)"), (1, "LONGS, for information (green candle, buy the break of its high)")):
        S = A[A.side == sd]
        for sm in ("10", "20"):
            print(f"\n## {nm}, stop {sm}% of ATR\n| group " + HD)
            for lab, g in (("IN PLAY: relvol >= 1, top 20 of the day", S[(S.rv >= 1) & (S["rank"] <= 20)]),
                           ("relvol >= 1, no top-20 cut", S[S.rv >= 1]), ("every open of this colour (no relvol pick)", S),
                           ("relvol < 1", S[S.rv < 1])):
                for mode in ("pess", "mid", "opt"): print(row(f"{lab} [{mode}]", g, sm + mode, ND))
    S = A[(A.side < 0) & (A.rv >= 1) & (A["rank"] <= 20) & A.traded]
    print("\n## concentration, in-play shorts\n| stop | mode | total R | top trade R | w/o top 5 trades avg R | w/o top 10 trades avg R | w/o top 10 days avg R |\n|---|---|---|---|---|---|---|")
    for sm in ("10", "20"):
        for mode in ("pess", "mid", "opt"):
            R = S[f"R{sm}{mode}"].sort_values(ascending=False); byd = S.groupby("date")[f"R{sm}{mode}"].sum().sort_values(ascending=False)
            print(f"| {sm}% ATR | {mode} | {R.sum():+.0f} | {R.iloc[0]:+.1f} ({S.loc[R.index[0], 'ticker']} {S.loc[R.index[0], 'date']}) | {R.iloc[5:].mean():+.3f} | {R.iloc[10:].mean():+.3f} | {S[~S.date.isin(byd.head(10).index)][f'R{sm}{mode}'].mean():+.3f} |")
    print(f"\nin-play shorts: median stop 10% ATR {S.sp10.median():.2f}%, entry time median {S.et.min()}..{S.et.max()}, share entered by 09:30 {(S.et <= '09:30').mean()*100:.0f}%, by 10:15 {(S.et <= '10:15').mean()*100:.0f}%; in-play stocks per day {A[(A.rv>=1)&(A['rank']<=20)].groupby('date').size().median():.0f}, red among them median {A[(A.rv>=1)&(A['rank']<=20)&(A.side<0)].groupby('date').size().median():.0f}")
