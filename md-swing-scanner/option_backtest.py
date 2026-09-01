import functools
from pathlib import Path

import pandas as pd

OPT_CACHE_DIR = Path(__file__).parent / "options_cache"
COLS = ["TradDt", "TckrSymb", "XpryDt", "StrkPric", "OptnTp", "OpnPric", "HghPric",
        "LwPric", "ClsPric", "OpnIntrst", "TtlTradgVol", "NewBrdLotQty"]
MIN_EXPIRY_RUNWAY_DAYS = 5  # trading days; less than this is pure theta bleed, no room for the thesis to play out


@functools.lru_cache(maxsize=None)
def trading_days():
    return sorted(pd.to_datetime(f.stem, format="%Y%m%d") for f in OPT_CACHE_DIR.glob("*.csv"))


def days_after(date):
    days = trading_days()
    import bisect
    i = bisect.bisect_right(days, date)
    return days[i:]


def trading_days_between(start, end):
    """Count of trading days strictly after start, up to and including end."""
    days = trading_days()
    import bisect
    return bisect.bisect_right(days, end) - bisect.bisect_right(days, start)


@functools.lru_cache(maxsize=None)
def load_day(ymd):
    path = OPT_CACHE_DIR / f"{ymd}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["TradDt", "XpryDt"])
    return df[df.FinInstrmTp == "STO"][COLS]


FUT_COLS = ["TradDt", "TckrSymb", "XpryDt", "ClsPric", "PrvsClsgPric", "OpnIntrst", "ChngInOpnIntrst"]
OI_BUILDUP_WINDOW = 3  # trading days — matches the 3-day cadence used elsewhere in this project


@functools.lru_cache(maxsize=None)
def load_day_futures(ymd):
    path = OPT_CACHE_DIR / f"{ymd}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["TradDt", "XpryDt"])
    return df[df.FinInstrmTp == "STF"][FUT_COLS]


def front_month_future(ticker, date):
    day_df = load_day_futures(date.strftime("%Y%m%d"))
    if day_df is None:
        return None
    chain = day_df[day_df.TckrSymb == ticker]
    if chain.empty:
        return None
    expiries = sorted(e for e in chain.XpryDt.unique() if e >= date)
    if not expiries:
        return None
    row = chain[chain.XpryDt == expiries[0]]
    return row.iloc[0] if not row.empty else None


def oi_buildup_bullish(ticker, date):
    """Long buildup (price up AND futures OI up) over a trailing window, as an extra
    confirmation on top of the stock-price signal: rejects rallies that are just short
    covering (price up, OI flat/falling — no fresh money committing, weaker/more likely
    to reverse) even though the price action alone looks identical to a real breakout."""
    days = [d for d in trading_days() if d <= date]
    if len(days) < OI_BUILDUP_WINDOW:
        return False
    window = days[-OI_BUILDUP_WINDOW:]
    net_oi_chg = 0
    first_price = last_price = None
    for d in window:
        row = front_month_future(ticker, d)
        if row is None:
            return False
        net_oi_chg += row.ChngInOpnIntrst
        if first_price is None:
            first_price = row.PrvsClsgPric
        last_price = row.ClsPric
    return last_price > first_price and net_oi_chg > 0


def liquid(row):
    """Real minimum bar, not a robust liquidity guarantee: some open interest
    AND an actual trade that day. Both zero -> the ClsPric is a stale
    carried-forward theoretical price, not something you could transact at."""
    return row.OpnIntrst > 0 and row.TtlTradgVol > 0


ITM_PCT = 0.05  # contract-selection isolation experiment (2026-08-31): how far in-the-money
                 # the "itm" moneyness variant targets. No real delta available (no IV column
                 # in the bhavcopy, would need a Black-Scholes back-out — see README's known
                 # limitations), so this is a moneyness PROXY: the real, available strike
                 # closest to spot*(1-ITM_PCT), not an actual 0.60-0.70 delta band.


def pick_contract(ticker, entry_date, spot_price, moneyness="atm", expiry_choice="current"):
    """moneyness: 'atm' (nearest strike to spot, default/original behavior) or 'itm'
    (nearest strike to spot*(1-ITM_PCT) — less theta/vega sensitivity, closer to
    tracking the underlying 1:1, at a higher premium).
    expiry_choice: 'current' (front month, rolling to next if <MIN_EXPIRY_RUNWAY_DAYS
    left — default/original behavior) or 'next' (always skip straight to the next
    month, more runway from day one; no trade if only one expiry is listed)."""
    day_df = load_day(entry_date.strftime("%Y%m%d"))
    if day_df is None:
        return None
    chain = day_df[(day_df.TckrSymb == ticker) & (day_df.OptnTp == "CE")]
    if chain.empty:
        return None

    expiries = sorted(e for e in chain.XpryDt.unique() if e >= entry_date)
    if not expiries:
        return None
    if expiry_choice == "current":
        expiry = expiries[0]  # nearest available expiry — front month, same as a real trader would buy
        if len(expiries) > 1 and trading_days_between(entry_date, expiry) < MIN_EXPIRY_RUNWAY_DAYS:
            expiry = expiries[1]  # front-month is about to die — roll to next month instead of buying a corpse
    elif expiry_choice == "next":
        if len(expiries) < 2:
            return None
        expiry = expiries[1]
    else:
        raise ValueError(expiry_choice)

    strikes = chain[(chain.XpryDt == expiry) & chain.apply(liquid, axis=1)]
    if strikes.empty:
        return None
    target = spot_price if moneyness == "atm" else spot_price * (1 - ITM_PCT)
    idx = (strikes.StrkPric - target).abs().idxmin()
    row = strikes.loc[idx]
    return expiry, row.StrkPric, row.NewBrdLotQty


