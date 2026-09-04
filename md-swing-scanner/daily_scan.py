"""Run once/day, after refreshing data_cache (`python3 fetch_prices.py`) and the Nifty
regime cache (`python3 market_regime.py`) for today. Scans the full NIFTY 500 universe
(the pure-swing default, see relative_strength.py's UNIVERSE_FILE comment) for a NEW
entry signal as of the latest cached trading day — reuses backtest.py's detect_entry()
directly, so this can never drift from what the validated backtest actually tested.

Default output is now three sections: "Tradable Today" (gate-respecting, real
signals), "Watchlist — fails only on regime" (2026-08-31, pattern fired, only the ADX/
200-SMA gate blocked it — computed automatically, no flag needed, cheap since it only
costs one extra detect_entry(require_regime=False) call per ticker that didn't
already pass), and "Near-miss — intraday High cleared resistance, Close didn't
confirm" (2026-09-03, a Breakout-Continuation-only, LOW-WEIGHT ranking signal — see
signals.near_miss_high_breakout's docstring for the full backtest numbers behind it;
real but modestly below-average trades, meant to come in handy on a quiet day, not a
standing recommendation). Checked directly (2026-08-31) that loosening the gate on
breadth or an isolation basis doesn't rescue the current drought with quality trades
(see backtest.py comments/memory) — the watchlist is for observation, not a signal
that these are secretly tradable, same caveat as before.

--ignore-regime (2026-08-30): bypasses the Nifty ADX/200-SMA gate for THIS SCAN ONLY
(collapses to a single "Tradable Today" list with no watchlist split, since there's
no gate left to fail on), so pattern breakouts still surface during a regime drought
instead of relying on the watchlist section alone. These are explicitly NOT validated
trade signals — the validated backtest numbers (see README.md's Current status) all
assume the gate is on — hence the loud banner below. Purely for observing how
candidates would have looked, not for taking real positions. (2026-09-01: deliberately
not naming a specific version here anymore — this comment cited "v25" long after the
project had moved to v27, a stale-label bug caught during a repo review. Point at
README.md instead of a version number that will go stale again at the next bump.)

--live [--cutoff HH:MM] (2026-08-30): same-day intraday check instead of waiting for
tomorrow's cached close, so a real breakout can be caught same-day near the close
instead of only discovered the next morning. Two-pass, NOT a full-universe intraday
fetch (500 tickers of live data every run would be slow and mostly wasted, since only
a handful can plausibly fire on any given day):
  Pass 1 (shortlist_primed, cheap, yesterday's cached EOD data only): which tickers
    could PLAUSIBLY fire today at all — VCP's stage2 trend template + a valid base
    already formed (base_pivot is entirely backward-looking, no today data needed);
    Breakout Continuation's non-today-specific gates (trend/RSI/liquidity/momentum)
    already passing as of yesterday. Real size on 2026-08-28: 31 of 500 tickers.
  Pass 2 (fetch_live_bars, the only part that costs anything): intraday 5-min bars for
    JUST the Pass-1 shortlist, aggregated into one synthetic "today, as of cutoff" OHLCV
    bar per ticker (default cutoff 14:45 IST — most of the day's volume is typically
    already in by then). That partial bar goes through load_with_extra_row() into the
    EXACT same build_indicators()/detect_entry() as any real day — no separate
    partial-day formula, per explicit instruction. Real caveat, not swept under the
    rug: the volume figure is only what's traded so far, so vol_zscore understates the
    eventual full-day value — accepted as an approximation, not corrected for.
  Tickers outside the shortlist still scan normally off yesterday's cached close (they
  can't fire today per Pass 1, so there's nothing live to check). yfinance intraday is
  itself delayed, not a real broker feed — treat --live the same as --ignore-regime,
  observation to inform same-day action, not a validated backtest-tested signal path
  (the backtest never runs on partial-day bars)."""
import argparse
from datetime import time as dtime

import pandas as pd
import yfinance as yf

from backtest import (load, load_with_extra_row, detect_entry, resistance_target,
                      stage2_trend_template, current_stop_level, MAX_INITIAL_RISK_PCT)
from signals import base_filters_pass, entry_signal, near_miss_high_breakout
from vcp import base_pivot, vcp_breakout
from pivots import daily_pivots
from sector_strength import sector_rs
import breadth

LIVE_CUTOFF_DEFAULT = "14:45"  # IST


