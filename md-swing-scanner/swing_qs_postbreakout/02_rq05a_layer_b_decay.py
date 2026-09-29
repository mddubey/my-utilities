"""RQ-QS-05A, Layer B -- Post-Breakout Decay characterization (2026-09-29).

Per critic's exact spec, gated on Layer A holding up (it did, see FINDINGS.md):
"characterize: range decay, volume decay, number of decay days, whether decay is
monotonic or merely declining on average, whether price holds above the breakout
area, whether there is a subsequent expansion. No threshold optimization. No
returns." This script does ONLY that -- purely descriptive, no P&L, no R, no gate.

Reuses Layer A's episode output directly (rq05a_layer_a_candidates.csv) -- same
episodes, not re-derived. Two forward windows pre-declared BEFORE looking at any
result: 15 trading days (~3 weeks, Bulkowski's own stated flag/pennant duration) and
40 trading days (~2 months, long enough to have caught JUSTDIAL's real Aug-28
secondary pop during the hand-check, chosen for that documented reason before this
script existed, not tuned afterward).

Reuses `signals.py`'s existing `vol_declining5` production column (the SAME literal
"5 consecutive days of falling volume" flag the user's own Chartink screener checks,
already computed for a different purpose -- `reject_theta_trap()`'s options-side
"this is dead, don't trade it" rule) rather than reimplementing that specific check --
single-source-of-truth discipline. Also computes its own decay-run-length ANCHORED at
the episode's end (vol_declining5 is a rolling flag anywhere in history, not anchored
to "counting from right after this specific breakout").
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from backtest import load, daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
WINDOWS = [15, 40]  # trading days, pre-declared (see module docstring)


def analyze_episode(rows, ticker, episode_start_i, episode_end_i, vol_baseline, all_starts_this_ticker):
    n_rows = len(rows)
    a_row = rows.iloc[episode_start_i]
    end_row = rows.iloc[episode_end_i]
    episode_peak_vol = rows.iloc[episode_start_i:episode_end_i + 1].Volume.max()
    pre_breakout_close = rows.iloc[episode_start_i - 1].Close if episode_start_i > 0 else np.nan
    breakout_peak_high = rows.iloc[episode_start_i:episode_end_i + 1].High.max()
    atr_at_end = end_row.atr14

    rec = dict(ticker=ticker, episode_start_i=episode_start_i, episode_end_i=episode_end_i,
                episode_start_date=str(a_row.Date.date()), episode_end_date=str(end_row.Date.date()),
                episode_peak_vol=episode_peak_vol, vol_baseline=vol_baseline,
                pre_breakout_close=pre_breakout_close, breakout_peak_high=breakout_peak_high,
                atr_at_end=atr_at_end)

    for W in WINDOWS:
        end = min(episode_end_i + 1 + W, n_rows)
        # truncate at a corp-action day, same convention as RQ-QS-04A
        for k in range(episode_end_i + 1, end):
            if rows.iloc[k].corp_action_day:
                end = k
                break
        span = rows.iloc[episode_end_i + 1:end]
        if len(span) < 3:
            for suffix in ["vol_ratio_to_baseline", "vol_ratio_to_peak", "vol_trend_corr",
                            "range_over_atr", "range_trend_corr", "vol_declining5_pct",
                            "decay_run_len", "min_low_vs_prebreakout_pct", "min_low_vs_peak_pct",
                            "subsequent_expansion_day"]:
                rec[f"{suffix}_{W}d"] = None
            continue

        vol_ratio_baseline = span.Volume.mean() / vol_baseline if vol_baseline else None
        vol_ratio_peak = span.Volume.mean() / episode_peak_vol if episode_peak_vol else None
        vol_trend_corr = float(np.corrcoef(np.arange(len(span)), span.Volume)[0, 1]) if len(span) >= 3 else None
        rng = span.High - span.Low
        range_over_atr = (rng.mean() / atr_at_end) if pd.notna(atr_at_end) and atr_at_end else None
        range_trend_corr = float(np.corrcoef(np.arange(len(span)), rng)[0, 1]) if len(span) >= 3 else None
        vol_declining5_pct = span.vol_declining5.mean() * 100

        # decay run-length: consecutive day-over-day volume DECREASES, counted starting
        # the first day right after the episode ends (anchored, not a rolling-anywhere flag)
        vols = span.Volume.values
        run = 0
        for k in range(1, len(vols)):
            if vols[k] < vols[k - 1]:
                run += 1
            else:
                break
        min_low = span.Low.min()
        min_low_vs_pre = ((min_low - pre_breakout_close) / pre_breakout_close * 100) if pd.notna(pre_breakout_close) else None
        min_low_vs_peak = ((min_low - breakout_peak_high) / breakout_peak_high * 100)

        # subsequent expansion: another episode start for this SAME ticker within the window
        later_starts = [s for s in all_starts_this_ticker if episode_end_i < s <= episode_end_i + W]
        subsequent_day = (later_starts[0] - episode_end_i) if later_starts else None

        rec.update({
            f"vol_ratio_to_baseline_{W}d": vol_ratio_baseline,
            f"vol_ratio_to_peak_{W}d": vol_ratio_peak,
            f"vol_trend_corr_{W}d": vol_trend_corr,
            f"range_over_atr_{W}d": range_over_atr,
            f"range_trend_corr_{W}d": range_trend_corr,
            f"vol_declining5_pct_{W}d": vol_declining5_pct,
            f"decay_run_len_{W}d": run,
            f"min_low_vs_prebreakout_pct_{W}d": min_low_vs_pre,
            f"min_low_vs_peak_pct_{W}d": min_low_vs_peak,
            f"subsequent_expansion_day_{W}d": subsequent_day,
        })
    return rec


def pstack(s, fmt="{:.2f}", suffix=""):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}{suffix}" for p in [25, 50, 75, 90]) + f"  (n={len(s)})"


if __name__ == "__main__":
    day = pd.read_csv("swing_qs_postbreakout/rq05a_layer_a_candidates.csv")
    starts = day[day.is_episode_start].copy()
    ends = day.groupby(["ticker", "episode_start_i"]).i.max().rename("episode_end_i").reset_index()
    ep = starts.merge(ends, on=["ticker", "episode_start_i"], how="left")
    print(f"{len(ep)} episodes to characterize")

    cache = {}
    recs = []
    for n, r in enumerate(ep.itertuples()):
        if n % 2000 == 0:
            print(f"{n}/{len(ep)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        starts_this = sorted(ep[ep.ticker == r.ticker].episode_start_i.tolist())
        rec = analyze_episode(rows, r.ticker, int(r.episode_start_i), int(r.episode_end_i),
                                r.vol_baseline, starts_this)
        rec["novel_63d"], rec["novel_126d"], rec["novel_252d"] = r.novel_63d, r.novel_126d, r.novel_252d
        recs.append(rec)

    out = pd.DataFrame(recs)
    out.to_csv(f"{OUT_DIR}/rq05a_layer_b_decay.csv", index=False)

    for W in WINDOWS:
        print(f"\n{'='*90}\n=== Layer B, forward window = {W} trading days (n={len(out)} episodes) ===\n{'='*90}")
        print(f"vol_ratio_to_baseline: {pstack(out[f'vol_ratio_to_baseline_{W}d'], '{:.2f}', 'x')}")
        print(f"vol_ratio_to_peak:     {pstack(out[f'vol_ratio_to_peak_{W}d'], '{:.3f}', 'x')}")
        print(f"vol_trend_corr:        {pstack(out[f'vol_trend_corr_{W}d'], '{:.3f}')}  "
              f"(% negative: {(out[f'vol_trend_corr_{W}d'] < 0).mean()*100:.1f}%)")
        print(f"range_over_atr:        {pstack(out[f'range_over_atr_{W}d'], '{:.2f}', 'x')}")
        print(f"range_trend_corr:      {pstack(out[f'range_trend_corr_{W}d'], '{:.3f}')}  "
              f"(% negative: {(out[f'range_trend_corr_{W}d'] < 0).mean()*100:.1f}%)")
        print(f"vol_declining5_pct (days where the EXISTING production vol_declining5 flag is True): "
              f"{pstack(out[f'vol_declining5_pct_{W}d'], '{:.1f}', '%')}")
        print(f"decay_run_len (consecutive day-over-day vol decreases from episode end): "
              f"{pstack(out[f'decay_run_len_{W}d'], '{:.0f}')}")
        print(f"min_low_vs_prebreakout_pct: {pstack(out[f'min_low_vs_prebreakout_pct_{W}d'], '{:.1f}', '%')}  "
              f"(% staying above pre-breakout close: {(out[f'min_low_vs_prebreakout_pct_{W}d'] > 0).mean()*100:.1f}%)")
        print(f"min_low_vs_peak_pct:        {pstack(out[f'min_low_vs_peak_pct_{W}d'], '{:.1f}', '%')}  "
              f"(% staying above the flagpole's own peak High: {(out[f'min_low_vs_peak_pct_{W}d'] > 0).mean()*100:.1f}%)")
        sub = out[f"subsequent_expansion_day_{W}d"]
        print(f"subsequent expansion within window: {sub.notna().sum()} ({sub.notna().mean()*100:.1f}%)  "
              f"day-offset {pstack(sub, '{:.0f}')}")

        print(f"\n--- Descriptive split by novel_252d (NOT a performance comparison) ---")
        for label, mask in [("novel (no qualifying event in prior 12mo)", out.novel_252d),
                              ("re-accel (already active in prior 12mo)", ~out.novel_252d)]:
            sub_df = out[mask]
            print(f"  {label}: n={len(sub_df)}  "
                  f"vol_ratio_to_baseline med={sub_df[f'vol_ratio_to_baseline_{W}d'].median():.2f}x  "
                  f"vol_trend_corr med={sub_df[f'vol_trend_corr_{W}d'].median():.3f}  "
                  f"%neg={( sub_df[f'vol_trend_corr_{W}d']<0).mean()*100:.1f}%  "
                  f"holds-above-prebreakout={(sub_df[f'min_low_vs_prebreakout_pct_{W}d']>0).mean()*100:.1f}%  "
                  f"subsequent-expansion={sub_df[f'subsequent_expansion_day_{W}d'].notna().mean()*100:.1f}%")

    print(f"\n{'='*90}\n--- Rule #22 anchors ---\n{'='*90}")
    for tk, dt in [("JUSTDIAL", "2026-07-13"), ("GOCLCORP", "2026-09-03")]:
        row = out[(out.ticker == tk) & (out.episode_start_date == dt)]
        if row.empty:
            print(f"{tk} {dt}: not found")
            continue
        r = row.iloc[0]
        print(f"\n{tk} episode {r.episode_start_date} -> {r.episode_end_date}  "
              f"peak_vol={r.episode_peak_vol:,.0f}  baseline={r.vol_baseline:,.0f}")
        for W in WINDOWS:
            print(f"  {W}d: vol_ratio_to_baseline={r[f'vol_ratio_to_baseline_{W}d']:.2f}x  "
                  f"vol_trend_corr={r[f'vol_trend_corr_{W}d']:.3f}  "
                  f"decay_run_len={r[f'decay_run_len_{W}d']:.0f}  "
                  f"min_low_vs_prebreakout={r[f'min_low_vs_prebreakout_pct_{W}d']:.1f}%  "
                  f"min_low_vs_peak={r[f'min_low_vs_peak_pct_{W}d']:.1f}%  "
                  f"subsequent_expansion_day={r[f'subsequent_expansion_day_{W}d']}")
