"""QS (Quick Swing) Live Dashboard — critic-specified deliverable, 2026-09-28.

Frozen v0.1 gate only (see swing_qs/PRODUCT_DEFINITION.md's freeze note — the single
conditional, NOT base_filters_pass()): a fresh trigger is a QS candidate unless
base_duration==0 AND gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT. No new filters here.

Three modes:
  morning  — live scan for fresh QS triggers today (reuses daily_scan.py's
             fetch_live_bars()/load_with_extra_row() — same intraday-touch mechanism
             BC uses, not reinvented). Candidates that PASS the gate are printed;
             candidates that FAIL it are auto-logged to qs_shadow.csv (deduped) for
             the shadow dashboard below — nothing needs adding by hand for shadow.
  track    — for open QS positions (qs_positions.csv), reports days held, current R,
             max R reached, proof status (0.25R/1R/2R + day reached), BLAST/DRIFT/
             FAILURE label (or "developing" if still inside the labeling window),
             reclaim state, and today's body%/close-location (same-day telemetry,
             per Rule #21 — descriptive, not a live-IOC filter or exit trigger).
  shadow   — Deliverable 2 (critic-specified): classifies every REJECTED trigger's
             eventual outcome, answering "is the gate too strict or correctly
             rejecting" per ticker. Reads qs_shadow.csv (auto-populated by `morning`),
             reuses the exact same trajectory walk as `track`.

Position tracking is file-based (qs_positions.csv: ticker,entry_date,entry_price,
entry_definition,initial_stop_price — one row per open QS trade you actually took,
added by hand same as open_positions.csv). This script never invents which trades
were taken.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from backtest import load, load_with_extra_row
from daily_scan import fetch_live_bars, LIVE_CUTOFF_DEFAULT
from pivots import daily_pivots
import primed_engine as pe

GAP_BAD_THRESHOLD_PCT = 2.343  # frozen v0.1 value — swing_qs/QS_V01_ENTRY_GATE.md
CONSOLIDATION_TOLERANCE_PCT = 3.0  # reused exactly from live_checkpoint.py's _consolidation_days
LOOKBACKS = (10, 20, 40)
POSITIONS_FILE = "qs_positions.csv"
SHADOW_FILE = "qs_shadow.csv"

# BLAST/DRIFT/FAILURE label thresholds — swing_qs/FINDINGS.md's Feature Battle section
STOP_R = -1.0
PROOF_R = 0.25
BLAST_R = 2.0
BLAST_BY_DAY = 5
FAILURE_BY_DAY = 10
MAX_TRACK_DAYS = 15  # matches the research population's own MAX_DAYS — a QS position
                     # has no business still being "tracked" past this; a stale
                     # qs_positions.csv row (forgotten to close out) would otherwise
                     # walk forward through the ticker's ENTIRE remaining cached
                     # history with no natural stopping point (caught in testing:
                     # a real DRIFT example walked 565 trading days before this cap)

# Shadow-only classification constants (critic-specified table, 2026-09-28) — both
# provisional/illustrative thresholds, disclosed here rather than picked silently:
STOPPED_IMMEDIATELY_BY_DAY = 2  # tighter than the standard 3-day proof-check window
LATE_BLAST_AFTER_DAY = 8       # >=2R after this day, having missed the day-5 BLAST
                                # window — critic's "probably a BC candidate, not QS"


def _base_duration(rows, high_prior_series, i):
    """Consecutive prior days within CONSOLIDATION_TOLERANCE_PCT of that day's own
    high_prior — exact formula reused from rq_qs_literature_features.py (already
    validated all session, not reimplemented differently here)."""
    cnt = 0
    for k in range(i - 1, max(i - 60, 0), -1):
        hp = high_prior_series.iloc[k]
        if pd.isna(hp) or not hp:
            break
        gap_pct = (hp - rows.iloc[k].Close) / hp * 100
        if 0 <= gap_pct <= CONSOLIDATION_TOLERANCE_PCT:
            cnt += 1
        else:
            break
    return cnt


def morning(tickers, cutoff_ist=LIVE_CUTOFF_DEFAULT, shadow_file=SHADOW_FILE):
    """Live QS candidates for today, frozen v0.1 gate only. Returns a list of dicts,
    one per (ticker, entry_definition) that triggers AND passes the gate today —
    a ticker can appear once per lookback definition (10D/20D/40D are independent
    candidate definitions, per RQ-QS's Alternative-Definition Integrity Rule).
    Triggers that FAIL the gate are appended to shadow_file (deduped against what's
    already there) for the `shadow` dashboard to classify later."""
    live_bars = fetch_live_bars(tickers, cutoff_ist)
    candidates = []
    rejected = []
    for ticker in tickers:
        try:
            if ticker in live_bars:
                df = load_with_extra_row(ticker, live_bars[ticker], daily_pivots, cutoff_ist=cutoff_ist)
            else:
                df = load(ticker, daily_pivots)
        except FileNotFoundError:
            continue
        rows = df.reset_index()
        if len(rows) < 61:
            continue
        i = len(rows) - 1
        row = rows.iloc[i]
        if row.corp_action_day:
            continue
        row_t1 = rows.iloc[i - 1]

        for lookback in LOOKBACKS:
            high_prior_series = rows.High.shift(1).rolling(lookback).max()
            high_prior = high_prior_series.iloc[i]
            if pd.isna(high_prior):
                continue
            entry_price = high_prior * pe.TRIGGER_CLEARANCE
            if row.High < entry_price:
                continue  # not triggered today, this lookback

            base_duration = _base_duration(rows, high_prior_series, i)
            gap_to_trigger_pct = (entry_price / row_t1.Close - 1) * 100 if row_t1.Close else None
            initial_stop_price = row_t1.Low  # S1b — prior trading day's Low
            initial_risk_pct = (entry_price - initial_stop_price) / entry_price * 100
            adr_pct = (row.atr14 / row.Close * 100) if pd.notna(row.get("atr14")) and row.Close else None
            rec = dict(
                ticker=ticker, entry_date=str(row.Date.date()), entry_definition=lookback,
                entry_price=round(entry_price, 2), initial_stop_price=round(initial_stop_price, 2),
                initial_risk_pct=round(initial_risk_pct, 2),
                adr_pct=round(adr_pct, 2) if adr_pct else None, base_duration=base_duration,
                gap_to_trigger_pct=round(gap_to_trigger_pct, 2) if gap_to_trigger_pct is not None else None,
                live=(ticker in live_bars),
            )
            gate_reject = base_duration == 0 and gap_to_trigger_pct is not None and gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT
            if gate_reject:
                rejected.append(rec)
            else:
                candidates.append(rec)

    if rejected:
        _append_shadow(rejected, shadow_file)
    return candidates


def _append_shadow(rejected, shadow_file):
    cols = ["ticker", "entry_date", "entry_definition", "entry_price", "initial_stop_price",
            "initial_risk_pct", "adr_pct", "base_duration", "gap_to_trigger_pct"]
    new_rows = pd.DataFrame(rejected)[cols]
    path = Path(shadow_file)
    if path.exists():
        existing = pd.read_csv(path)
        key = ["ticker", "entry_date", "entry_definition"]
        merged = pd.concat([existing, new_rows]).drop_duplicates(subset=key, keep="first")
    else:
        merged = new_rows
    merged.to_csv(path, index=False)


def _label(max_r_by_day, days_held, stopped_out_day):
    """BLAST/DRIFT/FAILURE, matching swing_qs/FINDINGS.md's Feature Battle definitions
    exactly (S1b risk unit). Returns 'developing' if not enough days have passed yet
    to rule out a still-possible BLAST or reach the FAILURE_BY_DAY horizon."""
    blast_day = next((d for d, r in max_r_by_day.items() if d <= BLAST_BY_DAY and r >= BLAST_R), None)
    if blast_day is not None:
        return "BLAST"
    proof_day = next((d for d, r in max_r_by_day.items() if r >= PROOF_R), None)
    if stopped_out_day is not None and (proof_day is None or stopped_out_day <= proof_day):
        return "FAILURE"
    if proof_day is None and days_held >= FAILURE_BY_DAY:
        return "FAILURE"
    if days_held < BLAST_BY_DAY or proof_day is None and days_held < FAILURE_BY_DAY:
        return "developing"
    return "DRIFT"


def _walk_trajectory(rows, i, entry_price, initial_risk_pct):
    """Shared by `track` and `shadow` — identical walk-forward logic, one definition
    so the two dashboards can never silently drift apart. Returns (max_r_by_day,
    stopped_out_day, latest_row, days_held)."""
    max_r_by_day, stopped_out_day = {}, None
    latest_row = None
    days_held = 0
    for k in range(i + 1, len(rows)):
        if days_held >= MAX_TRACK_DAYS:
            break
        row_k = rows.iloc[k]
        if row_k.corp_action_day:
            break
        days_held += 1
        latest_row = row_k
        high_r = (row_k.High / entry_price - 1) * 100 / initial_risk_pct
        low_r = (row_k.Low / entry_price - 1) * 100 / initial_risk_pct
        max_r_by_day[days_held] = high_r
        if low_r <= STOP_R and stopped_out_day is None:
            stopped_out_day = days_held
            break  # position/candidate is done, stop tracking forward
    return max_r_by_day, stopped_out_day, latest_row, days_held


def track(positions_file=POSITIONS_FILE):
    """For each open QS position, report trajectory so far. Prints a table; returns
    the list of dicts for programmatic use."""
    path = Path(positions_file)
    if not path.exists():
        print(f"No {positions_file} found — nothing to track. One row per open QS "
              f"trade you actually took: ticker,entry_date,entry_price,entry_definition,initial_stop_price")
        return []
    positions = pd.read_csv(path, parse_dates=["entry_date"])
    results = []
    for pos in positions.itertuples():
        try:
            rows = load(pos.ticker, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        m = rows.index[rows.Date == pos.entry_date]
        if len(m) == 0:
            continue
        i = m[0]
        entry_price = pos.entry_price
        initial_risk_pct = (entry_price - pos.initial_stop_price) / entry_price * 100

        max_r_by_day, stopped_out_day, latest_row, days_held = _walk_trajectory(
            rows, i, entry_price, initial_risk_pct)

        if latest_row is None:
            continue
        close_r = (latest_row.Close / entry_price - 1) * 100 / initial_risk_pct
        max_r_so_far = max(max_r_by_day.values()) if max_r_by_day else None
        proof_day = next((d for d, r in max_r_by_day.items() if r >= PROOF_R), None)
        reclaim = (latest_row.Close > entry_price) if days_held >= 1 else None
        body_pct = ((latest_row.Close - latest_row.Open) / latest_row.Open * 100) if latest_row.Open else None
        rng = latest_row.High - latest_row.Low
        close_location = ((latest_row.Close - latest_row.Low) / rng) if rng else None

        results.append(dict(
            ticker=pos.ticker, entry_definition=pos.entry_definition, days_held=days_held,
            stopped_out=stopped_out_day is not None, stopped_out_day=stopped_out_day,
            stale=(stopped_out_day is None and days_held >= MAX_TRACK_DAYS),
            close_r=round(close_r, 2), max_r_so_far=round(max_r_so_far, 2) if max_r_so_far else None,
            proof_day=proof_day, reclaim=reclaim,
            label=_label(max_r_by_day, days_held, stopped_out_day),
            body_pct_today=round(body_pct, 2) if body_pct is not None else None,
            close_location_today=round(close_location, 2) if close_location is not None else None,
        ))
    return results


def _shadow_label(max_r_by_day, days_held, stopped_out_day):
    """Critic's exact 2026-09-28 interpretation table, made precise. Reuses the same
    BLAST/FAILURE/DRIFT boundaries as _label() (so shadow and live outcomes stay
    comparable) plus two shadow-specific splits: an early-stop carve-out and a
    late-blast carve-out."""
    blast_day = next((d for d, r in max_r_by_day.items() if d <= BLAST_BY_DAY and r >= BLAST_R), None)
    if blast_day is not None:
        return "BLAST_MISSED", "gate too strict — this would have blasted"
    late_blast_day = next((d for d, r in max_r_by_day.items() if d > LATE_BLAST_AFTER_DAY and r >= BLAST_R), None)
    if late_blast_day is not None:
        return "LATE_BLAST", "huge move, but late — probably a BC candidate, not QS"
    proof_day = next((d for d, r in max_r_by_day.items() if r >= PROOF_R), None)
    if stopped_out_day is not None and stopped_out_day <= STOPPED_IMMEDIATELY_BY_DAY and proof_day is None:
        return "STOPPED_IMMEDIATELY", "correct rejection"
    if stopped_out_day is not None and (proof_day is None or stopped_out_day <= proof_day):
        return "FAILURE", "correct rejection"
    if proof_day is None and days_held >= FAILURE_BY_DAY:
        return "FAILURE", "correct rejection"
    if days_held < FAILURE_BY_DAY:
        return "developing", "still inside the classification window"
    return "DRIFT", "correct rejection for QS (too slow for this product)"


def shadow(shadow_file=SHADOW_FILE):
    """Deliverable 2 — classifies every gate-REJECTED trigger's eventual outcome.
    Prints a summary count first (per house convention), then per-ticker detail."""
    path = Path(shadow_file)
    if not path.exists():
        print(f"No {shadow_file} found yet — it's auto-populated by `morning` whenever "
              f"a trigger fails the gate. Run `morning` first.")
        return []
    rejected = pd.read_csv(path, parse_dates=["entry_date"])
    results = []
    for rec in rejected.itertuples():
        try:
            rows = load(rec.ticker, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        m = rows.index[rows.Date == rec.entry_date]
        if len(m) == 0:
            continue
        i = m[0]
        entry_price = rec.entry_price
        initial_risk_pct = rec.initial_risk_pct

        max_r_by_day, stopped_out_day, latest_row, days_held = _walk_trajectory(
            rows, i, entry_price, initial_risk_pct)
        if latest_row is None:
            continue
        max_r_so_far = max(max_r_by_day.values()) if max_r_by_day else None
        label, interpretation = _shadow_label(max_r_by_day, days_held, stopped_out_day)
        results.append(dict(
            ticker=rec.ticker, entry_definition=rec.entry_definition,
            entry_date=str(rec.entry_date.date()), days_held=days_held,
            max_r_so_far=round(max_r_so_far, 2) if max_r_so_far else None,
            label=label, interpretation=interpretation,
        ))
    return results


def _print_morning(candidates):
    if not candidates:
        print("No QS candidates today.")
        return
    print(f"{len(candidates)} QS candidate(s) today (frozen v0.1 gate):\n")
    for c in sorted(candidates, key=lambda c: c["gap_to_trigger_pct"] or 0):
        live_tag = "" if c["live"] else "  [stale — no live bar]"
        print(f"  {c['ticker']:<14} {c['entry_definition']}D  entry=₹{c['entry_price']}  "
              f"stop=₹{c['initial_stop_price']}  risk={c['initial_risk_pct']}%  "
              f"base_dur={c['base_duration']}  gap_to_trigger={c['gap_to_trigger_pct']}%{live_tag}")


def _print_shadow(results):
    if not results:
        print("No shadow candidates classified yet.")
        return
    resolved = [r for r in results if r["label"] != "developing"]
    developing = [r for r in results if r["label"] == "developing"]
    print(f"{len(results)} rejected trigger(s) in the shadow log — {len(resolved)} resolved, "
          f"{len(developing)} still developing.\n")
    if resolved:
        print("Summary (resolved only):")
        counts = pd.Series([r["label"] for r in resolved]).value_counts()
        for label, n in counts.items():
            print(f"  {label:<20} {n:>4}  ({n/len(resolved)*100:.1f}%)")
        print()
    print("Detail:")
    for r in sorted(results, key=lambda r: r["label"]):
        print(f"  {r['ticker']:<14} {r['entry_definition']}D  entry={r['entry_date']}  "
              f"day{r['days_held']}  max_r={r['max_r_so_far']}R  "
              f"[{r['label']}] {r['interpretation']}")


def _print_track(results):
    if not results:
        print("No open QS positions found (or none matched cached data).")
        return
    print(f"{len(results)} open QS position(s):\n")
    for r in results:
        if r["stopped_out"]:
            status = f"STOPPED @day{r['stopped_out_day']}"
        elif r["stale"]:
            status = f"day{r['days_held']} — STALE, past tracking window, close it out manually"
        else:
            status = f"day{r['days_held']}"
        proof = f"proved day{r['proof_day']}" if r["proof_day"] else "not yet proven"
        print(f"  {r['ticker']:<14} {r['entry_definition']}D  [{status}]  label={r['label']:<11}  "
              f"close_r={r['close_r']}R  max_r={r['max_r_so_far']}R  {proof}  "
              f"reclaim={r['reclaim']}  body%={r['body_pct_today']}  close_loc={r['close_location_today']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    p_morning = sub.add_parser("morning", help="live scan for fresh QS candidates today")
    p_morning.add_argument("--cutoff", default=LIVE_CUTOFF_DEFAULT)
    sub.add_parser("track", help="trajectory report for open QS positions (qs_positions.csv)")
    sub.add_parser("shadow", help="classify every gate-rejected trigger's eventual outcome")
    args = parser.parse_args()

    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    if args.mode == "morning":
        _print_morning(morning(tickers, args.cutoff))
    elif args.mode == "track":
        _print_track(track())
    elif args.mode == "shadow":
        _print_shadow(shadow())