def option_row(ticker, date, expiry, strike):
    day_df = load_day(date.strftime("%Y%m%d"))
    if day_df is None:
        return None
    r = day_df[(day_df.TckrSymb == ticker) & (day_df.OptnTp == "CE")
               & (day_df.XpryDt == expiry) & (day_df.StrkPric == strike)]
    return r.iloc[0] if not r.empty else None


@functools.lru_cache(maxsize=None)
def _stock_closes(ticker):
    path = Path(__file__).parent / "data_cache" / f"{ticker}.csv"
    if not path.exists():
        return None
    return pd.read_csv(path, index_col="Date", parse_dates=True).Close


def stock_close(ticker, date):
    s = _stock_closes(ticker)
    if s is None or date not in s.index:
        return None
    return s.loc[date]


def simulate_option_trade(trade, moneyness="atm", expiry_choice="current"):
    contract = pick_contract(trade.ticker, trade.entry_date, trade.entry_price, moneyness, expiry_choice)
    if contract is None:
        return None
    expiry, strike, lot_size = contract

    entry_row = option_row(trade.ticker, trade.entry_date, expiry, strike)
    if entry_row is None or not entry_row.ClsPric or not liquid(entry_row):
        return None
    entry_px = entry_row.ClsPric

    held_to_expiry = expiry < trade.exit_date

    if held_to_expiry:
        # NSE cash-settles ITM calls at expiry to intrinsic value based on the
        # UNDERLYING's closing price — this happens regardless of whether this
        # specific strike traded that day. Using the option's own ClsPric here is
        # wrong when volume is zero: it's just the last real trade carried forward,
        # which can be badly stale if the stock kept moving after that (verified:
        # POWERINDIA's last trade was 4 days pre-expiry, ~20% below true intrinsic
        # by the actual expiry date). Compute settlement directly from the spot.
        exit_date = expiry
        spot = stock_close(trade.ticker, expiry)
        if spot is None:
            return None
        exit_px = max(0.0, spot - strike)
    else:
        exit_date = trade.exit_date
        exit_row = option_row(trade.ticker, exit_date, expiry, strike)
        if exit_row is None or exit_row.ClsPric is None:
            return None

        # a signal-driven exit needs a REAL counterparty that day — if that day
        # never traded, walk forward to the next day that did, up to expiry
        if not liquid(exit_row):
            found = False
            for d in days_after(exit_date):
                if d > expiry:
                    break
                r = option_row(trade.ticker, d, expiry, strike)
                if r is not None and r.ClsPric is not None and liquid(r):
                    exit_date, exit_row, found = d, r, True
                    break
            if not found:
                # never traded again before expiry -> settles at expiry instead
                held_to_expiry = True
                exit_date = expiry
                spot = stock_close(trade.ticker, expiry)
                if spot is None:
                    return None
                exit_px = max(0.0, spot - strike)
            else:
                exit_px = exit_row.ClsPric
        else:
            exit_px = exit_row.ClsPric

    return dict(
        ticker=trade.ticker, entry_date=trade.entry_date, exit_date=exit_date,
        expiry=expiry, strike=strike, lot_size=int(lot_size),
        entry_opt_price=entry_px, exit_opt_price=exit_px,
        pnl_pct=(exit_px / entry_px - 1) * 100,
        exit_reason="expired" if held_to_expiry else "signal",
        stock_pnl_pct=trade.pnl_pct,
    )


def run(trades_csv, moneyness="atm", expiry_choice="current"):
    trades = pd.read_csv(trades_csv, parse_dates=["entry_date", "exit_date"])
    trades = trades[~trades.open_at_end]

    results, skipped = [], 0
    for _, trade in trades.iterrows():
        r = simulate_option_trade(trade, moneyness, expiry_choice)
        if r is None:
            skipped += 1
        else:
            results.append(r)

    print(f"{len(results)} option trades simulated, {skipped} skipped (illiquid contract or no data)")
    return pd.DataFrame(results)


if __name__ == "__main__":
    # Points at the current validated F&O-scoped swing trade set (2026-09-01 — was
    # stale at v23's trades_v23_recent.csv, a stale-label bug caught during a repo
    # review, see FINDINGS.md). options_cache/ now covers back to 2022-06
    # (fetch_stock_options_pre2024.py extended it from the original UDiFF-only, 2024+
    # coverage), so no separate recent-window pre-filter is needed — trades_v28_fo.csv
    # is already pre-filtered to fo_universe.csv's F&O-eligible tickers.
    out = run("runs/trades_v28_fo.csv")
    out.to_csv("runs/option_trades.csv", index=False)

    wins = out[out.pnl_pct > 0]
    losses = out[out.pnl_pct <= 0]
    win_rate = len(wins) / len(out) * 100
    avg_win = wins.pnl_pct.mean()
    avg_loss = losses.pnl_pct.mean()
    expectancy = (win_rate / 100) * avg_win + (1 - win_rate / 100) * avg_loss

    print(f"\nwin rate           : {win_rate:.1f}%")
    print(f"avg win / avg loss : {avg_win:.2f}% / {avg_loss:.2f}%")
    print(f"expectancy/trade   : {expectancy:.2f}%")
    print(f"median pnl_pct     : {out.pnl_pct.median():.2f}%")
    print(f"held to expiry     : {(out.exit_reason == 'expired').sum()} / {len(out)}")
