"""RQ-QS-06E -- Post-Peak Deterioration Anatomy (2026-09-29, critic-specified).

Question changes from "can we predict the turn" (06C/06D, both closed negative --
see swing_qs/CLAUDE.md's standing closed result) to: "can we RECOGNIZE the turn
once it has actually happened, and react without systematically damaging
persistent_continuation trades?" No exit rule, no giveback threshold chosen as an
intervention here -- this is Observe only, same discipline as every prior 06-series
script.

PRIMARY layer: price deterioration, fully decision-time-safe (no hindsight on
"which day was the peak" -- see DETERIORATION EVENT definition below, which only
ever looks one day backward, exactly like a live system could).

SECONDARY layer, per critic's explicit instruction: volume/ATR are DESCRIPTIVE
ANNOTATIONS around an already-defined deterioration event, NOT new candidate
predictors -- 06D already closed the "does contemporaneous volume/ATR/market state
separate the archetypes" question. Re-testing "volume at the exact deterioration
point" as a predictor would be the same closed hypothesis wearing a new timestamp.

DETERIORATION EVENT (fully causal, real-time-observable): the first day T such
that (a) day T-1 just set a fresh running-MFE high (a real "peak moment"), AND
(b) day T's Close < day T-1's Close. Both conditions use only information through
day T -- no lookahead, no picking "the" eventual best day of the whole trade in
hindsight and pretending it was knowable in real time.

Population: trades whose OWN eventual 15-day running MFE reaches >=0.5R (this
project's standing "meaningful" floor) -- computed on the full walk for population
selection only, never as a live decision input.

Per critic's point 4: classify what happens AFTER the deterioration event into
transient (recovers to a NEW high above the pre-deterioration peak),
persistent_decay (never recovers to that peak, but isn't stopped either), or
terminal (eventually stopped out, S1b -1R) -- evaluated over the rest of the 15-day
window, evaluation-only, not a predictor.

Per critic's point 3, the crucial cross-tab: report the SAME marker's firing rate
and behavior for burst_then_exhaustion AND persistent_continuation separately --
the economic question is "how much good continuation would reacting to this marker
destroy," not merely "does it precede burst exhaustion."
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq_qs_06b", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rq_qs_06b_favorable_state_trajectory.py"))
rq_qs_06b = module_from_spec(_spec)
_spec.loader.exec_module(rq_qs_06b)
walk_full = rq_qs_06b.walk_full

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
MEANINGFUL_FLOOR = 0.5
PRIMARY = ["burst_then_exhaustion", "persistent_continuation"]


def find_deterioration(days):
    """First causal deterioration event: day T where T-1 set a fresh running-MFE
    high and T's close < T-1's close. Returns None if never occurs."""
    for i in range(1, len(days)):
        prev, cur = days[i - 1], days[i]
        prev_is_fresh_peak = (i == 1) or (prev["mfe_so_far"] > days[i - 2]["mfe_so_far"])
        if prev_is_fresh_peak and cur["close_r"] < prev["close_r"]:
            return i  # index into `days`, 0-based
    return None


def analyze(rows, entry_i, days, row_at):
    eventual_mfe = max(d["mfe_so_far"] for d in days)
    if eventual_mfe < MEANINGFUL_FLOOR:
        return None

    idx = find_deterioration(days)
    rec = dict(eventual_mfe_15d=eventual_mfe, deterioration_found=idx is not None)
    if idx is None:
        return rec

    prev, cur = days[idx - 1], days[idx]
    peak_r_before = prev["mfe_so_far"]
    peak_close_r = prev["close_r"]
    # was the pre-deterioration peak day ALSO the highest CLOSE so far (acceptance), or only an intraday high?
    prior_closes = [d["close_r"] for d in days[:idx - 1]]
    peak_was_closing_high = bool(not prior_closes or peak_close_r >= max(prior_closes))
    drawdown_r = peak_r_before - cur["close_r"]

    # consecutive lower closes starting at the deterioration day
    run = 1
    for k in range(idx + 1, len(days)):
        if days[k]["close_r"] < days[k - 1]["close_r"]:
            run += 1
        else:
            break

    after = days[idx:]  # from the deterioration day onward
    recovered_new_high = any(d["mfe_so_far"] > peak_r_before for d in after)
    ever_stopped = any(d["low_r"] <= -1.0 for d in after)
    if recovered_new_high:
        fate = "transient"
    elif ever_stopped:
        fate = "terminal"
    else:
        fate = "persistent_decay"

    d1 = days[idx] if idx < len(days) else None  # deterioration day itself, for context annotation
    kabs = entry_i + cur["day"]
    row = row_at(kabs)
    vol_ratio = (row.Volume / row.vol_avg10_prior) if pd.notna(row.vol_avg10_prior) and row.vol_avg10_prior else None
    day_range_atr = ((row.High - row.Low) / row.atr14) if pd.notna(row.atr14) and row.atr14 else None
    vol_expanded_vs_prior_day = None
    kprev = entry_i + prev["day"]
    prow = row_at(kprev)
    if pd.notna(row.Volume) and pd.notna(prow.Volume) and prow.Volume:
        vol_expanded_vs_prior_day = bool(row.Volume > prow.Volume)

    rec.update(dict(
        deterioration_day=cur["day"], peak_day=prev["day"], peak_r_before=peak_r_before,
        peak_was_closing_high=peak_was_closing_high, drawdown_r_at_deterioration=drawdown_r,
        consecutive_lower_closes=run, fate=fate,
        volume_ratio_at_deterioration=vol_ratio, day_range_over_atr_at_deterioration=day_range_atr,
        volume_expanded_at_deterioration=vol_expanded_vs_prior_day,
        eventual_max_mfe_after_deterioration=max(d["mfe_so_far"] for d in after),
        eventual_close_r_15d=days[-1]["close_r"],
    ))
    return rec


if __name__ == "__main__":
    labels = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06b_state_trajectory.csv")[
        ["ticker", "entry_date", "entry_definition", "archetype", "eventual_exit_r", "eventual_max_r_15d"]]
    env = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06_envelope.csv")
    src = env.merge(labels, on=["ticker", "entry_date", "entry_definition"], how="inner")
    assert len(src) == len(env), f"join not 1:1: {len(src)} vs {len(env)}"
    src["entry_date"] = pd.to_datetime(src.entry_date)
    print(f"{len(src)} trades with archetype labels")

    cache = {}
    recs = []
    for n, r in enumerate(src.itertuples()):
        if n % 5000 == 0:
            print(f"{n}/{len(src)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        m = rows.index[rows.Date == r.entry_date]
        if len(m) == 0:
            continue
        entry_i = m[0]
        days, exit_reason, exit_day = walk_full(rows, entry_i, r.entry_price, r.initial_risk_pct)
        if not days:
            continue
        rec = analyze(rows, entry_i, days, lambda k, rows=rows: rows.iloc[k])
        if rec is None:
            continue
        rec.update(ticker=r.ticker, entry_date=r.entry_date.date(), archetype=r.archetype)
        recs.append(rec)

    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq_qs_06e_deterioration.csv", index=False)
    print(f"\n{len(df)} trades with eventual MFE >= {MEANINGFUL_FLOOR}R\n")

    print(f"Deterioration event found: {df.deterioration_found.sum()} ({df.deterioration_found.mean()*100:.1f}%)")
    print(f"No deterioration event within 15 days (kept making higher closes or was stopped before any down-close): "
          f"{(~df.deterioration_found).sum()} ({(~df.deterioration_found).mean()*100:.1f}%)")

    det = df[df.deterioration_found].copy()

    def pstack(s, fmt="{:.2f}"):
        s = pd.Series(s).dropna()
        if len(s) == 0:
            return "n=0"
        return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s)})"

    print(f"\n=== Deterioration event characteristics (n={len(det)}) ===")
    print(f"  peak_day (day # of the pre-deterioration peak):  {pstack(det.peak_day, '{:.0f}')}")
    print(f"  deterioration_day:                                 {pstack(det.deterioration_day, '{:.0f}')}")
    print(f"  peak_was_closing_high (acceptance, not just wick): {det.peak_was_closing_high.mean()*100:.1f}%")
    print(f"  drawdown_r_at_deterioration:                       {pstack(det.drawdown_r_at_deterioration, '{:.2f}')}")
    print(f"  consecutive_lower_closes:                          {pstack(det.consecutive_lower_closes, '{:.1f}')}")

    print(f"\n=== Fate after deterioration (n={len(det)}) ===")
    print(det.fate.value_counts())
    print(det.fate.value_counts(normalize=True).mul(100).round(1))

    print(f"\n=== Contextual annotation at the deterioration moment (descriptive only) ===")
    print(f"  volume_ratio_at_deterioration:        {pstack(det.volume_ratio_at_deterioration, '{:.2f}')}")
    print(f"  day_range_over_atr_at_deterioration:   {pstack(det.day_range_over_atr_at_deterioration, '{:.2f}')}")
    print(f"  volume expanded vs prior day:          {det.volume_expanded_at_deterioration.mean()*100:.1f}%")

    print(f"\n{'='*100}\nTHE CRITICAL CROSS-TAB: marker behavior in burst_then_exhaustion vs persistent_continuation\n{'='*100}")
    prim = det[det.archetype.isin(PRIMARY)]
    all_prim = df[df.archetype.isin(PRIMARY)]
    for arch in PRIMARY:
        total = (all_prim.archetype == arch).sum()
        fired = (prim.archetype == arch).sum()
        sub = prim[prim.archetype == arch]
        print(f"\n--- {arch} (n total with eventual MFE>=0.5R = {total}) ---")
        print(f"  Marker fires (a deterioration event occurs at all): {fired} ({fired/total*100:.1f}% of this archetype)")
        print(f"  fate breakdown: {dict(sub.fate.value_counts())}")
        print(f"  median drawdown_r_at_deterioration: {sub.drawdown_r_at_deterioration.median():.2f}")
        print(f"  median eventual_max_mfe_after_deterioration: {sub.eventual_max_mfe_after_deterioration.median():.2f}")
        print(f"  median eventual_close_r_15d: {sub.eventual_close_r_15d.median():.2f}")

    print(f"\n--- The economic question: if we reacted to the FIRST deterioration event, what would we destroy? ---")
    persist_sub = prim[prim.archetype == "persistent_continuation"]
    persist_transient = persist_sub[persist_sub.fate == "transient"]
    print(f"  Of persistent_continuation trades where a deterioration event fired: {len(persist_sub)}")
    print(f"  Of those, fate='transient' (recovered to a NEW high after the marker fired): "
          f"{len(persist_transient)} ({len(persist_transient)/len(persist_sub)*100:.1f}% of fired persistent trades)")
    print(f"  Median MFE these transient-persistent trades achieved AFTER the marker fired: "
          f"{persist_transient.eventual_max_mfe_after_deterioration.median():.2f}R")
    print(f"  -> This is the opportunity a 'react on first deterioration' rule would destroy for this group.")

    burst_sub = prim[prim.archetype == "burst_then_exhaustion"]
    burst_terminal_or_decay = burst_sub[burst_sub.fate != "transient"]
    print(f"\n  Of burst_then_exhaustion trades where a deterioration event fired: {len(burst_sub)}")
    print(f"  Of those, fate != 'transient' (genuinely deteriorated, did NOT recover to a new high): "
          f"{len(burst_terminal_or_decay)} ({len(burst_terminal_or_decay)/len(burst_sub)*100:.1f}% of fired burst trades)")
    print(f"  -> This is the group a 'react on first deterioration' rule would correctly protect.")
