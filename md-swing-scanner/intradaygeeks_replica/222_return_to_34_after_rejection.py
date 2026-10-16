"""After a rejection at the 1H EMA34, price falls away and later comes BACK to the 34 the same day: re-rejected (a better
entry) or broken (the stop)? (user, 2026-10-15: 'going back to the 34 is not always the SL, sometimes it gives a better
price -- how do we find those?'). DESCRIPTIVE, spec fixed before running.
Population: how_low_P0.csv (old-live / plan B checklist signals, any regime), first signal per stock-day.
  a = 30m set (5-min bars, 2026-06..09), b = 3-yr 1H set (hourly bars, 2024-01..2026-09).
Line = 1H EMA34 as of the previous completed hourly bar (h1_cache closes), per bar.
Event: after the signal's alarm time, the low first goes >= 0.5% below the line (fell away), then a later bar's High
  reaches the line (RETURN), touch bar starting by 14:10 (5-min) / 13:15 (1H). Short fill = the line (sell limit).
Outcome from the touch: RE-REJECTED = a later bar's Low <= line - 1% first; BROKE = any bar from the touch bar on reaches
  line + 0.3% first (same bar both = BROKE; the touch bar's own Low is ignored for the target, its order is unknown);
  else STALL, out at the 15:15 close. Return % = +1.0 / -0.3 / (line - close). Net = (ret - 0.085%) per Rs 1 lakh.
  After a RE-REJECTED event the search continues (2nd, 3rd return); after BROKE it stops.
Features, computed from bars BEFORE the touch bar only:
  1 speed     = bars from the lowest-low bar to the touch bar (a: 5-min bars, b: hours)
  2 green     = biggest green move on the way back / the signal candle's red body. a: biggest 6-bar (30-min) rise
                Close[j] - Open[j-5] within the return; b: biggest hourly green body
  3 volume    = mean volume per bar on the way back (after the low bar) / mean on the fall (alarm .. low bar)
  4 nifty     = Nifty % change from the last completed hour at the alarm to the last completed hour before the touch
  5 return_no = 1st vs 2nd+ return
  6 depth     = (line - lowest low) / daily ATR in price, ATR from the population's atrp
Report: baseline + each feature's declared bands, per set; set b also by year, Nifty vs 200d, 2026-03..09 bear phase."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR, INDEX_INTRADAY_DIR, DAILY_DIR
HERE = Path(__file__).resolve().parent; COST = 0.085
AWAY, TGT, STP = 0.005, 0.01, 0.003


def load(p):
    m = pd.read_csv(p, index_col=0); m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return m


def hour_key(idx):
    d = idx.normalize(); return d + pd.Timedelta("9h15min") + ((idx - d - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def run(args):
    t, g = args
    if not (HERE / "h1_cache" / f"{t}.csv").exists(): return []  # 3 tickers / 6 30m signals have no hourly cache
    h = load(HERE / "h1_cache" / f"{t}.csv"); h = h[~h.index.duplicated()]
    line_by_hour = h.Close.ewm(span=34, adjust=False).mean().shift(1)  # EMA as of the previous completed hour
    m5 = None; out = []
    for ix, r in g.iterrows():
        day = pd.Timestamp(r.date)
        if r.set == "a":
            if m5 is None: m5 = load(INTRADAY_5M_DIR / f"{t}.csv")
            at = day + pd.Timedelta("9h15min") + (int(r.alarm) + 1) * pd.Timedelta("30min"); step = pd.Timedelta("5min")
            m = m5[m5.index.normalize() == day]; so = m[(m.index >= at - pd.Timedelta("30min")) & (m.index < at)]
            last_touch = day + pd.Timedelta("14h10min")
        else:
            at = day + pd.Timedelta(hours=int(r.alarm) + 1, minutes=15); step = pd.Timedelta("60min")
            m = h[h.index.normalize() == day]; so = m[(m.index >= at - step) & (m.index < at)]
            last_touch = day + pd.Timedelta("13h15min")
        if so.empty: continue
        body = so.Open.iloc[0] - r.qc
        b = m[m.index >= at]
        if b.empty: continue
        L = line_by_hour.reindex(hour_key(b.index)).values
        if np.isnan(L).any(): continue
        O, H, Lo, C, V = b.Open.values, b.High.values, b.Low.values, b.Close.values, b.Volume.values
        ts = b.index; end_i = np.where(ts + step <= day + pd.Timedelta("15h15min"))[0]
        if not len(end_i): continue
        last = end_i[-1]; k0 = 0; no = 0
        while k0 <= last:
            away = None; ev = None
            for k in range(k0, last + 1):
                if away is None:
                    if Lo[k] <= L[k] * (1 - AWAY): away = k
                    continue
                if H[k] >= L[k]:
                    if ts[k] > last_touch: break
                    ev = k; break
            if ev is None: break
            no += 1; line = L[ev]; seg = slice(k0, ev)
            lowk = k0 + int(np.argmin(Lo[seg])); low = Lo[lowk]
            # outcome
            res, st, rk = None, None, None
            for k in range(ev, last + 1):
                if H[k] >= line * (1 + STP): res, st, rk = -STP * 100, "broke", k; break
                if k > ev and Lo[k] <= line * (1 - TGT): res, st, rk = TGT * 100, "re-rejected", k; break
            if res is None: res, st, rk = (line - C[last]) / line * 100, "stall", last
            # features
            back = slice(lowk + 1, ev)
            if r.set == "a":
                w = [C[j] - O[max(lowk, j - 5)] for j in range(lowk, ev)]
                green = max(w) if w else np.nan
            else:
                gb = C[lowk:ev] - O[lowk:ev]; green = gb.max() if len(gb) else np.nan
            vb, vf = V[back], V[k0:lowk + 1]
            vol = vb.mean() / vf.mean() if len(vb) and vf.mean() > 0 else np.nan
            out.append(dict(ix=ix, set=r.set, ticker=t, date=r.date, alarm=int(r.alarm), return_no=no, line=round(line, 2),
                            low=low, low_time=ts[lowk].strftime("%H:%M"), touch_time=ts[ev].strftime("%H:%M"),
                            res_time=ts[rk].strftime("%H:%M"), outcome=st, ret=res, speed=ev - lowk,
                            green=green / body if body > 0 and not np.isnan(green) else np.nan, vol=vol,
                            depth=(line - low) / (r.atrp / 100 * r.qc), t_alarm=at, t_touch=ts[ev]))
            if st != "re-rejected": break
            k0 = rk + 1
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    y = pd.read_csv(HERE / "how_low_P0.csv")
    y = y.sort_values(["set", "ticker", "date", "alarm"]).groupby(["set", "ticker", "date"]).head(1)
    with Pool(6) as p:
        E = pd.DataFrame(sum(p.map(run, list(y.groupby("ticker"))), []))
    # Nifty during the pullback (1H closes, last completed hour)
    N = load(INDEX_INTRADAY_DIR / "_NIFTY_1h.csv").Close; N = N[~N.index.duplicated()].sort_index()
    def nlast(T): s = N[N.index + pd.Timedelta("60min") <= T]; return s.iloc[-1] if len(s) else np.nan
    E["nifty"] = [(nlast(b) / nlast(a) - 1) * 100 for a, b in zip(E.t_alarm, E.t_touch)]
    nd = pd.read_csv(DAILY_DIR / "_NIFTY.csv", index_col=0, parse_dates=True).Close.sort_index()
    above = (nd > nd.rolling(200).mean()).shift(1)
    E["n200"] = E.date.map(lambda d: bool(above.get(pd.Timestamp(d), np.nan)) if pd.notna(above.get(pd.Timestamp(d), np.nan)) else np.nan)
    E.drop(columns=["t_alarm", "t_touch"]).to_csv(HERE / "return_to_34_events.csv", index=False)
    print(f"signals (first per stock-day): a {sum(y.set == 'a')}, b {sum(y.set == 'b')} | return events: "
          + ", ".join(f"{s} {sum(E.set == s)} ({E[E.set == s].ix.nunique()} signals)" for s in "ab"))

    def row(lab, x):
        if not len(x): return f"| {lab} | 0 | | | | | |"
        return (f"| {lab} | {len(x)} | {(x.outcome == 're-rejected').mean()*100:.0f}% | {(x.outcome == 'broke').mean()*100:.0f}% | "
                f"{(x.outcome == 'stall').mean()*100:.0f}% | {x.ret.mean():+.3f}% | {(x.ret.mean() - COST)*1000:+.0f} |")
    HDR = "| group | events | re-rejected | broke | stall | mean gross | net Rs @1L |\n|---|---|---|---|---|---|---|"
    BANDS = {
        "1 speed": {"a": [("fast <= 3 bars (15 min)", lambda x: x.speed <= 3), ("4-9 bars", lambda x: x.speed.between(4, 9)), ("slow >= 10 bars (50 min)", lambda x: x.speed >= 10)],
                    "b": [("1 hour", lambda x: x.speed <= 1), ("2 hours", lambda x: x.speed == 2), ("3+ hours", lambda x: x.speed >= 3)]},
        "2 green vs red body": [("small < 0.5", lambda x: x.green < 0.5), ("0.5-1", lambda x: x.green.between(0.5, 1, inclusive="left")), ("big >= 1", lambda x: x.green >= 1), ("n/a", lambda x: x.green.isna())],
        "3 volume back / fall": [("lighter < 0.8", lambda x: x.vol < 0.8), ("0.8-1.25", lambda x: x.vol.between(0.8, 1.25)), ("heavier > 1.25", lambda x: x.vol > 1.25), ("n/a (no bar between)", lambda x: x.vol.isna())],
        "4 Nifty during pullback": [("down < -0.1%", lambda x: x.nifty < -0.1), ("flat", lambda x: x.nifty.between(-0.1, 0.1)), ("up > +0.1%", lambda x: x.nifty > 0.1)],
        "5 which return": [("1st", lambda x: x.return_no == 1), ("2nd+", lambda x: x.return_no >= 2)],
        "6 depth before return": [("< 0.5 ATR", lambda x: x.depth < 0.5), ("0.5-1 ATR", lambda x: x.depth.between(0.5, 1, inclusive="left")), (">= 1 ATR", lambda x: x.depth >= 1)],
    }
    for s, nm in (("a", "30m set, 5-min bars, 2026-06..09"), ("b", "3-yr 1H set, hourly bars, 2024-01..2026-09")):
        x = E[E.set == s]
        print(f"\n### {nm}\n{HDR}\n{row('BASELINE', x)}")
        for f, bands in BANDS.items():
            bl = bands[s] if isinstance(bands, dict) else bands
            for lab, fn in bl: print(row(f"{f}: {lab}", x[fn(x)]))
        if s == "b":
            for yr, g in x.groupby(x.date.str[:4]): print(row(f"year {yr}", g))
            print(row("Nifty above 200d", x[x.n200 == True])); print(row("Nifty below 200d", x[x.n200 == False]))
            print(row("bear phase 2026-03..09", x[x.date >= "2026-03"]))
    print("\nHAND CHECK (3 random 30m events):")
    print(E[E.set == "a"].sample(3, random_state=7)[["ticker", "date", "alarm", "line", "low", "low_time", "touch_time", "outcome", "res_time", "ret", "speed", "green", "vol", "nifty", "depth"]].round(3).to_string(index=False))
