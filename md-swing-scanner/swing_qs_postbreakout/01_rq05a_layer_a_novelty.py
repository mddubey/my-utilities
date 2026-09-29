"""RQ-QS-05A, Layer A only -- Breakout Novelty classification (2026-09-29).

Per critic's exact sequencing: "For a candidate expansion day, determine whether it
is: a breakout from an established prior range/base, or a re-acceleration inside an
already-active/range-bound stock. No performance yet." This script does ONLY that --
no decay characterization (Layer B), no returns, no R, no thresholds optimized.

Candidate expansion day (deliberately generous search net, literature-anchored, not
fit to any example -- see FINDINGS.md's Preflight):
  Volume_t >= 3 * median(Volume, trailing 50 trading days, days t-50..t-1)
  AND |Close_t / Close_{t-1} - 1| >= 5%
Both trailing-only -> decision-time-safe by construction.

Novelty measure, 3 pre-declared horizons (63/126/252 trading days ~ 3/6/12 months):
  For candidate day t, count prior EPISODES for the SAME ticker in [t-horizon, t-1].
  count == 0 -> "novel" at that horizon; count >= 1 -> "re-accel".

EPISODE CLUSTERING (added after a pre-registered-anchor catch, see FINDINGS.md): a
single flagpole can print as 2+ consecutive candidate days (confirmed: JUSTDIAL's
2026-07-13 and 2026-07-14 are BOTH individually candidate days, same continuing move
-- counting July 13 as a separate "prior candidate" against July 14 wrongly flagged a
2-day flagpole as its own re-acceleration). Candidate days for the same ticker within
EPISODE_GAP trading days of each other are merged into one episode, anchored at the
episode's FIRST day; novelty counts prior EPISODE starts, not raw candidate days.
EPISODE_GAP=3 is declared from the literature (Bulkowski describes the flagpole itself
as typically 1-3 bars), not tuned after looking at whether it fixes the JUSTDIAL
anchor -- it was chosen once, before rerunning, and is reported as-is either way.

No survivorship games: walks the full nifty500 universe, full cached daily history.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
VOL_MULT = 3.0
MOVE_PCT_MIN = 5.0
HORIZONS = [63, 126, 252]  # trading days ~ 3/6/12 months
BASELINE_WINDOW = 50
EPISODE_GAP = 3  # trading days; merges consecutive candidate days into one flagpole episode


def find_candidates(ticker):
    try:
        rows = load(ticker, daily_pivots).reset_index()
    except FileNotFoundError:
        return None
    if len(rows) < BASELINE_WINDOW + max(HORIZONS) + 5:
        return None
    vol = rows.Volume.values
    close = rows.Close.values
    n = len(rows)
    baseline = pd.Series(vol).rolling(BASELINE_WINDOW).median().shift(1).values  # median of t-50..t-1
    move_pct = np.abs(close / np.roll(close, 1) - 1) * 100
    move_pct[0] = np.nan
    is_candidate = (baseline > 0) & (vol >= VOL_MULT * baseline) & (move_pct >= MOVE_PCT_MIN)
    is_candidate = is_candidate & ~rows.corp_action_day.values  # exclude corp-action-driven jumps
    idx = np.where(is_candidate)[0]
    if len(idx) == 0:
        return []

    # --- cluster consecutive candidate days into episodes, anchored at each episode's first day ---
    episode_start = {}  # candidate index i -> that episode's first index
    cur_start = idx[0]
    episode_start[idx[0]] = cur_start
    for prev, cur in zip(idx[:-1], idx[1:]):
        if cur - prev > EPISODE_GAP:
            cur_start = cur
        episode_start[cur] = cur_start
    episode_starts_sorted = np.array(sorted(set(episode_start.values())))

    out = []
    for i in idx:
        rec = dict(ticker=ticker, i=i, date=str(rows.Date.iloc[i].date()),
                    volume=vol[i], vol_baseline=baseline[i], vol_mult=vol[i] / baseline[i],
                    move_pct=move_pct[i], close=close[i],
                    episode_start_i=int(episode_start[i]),
                    is_episode_start=bool(episode_start[i] == i))
        this_episode_start = episode_start[i]
        for h in HORIZONS:
            lo = this_episode_start - h
            prior_episodes = int(((episode_starts_sorted >= lo) & (episode_starts_sorted < this_episode_start)).sum())
            rec[f"prior_candidates_{h}d"] = prior_episodes
            rec[f"novel_{h}d"] = bool(prior_episodes == 0)
        out.append(rec)
    return out


if __name__ == "__main__":
    # NOT nifty500_universe.csv alone: neither JUSTDIAL (only in extended_universe.csv)
    # nor GOCLCORP (in no tracked universe list at all -- a stray cache file) would be
    # included, and those two are the actual motivating examples for this RQ. Use
    # every ticker we have real cached daily history for instead -- the honest
    # population given what data actually exists (Preflight Q1), not an idealized
    # subset. Confirmed 2026-09-29: 198 of 703 cached tickers are outside
    # nifty500_universe.csv (195 match extended_universe.csv, the rest -- including
    # GOCLCORP -- are in neither tracked list).
    tickers = sorted(f[:-4] for f in os.listdir("data_cache") if f.endswith(".csv") and not f.startswith("_"))
    print(f"Universe: {len(tickers)} tickers (every cached ticker, not just nifty500_universe.csv)")
    recs = []
    for n, t in enumerate(tickers):
        if n % 100 == 0:
            print(f"{n}/{len(tickers)}", flush=True)
        r = find_candidates(t)
        if r:
            recs.extend(r)
    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq05a_layer_a_candidates.csv", index=False)

    ep = df[df.is_episode_start].copy()  # one row per episode -- this is the real unit for aggregate %s,
                                          # raw day-level rows double-count multi-day flagpoles otherwise
    print(f"\n=== RQ-QS-05A Layer A: {len(df)} candidate DAYS, {len(ep)} EPISODES "
          f"(Volume>={VOL_MULT}x trailing-50d median AND |move|>={MOVE_PCT_MIN}%, "
          f"episodes = candidate days within {EPISODE_GAP}d of each other merged) ===\n")
    for h in HORIZONS:
        col = f"novel_{h}d"
        pct = ep[col].mean() * 100
        print(f"horizon {h}d (~{h/21:.0f} months): novel={ep[col].sum()} ({pct:.1f}%)  "
              f"re-accel={(~ep[col]).sum()} ({100-pct:.1f}%)")

    print(f"\nvol_mult distribution (episode-start days): median={ep.vol_mult.median():.1f}x  P90={ep.vol_mult.quantile(.9):.1f}x")
    print(f"move_pct distribution (episode-start days): median={ep.move_pct.median():.1f}%  P90={ep.move_pct.quantile(.9):.1f}%")
    print(f"episode length (days): median={df.groupby(['ticker','episode_start_i']).size().median():.0f}  "
          f"max={df.groupby(['ticker','episode_start_i']).size().max()}")

    print("\n--- Rule #22 pre-registered anchors ---")
    for tk, dt in [("JUSTDIAL", "2026-07-14"), ("GOCLCORP", "2026-09-03")]:
        row = df[(df.ticker == tk) & (df.date == dt)]
        if row.empty:
            print(f"{tk} {dt}: NOT FOUND as a candidate day -- check trigger definition / data")
        else:
            r = row.iloc[0]
            print(f"{tk} {dt}: vol_mult={r.vol_mult:.1f}x move={r.move_pct:.1f}%  "
                  f"novel_63d={r.novel_63d} novel_126d={r.novel_126d} novel_252d={r.novel_252d}  "
                  f"(prior candidates in window: 63d={r.prior_candidates_63d}, "
                  f"126d={r.prior_candidates_126d}, 252d={r.prior_candidates_252d})")

    # secondary check: GOCLCORP's March events should themselves show up as candidates
    goc = df[df.ticker == "GOCLCORP"].sort_values("date")
    print(f"\nGOCLCORP all candidate days ({len(goc)}):")
    print(goc[["date", "vol_mult", "move_pct", "novel_63d", "novel_126d", "novel_252d"]].to_string(index=False))
