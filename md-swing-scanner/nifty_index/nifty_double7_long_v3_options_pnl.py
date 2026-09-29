"""Symmetric test per direct user question: Double 7s Short v3 (SMA200 declining + ADX<20)
gave a much cleaner real options result than plain Long (Close>SMA200 only). Never tested
the symmetric LONG v3: SMA200 RISING (not just Close>SMA200) + ADX<20. Same corrected
methodology throughout: real ATM CE, >20-day expiry, forced-settlement aware from the start.
"""
import pandas as pd
import os

OPTIONS_DIR = "../options_cache"


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


nifty = pd.read_csv("../data_cache/_NIFTY.csv")
nifty["Date"] = pd.to_datetime(nifty.Date)
nifty["adx14_c"] = compute_adx(nifty)
nifty["sma200_20ago"] = nifty.sma200.shift(20)
nifty["sma200_rising"] = nifty.sma200 > nifty.sma200_20ago
nifty["high7_prior"] = nifty.High.shift(1).rolling(7).max()
nifty["low7_prior"] = nifty.Low.shift(1).rolling(7).min()
nifty_close = nifty.set_index("Date").Close
n = len(nifty)

# --- Step 1: Double 7s LONG v3 trade list: 7d low + Close>SMA200 + SMA200 rising + ADX<20 ---
trades = []
i = 210
while i < n:
    row = nifty.iloc[i]
    if pd.isna(row.low7_prior) or pd.isna(row.sma200_rising) or pd.isna(row.adx14_c):
        i += 1
        continue
    signal = row.Low <= row.low7_prior and row.Close > row.sma200 and row.sma200_rising and row.adx14_c < 20
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
print(f"Double 7s LONG v3 (SMA200 rising + ADX<20) underlying trades: n={len(trades)}")
if not trades.empty:
    print(trades.to_string(index=False))
    print(f"underlying win rate: {(trades.ret>0).mean()*100:.1f}%  median hold: {trades.hold_days.median():.0f}d")
print()

# --- Step 2: real ATM CE options P&L, forced-settlement aware ---
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
print(f"=== Double 7s LONG v3, real ATM CE (>20-day expiry, forced-settlement aware): n={len(res)} ===")
if not res.empty:
    print(res.to_string(index=False))
    print()
    print(f"win rate: {(res.opt_ret>0).mean()*100:.1f}%")
    print(f"median: {res.opt_ret.median()*100:+.2f}%   mean: {res.opt_ret.mean()*100:+.2f}%")
    print(f"forced-settlement trades: {res.forced_settlement.sum()} of {len(res)}")
    s = res.opt_ret.sort_values(ascending=False)
    k = max(1, round(len(s) * 0.1))
    tot = s.sum()
    share = s.head(k).sum() / tot * 100 if abs(tot) > 1e-6 else float("nan")
    print(f"concentration check (top10% n={k}): {share:.1f}%")
    res.to_csv("nifty_double7_long_v3_atm_pnl.csv", index=False)
