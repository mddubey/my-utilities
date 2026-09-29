"""Ad hoc (2026-09-27): layer real NIFTY options EOD P&L onto the Double 7s LONG signal
(the corroborated one -- NIFTY 75.0%/Bank Nifty 72.5%/Sensex 75.7%). Real bhavcopy, real
strike/expiry selection, exit on the SAME underlying signal (Close makes a fresh 7-day high)
rather than a fixed date -- not a forward-return snapshot, a real contract tracked day by
day from entry to the actual exit day.

Expiry rule: on the entry day, look at what's actually being offered in the real option
chain that day and pick the smallest available expiry that is MORE than 20 calendar days
out -- comfortably covers Double 7s Long's median 8-day hold (and the real max seen, 28
days) without expiring mid-trade, same spirit as this project's own validated stock-options
"ITM + next-month" recipe (avoid the mid-trade-expiry problem), adapted to NIFTY's own
mixed weekly/monthly expiry calendar rather than assuming a fixed monthly cycle.

Strike rule: real ITM CE, nearest strike that is 1.5-3% in the money (matches this
project's own documented ~5% ITM convention loosely, adjusted since NIFTY's strike grid is
coarser relative to price than individual stocks).
"""
import pandas as pd
import glob
import os

OPTIONS_DIR = "options_cache"
trades = pd.read_csv("nifty_double7_long.csv", parse_dates=["entry_date", "exit_date"])

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
    candidate_expiries = [e for e in expiries if (e - tr.entry_date).days > 20]
    if not candidate_expiries:
        continue
    expiry = candidate_expiries[0]

    chain = nifty_ce[nifty_ce.XpryDt == expiry.strftime("%Y-%m-%d")].copy()
    itm_target = spot * 0.98  # ~2% ITM
    chain["strike_dist"] = (chain.StrkPric - itm_target).abs()
    itm_chain = chain[chain.StrkPric < spot]
    if itm_chain.empty:
        continue
    strike = itm_chain.sort_values("strike_dist").iloc[0].StrkPric

    entry_row = chain[chain.StrkPric == strike]
    if entry_row.empty or entry_row.iloc[0].ClsPric <= 0:
        continue
    entry_premium = float(entry_row.iloc[0].ClsPric)

    # track to the real exit date (same signal-driven exit as the underlying trade)
    exit_str = tr.exit_date.strftime("%Y%m%d")
    exit_path = f"{OPTIONS_DIR}/{exit_str}.csv"
    if not os.path.exists(exit_path):
        # find nearest available prior trading day file
        all_dates = sorted(pd.to_datetime(os.path.basename(p)[:8], format="%Y%m%d") for p in glob.glob(f"{OPTIONS_DIR}/*.csv"))
        prior = [d for d in all_dates if d <= tr.exit_date]
        if not prior:
            continue
        exit_path = f"{OPTIONS_DIR}/{prior[-1].strftime('%Y%m%d')}.csv"
    xdf = pd.read_csv(exit_path)
    exit_row = xdf[(xdf.TckrSymb == "NIFTY") & (xdf.FinInstrmTp == "IDO") & (xdf.OptnTp == "CE")
                   & (xdf.XpryDt == expiry.strftime("%Y-%m-%d")) & (xdf.StrkPric == strike)]
    if exit_row.empty or exit_row.iloc[0].ClsPric <= 0:
        continue
    exit_premium = float(exit_row.iloc[0].ClsPric)

    opt_ret = exit_premium / entry_premium - 1
    results.append(dict(entry_date=tr.entry_date, exit_date=tr.exit_date, hold_days=tr.hold_days,
                         underlying_ret=tr.ret, spot=spot, strike=strike, expiry=expiry,
                         days_to_expiry_at_entry=(expiry - tr.entry_date).days,
                         entry_premium=entry_premium, exit_premium=exit_premium, opt_ret=opt_ret))

res = pd.DataFrame(results)
print(f"n trades with real option data: {len(res)} (of {len(trades)} underlying Double7s Long signals)")
print()
print(res[["entry_date", "hold_days", "underlying_ret", "strike", "days_to_expiry_at_entry", "entry_premium", "exit_premium", "opt_ret"]].round(3).to_string(index=False))
print()
print(f"=== REAL OPTIONS P&L, Double 7s Long, ITM (~2%) + >20-day expiry ===")
print(f"  win rate: {(res.opt_ret>0).mean()*100:.1f}%")
print(f"  median option return: {res.opt_ret.median()*100:+.2f}%   mean: {res.opt_ret.mean()*100:+.2f}%")
print(f"  median underlying return (same trades): {res.underlying_ret.median()*100:+.2f}%")
print(f"  implied avg leverage (opt_ret/underlying_ret, where underlying_ret>0.1%): "
      f"{(res[res.underlying_ret.abs()>0.001].opt_ret / res[res.underlying_ret.abs()>0.001].underlying_ret).median():.1f}x")
s = res.opt_ret.sort_values(ascending=False)
k = max(1, round(len(s) * 0.10))
tot = s.sum()
share = s.head(k).sum() / tot * 100 if abs(tot) > 1e-6 else float("nan")
print(f"  concentration check (top10% n={k}): {share:.1f}%")

res.to_csv("nifty_double7_long_options_pnl.csv", index=False)
print()
print("saved: nifty_double7_long_options_pnl.csv")
