"""trader_dashboard.py -- one entry point for the daily workflow validated this
session, tying together four already-independently-validated tools rather than
reimplementing any of their logic (same reasoning as detect_entry()'s own docstring:
two copies of "what counts as a signal" drifting apart over time is a real risk):

  evening   -- tonight's candidate list: ticker, trigger price, stop, quality score.
               Wraps tomorrow_candidates.py's build_candidates() (the single source of
               truth for candidate selection/scoring) and adds a stop level via
               daily_scan.py's _initial_stop(), the same function daily_scan.py itself
               uses -- not re-derived here.
  morning   -- the live, tiered checkpoint (pulled back / kept going / watching /
               missed), wrapping live_checkpoint.py's classify_candidates() exactly as
               that file's own __main__ does, with ONE addition: cross-references
               open_positions.csv so a ticker you already hold is flagged
               "[ALREADY HOLDING]" instead of silently resurfacing as a fresh
               opportunity (a real gap noticed 2026-09-06 -- GLAND showed up as a
               fresh tier-1 pick on a day it was already a live position).
  night     -- wraps monitor_positions.py's monitor() unchanged: current stop/target
               for every row in open_positions.csv, replayed fresh each run. Added
               2026-09-06 after a direct question ("why isn't this part of the
               dashboard too") -- no good reason it wasn't, since the dashboard
               already reads that same file for the morning mode's holding-check.
  journal   -- a lightweight, append-only execution log (trade_journal.csv) -- NOT a
               replacement for open_positions.csv (monitor_positions.py's exit-logic
               replay needs that file's exact schema, untouched here). This is purely
               for reviewing what tier/price a trade actually came from later, since
               neither of the above tools remembers anything between runs.
               `journal add TICKER TIER PRICE [notes...]` appends one row.
               `journal show` prints the last 20 rows.

Usage:
  python3 trader_dashboard.py evening
  python3 trader_dashboard.py morning [HH:MM]
  python3 trader_dashboard.py night
  python3 trader_dashboard.py journal add GLAND pulled_back 2932.50 entered half size
  python3 trader_dashboard.py journal show
"""
import sys
from datetime import datetime

import pandas as pd

from backtest import load, current_stop_level, STRUCTURAL_LOOKBACK_BC
from vcp import stage2_trend_template, base_pivot
from signals import base_filters_pass
from daily_scan import _initial_stop, _fo_tickers
from tomorrow_candidates import build_candidates, TOP_N as EVENING_TOP_N
from live_checkpoint import classify_candidates, VELOCITY_LOOKBACK_MIN, fire_tier, vol_tier
from monitor_positions import monitor as monitor_positions
import breadth
import fetch_stock_options
import option_backtest

JOURNAL_FILE = "trade_journal.csv"
OPEN_POSITIONS_FILE = "open_positions.csv"


def _held_tickers():
    try:
        df = pd.read_csv(OPEN_POSITIONS_FILE)
    except FileNotFoundError:
        return set()
    return set(df.ticker) if "ticker" in df.columns else set()


def run_evening(tickers, fo_tickers):
    pool = build_candidates(tickers, fo_tickers)
    print(f"primed universe: n={len(pool)}\n")
    if pool.empty:
        return
    top = pool.sort_values("score", ascending=False).head(EVENING_TOP_N)
    held = _held_tickers()

    print(f"TOP {EVENING_TOP_N} TOMORROW CANDIDATES (quality + feasibility + stop):")
    for _, r in top.iterrows():
        df = load(r.ticker).reset_index()
        i = len(df) - 1
        row = df.iloc[i]
        if r.on_vcp_path:
            bp = base_pivot(df.iloc[:i + 1].reset_index(drop=True), i)
            pattern, structural_low = "coiled_spring", (bp[1] if bp else None)
        else:
            # (2026-09-15) breakout_cont's own structural low, same 20-day-lookback
            # convention as detect_entry() in backtest.py -- current_stop_level() now
            # needs a real value here too (used to be harmless when None since BC's
            # pre-engagement stop didn't touch structural_low at all).
            pattern = "breakout_cont"
            lo = max(0, i - STRUCTURAL_LOOKBACK_BC)
            structural_low = df.iloc[lo:i].Low.min() if i > lo else row.Close * 0.9
        stop = _initial_stop(pattern, structural_low, row) if structural_low is not None else None
        fo_tag = "[F&O]" if r.is_fo else "[NO OPTIONS]"
        held_tag = "  [ALREADY HOLDING]" if r.ticker in held else ""
        to_trigger_pct = (r.trigger_low / r.close - 1) * 100
        stop_str = f"{stop:9.2f}" if stop is not None else "     n/a"
        print(f"  {r.ticker:12s} {fo_tag:13s} close={r.close:9.2f}  "
              f"TRIGGER=[{r.trigger_low:.2f},{r.trigger_high:.2f}] ({to_trigger_pct:+.2f}% away)  STOP={stop_str}  "
              f"score={r.score:.3f} (quality={r.quality_score:.3f}){held_tag}")


