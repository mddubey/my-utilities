"""Per direct user point: SMA200 has been declining ~72% of the last 9 months, so "SMA200
rising" as a Long filter is nearly dead in the current regime -- misses real short-term
rallies happening inside the broader multi-month decline. Test SMA50 (faster-reacting)
instead: Close>SMA50, SMA50 rising (vs 10 days ago), ADX<20. Same corrected methodology:
real ATM CE, >20-day expiry, forced-settlement aware from the start.
"""
import pandas as pd
import os

OPTIONS_DIR = "options_cache"


def compute_adx(df, period=14):
    high, low, close = df.High, df.Low, df.Close
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm[(plus_dm - minus_dm) <= 0] = 0
    minus_dm[(minus_dm - plus_dm) <= 0] = 0
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, min_periods=period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return dx.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


nifty = pd.read_csv("data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
nifty["adx14_c"] = compute_adx(nifty)
nifty["sma50"] = nifty.Close.rolling(50).mean()
nifty["sma50_10ago"] = nifty.sma50.shift(10)
nifty["sma50_rising"] = nifty.sma50 > nifty.sma50_10ago
nifty["high7_prior"] = nifty.High.shift(1).rolling(7).max()
nifty["low7_prior"] = nifty.Low.shift(1).rolling(7).min()
nifty_close = nifty.set_index("Date").Close
n = len(nifty)

print(f"SMA50 rising base rate, full 5yr: {nifty.sma50_rising.mean()*100:.1f}%  "
      f"(last 180 days: {nifty.sma50_rising.tail(180).mean()*100:.1f}%)")
print()

trades = []
i = 60
while i < n:
    row = nifty.iloc[i]
    if pd.isna(row.low7_prior) or pd.isna(row.sma50_rising) or pd.isna(row.adx14_c):
        i += 1
        continue
    signal = row.Low <= row.low7_prior and row.Close > row.sma50 and row.sma50_rising and row.adx14_c < 20
    if not signal:
        i += 1
        continue
    entry_price = row.Close
    entry_date = row.Date
    j = i + 1
    exit_price = None
    while j < n:
        r = nifty.iloc[j]
        h7 = nifty.High.shift(1).rolling(7).max().iloc[j]
        if r.High >= h7:
            exit_price = r.Close
            break
        j += 1
    if exit_price is None:
        i += 1
        continue
    ret = exit_price / entry_price - 1
    trades.append(dict(entry_date=entry_date, exit_date=nifty.Date.iloc[j], hold_days=j - i, ret=ret))
    i = j + 1

trades = pd.DataFrame(trades)
print(f"Double 7s LONG (SMA50>rising + ADX<20) underlying trades: n={len(trades)}")
if not trades.empty:
    print(f"underlying win rate: {(trades.ret>0).mean()*100:.1f}%  median hold: {trades.hold_days.median():.0f}d")
    print(f"trades in last 9 months (>=2026-01-01): {(trades.entry_date>='2026-01-01').sum()}")
print()

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
    chain["d"] = (chain.StrkPric - spot).abs()
    if chain.empty:
        continue
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
        if expiry not in nifty_close.index:
            continue
        spot_at_expiry = nifty_close.loc[expiry]
        exit_premium = max(spot_at_expiry - strike, 0)
        forced_settlement = True

    opt_ret = exit_premium / entry_premium - 1
    results.append(dict(entry_date=tr.entry_date, hold_days=tr.hold_days, underlying_ret=tr.ret,
                         strike=strike, forced_settlement=forced_settlement, opt_ret=opt_ret))

res = pd.DataFrame(results)
print(f"=== Double 7s LONG (SMA50 rising + ADX<20), real ATM CE: n={len(res)} ===")
if not res.empty:
    print(res.to_string(index=False))
    print()
    print(f"win rate: {(res.opt_ret>0).mean()*100:.1f}%")
    print(f"median: {res.opt_ret.median()*100:+.2f}%   mean: {res.opt_ret.mean()*100:+.2f}%")
    print(f"forced-settlement: {res.forced_settlement.sum()} of {len(res)}")
    s = res.opt_ret.sort_values(ascending=False)
    k = max(1, round(len(s) * 0.1))
    tot = s.sum()
    share = s.head(k).sum() / tot * 100 if abs(tot) > 1e-6 else float("nan")
    print(f"concentration (top10% n={k}): {share:.1f}%")
