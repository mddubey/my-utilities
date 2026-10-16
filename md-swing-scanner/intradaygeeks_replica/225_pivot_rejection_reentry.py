"""5-MIN PIVOT REJECTION SHORT + RE-ENTRY AFTER THE STOP (user, 2026-10-15, from live GRANULES: short 822 at the weekly
pivot ~10:00, stopped at ~824 by the Nifty push, then it fell back under 822 and ran to 813). Spec declared in chat before running:
  Data: 30m set (5-min bars, 2026-06..10). Universe: prev-day median 5-min turnover >= Rs15 lakh, prev close >= Rs100.
  Levels (known at the open): daily PP / R1 / R2 (yesterday's H/L/C), weekly PP / R1 / R2 (last completed week), daily EMA8
    (through yesterday's close = today's touch price).
  SETUP: a 5-min candle starting 09:30..13:00, previous 5-min close BELOW the level (came from below), high >= level, close
    < level, upper wick >= 1/3 of the range. First setup per stock-day; if several levels qualify, the one nearest the high.
  TRADE 1: entry = candle close, stop = candle high + 0.05% (a little beyond, the user's tick convention), target = entry - 1%,
    else out at the 15:15 close; stop first on a tie.
  TRADE 2 (only after trade 1 is STOPPED): the first later 5-min candle starting by 14:00 that closes back under the level ->
    short at that close, stop = highest high from the stop bar through that candle + 0.05%, same 1% target / 15:15 exit.
  Report: net Rs per Rs1 lakh (ret - 0.085%), trade 1 / trade 2 / combined per setup; % of stopped setups that came back under;
    Nifty rising vs falling over the 20 minutes before entry (Nifty 5-min file covers 2026-07-10 on); level type; month.
  Hand check: GRANULES 2026-10-15 (live 5-min appended) must show stopped -> re-entry."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import DAILY_DIR, INTRADAY_5M_DIR, INDEX_INTRADAY_DIR
COST = 0.085; TICK = 0.0005; TGT = 0.01


def levels_by_day(t, live_day=None):
    d = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True).sort_index()
    d = d[~d.index.duplicated()].dropna(subset=["Close"])
    if live_day is not None and live_day not in d.index: d.loc[live_day] = np.nan   # empty row so the shift gives today's levels (hand check)
    e8 = d.Close.ewm(span=8, adjust=False, ignore_na=True).mean()
    pp = (d.High + d.Low + d.Close) / 3
    dl = pd.DataFrame({"dPP": pp, "dR1": 2 * pp - d.Low, "dR2": pp + d.High - d.Low, "D8": e8, "pc": d.Close}).shift(1)   # known at the next open
    w = d.resample("W-FRI").agg({"High": "max", "Low": "min", "Close": "last"}).dropna()
    wp = (w.High + w.Low + w.Close) / 3
    wl = pd.DataFrame({"wPP": wp, "wR1": 2 * wp - w.Low, "wR2": wp + w.High - w.Low})
    wl.index = wl.index + pd.Timedelta(days=1)   # usable from the Saturday after the week closes
    wl = wl.reindex(d.index, method="ffill")
    return dl.join(wl)


def walk(H, L, C, i0, e, stop, last):
    tg = e * (1 - TGT)
    for k in range(i0, last + 1):
        if H[k] >= stop: return (e - stop) / e * 100, "stop", k
        if L[k] <= tg: return TGT * 100, "target", k
    return (e - C[last]) / e * 100, "time", last


def day_setups(t, g, lv, liq_ok=True):
    out = []
    hm = g.index.strftime("%H:%M").values
    O, H, L, C = g.Open.values, g.High.values, g.Low.values, g.Close.values
    lasts = np.where(hm <= "15:10")[0]
    if not len(lasts): return out
    last = lasts[-1]
    names = [k for k in ("dPP", "dR1", "dR2", "wPP", "wR1", "wR2", "D8") if pd.notna(lv.get(k, np.nan))]
    for i in range(1, last):
        if hm[i] < "09:30" or hm[i] > "13:00": continue
        rg = H[i] - L[i]
        if rg <= 0 or (H[i] - max(O[i], C[i])) < rg / 3: continue
        cand = [(H[i] - lv[k], k) for k in names if H[i] >= lv[k] > C[i] and C[i - 1] < lv[k]]
        if not cand: continue
        _, lk = min(cand); lvl = lv[lk]
        e1 = C[i]; s1 = H[i] * (1 + TICK)
        r1, w1, k1 = walk(H, L, C, i + 1, e1, s1, last)
        rec = dict(ticker=t, date=g.index[i].strftime("%Y-%m-%d"), time=hm[i], level=lk, lvl=round(lvl, 2), entry1=round(e1, 2),
                   stop1=round(s1, 2), risk1=(s1 - e1) / e1 * 100, ret1=r1, why1=w1, t_exit1=hm[k1], ret2=np.nan, why2="", entry2=np.nan,
                   stop2=np.nan, risk2=np.nan, time2="", came_back=np.nan, t_entry=g.index[i] + pd.Timedelta("5min"))
        if w1 == "stop":
            rec["came_back"] = False
            for j in range(k1 + 1, last):
                if hm[j] > "14:00": break
                if C[j] < lvl:
                    s2 = H[k1:j + 1].max() * (1 + TICK); e2 = C[j]
                    r2, w2, _ = walk(H, L, C, j + 1, e2, s2, last)
                    rec.update(came_back=True, entry2=round(e2, 2), stop2=round(s2, 2), risk2=(s2 - e2) / e2 * 100, ret2=r2, why2=w2,
                               time2=hm[j], t_entry2=g.index[j] + pd.Timedelta("5min"))
                    break
        out.append(rec)
        break   # first setup per stock-day
    return out


def run(t, extra=None):
    try:
        m = read5_official(t); lvd = levels_by_day(t, extra.index.normalize().min() if extra is not None else None)
    except Exception: return []
    if extra is not None: m = pd.concat([m[m.index.normalize() < extra.index.normalize().min()], extra])
    days = sorted(set(m.index.normalize())); mday = m.index.normalize(); out = []
    for a in range(1, len(days)):
        D, P = days[a], days[a - 1]
        if D not in lvd.index: continue
        lv = lvd.loc[D]
        if not lv.pc == lv.pc or lv.pc < 100: continue
        pv = m[(mday == P) & (m.Volume > 0)]
        if not len(pv) or (pv.Volume * pv.Close).median() < 15e5: continue
        g = m[mday == D]
        if len(g) < 60 and extra is None: continue
        out += day_setups(t, g, lv)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    uni = [f.stem for f in INTRADAY_5M_DIR.glob("*.csv") if not f.stem.startswith("_")]
    with Pool(6) as p: X = pd.DataFrame([r for rr in p.map(run, uni, chunksize=20) for r in rr])
    NF = pd.read_csv(INDEX_INTRADAY_DIR / "_NIFTY_5m_60d.csv", index_col=0, parse_dates=True)
    if NF.index.tz is not None: NF.index = NF.index.tz_convert("Asia/Kolkata").tz_localize(None)
    NC = NF.Close[~NF.index.duplicated()].sort_index()
    def n20(T):   # Nifty % move over the 20 minutes before entry (closes of the bars ending at T and T-20m)
        a, b = T - pd.Timedelta("25min"), T - pd.Timedelta("5min")
        return (NC[b] / NC[a] - 1) * 100 if a in NC.index and b in NC.index else np.nan
    X["nifty20"] = [n20(T) for T in X.t_entry]
    X["nifty20_2"] = [n20(T) if isinstance(T, pd.Timestamp) else np.nan for T in X.get("t_entry2", pd.Series([np.nan] * len(X)))]
    X["comb"] = (X.ret1 - COST) + (X.ret2.fillna(0) - COST * X.ret2.notna())
    X.drop(columns=[c for c in ("t_entry", "t_entry2") if c in X]).to_csv(HERE / "pivot_rejection_reentry.csv", index=False)

    def r(lab, x, k):
        x = x[x[f"ret{k}"].notna()]
        if not len(x): return f"| {lab} | 0 | | | | | |"
        w = x[f"why{k}"]
        return (f"| {lab} | {len(x)} | {(w == 'stop').mean()*100:.0f}% | {(w == 'target').mean()*100:.0f}% | {(w == 'time').mean()*100:.0f}% | "
                f"{x[f'risk{k}'].median():.2f}% | {(x[f'ret{k}'].mean() - COST)*1000:+.0f} |")
    HDR = "| group | trades | stopped | 1% target | out 15:15 | median stop | net Rs @1L |\n|---|---|---|---|---|---|---|"
    print(f"setups {len(X)} on {X.date.nunique()} days, {X.ticker.nunique()} stocks ({X.date.min()} .. {X.date.max()})")
    print(f"\n### TRADE 1 (5-min rejection, stop above the candle high)\n{HDR}\n{r('ALL', X, 1)}")
    for lk, g in X.groupby("level"): print(r(f"level {lk}", g, 1))
    print(r("Nifty UP > +0.1% in the 20 min before", X[X.nifty20 > 0.1], 1)); print(r("Nifty flat", X[X.nifty20.between(-0.1, 0.1)], 1))
    print(r("Nifty DOWN < -0.1%", X[X.nifty20 < -0.1], 1)); print(r("Nifty n/a (before 2026-07-10)", X[X.nifty20.isna()], 1))
    for mo, g in X.groupby(X.date.str[:7]): print(r(f"month {mo}", g, 1))
    st = X[X.why1 == "stop"]
    print(f"\nStopped trade 1: {len(st)} | came back under the level by 14:00: {st.came_back.sum()} ({st.came_back.mean()*100:.0f}%)")
    print(f"\n### TRADE 2 (re-entry after the stop)\n{HDR}\n{r('ALL', X, 2)}")
    for lk, g in X.groupby("level"): print(r(f"level {lk}", g, 2))
    print(r("Nifty UP > +0.1% (20 min before re-entry)", X[X.nifty20_2 > 0.1], 2)); print(r("Nifty flat", X[X.nifty20_2.between(-0.1, 0.1)], 2))
    print(r("Nifty DOWN < -0.1%", X[X.nifty20_2 < -0.1], 2))
    for mo, g in X.groupby(X.date.str[:7]): print(r(f"month {mo}", g, 2))
    print("\n### COMBINED per setup (trade 1 + trade 2 when taken; costs on both)\n| group | setups | net Rs @1L per setup |\n|---|---|---|")
    print(f"| ALL | {len(X)} | {X.comb.mean()*1000:+.0f} |")
    for mo, g in X.groupby(X.date.str[:7]): print(f"| month {mo} | {len(g)} | {g.comb.mean()*1000:+.0f} |")
    print(f"| top-10 trades removed (trade 1) | {len(X)-10} | {X.drop(X.ret1.nlargest(10).index).comb.mean()*1000:+.0f} |")

    print("\nHAND CHECK GRANULES 2026-10-15 (live 5-min):")
    import yfinance as yf
    g = yf.download("GRANULES.NS", period="1d", interval="5m", progress=False, auto_adjust=False)
    if isinstance(g.columns, pd.MultiIndex): g.columns = g.columns.get_level_values(0)
    g.index = g.index.tz_convert("Asia/Kolkata").tz_localize(None); g = g[["Open", "High", "Low", "Close", "Volume"]].dropna()
    hc = pd.DataFrame(run("GRANULES", extra=g)); hc = hc[hc.date == "2026-10-15"] if len(hc) else hc
    print(hc.drop(columns=[c for c in ("t_entry", "t_entry2") if c in hc]).round(2).T.to_string() if len(hc) else "  NOT CAUGHT")
    print("\n3 random setups:")
    print(X.sample(3, random_state=5)[["ticker", "date", "time", "level", "lvl", "entry1", "stop1", "why1", "t_exit1", "time2", "entry2", "stop2", "why2"]].to_string(index=False))