def shortlist_primed(tickers):
    """Pass 1 — see module docstring. Returns the sorted list of tickers worth an
    intraday fetch: NOT a prediction that they'll fire, just that they structurally
    could, using nothing but yesterday's already-cached close."""
    primed = set()
    for t in tickers:
        try:
            df = load(t, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        if len(rows) == 0:
            continue
        i = len(rows) - 1
        row = rows.iloc[i]
        if row.corp_action_day:
            continue
        if stage2_trend_template(row, t, row.Date) and base_pivot(rows, i) is not None:
            primed.add(t)
            continue
        required = ["ema34", "vol_avg10_prior", "high10_prior", "atr14_60ago",
                     "ema34_rising10", "traded_value_sma20", "close_20ago"]
        if row[required].isna().any():
            continue
        if base_filters_pass(row):
            primed.add(t)
    return sorted(primed)


def fetch_live_bars(tickers, cutoff_ist=LIVE_CUTOFF_DEFAULT):
    """Pass 2 — see module docstring. Returns {ticker: {Date, Open, High, Low, Close,
    Volume}} for tickers with usable intraday data up to cutoff_ist today."""
    if not tickers:
        return {}
    yf_tickers = [f"{t}.NS" for t in tickers]
    data = yf.download(yf_tickers, period="1d", interval="5m", group_by="ticker",
                        threads=True, progress=False, auto_adjust=False)
    cutoff_h, cutoff_m = map(int, cutoff_ist.split(":"))
    cutoff_time = dtime(cutoff_h, cutoff_m)
    bars = {}
    for t, yft in zip(tickers, yf_tickers):
        try:
            day = data[yft].dropna(how="all")
        except KeyError:
            continue
        if day.empty:
            continue
        day = day.tz_convert("Asia/Kolkata")
        today = day.index[-1].date()
        window = day[(day.index.date == today) & (day.index.time <= cutoff_time)]
        if window.empty:
            continue
        bars[t] = dict(
            Date=today, Open=window.Open.iloc[0], High=window.High.max(),
            Low=window.Low.min(), Close=window.Close.iloc[-1], Volume=window.Volume.sum(),
        )
    return bars


_FO_TICKERS = None


def _fo_tickers():
    """F&O-eligible tickers (210), lazily loaded once — used to flag whether a swing
    candidate is actually optionable at all (2026-09-01): the pure-swing universe
    (nifty500_universe.csv, 500 tickers) is a strict superset, so most scans will
    include names with NO options market whatsoever. A good swing signal on a
    non-F&O name is still a real stock trade, just never an options trade."""
    global _FO_TICKERS
    if _FO_TICKERS is None:
        _FO_TICKERS = set(pd.read_csv("fo_universe.csv", header=None)[0])
    return _FO_TICKERS


def _also_qualifies_other_pattern(ticker, pattern, rows, i):
    """Checked independently of whichever pattern actually claimed the day (2026-09-01)
    — detect_entry() itself short-circuits (Breakout Cont checked first, first match
    wins, VCP's own check never runs if BC already fired), so this re-runs the OTHER
    pattern's raw condition just for reporting. NOT a validated confidence signal:
    checked directly against 1430 v28 trades, only 40 (2.8%, all on the BC side — no
    VCP trade ever independently also clears BC's stricter same-day checklist) turned
    out dual-qualified, and their win rate was IDENTICAL to single-pattern trades
    (65.0% both ways) — the higher median (+4.07% vs +2.86%) rides on a lumpy few-
    big-winners distribution (concentration 131% on n=40), not enough evidence to
    trust as a real edge yet. Purely descriptive/informational, do not use to rank
    candidates against each other."""
    row = rows.iloc[i]
    if pattern == "breakout_cont":
        if not stage2_trend_template(row, ticker, row.Date):
            return False
        if base_pivot(rows, i) is None:
            return False
        return vcp_breakout(rows, i) is not None
    return entry_signal(row)


def _initial_stop(pattern, structural_low, row):
    """The stop level a fresh entry would start at TODAY, needed for position sizing
    before a trade even exists yet (2026-09-01) — same state shape simulate_ticker
    builds at entry (backtest.py), just reused here for a not-yet-taken candidate:
    peak_close/peak_high both equal today's own values on day zero, so
    current_stop_level's trail-engagement check can't have fired yet."""
    entry_price = row.Close
    if pattern == "coiled_spring":
        structural_low = max(structural_low, entry_price * (1 - MAX_INITIAL_RISK_PCT))
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=row.High,
                 structural_low=structural_low, target=None)
    return current_stop_level(pattern, state, row)


