"""NIFTY Index CE/PE Signal Checker -- standalone daily tool for the system validated in
nifty_index_swing_strategy.md. NOT wired into the main project (backtest.py, daily_scan.py,
FINDINGS.md, etc.) on purpose -- separate exploration, separate tooling, per explicit
instruction. Keeps its own tiny state file (nifty_index_position.json) for the one open
position at a time; this system doesn't stack multiple concurrent positions.

Usage:
  python3 nifty_index_signal_checker.py                    -- check today's signals + any open position
  python3 nifty_index_signal_checker.py enter CE 24500 24  -- record entry: side, ATM strike, days-to-expiry chosen
  python3 nifty_index_signal_checker.py exit                -- close the open position (manual, after you've exited for real)

Rules (see nifty_index_swing_strategy.md for the full backtest behind these):
  CE entry: fresh 7-day low AND Close>SMA50 AND SMA50 rising (vs 10d ago) AND ADX(14)<20
  PE entry: fresh 7-day high AND SMA200 declining (vs 20d ago) AND ADX(14)<20
  CE exit:  fresh 7-day high (same rolling-high trigger, opposite side)
  PE exit:  fresh 7-day low
  Strike:   ATM (nearest 50-pt strike to spot's close)
  Expiry:   smallest available expiry >20 calendar days from entry -- NEVER current-week,
            confirmed worse on both sides (forced-settlement risk with no real payoff edge)
"""
import sys
import json
import os
import pandas as pd

STATE_FILE = "nifty_index_position.json"


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


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return None


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def fetch_nifty():
    import yfinance as yf
    df = yf.download("^NSEI", period="3y", interval="1d", progress=False)
    df.columns = df.columns.droplevel(1) if hasattr(df.columns, "droplevel") and df.columns.nlevels > 1 else df.columns
    df = df.reset_index().rename(columns={"index": "Date"})
    return df


def main():
    df = fetch_nifty()
    df["sma50"] = df.Close.rolling(50).mean()
    df["sma200"] = df.Close.rolling(200).mean()
    df["adx14"] = compute_adx(df)
    df["sma50_10ago"] = df.sma50.shift(10)
    df["sma200_20ago"] = df.sma200.shift(20)
    df["high7_prior"] = df.High.shift(1).rolling(7).max()
    df["low7_prior"] = df.Low.shift(1).rolling(7).min()

    today = df.iloc[-1]
    spot = today.Close
    atm_strike = round(spot / 50) * 50

    ce_entry = bool(today.Low <= today.low7_prior and today.Close > today.sma50
                     and today.sma50 > today.sma50_10ago and today.adx14 < 20)
    pe_entry = bool(today.High >= today.high7_prior and today.sma200 < today.sma200_20ago
                     and today.adx14 < 20)
    ce_exit_trigger = bool(today.High >= today.high7_prior)
    pe_exit_trigger = bool(today.Low <= today.low7_prior)

    print(f"NIFTY Index CE/PE Signal Checker -- as of {today.Date.date()}")
    print(f"Close={spot:.2f}  SMA50={today.sma50:.2f}  SMA200={today.sma200:.2f}  ADX14={today.adx14:.1f}")
    print()

    state = load_state()
    if state:
        print(f"=== OPEN POSITION: {state['side']} entered {state['entry_date']} "
              f"@ strike {state['strike']}, ~{state['dte_chosen']}d expiry chosen ===")
        exit_fired = ce_exit_trigger if state["side"] == "CE" else pe_exit_trigger
        if exit_fired:
            print(f"  *** EXIT SIGNAL FIRED TODAY *** (fresh 7-day {'high' if state['side']=='CE' else 'low'})")
            print(f"  Run: python3 {sys.argv[0]} exit    (after you've closed the real position)")
        else:
            print("  No exit signal yet -- still holding.")
        print()
    else:
        print("=== No open position ===")
        print()
        print(f"CE entry signal today: {'*** FIRED ***' if ce_entry else 'no'}")
        if ce_entry:
            print(f"  -> ATM strike ~{atm_strike}, expiry: smallest available >20 calendar days out")
            print(f"  Run: python3 {sys.argv[0]} enter CE {atm_strike} <days_to_expiry_chosen>")
        print(f"PE entry signal today: {'*** FIRED ***' if pe_entry else 'no'}")
        if pe_entry:
            print(f"  -> ATM strike ~{atm_strike}, expiry: smallest available >20 calendar days out")
            print(f"  Run: python3 {sys.argv[0]} enter PE {atm_strike} <days_to_expiry_chosen>")
        if not ce_entry and not pe_entry:
            print()
            print("No signal today. Real base rates: CE ~62.5% win/+24.8% median (n=16, thin),")
            print("PE ~71.4% win/+33.3% median (n=7, very thin) -- see nifty_index_swing_strategy.md")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "enter":
        side, strike, dte = sys.argv[2], sys.argv[3], sys.argv[4]
        import datetime
        save_state(dict(side=side, entry_date=str(datetime.date.today()), strike=strike, dte_chosen=dte))
        print(f"Recorded: {side} position, strike {strike}, ~{dte}d expiry.")
    elif len(sys.argv) > 1 and sys.argv[1] == "exit":
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            print("Position closed, state cleared.")
        else:
            print("No open position to close.")
    else:
        main()
