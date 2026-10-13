"""RETRACE ENTRY on the user's SUPPORT candle (user, 2026-10-13: 'I was always catching it when price was back at the 34 EMA, never after a
long move' -- MOTILALOFS 11:00-11:50 / 13:20-13:30 sat on the line, 1035-1036 traded; 218 entered at the hourly close = 0.88% stop).
Two splits declared by the user: daily 8-EMA support right under (yesterday's EMA8 = the touch price), and Nifty up.
Spec fixed before running:
  Universe: v1's (liquid, >= Rs100, ATR >= 2%, stock daily EMA8 > EMA34 yesterday).
  Setup: 218's SUPPORT candle on the 10:15 / 11:15 / 12:15 / 13:15 hourly bar vs the 1H EMA34 of the previous completed hour
    (low <= line < close, opened >= line - 0.2%, close in the top 40%).
  Entry (after the support candle has CLOSED, within the next 2 hours, entry bar starting before 14:30): a buy limit at line + 0.1% (line =
    the 1H EMA34 for the current hour) fills on the first bar whose low reaches it, at that price or the bar open if it opened lower.
    Skip if that open is already at / below the stop.
  Stop: support candle low - 0.05%. Exits: +1% target | 2R target | hold to 15:15. Stop first if stop and target share a bar; a fill bar whose
    low also reaches the stop counts as stopped (5-min data cannot order them -- conservative).
  Splits: D8 = yesterday's daily EMA8 within 0.3% UNDER the support low (second support) vs not;
          NIFTY = Nifty above its own day open at the fill (30m set: Nifty 5-min close of the bar before the fill; 3-yr set: Nifty 1H close of
          the support-candle hour) vs not.
  Two data sets: 30m-SET = 5-min bars 2026-06-11 .. 2026-10-13 (precise fills; all Nifty-below-200d); 3YR-SET = hourly bars 2024-01 ..
    2026-10 (fill on a later hourly bar whose low reaches the limit; the fill hour's low at / below the stop = stopped -- approximate).
  Score: Rs per Rs1,000 risk net of Rs85 per Rs1 lakh; gross R; w/o top-10 days; by month (30m) / year + Nifty 200d (3yr); fills stopped
  within 15 min (30m) -- the 'a limit fills the losers' check (plan B 83 / 86). Hand check: MOTILALOFS 2026-10-13 printed."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR, INTRADAY_5M_DIR
HOURS = ("10:15", "11:15", "12:15", "13:15")
ND = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index()
NOPEN = ND.Open; N200 = (ND.Close > ND.Close.rolling(200).mean()).shift(1)
ix = HERE.parent / "data" / "index_intraday"
def _idx(f):
    x = pd.read_csv(ix / f, index_col=0); x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); return x[~x.index.duplicated()]
N5 = _idx("_NIFTY_5m_60d.csv").Close; N1 = _idx("_NIFTY_1h.csv").Close


def score(e, stp, px):
    risk = (e - stp) / e * 100
    return ((px / e - 1) * 100 / risk) * 1000 - 85 * (1000 / (risk / 100)) / 1e5, (px - e) / (e - stp)


def gen(t):
    out = []
    try:
        d = load(t); c = d.Close
        dc = pd.DataFrame({"pc": c, "atrp": d.atr14 / c * 100, "tv": d.traded_value_sma20, "e8": c.ewm(span=8, adjust=False).mean(),
                           "up": c.ewm(span=8, adjust=False).mean() > c.ewm(span=34, adjust=False).mean()}).shift(1)
        H = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0)
    except Exception: return out
    H.index = pd.to_datetime(H.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); H = H[~H.index.duplicated()]
    if len(H) < 100: return out
    H["line_prev"] = H.Close.ewm(span=34, adjust=False).mean().shift(1)     # line valid DURING each hour
    H["day"] = H.index.normalize(); H["hm"] = H.index.strftime("%H:%M"); H["n"] = np.arange(len(H))
    nz = H[H.Volume > 0]; liq = ((nz.Volume * nz.Close).groupby(nz.day).median() / 12 * 0.72 / 1e5).shift(1)
    p5 = INTRADAY_5M_DIR / f"{t}.csv"; M = None
    if p5.exists():
        M = pd.read_csv(p5, index_col=0, parse_dates=True); M.index = M.index.tz_convert("Asia/Kolkata").tz_localize(None); M = M[~M.index.duplicated()]
        M["hm"] = M.index.strftime("%H:%M"); M["day"] = M.index.normalize()
    for day, g in H[H.day >= "2024-01-01"].groupby("day"):
        if day not in dc.index: continue
        r = dc.loc[day]
        if not (r.up and r.pc >= 100 and r.atrp >= 2 and r.tv >= 1e8 and liq.get(day, 0) >= 15): continue
        hours = list(g.index)
        for i, (k, b) in enumerate(g.iterrows()):
            if b.hm not in HOURS or b.n < 60: continue
            L0 = b.line_prev
            if not (b.Low <= L0 < b.Close) or b.High <= b.Low: continue
            cp = (b.Close - b.Low) / (b.High - b.Low)
            if not ((b.Open / L0 - 1) * 100 >= -0.2 and cp >= 0.6): continue
            stp = b.Low * (1 - 0.0005)
            d8 = 0 <= (b.Low / r.e8 - 1) * 100 <= 0.3
            base = dict(t=t, day=day, hm=b.hm, low=b.Low, line=L0, d8=d8, n200=bool(N200.get(day, False)))
            # ---------- 3YR-SET: hourly approximation
            nxt = g.iloc[i + 1:i + 3]
            for k2, b2 in nxt.iterrows():
                if b2.hm > "14:15": break
                lim = b2.line_prev * 1.001
                if b2.Low > lim: continue
                e = min(lim, b2.Open)
                if e <= stp: break
                nup = N1.get(k) is not None and day in NOPEN.index and N1.get(k) > NOPEN[day]
                rec = dict(base, set="3YR", fill=b2.hm, e=e, stp=stp, nifty_up=bool(nup))
                rest = g[g.index > k2]
                for ex in ("1%", "2R", "hold"):
                    tgt = e * 1.01 if ex == "1%" else (e + 2 * (e - stp) if ex == "2R" else np.inf)
                    if b2.Low <= stp: px, how = stp, "stop"
                    else:
                        px, how = None, "time"
                        for lb in rest.itertuples():
                            if lb.Low <= stp: px, how = stp, "stop"; break
                            if lb.High >= tgt: px, how = tgt, "target"; break
                        if px is None: px = g.Close.iloc[-1]
                    rec[ex], rec[ex + "_R"] = score(e, stp, px); rec[ex + "_how"] = how
                out.append(rec); break
            # ---------- 30m-SET: 5-min fills
            if M is None: continue
            m = M[M.day == day]
            if len(m) < 60: continue
            start = k + pd.Timedelta("60min"); w = m[(m.index >= start) & (m.index < start + pd.Timedelta("120min")) & (m.hm < "14:30")]
            for k5, b5 in w.iterrows():
                hr = (k5 - pd.Timedelta("15min")).floor("60min") + pd.Timedelta("15min")
                if hr not in H.index: continue
                lim = H.at[hr, "line_prev"] * 1.001
                if b5.Low > lim: continue
                e = min(lim, b5.Open)
                if e <= stp: break
                prevn = N5[(N5.index < k5) & (N5.index.normalize() == day)]
                nup = (prevn.iloc[-1] > NOPEN[day]) if len(prevn) and day in NOPEN.index else np.nan
                rec = dict(base, set="30m", fill=b5.hm, e=e, stp=stp, nifty_up=nup)
                rest = m[(m.index > k5)]
                stopped15 = b5.Low <= stp or bool((rest[rest.index <= k5 + pd.Timedelta("15min")].Low <= stp).any())
                rec["stop15"] = stopped15
                for ex in ("1%", "2R", "hold"):
                    tgt = e * 1.01 if ex == "1%" else (e + 2 * (e - stp) if ex == "2R" else np.inf)
                    if b5.Low <= stp: px, how = stp, "stop"
                    else:
                        px, how = None, "time"
                        for lb in rest.itertuples():
                            if lb.hm >= "15:15": px = lb.Open; break
                            if lb.Low <= stp: px, how = stp, "stop"; break
                            if lb.High >= tgt: px, how = tgt, "target"; break
                        if px is None: px = m.Close.iloc[-1]
                    rec[ex], rec[ex + "_R"] = score(e, stp, px); rec[ex + "_how"] = how
                out.append(rec); break
    return out


def line(lab, x, ex):
    if len(x) == 0: return f"| {lab} | 0 |"
    v = x[ex]; top = x.groupby("day")[ex].sum().sort_values(ascending=False).head(10).index
    return (f"| {lab} | {len(x)} | {(v > 0).mean()*100:.0f}% | {(x[ex + '_how'] == 'stop').mean()*100:.0f}% | {x[ex + '_R'].mean():+.2f} | {v.mean():+.0f} | "
            f"{v[~x.day.isin(top)].mean():+.0f} |")


if __name__ == "__main__":
    uni = [p.stem for p in (HERE / "h1_cache").glob("*.csv")]
    with Pool(6) as pool:
        res = []
        for k, r in enumerate(pool.imap_unordered(gen, uni, chunksize=10), 1):
            res.extend(r)
            if k % 400 == 0: print(f"  {k}/{len(uni)} tickers", flush=True)
    X = pd.DataFrame(res); X.to_csv(HERE / "support_retrace_long.csv", index=False)
    X["yr"] = pd.to_datetime(X.day).dt.year; X["month"] = pd.to_datetime(X.day).dt.strftime("%Y-%m"); X["day"] = X.day.astype(str)
    print("HAND CHECK MOTILALOFS 2026-10-13:")
    print(X[(X.t == "MOTILALOFS") & (X.day.str[:10] == "2026-10-13")][["set", "hm", "low", "line", "fill", "e", "stp", "d8", "nifty_up", "1%_how", "1%_R", "hold_R"]].round(2).to_string(index=False))
    print("random 30m checks:"); print(X[X.set == "30m"].sample(3, random_state=2)[["t", "day", "hm", "low", "line", "fill", "e", "stp", "1%_how", "1%_R"]].round(2).to_string(index=False))
    H_ = "| group | trades | win % | stopped | gross R | Rs @1k net | w/o top-10 days |\n|---|---|---|---|---|---|---|"
    for st in ("30m", "3YR"):
        S = X[X.set == st]
        print(f"\n===== {st} SET: {len(S)} fills =====" + (f" | fills stopped within 15 min: {S.stop15.mean()*100:.0f}%" if st == "30m" else ""))
        for ex in ("1%", "2R", "hold"):
            print(f"\n-- exit {ex}\n{H_}")
            print(line("ALL fills", S, ex))
            print(line("D8: daily EMA8 within 0.3% under the low", S[S.d8 == True], ex)); print(line("  no D8", S[S.d8 == False], ex))
            print(line("NIFTY up at the fill", S[S.nifty_up == True], ex)); print(line("  Nifty not up", S[S.nifty_up == False], ex))
            print(line("D8 + NIFTY up", S[(S.d8 == True) & (S.nifty_up == True)], ex))
            if st == "3YR":
                for nv, lab in ((True, "Nifty ABOVE 200d"), (False, "Nifty BELOW 200d")): print(line(lab, S[S.n200 == nv], ex))
        per = "month" if st == "30m" else "yr"
        print(f"\nhold exit, Rs @1k by {per} (all / D8 + Nifty up): " + " | ".join(f"{k}: {g['hold'].mean():+.0f} ({len(g)}) / {g[(g.d8 == True) & (g.nifty_up == True)]['hold'].mean():+.0f} ({((g.d8 == True) & (g.nifty_up == True)).sum()})" for k, g in S.groupby(per)))
