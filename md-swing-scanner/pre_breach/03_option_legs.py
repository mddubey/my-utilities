"""Pre-breach detector, step 5 infra -- real ATM call legs from the daily NSE F&O bhavcopy for
every F&O panel row (options_cache coverage 2022-06-01 .. 2026-09-22).

Decision-time-safe contract selection (differs from option_backtest.pick_contract on purpose,
which filters liquidity on the entry day's own row):
  * spot for strike choice = day-T stock Open, un-adjusted for later splits via the T-1
    bhavcopy's own UndrlygPric / data_cache Close(T-1) ratio (option strikes are never
    split-adjusted; data_cache is -- the 2026-09-03 BEL bug in option_backtest.py).
  * expiry = front month, rolled to next if < MIN_EXPIRY_RUNWAY_DAYS trading days remain
    (option_backtest's own rule, imported).
  * strike = nearest CE strike to real spot among strikes that were liquid on T-1
    (OI>0 and traded on T-1) -- known before the open.
  * fill requires the chosen contract to have traded on T (OpnPric>0, TtlTradgVol>0).

Known, unfixable data limit: bhavcopy OpnPric is the FIRST TRADE of the day, not a 09:15
quote. For thin contracts the first trade can be well after 09:15. Rows carry the day's
contract volume so results can be restricted to liquid contracts.

Touch-entry price (the current convention, entering at the real IOC touch) is not in the
daily data. Reconstructed with ox1_reconstruction's frozen, validated ATM/current beta
(0.492): opt_touch = opt_open + 0.492 * (trigger_real - open_real) when the stock opened
below the trigger; = opt_open when it opened through the trigger (touch at the open).
Clamped into the option's own [Low, High] for the day; clamp frequency reported.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent

import option_backtest as ob  # noqa: E402
from ox1_reconstruction import BETA_ATM_CURRENT  # noqa: E402

DAYS = ob.trading_days()
DAY_IDX = {d: k for k, d in enumerate(DAYS)}


def chain(d):
    df = ob.load_day(d.strftime("%Y%m%d"))
    if df is None:
        return None
    return df[df.OptnTp == "CE"]


def full_day(d):
    """Real (never split-adjusted) underlying close on d. UndrlygPric exists only in the
    2024+ bhavcopy format; older files fall back to fetch_cash_bhav's cash-market file."""
    p = ob.OPT_CACHE_DIR / f"{d.strftime('%Y%m%d')}.csv"
    cols = pd.read_csv(p, nrows=0).columns
    if "UndrlygPric" in cols:
        df = pd.read_csv(p, usecols=["FinInstrmTp", "TckrSymb", "UndrlygPric"])
        return df[df.FinInstrmTp == "STO"].groupby("TckrSymb").UndrlygPric.first()
    cb = ROOT / "cash_bhav_cache" / f"{d.strftime('%Y%m%d')}.csv"
    if cb.exists():
        return pd.read_csv(cb).set_index("ticker").close
    return parity_spot(d)


def parity_spot(d):
    """Fallback real-spot estimate from put-call parity on d's own closing chain (front
    expiry): S ~= K + C - P at the strike where |C - P| is smallest. Ignores carry/dividends
    (small for a <=1-month expiry); only used to pick the ATM strike and un-adjust prices,
    never as a P&L input. Validated against UndrlygPric on 2024+ files in 04_validate."""
    raw = ob.load_day(d.strftime("%Y%m%d"))
    raw = raw[(raw.TtlTradgVol > 0) & (raw.ClsPric > 0)]
    out = {}
    for t, g in raw.groupby("TckrSymb"):
        e = g.XpryDt.min()
        g = g[g.XpryDt == e]
        c = g[g.OptnTp == "CE"].set_index("StrkPric").ClsPric
        p = g[g.OptnTp == "PE"].set_index("StrkPric").ClsPric
        k = c.index.intersection(p.index)
        if len(k) == 0:
            continue
        diff = (c[k] - p[k])
        kk = diff.abs().idxmin()
        out[t] = kk + diff[kk]
    return pd.Series(out, dtype=float)


