"""RQ-EMAPB-03 -- Visual Base Audit (critic-specified, 2026-10-04). Builds 30 blinded chart
episodes (15 eventual continuation, 15 eventual non-continuation) for manual review. No new
filters/indicators/thresholds -- reuses the exact A/impulse/pullback definitions from
RQ-EMAPB-01/02. See RQ-EMAPB-03_SPEC.md for the full critic design.

Outcome label (zero-parameter, reusing only what's already computed): CONTINUATION = price
makes a new high above the original impulse peak (swing_high) at some point after the pullback
starts, within the window. NON-CONTINUATION = it never does. No threshold invented.

Blind stopping point (fixed, predeclared, same rule for every episode, not hindsight-picked):
peak_i + 14 bars (~2 trading days) -- enough room for a base to visibly develop without
showing the eventual resolution.

Usage: python3 swing_qs_emapb/07_visual_audit_build.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "visual_audit")
os.makedirs(OUT_DIR, exist_ok=True)
WINDOW_BARS = 70
BLIND_STOP_OFFSET = 14   # bars after peak_i, fixed, predeclared, same for every episode
PRE_LOOKBACK = 20        # bars before A shown for context
SEED = 2026


def load_60m(ticker):
    f = INTRADAY_60M_DIR / f"{ticker}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f, index_col=0)
    if d.empty:
        return None
    d.index = pd.to_datetime(d.index, utc=True).tz_convert("Asia/Kolkata")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    d = d.dropna(subset=["Close", "High", "Low"])
    if len(d) < 100:
        return None
    d["session_date"] = d.index.normalize().tz_localize(None)
    d["ema8"] = d.Close.ewm(span=8, adjust=False).mean()
    d["ema21"] = d.Close.ewm(span=21, adjust=False).mean()
    return d.reset_index(drop=True)


def find_peak(rows, ia, end):
    running_high = rows.iloc[ia].High
    peak_i = ia
    for k in range(ia + 1, end):
        if rows.iloc[k].High > running_high:
            running_high = rows.iloc[k].High
            peak_i = k
        else:
            return peak_i, running_high, k
    return peak_i, running_high, end


def d1_outcome(rows, touch_anchor_i, c0):
    """Reuses the same D1 definition as RQ-EMAPB-01/02."""
    anchor_session = rows.iloc[touch_anchor_i].session_date
    future = rows.loc[rows.session_date > anchor_session, "session_date"]
    if future.empty:
        return None
    d1_session = future.iloc[0]
    d1_bars = rows[rows.session_date == d1_session]
    if d1_bars.empty:
        return None
    return dict(
        d1_open_pct=(d1_bars.Open.iloc[0] / c0 - 1) * 100,
        d1_peak_pct=(d1_bars.High.max() / c0 - 1) * 100,
        d1_close_pct=(d1_bars.Close.iloc[-1] / c0 - 1) * 100,
    )


def plot_episode(rows, ia, peak_i, stop_i, end_i, episode_id, label_tag, swing_low, swing_high,
                  a_date, blinded):
    lo = max(ia - PRE_LOOKBACK, 0)
    hi = (stop_i + 1) if blinded else (end_i + 1)
    seg = rows.iloc[lo:hi]

    fig, (ax, axv) = plt.subplots(2, 1, figsize=(14, 7), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    for x, (_, c) in zip(range(lo, hi), seg.iterrows()):
        col = "#2a9d4f" if c.Close >= c.Open else "#d1392f"
        ax.plot([x, x], [c.Low, c.High], color=col, lw=1)
        ax.add_patch(plt.Rectangle((x - 0.3, min(c.Open, c.Close)), 0.6,
                                    max(abs(c.Close - c.Open), 1e-6), color=col))
        axv.bar(x, c.Volume, color=col, width=0.6)
    ax.plot(range(lo, hi), seg.ema8, color="#3b82f6", lw=1.2, label="EMA8")
    ax.plot(range(lo, hi), seg.ema21, color="#f59e0b", lw=1.0, ls="--", label="EMA21 (context)")
    for lvl, lbl, col in [(swing_low, "A / retest", "#888"),
                          (swing_high - 0.382 * (swing_high - swing_low), "Fib38.2", "#aaa"),
                          (swing_high - 0.5 * (swing_high - swing_low), "Fib50", "#aaa"),
                          (swing_high - 0.618 * (swing_high - swing_low), "Fib61.8", "#aaa")]:
        ax.axhline(lvl, color=col, lw=0.6, ls=":")
    ax.axvline(ia, color="#1f6feb", ls=":", lw=1.2)
    ax.axvline(peak_i, color="#9333ea", ls=":", lw=1.2)
    if not blinded:
        ax.axvline(stop_i, color="#d1392f", ls="--", lw=1.0, alpha=0.6)
    title_tag = "BLINDED (stopped before outcome)" if blinded else f"FULL -- outcome: {label_tag}"
    ax.set_title(f"Episode #{episode_id} -- {rows.ticker.iloc[0] if 'ticker' in rows.columns else ''} "
                 f"A={a_date}  [{title_tag}]", fontsize=10)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xticks([])
    axv.set_xticks([])
    fig.tight_layout()
    suffix = "blinded" if blinded else "full"
    fig.savefig(os.path.join(OUT_DIR, f"ep{episode_id:02d}_{suffix}.png"), dpi=80)
    plt.close(fig)


def main():
    pop = pd.read_csv("swing_qs_bpc/rq_bpc05_a_volume_diagnostics.csv")
    pop = pop[(pop.entry_definition == 10) & (pop.vol_ratio >= 1.5) &
              (pop.a_entry_date >= "2023-10-23")]

    rows_cache = {}
    candidates = []
    for n, (ticker, grp) in enumerate(pop.groupby("ticker")):
        rows = rows_cache.setdefault(ticker, load_60m(ticker))
        if rows is None:
            continue
        for r in grp.itertuples():
            a_date = pd.Timestamp(r.a_entry_date)
            match = rows.index[rows.session_date >= a_date]
            if len(match) == 0:
                continue
            ia = int(match[0])
            if rows.iloc[ia].session_date != a_date:
                continue
            end = min(ia + 1 + WINDOW_BARS, len(rows))
            if end - ia < BLIND_STOP_OFFSET + 20:
                continue
            peak_i, swing_high, pullback_start = find_peak(rows, ia, end)
            swing_low = r.a_entry_price
            if swing_high <= swing_low:
                continue
            stop_i = min(peak_i + BLIND_STOP_OFFSET, end - 1)
            if stop_i <= peak_i + 2:
                continue
            # zero-parameter outcome: does price exceed swing_high again, after the pullback starts?
            post_pullback = rows.iloc[pullback_start:end]
            continuation = bool((post_pullback.High > swing_high).any())
            c0 = rows.iloc[ia].Close
            out = d1_outcome(rows, ia, c0)
            candidates.append(dict(ticker=ticker, a_entry_date=r.a_entry_date, ia=ia, peak_i=peak_i,
                                    pullback_start=pullback_start, stop_i=stop_i, end_i=end,
                                    swing_low=swing_low, swing_high=swing_high,
                                    continuation=continuation,
                                    d1_open_pct=out["d1_open_pct"] if out else None,
                                    d1_peak_pct=out["d1_peak_pct"] if out else None,
                                    d1_close_pct=out["d1_close_pct"] if out else None))

    cand_df = pd.DataFrame(candidates)
    print(f"Eligible candidates: {len(cand_df):,}  "
          f"(continuation={cand_df.continuation.sum():,}, non-continuation={(~cand_df.continuation).sum():,})")

    rng = np.random.RandomState(SEED)
    cont_sample = cand_df[cand_df.continuation].sample(15, random_state=rng)
    noncont_sample = cand_df[~cand_df.continuation].sample(15, random_state=rng)
    sample = pd.concat([cont_sample, noncont_sample]).sample(frac=1, random_state=rng).reset_index(drop=True)
    sample["episode_id"] = sample.index + 1

    meta_rows, outcome_rows = [], []
    for r in sample.itertuples():
        rows = rows_cache[r.ticker]
        rows = rows.copy()
        rows["ticker"] = r.ticker
        label = "CONTINUATION" if r.continuation else "NON-CONTINUATION"
        plot_episode(rows, r.ia, r.peak_i, r.stop_i, r.end_i, r.episode_id, label,
                     r.swing_low, r.swing_high, r.a_entry_date, blinded=True)
        plot_episode(rows, r.ia, r.peak_i, r.stop_i, r.end_i, r.episode_id, label,
                     r.swing_low, r.swing_high, r.a_entry_date, blinded=False)
        meta_rows.append(dict(episode_id=r.episode_id, ticker=r.ticker, a_entry_date=r.a_entry_date,
                               a_entry_price=round(r.swing_low, 2),
                               peak_date=str(rows.iloc[r.peak_i].session_date.date()),
                               peak_price=round(r.swing_high, 2),
                               blind_stop_date=str(rows.iloc[r.stop_i].session_date.date())))
        outcome_rows.append(dict(episode_id=r.episode_id, outcome=label,
                                  d1_open_pct=r.d1_open_pct, d1_peak_pct=r.d1_peak_pct,
                                  d1_close_pct=r.d1_close_pct))

    pd.DataFrame(meta_rows).to_csv(os.path.join(OUT_DIR, "episode_metadata.csv"), index=False)
    pd.DataFrame(outcome_rows).to_csv(os.path.join(OUT_DIR, "episode_outcomes_DO_NOT_OPEN_YET.csv"), index=False)
    print(f"\n30 episodes built -> {OUT_DIR}/")
    print("Blinded charts: ep01_blinded.png .. ep30_blinded.png")
    print("Full charts (held back): ep01_full.png .. ep30_full.png")
    print("Metadata (no outcome): episode_metadata.csv")
    print("Outcomes (separate, for after review): episode_outcomes_DO_NOT_OPEN_YET.csv")


if __name__ == "__main__":
    main()