def _print_tier(label, df, note, price_col, price_label, held):
    print()
    print(f"=== {label} ({len(df)}) ===")
    if note:
        print(f"    {note}")
    if df.empty:
        print("  (none)")
        return
    has_velocity = "velocity_pct" in df.columns
    has_fire_rate = "fire_rate_pct" in df.columns
    has_dist = "dist_to_trigger_pct" in df.columns
    for _, r in df.iterrows():
        q = f"quality={r.quality_score:.2f}" if pd.notna(r.quality_score) else "quality=n/a"
        sec = f"{r.sector} (sector RS {r.sector_rs:.0f})" if r.sector and pd.notna(r.sector_rs) else (r.sector or "n/a")
        dist = f"  dist={r.dist_to_trigger_pct:+.2f}%" if has_dist and pd.notna(r.dist_to_trigger_pct) else ""
        vel = ""
        if has_velocity:
            vel = f"  vel={r.velocity_pct:+.2f}%/{VELOCITY_LOOKBACK_MIN}min" if pd.notna(r.velocity_pct) else "  vel=n/a"
        fire = f"  [{fire_tier(r.fire_rate_pct)}] ~{r.fire_rate_pct:.0f}%" if has_fire_rate and pd.notna(r.fire_rate_pct) else ""
        held_tag = "  [ALREADY HOLDING]" if r.ticker in held else ""
        # distance from the RAW pivot (high10_effective, the 0% base level) -- per
        # user correction (2026-09-07): the 0.3-0.6% band is the expected/standard
        # entry, NOT a discount. A genuine better price means pulling back below the
        # band toward the raw pivot itself, not just staying inside the band.
        clr = (f"  clr_vs_pivot={r.clearance_vs_raw_pivot_pct:+.2f}%"
               if "clearance_vs_raw_pivot_pct" in r and pd.notna(r.clearance_vs_raw_pivot_pct) else "")
        # informational only, not a filter -- see live_checkpoint.py's extension_days comment
        ext = f"  ext={r.extension_days}d" if "extension_days" in r and r.extension_days >= 2 else ""
        # live volume checks (2026-09-07) -- see live_checkpoint.py's comment for the
        # NIACL case that prompted these. vol_vs_breakout only exists for extension_days>=1.
        vol = ""
        if "vol_vs_breakout_pct" in r and pd.notna(r.vol_vs_breakout_pct):
            vol = f"  vol=[{vol_tier(r.vol_vs_breakout_pct)}]vs-breakout ({r.vol_vs_breakout_pct:.0f}%)"
        elif "vol_vs_normal_pct" in r and pd.notna(r.vol_vs_normal_pct):
            vol = f"  vol=[{vol_tier(r.vol_vs_normal_pct)}] ({r.vol_vs_normal_pct:.0f}%)"
        ticker_label = f"{r.ticker}(F/O)" if r.ticker in _fo_tickers() else r.ticker
        # the raw pivot itself (2026-09-07, user correction): the level that had to be
        # broken to become eligible, BEFORE the 0.3-0.6% buffer -- always has a value,
        # unlike the old pp/r1/r2 resistance_target() this replaced (which goes blank
        # once price runs past all three classic pivot levels).
        pivot = f"  pivot={r.high10_effective:.2f}" if "high10_effective" in r and pd.notna(r.high10_effective) else ""
        # (2026-09-15) this dashboard's own _print_tier had drifted from live_checkpoint.py's
        # richer one -- freshness_score is this project's single most validated signal
        # across every population/exit-regime/metric tested (see FINDINGS.md), and it was
        # silently missing here even though classify_candidates() already computes it.
        # Added these four fields to match live_checkpoint.py's own display exactly,
        # rather than re-deriving the formatting independently.
        fscore = r.get("freshness_score")
        fresh = f"  freshness={fscore*100:.0f}%{' [FRESH]' if r.get('fresh_setup') else ''}" if fscore is not None and pd.notna(fscore) else ""
        cdays = r.get("consolidation_days")
        consol = f"  consol={cdays:.0f}d" if cdays is not None and pd.notna(cdays) else ""
        batr = r.get("body_atr")
        body = f"  body/atr={batr:.2f}" if batr is not None and pd.notna(batr) else ""
        accept = r.get("acceptance_state")
        acc = f"  accept={accept}" if accept else ""
        # (2026-09-16) trend-strength context, same reasoning/source as the freshness
        # fix above -- being on the primed list only proves clearing AT LEAST ONE of
        # VCP/BC's gates, not both, and a bare pass hides the margin. See
        # vcp.stage2_trend_breakdown()'s own docstring.
        gates = []
        if r.get("vcp_qualified"):
            gates.append("VCP")
        if r.get("bc_qualified"):
            gates.append("BC")
        gate = f"  gate=[{'+'.join(gates)}]" if gates else "  gate=[none]"
        stack = r.get("sma_stack_ok")
        smastack = f"  sma_stack={'OK' if stack else 'no'}" if stack is not None else ""
        rsr = r.get("rs_rating")
        rsrating = f"  rs={rsr:.0f}" if rsr is not None and pd.notna(rsr) else ""
        p52 = r.get("pct_to_52w_high")
        pct52 = f"  52wk={p52:.0f}%" if p52 is not None and pd.notna(p52) else ""
        print(f"  {ticker_label:18s} band=[{r.trigger_low:.2f},{r.trigger_high:.2f}]  "
              f"{price_label}={r[price_col]:9.2f}{clr}{pivot}{vol}  {q}  {sec}{dist}{vel}{fire}{fresh}{consol}{body}{acc}{ext}{held_tag}{gate}{smastack}{rsrating}{pct52}")