def main():
    panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date", "next_date"])
    panel = panel[panel.fo & (panel.date >= DAYS[1]) & (panel.date <= DAYS[-1])]
    closes_prev = {}
    recs, miss = [], dict(no_day=0, no_prev=0, no_chain=0, no_fill=0)
    for n, (d, grp) in enumerate(panel.groupby("date")):
        k = DAY_IDX.get(d)
        if k is None or k == 0:
            miss["no_day"] += len(grp)
            continue
        dprev = DAYS[k - 1]
        dnext = DAYS[k + 1] if k + 1 < len(DAYS) else None
        cT, cP = chain(d), chain(dprev)
        cN = chain(dnext) if dnext is not None else None
        und_prev = full_day(dprev)
        for r in grp.itertuples():
            ch_prev = cP[cP.TckrSymb == r.ticker]
            if ch_prev.empty or r.ticker not in und_prev.index:
                miss["no_prev"] += 1
                continue
            # un-adjust: prev-close in data_cache is recoverable from open_ and gap_pct
            cache_prev_close = r.open_ / (1 + r.gap_pct / 100)
            adj = und_prev[r.ticker] / cache_prev_close
            open_real, trig_real = r.open_ * adj, r.trigger * adj
            expiries = sorted(e for e in ch_prev.XpryDt.unique() if e >= d)
            if not expiries:
                miss["no_chain"] += 1
                continue
            expiry = expiries[0]
            if len(expiries) > 1 and ob.trading_days_between(d, expiry) < ob.MIN_EXPIRY_RUNWAY_DAYS:
                expiry = expiries[1]
            liq = ch_prev[(ch_prev.XpryDt == expiry) & (ch_prev.OpnIntrst > 0) & (ch_prev.TtlTradgVol > 0)]
            if liq.empty:
                miss["no_chain"] += 1
                continue
            strike = liq.StrkPric.iloc[(liq.StrkPric - open_real).abs().argmin()]
            rowT = cT[(cT.TckrSymb == r.ticker) & (cT.XpryDt == expiry) & (cT.StrkPric == strike)]
            if rowT.empty or not (rowT.OpnPric.iloc[0] > 0 and rowT.TtlTradgVol.iloc[0] > 0):
                miss["no_fill"] += 1
                continue
            t = rowT.iloc[0]
            rowN = None
            if cN is not None:
                x = cN[(cN.TckrSymb == r.ticker) & (cN.XpryDt == expiry) & (cN.StrkPric == strike)]
                rowN = x.iloc[0] if not x.empty else None
            if open_real >= trig_real:
                touch_raw = t.OpnPric
            else:
                touch_raw = t.OpnPric + BETA_ATM_CURRENT * (trig_real - open_real)
            touch = min(max(touch_raw, t.LwPric), t.HghPric)
            recs.append(dict(
                ticker=r.ticker, date=d, expiry=expiry, strike=strike, lot=t.NewBrdLotQty,
                dte=ob.trading_days_between(d, expiry), open_real=open_real, trig_real=trig_real,
                opt_open=t.OpnPric, opt_high=t.HghPric, opt_low=t.LwPric, opt_close=t.ClsPric,
                opt_vol=t.TtlTradgVol, opt_oi=t.OpnIntrst,
                opt_touch=touch, touch_clamped=touch != touch_raw,
                opt_next_open=rowN.OpnPric if rowN is not None and rowN.OpnPric > 0 else np.nan,
                opt_next_close=rowN.ClsPric if rowN is not None and rowN.ClsPric > 0 else np.nan,
                next_expired=expiry < dnext if dnext is not None else False,
            ))
        if n % 50 == 0:
            print(n, d.date(), len(recs), miss, flush=True)
    pd.DataFrame(recs).to_csv(OUT / "option_legs.csv", index=False)
    print("done", len(recs), miss)


if __name__ == "__main__":
    main()
