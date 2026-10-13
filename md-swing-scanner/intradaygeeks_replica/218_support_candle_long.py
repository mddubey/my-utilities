"""LONG SIDE: the user's SUPPORT candle at the 1H EMA34 in UPTREND stocks (user, 2026-10-13: MOTILALOFS 11:15 / 13:15 -- 'sellers lost
at the line'; never tested as a long: v1's long mirror (166) only took DOWNtrend stocks, 118 lumped every touch together).
Spec declared in chat / here before running (mirror of 217's short classes):
  Universe: v1's -- liquid (prior-day median hourly turnover / 12 x 0.72 >= Rs15 lakh), price >= Rs100, daily ATR14 >= 2%, stock daily
  EMA8 > EMA34 (yesterday). 3-yr 1H set (h1_cache), 2024-01 .. 2026-10. Hourly candles 10:15 / 11:15 / 12:15 / 13:15.
  Line = 1H EMA34 as of the previous completed hour. Touch = LOW <= line and CLOSE > line. cp = (C - L) / (H - L).
    SUPPORT          opened above the line or only marginally below (>= -0.2%) AND closed in the top 40% (cp >= 0.6) -- sellers lost AT the line
    WEAK SUPPORT     same open, closed lower (cp < 0.6)
    BREAKOUT         opened clearly below (< -0.2%) AND cp >= 0.6 -- body cross up
    BREAKOUT + WICK  opened clearly below AND cp < 0.6
  Trade: long at the candle close, stop = candle low; E1 = +1% target, only if stop <= 0.5%; E2 = max(1%, 0.35 x ATR) target, only if
  stop <= half the target; out after 5 candles / the day's last candle; stop first if both in one candle. Rs per Rs1 lakh, net of Rs85.
  Report per class: Nifty above / below its 200-day, by year below 200d, by hour; extra split (user: 'daily 8-EMA = extra support'):
  yesterday's daily EMA8 (the touch price) within 0.5% below the candle low vs not. 3 SUPPORT trades printed for a hand check.
  Compare with v1's clean rejections (217): above 200d +151 / +154, below -50 / -52."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from multiprocessing import Pool
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from backtest import load
from data.paths import DAILY_DIR
HOURS = ("10:15", "11:15", "12:15", "13:15")


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
    H["line"] = H.Close.ewm(span=34, adjust=False).mean().shift(1); H["day"] = H.index.normalize(); H["hm"] = H.index.strftime("%H:%M")
    H["n"] = np.arange(len(H))
    nz = H[H.Volume > 0]; liq = ((nz.Volume * nz.Close).groupby(nz.day).median() / 12 * 0.72 / 1e5).shift(1)
    for day, g in H[(H.day >= "2024-01-01")].groupby("day"):
        if day not in dc.index: continue
        r = dc.loc[day]
        if not (r.up and r.pc >= 100 and r.atrp >= 2 and r.tv >= 1e8 and liq.get(day, 0) >= 15): continue
        for i, (k, b) in enumerate(g.iterrows()):
            if b.hm not in HOURS or b.n < 60: continue
            L0 = b.line
            if not (b.Low <= L0 < b.Close) or b.High <= b.Low: continue
            cp = (b.Close - b.Low) / (b.High - b.Low); ov = (b.Open / L0 - 1) * 100
            cls = ("SUPPORT" if cp >= 0.6 else "WEAK SUPPORT") if ov >= -0.2 else ("BREAKOUT" if cp >= 0.6 else "BREAKOUT + WICK")
            e = b.Close; stp = b.Low; risk = (e - stp) / e * 100
            if risk <= 0: continue
            later = g.iloc[i + 1:i + 6]
            if not len(later): continue
            rec = dict(t=t, day=day, hm=b.hm, cls=cls, cp=cp, ov=ov, risk=risk, atrp=r.atrp, o=b.Open, h=b.High, l=b.Low, c=b.Close, line=L0,
                       e8_gap=(stp / r.e8 - 1) * 100)
            for ex, tp in (("E1", 1.0), ("E2", max(1.0, 0.35 * r.atrp))):
                if (ex == "E1" and risk > 0.5) or (ex == "E2" and risk > tp / 2): rec[ex] = np.nan; continue
                tgt = e * (1 + tp / 100); px = None; how = "stall"
                for lb in later.itertuples():
                    if lb.Low <= stp: px, how = stp, "stop"; break
                    if lb.High >= tgt: px, how = tgt, "target"; break
                if px is None: px = later.Close.iloc[-1]
                rec[ex] = (px / e - 1) * 100 * 1000 - 85; rec[ex + "_how"] = how
            out.append(rec)
    return out


if __name__ == "__main__":
    uni = [p.stem for p in (HERE / "h1_cache").glob("*.csv")]
    with Pool(6) as pool:
        res = []
        for k, r in enumerate(pool.imap_unordered(gen, uni, chunksize=10), 1):
            res.extend(r)
            if k % 400 == 0: print(f"  {k}/{len(uni)} tickers", flush=True)
    X = pd.DataFrame(res); X.to_csv(HERE / "support_candle_long.csv", index=False)
    N = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).sort_index().Close
    n200 = (N > N.rolling(200).mean()).shift(1); X["n200"] = X.day.map(lambda d: bool(n200.get(d, False))); X["yr"] = pd.to_datetime(X.day).dt.year
    print("HAND CHECK (3 random SUPPORT trades, E2):")
    print(X[(X.cls == "SUPPORT") & X.E2.notna()].sample(3, random_state=21)[["t", "day", "hm", "o", "h", "l", "c", "line", "cp", "ov", "risk", "E2_how", "E2"]].round(2).to_string(index=False))
    ORDER = ["SUPPORT", "WEAK SUPPORT", "BREAKOUT", "BREAKOUT + WICK"]
    for ex in ("E1", "E2"):
        Y = X[X[ex].notna()]
        print(f"\n## {ex}\n| class | Nifty ABOVE 200d: trades / stopped / Rs @1L | Nifty BELOW 200d: trades / stopped / Rs @1L | below 200d by year 2024 / 2025 / 2026 |\n|---|---|---|---|")
        for c in ORDER + ["ALL"]:
            x = Y if c == "ALL" else Y[Y.cls == c]; cells = []
            for nv in (True, False):
                y = x[x.n200 == nv]; cells.append(f"{len(y)} / {(y[ex + '_how'] == 'stop').mean()*100:.0f}% / {y[ex].mean():+.0f}" if len(y) else "0")
            yb = x[~x.n200]; yrs = " / ".join(f"{yb[yb.yr == yr][ex].mean():+.0f} ({(yb.yr == yr).sum()})" if (yb.yr == yr).any() else "- (0)" for yr in (2024, 2025, 2026))
            print(f"| {c} | {cells[0]} | {cells[1]} | {yrs} |")
        S = Y[Y.cls == "SUPPORT"]
        print(f"\nSUPPORT by hour ({ex}), above / below 200d: " + " | ".join(f"{h}: {S[(S.hm == h) & S.n200][ex].mean():+.0f} ({(( S.hm == h) & S.n200).sum()}) / {S[(S.hm == h) & ~S.n200][ex].mean():+.0f} ({((S.hm == h) & ~S.n200).sum()})" for h in HOURS))
        near = (S.e8_gap >= 0) & (S.e8_gap <= 0.5)
        print(f"SUPPORT + yesterday's daily EMA8 within 0.5% under the candle low ({ex}): above {S[near & S.n200][ex].mean():+.0f} ({(near & S.n200).sum()}) vs not {S[~near & S.n200][ex].mean():+.0f} | "
              f"below {S[near & ~S.n200][ex].mean():+.0f} ({(near & ~S.n200).sum()}) vs not {S[~near & ~S.n200][ex].mean():+.0f}")