def run_morning(tickers, cutoff):
    print(f"Checking as of {'now' if cutoff is None else cutoff} IST...")
    pulled_back, kept_going_near, watching, missed = classify_candidates(tickers, cutoff_ist=cutoff)
    held = _held_tickers()

    try:
        latest_date = breadth._breadth_frame().index.max()
        pct = breadth.breadth_pct(latest_date)
        if pd.notna(pct):
            print(f"market breadth today: {pct:.0f}% of NIFTY 500 above their own 200-SMA "
                  f"-- how much weight to put on today's whole list, not a per-candidate filter")
    except FileNotFoundError:
        pass

    print()
    print("NOTE: for tiers 1/2/missed, 'band' is reference only (where it fired earlier today) --")
    print("      the real order price is the 'price' column, not bounded by the band.")
    if held:
        print(f"      Already holding: {', '.join(sorted(held))} -- flagged inline, not dropped.")

    _print_tier("TIER 1: PULLED BACK (best price, settled, no timing race)", pulled_back,
                "sorted by closeness to the raw pivot, either side -- closest = best price",
                "current_price", "price", held)
    _print_tier("TIER 2: KEPT GOING, STILL NEAR TRIGGER (settled, no timing race)", kept_going_near,
                "sorted by closeness to the raw pivot, either side", "current_price", "price", held)
    _print_tier(f"TIER 3: WATCHING, not yet fired (top 10 of {len(watching)})", watching.head(10),
                "ranked by distance blended 80/20 with closing-speed vs 10 min ago, "
                "volume breaks near-ties",
                "close", "close", held)
    _print_tier("MISSED (fired, ran well past the band -- not actionable)", missed,
                "if it settles back into tier 1/2 on a later run, it'll reappear there",
                "current_price", "price", held)


