"""Pre-placed trigger order (user, 2026-10-08: "don't be tied to the 10:45 timing -- spot the candidate when free at 10:15,
leave an order that fires by itself"; user not convinced, "let's see"). Spec fixed before running:
  The 1H EMA34 only changes at an hour close, so at 10:15 (and again at 11:15) its value for the next hour is known.
  ARM at 10:15 for the 10:15-11:15 hour; if nothing fired, re-arm at 11:15 for 11:15-12:15 (user free after standup).
  Candidate at arming (known then): same universe as plan B (liquid tv20 >= Rs10cr, daily ADX <= 25, ATR >= 2.56%, no
  corporate-action day), 1H EMA8 < EMA34, last price (close of the hour just finished) below the EMA34 and below
  yesterday's daily 8-EMA. The candle checks that need a closed candle (red, close below EMA34, VWAP) cannot apply.
  Order: once a 5-min bar's high touches the EMA34 (E), a sell-stop at E*(1 - a) is live from the NEXT bar; fill at
  the trigger, or at the bar open if it opens below. Cancelled for that hour if the high reaches the stop E*(1 + b)
  before the trigger fires (wick too deep). Stop E*(1 + b) (a bar after entry with high >= stop; open if gapped above;
  the trigger bar itself counts as stopped if its high >= stop -- conservative). Target entry*0.99; out at entry + 5h
  or 15:15. One trade a day: first fill by time; same bar -> closest to the EMA34 at arming.
  Variants (pre-declared, robustness, not a sweep): a in {0.1, 0.2}%, b in {0.2, 0.3}%.
  Compare with plan B on the same days (green_rejection.csv RED, alarms 10:45/11:15/11:45, candle-close entry -- the
  same numbers as script 96's "red only" plan). Net = gross - Rs85. By month, plus all fills (not just one a day).
Pass = a variant beats plan B net per trade AND total in >= 3 of 4 months with its neighbours agreeing. Else closed."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
exec(compile(open(HERE / "60_filter_ablation.py").read().split("def gen_a")[0], "60head", "exec"))
VARS = [(0.1, 0.2), (0.1, 0.3), (0.2, 0.2), (0.2, 0.3)]


def gen(t):
    p = M5 / f"{t}.csv"
    if not p.exists(): return []
    try: d, d8y, adx, tv = daily_inputs(t)
    except Exception: return []
    atrp = (d.atr14 / d.Close * 100).shift(1) if "atr14" in d else None
    if atrp is None: return []
    m = read(p)
    if len(m) < 1500: return []
    hc = m.Close.groupby(hour_key(m.index)).last()
    e34 = hc.ewm(span=34, adjust=False).mean().shift(1); e8 = hc.ewm(span=8, adjust=False).mean().shift(1)
    rows = []
    for day, g in m.groupby(m.index.normalize()):
        if day < pd.Timestamp("2026-06-10") or len(g) < 70 or tv.get(day, 0) < 1e8 or bool(d.corp_action_day.get(day, False)): continue
        D8, AD, AT = d8y.get(day, np.nan), adx.get(day, np.nan), atrp.get(day, np.nan)
        if np.isnan(D8) or np.isnan(AD) or AD > 25 or np.isnan(AT) or AT < 2.56: continue
        O, H, L, C, T = g.Open.values, g.High.values, g.Low.values, g.Close.values, g.index
        for arm in ("10:15", "11:15"):
            hs = day + pd.Timedelta(hours=int(arm[:2]), minutes=int(arm[3:]))
            E, E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)
            pre = np.where(T < hs)[0]
            if np.isnan(E) or len(pre) == 0: continue
            last = C[pre[-1]]
            if not (E8 < E and last < E and last < D8): continue
            win = np.where((T >= hs) & (T < hs + pd.Timedelta("60min")))[0]
            if len(win) == 0: continue
            for a, b in VARS:
                trig, stop = E * (1 - a / 100), E * (1 + b / 100)
                touched = False; fill = fi = None
                for k in win:
                    if touched:
                        if O[k] <= trig: fill, fi = O[k], k; break
                        if L[k] <= trig: fill, fi = trig, k; break
                    if H[k] >= stop: break                     # wick too deep before the trigger -> cancelled
                    if H[k] >= E: touched = True
                if fill is None: continue
                tgt, endt = fill * 0.99, min(T[fi] + pd.Timedelta("5h"), day + pd.Timedelta("15h15min"))
                if H[fi] >= stop: px, why = stop, "stop"
                else:
                    px, why = None, None
                    for k in range(fi + 1, len(C)):
                        if T[k] >= endt: px, why = C[k - 1], "stall"; break
                        if O[k] >= stop: px, why = O[k], "stop"; break
                        if H[k] >= stop: px, why = stop, "stop"; break
                        if L[k] <= tgt: px, why = tgt, "target"; break
                    if px is None: px, why = C[-1], "stall"
                rows.append(dict(ticker=t, date=f"{day:%Y-%m-%d}", arm=arm, a=a, b=b, fill_t=T[fi], dist=(E - last) / E * 100,
                                 entry=fill, ret=(fill - px) / fill * 100, why=why))
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        X = pd.DataFrame(sum(p.map(gen, t5, chunksize=10), []))
    X.to_csv(HERE / "preplaced_trigger.csv", index=False)
    Y = pd.read_csv(HERE / "green_rejection.csv"); Y = Y[(Y.set == "a") & (~Y.green) & Y.alarm.isin([2, 3, 4])]
    Y["why"] = Y.why.replace({"time": "stall", "eod": "stall"})
    B = Y.sort_values(["date", "alarm", "dist"]).groupby("date").head(1)
    days = sorted(set(X.date) | set(B.date))

    def line(lab, z):
        o = z.why; r = z.ret.mean() * 1000
        per = (z.groupby(z.date.str[:7]).ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        return (f"| {lab} | {len(z)} | {(o == 'target').mean()*100:.0f} | {(o == 'stall').mean()*100:.0f} | {(o == 'stop').mean()*100:.0f} | "
                f"{r:+.0f} | {r - 85:+.0f} | {z.ret.sum()*1000 - 85*len(z):+,.0f} | " + " ".join(f"{k[5:]}:{v:+d}" for k, v in per.items()) + " |")
    print(f"days in window: {len(days)}\n| plan | trades | target % | stall % | stop % | Rs gross | Rs net | total net | net by month |\n|---|---|---|---|---|---|---|---|---|")
    print(line("plan B (current, candle close entry)", B))
    for a, b in VARS:
        z = X[(X.a == a) & (X.b == b)]
        pk = z.sort_values(["date", "fill_t", "dist"]).groupby("date").head(1)
        print(line(f"D: trigger EMA-{a}%, stop EMA+{b}% (one a day)", pk))
    print("\nall fills (not one a day):\n| variant | fills | target % | stall % | stop % | Rs gross | Rs net | total net | net by month |\n|---|---|---|---|---|---|---|---|---|")
    for a, b in VARS:
        print(line(f"EMA-{a}% / EMA+{b}%", X[(X.a == a) & (X.b == b)]))
    z = X[(X.a == 0.2) & (X.b == 0.3)]
    print(f"\nfills by arm (EMA-0.2/+0.3): {z.arm.value_counts().to_dict()} | days with a D fill {z.date.nunique()} vs plan B days {B.date.nunique()}")
