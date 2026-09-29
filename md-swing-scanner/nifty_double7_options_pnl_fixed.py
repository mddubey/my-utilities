"""Ad hoc (2026-09-27), bug fix per direct user catch: the original ITM/ATM ">20 day
expiry" backtests silently DROPPED any trade where the chosen expiry still ran out before
the real signal exit (found: exactly the 3 longest trades, 24/25/34-day holds) instead of
counting the real forced settlement. This likely inflated the reported win rates by
excluding the hardest, most chop-prone (per the efficiency-ratio finding) trades. Fixed:
if the exit lookup fails because the contract already expired, fall back to real cash
settlement (intrinsic value = max(spot_at_expiry - strike, 0)) at that expiry date instead
of skipping the trade.
"""
import pandas as pd
import os

OPTIONS_DIR = "options_cache"
nifty = pd.read_csv("data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
nifty_idx = nifty.set_index("Date").Close

trades = pd.read_csv("nifty_double7_long.csv", parse_dates=["entry_date", "exit_date"])


def run(moneyness):
    results = []
    for _, tr in trades.iterrows():
        entry_str = tr.entry_date.strftime("%Y%m%d")
        entry_path = f"{OPTIONS_DIR}/{entry_str}.csv"
        if not os.path.exists(entry_path):
            continue
        edf = pd.read_csv(entry_path)
        nifty_ce = edf[(edf.TckrSymb == "NIFTY") & (edf.FinInstrmTp == "IDO") & (edf.OptnTp == "CE")]
        if nifty_ce.empty:
            continue
        spot = nifty_ce.UndrlygPric.iloc[0]
        expiries = sorted(pd.to_datetime(nifty_ce.XpryDt.unique()))
        cands = [e for e in expiries if (e - tr.entry_date).days > 20]
        if not cands:
            continue
        expiry = cands[0]

        chain = nifty_ce[nifty_ce.XpryDt == expiry.strftime("%Y-%m-%d")].copy()
        if moneyness == "ITM":
            target = spot * 0.98
            chain = chain[chain.StrkPric < spot]
        else:
            target = spot
        if chain.empty:
            continue
        chain["d"] = (chain.StrkPric - target).abs()
        strike = chain.sort_values("d").iloc[0].StrkPric
        er = chain[chain.StrkPric == strike]
        if er.empty or er.iloc[0].ClsPric <= 0:
            continue
        entry_premium = float(er.iloc[0].ClsPric)

        forced_settlement = tr.exit_date > expiry
        exit_premium = None
        if not forced_settlement:
            exit_str = tr.exit_date.strftime("%Y%m%d")
            exit_path = f"{OPTIONS_DIR}/{exit_str}.csv"
            if os.path.exists(exit_path):
                xdf = pd.read_csv(exit_path)
                xr = xdf[(xdf.TckrSymb == "NIFTY") & (xdf.FinInstrmTp == "IDO") & (xdf.OptnTp == "CE")
                         & (xdf.XpryDt == expiry.strftime("%Y-%m-%d")) & (xdf.StrkPric == strike)]
                if not xr.empty and xr.iloc[0].ClsPric > 0:
                    exit_premium = float(xr.iloc[0].ClsPric)
        if exit_premium is None:
            # either genuinely forced past expiry, or the exit-day lookup failed (contract gone) -- settle real
            if expiry not in nifty_idx.index:
                continue
            spot_at_expiry = nifty_idx.loc[expiry]
            exit_premium = max(spot_at_expiry - strike, 0)
            forced_settlement = True

        opt_ret = exit_premium / entry_premium - 1
        results.append(dict(entry_date=tr.entry_date, hold_days=tr.hold_days, underlying_ret=tr.ret,
                             strike=strike, forced_settlement=forced_settlement, opt_ret=opt_ret))
    return pd.DataFrame(results)


for moneyness in ["ITM", "ATM"]:
    res = run(moneyness)
    print(f"=== {moneyness} (>20 day expiry, FIXED forced-settlement accounting): n={len(res)} ===")
    print(f"  win rate: {(res.opt_ret>0).mean()*100:.1f}%")
    print(f"  median: {res.opt_ret.median()*100:+.2f}%   mean: {res.opt_ret.mean()*100:+.2f}%")
    print(f"  forced-settlement trades (contract ran out before real exit): {res.forced_settlement.sum()}")
    if res.forced_settlement.sum() > 0:
        fs = res[res.forced_settlement]
        print(f"    of those: win={ (fs.opt_ret>0).mean()*100:.1f}%  median={fs.opt_ret.median()*100:+.2f}%")
    print(res.to_string(index=False))
    print()
    res.to_csv(f"nifty_double7_long_{moneyness.lower()}_pnl_fixed.csv", index=False)