def _annotate(ticker, pattern, structural_low, row, prev_row, live, rows, i):
    """Points about TODAY's move specifically, on top of the raw entry (2026-08-31) —
    close/target alone can't distinguish a fresh breakout with real room to run from
    one that's already basically arrived (real case: CGPOWER close=916.00 vs
    target=917.97 is only 0.2% of headroom left) or one that already got rejected at
    that exact level intraday (real case: KAJARIACER's High today already exceeded its
    own target before closing back below it)."""
    target = resistance_target(row.Close, row)
    sector, sector_rs_pct = sector_rs(ticker, row.Date)
    return dict(
        ticker=ticker, pattern=pattern, close=row.Close, target=target,
        structural_low=structural_low, live=live,
        pct_chg=(row.Close / prev_row.Close - 1) * 100 if prev_row.Close else None,
        pct_to_target=(target / row.Close - 1) * 100 if target else None,
        target_tested_today=target is not None and row.High >= target,
        vol_zscore=row.vol_zscore,
        is_fo=ticker in _fo_tickers(),
        dual_pattern=_also_qualifies_other_pattern(ticker, pattern, rows, i),
        stop=_initial_stop(pattern, structural_low, row),
        sector=sector, sector_rs=sector_rs_pct,
    )


def _near_miss_annotate(ticker, row, prev_row):
    """Lighter than _annotate() — near-miss isn't a validated pattern match (no
    structural_low, no resolved target), just a raw checklist near-hit, so there's no
    stop/target to report, only what actually differs from a real signal today."""
    return dict(
        ticker=ticker, close=row.Close, high=row.High, high10_prior=row.high10_prior,
        pct_chg=(row.Close / prev_row.Close - 1) * 100 if prev_row.Close else None,
        vol_zscore=row.vol_zscore, is_fo=ticker in _fo_tickers(),
    )