def _log_oi_buildup_for_new_entries(positions):
    """EOD Audit Telemetry only (2026-09-17, see FINDINGS.md's "RQ-48 close-out") --
    scoped to TODAY's real new entries only (never the whole F&O universe, and never
    re-touches older positions -- this is a one-shot record, not a recurring check).
    Lazily fetches just today's F&O bhavcopy (idempotent, ~5.4MB, skipped if already
    cached) rather than a standing nightly job, since this is the first point in the
    day the data even exists (NSE publishes it post-close). Never gates or ranks
    anything -- purely appended to trade_journal.csv for later review, same as any
    other journal entry."""
    today = pd.Timestamp.now().normalize()
    todays_entries = positions[positions.entry_date == today]
    if todays_entries.empty:
        return

    try:
        journal = pd.read_csv(JOURNAL_FILE)
    except FileNotFoundError:
        journal = pd.DataFrame(columns=["date", "ticker", "tier", "price", "notes"])
    already_logged = set(journal[journal.tier == "oi_buildup"].ticker) if not journal.empty else set()

    fo_tickers = _fo_tickers()
    fetched = False
    for pos in todays_entries.itertuples():
        if pos.ticker in already_logged:
            continue
        if pos.ticker not in fo_tickers:
            journal_add([pos.ticker, "oi_buildup", str(pos.entry_price), "N/A (not F&O)"])
            continue
        if not fetched:
            fetch_stock_options.fetch_day(today)
            fetched = True
        buildup = option_backtest.oi_buildup_bullish(pos.ticker, today)
        label = "N/A (no futures data)" if buildup is None else ("present" if buildup else "absent")
        journal_add([pos.ticker, "oi_buildup", str(pos.entry_price), label])


def run_night():
    try:
        positions = pd.read_csv(OPEN_POSITIONS_FILE, parse_dates=["entry_date"])
    except FileNotFoundError:
        print(f"{OPEN_POSITIONS_FILE} not found -- create it with columns: ticker,entry_date,entry_price,pattern")
        return
    if positions.empty:
        print("no open positions logged")
        return
    monitor_positions(positions)
    _log_oi_buildup_for_new_entries(positions)


def journal_add(args):
    if len(args) < 3:
        print("usage: journal add TICKER TIER PRICE [notes...]")
        return
    ticker, tier, price = args[0], args[1], args[2]
    notes = " ".join(args[3:])
    row = dict(date=datetime.now().strftime("%Y-%m-%d %H:%M"), ticker=ticker, tier=tier,
               price=price, notes=notes)
    try:
        df = pd.read_csv(JOURNAL_FILE)
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    except FileNotFoundError:
        df = pd.DataFrame([row])
    df.to_csv(JOURNAL_FILE, index=False)
    print(f"logged: {row}")


def journal_show():
    try:
        df = pd.read_csv(JOURNAL_FILE)
    except FileNotFoundError:
        print("no journal entries yet")
        return
    print(df.tail(20).to_string(index=False))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    mode = sys.argv[1]

    if mode == "evening":
        tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
        fo_tickers = set(pd.read_csv("fo_universe.csv", header=None)[0])
        run_evening(tickers, fo_tickers)
    elif mode == "morning":
        cutoff = sys.argv[2] if len(sys.argv) > 2 else None
        tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
        run_morning(tickers, cutoff)
    elif mode == "night":
        run_night()
    elif mode == "journal":
        sub = sys.argv[2] if len(sys.argv) > 2 else None
        if sub == "add":
            journal_add(sys.argv[3:])
        elif sub == "show":
            journal_show()
        else:
            print("usage: journal add TICKER TIER PRICE [notes...] | journal show")
    else:
        print(__doc__)
