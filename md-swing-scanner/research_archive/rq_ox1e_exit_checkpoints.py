"""RQ-OX1-E -- Day+1 Intraday Exit-Checkpoint Behavior (2026-09-23).

Direct answer to the original live-execution problem that started the whole
OX1 arc: the fast/day+1 options play's planned exit at day+1 MARKET OPEN
(09:15) is not realistically achievable -- real quoted premiums vs. actual
fills diverge hugely (real example: MAXHEALTH quote Rs19->25->30 vs actual
fill Rs21). This asks: how does the option behave at more realistic, later
checkpoints -- day+1 09:30, 10:00, 11:30 -- against the (unrealistic) 09:15
open and the day+1 EOD close as references?

Uses ox1_reconstruction.py (RQ-OX1-A/B/C/D, PROMOTED Research Infrastructure)
to reconstruct the option's value at each checkpoint from REAL day+1
intraday STOCK prices (intraday_cache). Entry anchor (O0, S0) is REAL EOD
option-chain + cash-bhav data at breakout-day close (option_backtest.py's
own pick_contract/option_row/_real_spot/liquid) -- no reconstruction needed
for the entry side, only for the day+1 exit checkpoints.

Population: rq_a5_retest_dominance.csv's full breakout population (one row
per real detected breakout, 5-year, both patterns), restricted per the
project's standing population-choice convention: freshness<=0.40, F&O-
eligible, breakout_date's day+1 trading date inside intraday_cache's real
coverage window (2026-06-10..2026-09-19).

Guardrails (per RQ-OX1-D disposition): no new beta, no theta correction, no
threshold optimization on the checkpoints themselves -- 09:30/10:00/11:30
are the user's own round, pre-specified candidate exit times, not swept.
This is comparative/ranking research (OX1's validated use case): reported
as reconstructed_pnl, never claimed as an executable price. Per the OX1-D
Non-Goals, this output must never be used as an optimization target -- it
answers "how does it behave", not "what is the optimal exit second".
"""
import warnings
warnings.filterwarnings("ignore")

import sys
from pathlib import Path

import pandas as pd

import option_backtest as ob
from daily_scan import _fo_tickers
from ox1_reconstruction import reconstruct_option_value
from research.metrics import win_rate, expectancy

INTRADAY_CACHE_DIR = Path(__file__).parent / "intraday_cache"
INTRADAY_LO = pd.Timestamp("2026-06-10")
INTRADAY_HI = pd.Timestamp("2026-09-19")

CHECKPOINTS = ["09:15", "09:30", "10:00", "11:30", "15:25"]
UNREALISTIC_BASELINE = "09:15"  # what the current recipe assumes, shown for contrast only
REFERENCE_CLOSE = "15:25"       # day+1 EOD reference, not a claimed "better" exit


def _load_intraday(ticker):
    path = INTRADAY_CACHE_DIR / f"{ticker}.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, parse_dates=["Datetime"])
    if df.empty:
        return None
    df["Datetime"] = df["Datetime"].dt.tz_convert("Asia/Kolkata")
    df["day"] = df["Datetime"].dt.normalize()
    return df


def _day_bars(intraday_df, date):
    target = pd.Timestamp(date).normalize().tz_localize("Asia/Kolkata")
    d = intraday_df[intraday_df.day == target]
    return d.reset_index(drop=True) if len(d) else None


def _bar_at_or_before(day_bars, hhmm):
    h, m = map(int, hhmm.split(":"))
    target_time = day_bars.Datetime.iloc[0].replace(hour=h, minute=m, second=0, microsecond=0)
    eligible = day_bars[day_bars.Datetime <= target_time]
    return eligible.iloc[-1] if len(eligible) else None


def load_population():
    df = pd.read_csv("rq_a5_retest_dominance.csv", parse_dates=["breakout_date"])
    fo = set(_fo_tickers())
    df = df[df.ticker.isin(fo)]
    df = df[df.freshness <= 0.40]
    df = df.drop_duplicates(["ticker", "breakout_date"])
    return df.reset_index(drop=True)