def scan(tickers, require_regime=True, live=False, cutoff_ist=LIVE_CUTOFF_DEFAULT):
    """candidates: real, gate-respecting signals (empty if require_regime and the
    gate's shut). watchlist: candidates whose PATTERN fired but only the regime gate
    blocked them (2026-08-31) — always computed, regardless of require_regime, so a
    normal run shows both "what's tradable today" and "what to keep an eye on" without
    needing a separate --ignore-regime invocation. Cheap: only costs one extra
    detect_entry(require_regime=False) call, and only for tickers that didn't already
    pass with the gate on.

    near_miss (2026-09-03): a THIRD, lower-priority bucket, unrelated to the regime
    gate — Breakout Continuation candidates where today's intraday High cleared the
    prior 10-day high but the Close didn't confirm it (see signals.near_miss_high_
    breakout's own docstring for the full backtest numbers: real but modestly
    below-average trades, kept as a low-weight "worth a second look" flag only, not a
    validated signal). Checked independently of require_regime — this is about the
    Close-vs-High distinction, nothing to do with the market regime."""
    live_bars = {}
    live_shortlist = []
    if live:
        live_shortlist = shortlist_primed(tickers)
        live_bars = fetch_live_bars(live_shortlist, cutoff_ist)

    candidates = []
    watchlist = []
    near_miss = []
    scan_date = None
    for ticker in tickers:
        try:
            if ticker in live_bars:
                df = load_with_extra_row(ticker, live_bars[ticker], daily_pivots)
            else:
                df = load(ticker, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        if len(rows) == 0:
            continue
        i = len(rows) - 1
        row = rows.iloc[i]
        scan_date = row.Date
        if row.corp_action_day:
            continue  # today's own data looks like a corporate-action glitch — skip
        result = detect_entry(ticker, rows, i, require_regime=require_regime)
        if result is not None:
            pattern, structural_low = result
            candidates.append(_annotate(ticker, pattern, structural_low, row, rows.iloc[i - 1],
                                         live=(ticker in live_bars), rows=rows, i=i))
            continue
        if require_regime:
            ungated = detect_entry(ticker, rows, i, require_regime=False)
            if ungated is not None:
                pattern, structural_low = ungated
                watchlist.append(_annotate(ticker, pattern, structural_low, row, rows.iloc[i - 1],
                                            live=(ticker in live_bars), rows=rows, i=i))
                continue
        if near_miss_high_breakout(row):
            near_miss.append(_near_miss_annotate(ticker, row, rows.iloc[i - 1]))
    return scan_date, candidates, watchlist, near_miss, live_shortlist


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ignore-regime", action="store_true",
                         help="skip the Nifty ADX/200-SMA gate — observation only, NOT validated trade signals")
    parser.add_argument("--live", action="store_true",
                         help="check a shortlist of primed tickers against today's intraday data instead of waiting for tomorrow's close")
    parser.add_argument("--cutoff", default=LIVE_CUTOFF_DEFAULT,
                         help=f"IST cutoff time for --live's intraday snapshot (default {LIVE_CUTOFF_DEFAULT})")
    args = parser.parse_args()

    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    scan_date, candidates, watchlist, near_miss, live_shortlist = scan(
        tickers, require_regime=not args.ignore_regime, live=args.live, cutoff_ist=args.cutoff,
    )
    print(f"scan date: {scan_date.date() if scan_date is not None else 'no data'}")
    if scan_date is not None:
        pct = breadth.breadth_pct(scan_date)
        if pd.notna(pct):
            # informational only, not a filter (2026-09-02) — real backtest evidence
            # (see FINDINGS.md) shows a genuine, monotonic relationship between market
            # breadth and how today's WHOLE candidate list should be weighted: win
            # 65.0%/median +2.89% at no filter vs 69.3%/+3.58% at breadth>=80 — but per
            # direct user instruction, this stays a ranking/confidence signal, not a
            # gate that excludes low-breadth days entirely.
            print(f"market breadth today: {pct:.0f}% of NIFTY 500 above their own 200-SMA "
                  f"— historically, higher breadth days produce meaningfully better candidates "
                  f"(65.0%/+2.89% median at no filter vs 69.3%/+3.58% at breadth>=80)")
    if args.live:
        print(f"⚠ LIVE MODE (intraday as of {args.cutoff} IST, not the final close) — checked "
              f"{len(live_shortlist)} pre-filtered tickers: {live_shortlist}")
    if args.ignore_regime:
        print("⚠ REGIME GATE DISABLED — these are NOT validated trade signals (the validated")
        print("  backtest numbers assume the gate is on). Observation only, do not trade these as-is.")

    def print_row(c):
        target_str = f"₹{c['target']:.2f} ({c['pct_to_target']:+.1f}% away)" if c['target'] is not None else "n/a"
        live_tag = " [LIVE]" if c.get("live") else ""
        chg_str = f"{c['pct_chg']:+.1f}% today" if c['pct_chg'] is not None else "n/a"
        fo_tag = "[F&O]" if c["is_fo"] else "[NO OPTIONS]"
        dual_tag = " [BOTH]" if c["dual_pattern"] else ""
        sector_str = (f"{c['sector']} (sector RS {c['sector_rs']:.0f})"
                      if c["sector"] and c["sector_rs"] is not None else "sector n/a")
        print(f"  {c['ticker']:<14} {fo_tag:<12} {c['pattern']:<14} close=₹{c['close']:.2f} ({chg_str})  "
              f"stop=₹{c['stop']:.2f}  target={target_str}  vol_z={c['vol_zscore']:+.1f}{live_tag}{dual_tag}")
        print(f"    {sector_str}")
        if c["target_tested_today"]:
            print(f"    ⚠ already touched/exceeded this target intraday today — thin or no room left")
        if c["dual_pattern"]:
            print(f"    ℹ also independently clears the other pattern's condition today — informational only, "
                  f"NOT a validated confidence signal (checked: win rate identical either way, see FINDINGS.md)")

    print(f"\nTradable Today ({len(candidates)}):")
    if not candidates:
        print("  none")
    for c in candidates:
        print_row(c)

    if not args.ignore_regime:
        print(f"\nWatchlist — fails only on regime ({len(watchlist)}):")
        print("  Pattern fired but the Nifty ADX/200-SMA gate blocked it — not validated")
        print("  trade signals, for watching only in case the regime opens back up.")
        if not watchlist:
            print("  none")
        for c in watchlist:
            print_row(c)

    print(f"\nNear-miss — intraday High cleared resistance, Close didn't confirm ({len(near_miss)}):")
    print("  LOW WEIGHT / informational only. Full-backtest checked: real, tradeable trades,")
    print("  but modestly BELOW the standard pool's quality (63.0% win/+2.29% median vs")
    print("  65.0%/+2.89%) — worth a second look on a quiet day, not a standing recommendation.")
    if not near_miss:
        print("  none")
    for c in near_miss:
        chg_str = f"{c['pct_chg']:+.1f}% today" if c['pct_chg'] is not None else "n/a"
        fo_tag = "[F&O]" if c["is_fo"] else "[NO OPTIONS]"
        print(f"  {c['ticker']:<14} {fo_tag:<12} close=₹{c['close']:.2f}  high=₹{c['high']:.2f}  "
              f"resistance=₹{c['high10_prior']:.2f}  ({chg_str})  vol_z={c['vol_zscore']:+.1f}")
