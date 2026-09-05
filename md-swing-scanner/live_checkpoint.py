"""Run any time during market hours (built for a 9:15-10:00 IST checkpoint, but works
whenever called) to answer: of today's primed watchlist, which candidates are closest
to actually firing their +1% trigger RIGHT NOW? Validated finding (2026-09-05, see
FINDINGS.md's "reverse-engineering entry timing" section): ranking the still-live pool
by same-day distance-to-trigger at a single checkpoint gets the real mover into the
top-1 pick 64.4% of the time and the top-2 picks 76.3% of the time (n=59 real days) --
dramatically stronger than the night-before candidate score (Recall@5 only 9.6%).
This is NOT a replacement for that night-before list (which still decides the overall
watchlist pool via shortlist_primed) -- it's a same-day re-rank of that same pool,
meant for deciding where to actually commit scarce capital (IOC orders) once you have
a moment to check, not for building the watchlist itself.

Two-pass design, same reasoning as daily_scan.py --live: Pass 1 (shortlist_primed,
cheap, yesterday's cached close only) narrows the 500-ticker universe to the ~70-100
that could plausibly fire today at all. Pass 2 (fetch_live_bars, the only part that
costs anything) fetches real intraday 5-min bars for just that shortlist, up to
whatever time this is run.

Real caveats, not swept under the rug:
- yfinance intraday is itself delayed, not a real broker feed.
- Trigger clearance uses the NEW 0.3-0.6% band (2026-09-05 finding), not the older
  1% production value -- checked directly (same date, re-run at 0.3/0.5/0.6/1.0%
  clearance) that the checkpoint-ranking result is robust across this whole range
  (Recall@1 60.7-68.9%, Recall@2 76.3-83.6%, Recall@5 88.1-96.7%), so this isn't
  sensitive to the exact clearance chosen. A ticker "fires" once its live High clears
  the LOWER edge (0.3%) -- matches the "limit order, ceiling at the upper edge"
  framing: the entry itself would fill somewhere in [0.3%, 0.6%], so 0.3% is the
  earliest honest trigger point, not the latest.
- Volume was tested as a secondary ranking signal (blended 70/30 with distance) and
  made the ranking WORSE, not better (Recall@1 60.7%->44.3%) -- distance to trigger
  alone is deliberately the only signal used here, not an oversight.
- Tickers that have ALREADY crossed their trigger by the time this runs are flagged
  separately, not silently dropped -- act on those first if you haven't already.
"""
import sys

import pandas as pd

from backtest import load
from daily_scan import shortlist_primed, fetch_live_bars

TRIGGER_CLEARANCE_LOW = 0.003   # 0.3% -- earliest honest fire point
TRIGGER_CLEARANCE_HIGH = 0.006  # 0.6% -- limit-order ceiling, never pay more than this
TOP_N = 10


def rank_by_distance_to_trigger(tickers, cutoff_ist=None):
    """Returns (already_fired, still_watching) -- two DataFrames. already_fired lists
    tickers whose live High has already cleared today's trigger (sorted by how much
    clearance, most-clear first). still_watching lists everything else, sorted by
    distance to trigger ascending (closest first) -- this is the validated ranking."""
    pool = shortlist_primed(tickers)
    live = fetch_live_bars(pool, cutoff_ist=cutoff_ist) if cutoff_ist else fetch_live_bars(pool)

    fired, watching = [], []
    for t in pool:
        bar = live.get(t)
        if bar is None:
            continue
        try:
            row = load(t).reset_index().iloc[-1]
        except (FileNotFoundError, IndexError):
            continue
        if pd.isna(row.high10_prior):
            continue
        trigger_low = row.high10_prior * (1 + TRIGGER_CLEARANCE_LOW)
        trigger_high = row.high10_prior * (1 + TRIGGER_CLEARANCE_HIGH)
        if bar["High"] >= trigger_low:
            clearance_pct = (bar["High"] / trigger_low - 1) * 100
            fired.append(dict(ticker=t, trigger_low=trigger_low, trigger_high=trigger_high,
                               high=bar["High"], clearance_pct=clearance_pct))
        else:
            dist_pct = (trigger_low / bar["Close"] - 1) * 100
            watching.append(dict(ticker=t, trigger_low=trigger_low, trigger_high=trigger_high,
                                  close=bar["Close"], dist_to_trigger_pct=dist_pct))

    fired_df = pd.DataFrame(fired).sort_values("clearance_pct", ascending=False) if fired else pd.DataFrame(fired)
    watching_df = pd.DataFrame(watching).sort_values("dist_to_trigger_pct") if watching else pd.DataFrame(watching)
    return fired_df, watching_df


if __name__ == "__main__":
    cutoff = sys.argv[1] if len(sys.argv) > 1 else None
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()

    print(f"Checking as of {'now' if cutoff is None else cutoff} IST...")
    fired_df, watching_df = rank_by_distance_to_trigger(tickers, cutoff_ist=cutoff)

    print()
    print(f"=== ALREADY TRIGGERED ({len(fired_df)}) -- act now if you haven't, IOC ceiling is trigger_high ===")
    if fired_df.empty:
        print("  (none yet)")
    else:
        for _, r in fired_df.iterrows():
            print(f"  {r.ticker:12s} band=[{r.trigger_low:.2f},{r.trigger_high:.2f}]  high={r.high:9.2f}  cleared low-edge by {r.clearance_pct:+.2f}%")

    print()
    print(f"=== CLOSEST TO TRIGGER, not yet fired (top {TOP_N} of {len(watching_df)}) ===")
    print("    (validated across the 0.3-0.6% band: top-1 catches the real mover 60-69% of the time, top-2 76-84%)")
    if watching_df.empty:
        print("  (nothing left to watch)")
    else:
        for _, r in watching_df.head(TOP_N).iterrows():
            print(f"  {r.ticker:12s} band=[{r.trigger_low:.2f},{r.trigger_high:.2f}]  close={r.close:9.2f}  {r.dist_to_trigger_pct:+.2f}% away")