def gather(events, verbose=False):
    rows = []
    cache = {}
    n_no_entry = n_no_intraday = n_out_of_window = 0
    for n, ev in enumerate(events.itertuples()):
        if verbose and n % 200 == 0:
            print(f"  {n}/{len(events)}, {len(rows)} checkpoint-rows so far", file=sys.stderr)
        t = ev.ticker

        day1_candidates = ob.days_after(ev.breakout_date)
        if not day1_candidates:
            n_out_of_window += 1
            continue
        day1 = day1_candidates[0]
        if not (INTRADAY_LO <= day1 <= INTRADAY_HI):
            n_out_of_window += 1
            continue

        fallback_close = ob.stock_close(t, ev.breakout_date)
        entry_spot = ob._real_spot(t, ev.breakout_date, fallback_close)
        if entry_spot is None:
            n_no_entry += 1
            continue
        contract = ob.pick_contract(t, ev.breakout_date, entry_spot, "atm", "current")
        if contract is None:
            n_no_entry += 1
            continue
        expiry, strike, lot_size = contract
        entry_row = ob.option_row(t, ev.breakout_date, expiry, strike)
        if entry_row is None or not entry_row.ClsPric or not ob.liquid(entry_row):
            n_no_entry += 1
            continue
        O0 = entry_row.ClsPric

        if t not in cache:
            cache[t] = _load_intraday(t)
        idf = cache[t]
        if idf is None:
            n_no_intraday += 1
            continue
        day1_bars = _day_bars(idf, day1)
        if day1_bars is None or len(day1_bars) < 10:
            n_no_intraday += 1
            continue

        entry_ts = pd.Timestamp(ev.breakout_date).tz_localize("Asia/Kolkata").replace(hour=15, minute=30).isoformat()

        for hhmm in CHECKPOINTS:
            bar = _bar_at_or_before(day1_bars, hhmm)
            if bar is None:
                continue
            current_ts = bar.Datetime.isoformat()
            path_bars = day1_bars[day1_bars.Datetime <= bar.Datetime]
            stock_path = [(b.Datetime.isoformat(), b.Close) for b in path_bars.itertuples()]

            r = reconstruct_option_value(
                ticker=t, strike=strike, expiry=str(expiry.date()), option_type="CE",
                entry_timestamp=entry_ts, entry_spot=entry_spot, entry_option_price=O0,
                current_timestamp=current_ts, stock_path=stock_path,
            )
            rows.append(dict(
                ticker=t, breakout_date=ev.breakout_date, day1=day1, checkpoint=hhmm,
                O0=O0, S0=entry_spot, S=bar.Close,
                reconstructed_value=r.reconstructed_option_value,
                reconstructed_pnl_pct=(r.reconstructed_option_value / O0 - 1) * 100,
                confidence=r.reconstruction_confidence,
                flags="|".join(r.reconstruction_flags),
            ))
    print(f"\nSkipped -- day+1 outside intraday coverage window: {n_out_of_window}", file=sys.stderr)
    print(f"Skipped -- no real entry option data: {n_no_entry}", file=sys.stderr)
    print(f"Skipped -- ticker has no intraday cache / day+1 bars: {n_no_intraday}", file=sys.stderr)
    print(f"Usable breakout events: {len(events) - n_out_of_window - n_no_entry - n_no_intraday}/{len(events)}",
          file=sys.stderr)
    return pd.DataFrame(rows)


def report(df):
    n_events = df.ticker.str.cat(df.breakout_date.astype(str), sep="|").nunique()
    print(f"\n=== RQ-OX1-E: day+1 exit-checkpoint behavior, n={n_events} breakout events ===\n")
    print(f"{'Checkpoint':<12}{'n':>6}{'win%':>8}{'expectancy%':>14}{'median%':>10}{'BASELINE':>10}{'CAUTION':>9}{'LOW_CONF':>10}")
    for cp in CHECKPOINTS:
        g = df[df.checkpoint == cp]
        pnl = g.reconstructed_pnl_pct.dropna()
        conf_counts = g.confidence.value_counts()
        label = cp + (" (unrealistic)" if cp == UNREALISTIC_BASELINE else " (EOD ref)" if cp == REFERENCE_CLOSE else "")
        print(f"{label:<12}{len(g):>6}{win_rate(pnl):>7.1f}%{expectancy(pnl):>+13.3f}%{pnl.median():>+9.3f}%"
              f"{conf_counts.get('BASELINE',0):>10}{conf_counts.get('CAUTION',0):>9}{conf_counts.get('LOW_CONFIDENCE',0):>10}")

    print("\n--- Opportunity cost vs the unrealistic 09:15-open assumption ---")
    piv = df.pivot_table(index=["ticker", "breakout_date"], columns="checkpoint", values="reconstructed_pnl_pct")
    for cp in CHECKPOINTS:
        if cp == UNREALISTIC_BASELINE or cp not in piv.columns:
            continue
        diff = (piv[cp] - piv[UNREALISTIC_BASELINE]).dropna()
        print(f"  {cp:<8} vs 09:15: mean diff {diff.mean():+.3f}pp, median diff {diff.median():+.3f}pp, "
              f"n={len(diff)}, %-of-events-worse={100*(diff<0).mean():.1f}%")


if __name__ == "__main__":
    events = load_population()
    print(f"Population: {len(events)} breakout events (freshness<=0.40, F&O)", file=sys.stderr)
    df = gather(events, verbose=True)
    df.to_csv("rq_ox1e_exit_checkpoints.csv", index=False)
    report(df)
