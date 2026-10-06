"""RQ-EMAPB-06 -- Top-down multi-timeframe synthesis (user's idea, critic buy-in 2026-10-04).

Daily resolution decides whether a move is real and where it peaked (FROZEN from RQ-EMAPB-04,
not recomputed here). 1H resolution measures what happens after that daily event is fully
closed -- starting strictly at the first completed 1H bar of the NEXT trading session, never
inside the peak day itself. No new algorithmic "hourly peak" is introduced (the running-high-walk
was shown unreliable in RQ-EMAPB-05 -- 89.5% mis-segmentation); peak_high is the sole structural
reference, kept separate from the tradable starting price (next session's first 1H Open).

Builds TWO populations for the critic's required conditional-separation check:
  1. Real: post-daily-peak 1H behavior (frozen daily episodes from 04).
  2. Baseline: unconditional 1H behavior -- same mechanics, random (ticker, day) pairs NOT
     conditioned on being a daily peak.

Purely descriptive. No filter, no promotion, no optimization.

Usage: python3 swing_qs_emapb/10_rq_emapb06_post_peak.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = "data/daily"
WINDOW_BARS = 300          # same convention as RQ-EMAPB-04/05, not re-tuned
FIB_LEVELS = [0.382, 0.5, 0.618]   # diagnostic only, reported without picking a winner
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
    d = d.dropna(subset=["Close", "High", "Low", "Open"])
    d["session_date"] = d.index.normalize().tz_localize(None)
    return d.reset_index(drop=True)


def load_daily(ticker):
    f = os.path.join(DAILY_DIR, f"{ticker}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d["Date"])
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def first_1h_bar_after(d, ref_date):
    match = d.index[d.session_date > pd.Timestamp(ref_date)]
    if len(match) == 0:
        return None
    return int(match[0])


def compute_metrics(d, start_i, reference_high, impulse_range=None):
    end = min(start_i + WINDOW_BARS, len(d))
    if end - start_i < 5:
        return None
    window = d.iloc[start_i:end]
    start_price = window.Open.iloc[0]

    max_pullback_pct = (window.Low.min() / reference_high - 1) * 100
    mfe_pct = (window.High.max() / start_price - 1) * 100
    mae_pct = (window.Low.min() / start_price - 1) * 100

    regain_idx = None
    highs = window.High.values
    for k in range(len(highs)):
        if highs[k] > reference_high:
            regain_idx = k
            break

    out = dict(start_price=start_price, max_pullback_pct=max_pullback_pct,
               mfe_pct=mfe_pct, mae_pct=mae_pct,
               bars_to_regain=regain_idx, resumed_within_window=(regain_idx is not None))

    if impulse_range is not None and impulse_range > 0:
        lows = window.Low.values
        for lvl in FIB_LEVELS:
            level_price = reference_high - lvl * impulse_range
            idx = None
            for k in range(len(lows)):
                if lows[k] <= level_price:
                    idx = k
                    break
            out[f"bars_to_retrace_{int(lvl*1000)}"] = idx
    return out


def build_real_population():
    pop = pd.read_csv(f"{HERE}/rq_emapb04_daily_episodes.csv")
    pop = pop[pop.peak_date.notna()].copy()
    print(f"RQ-EMAPB-04 frozen episodes with a valid peak_date: {len(pop):,}")

    rows = []
    cache60 = {}
    for r in pop.itertuples():
        d = cache60.setdefault(r.ticker, load_60m(r.ticker))
        if d is None:
            continue
        start_i = first_1h_bar_after(d, r.peak_date)
        if start_i is None:
            continue
        impulse_range = r.peak_high - r.a_entry_price
        m = compute_metrics(d, start_i, r.peak_high, impulse_range)
        if m is None:
            continue
        m.update(ticker=r.ticker, a_entry_date=r.a_entry_date, peak_date=r.peak_date,
                  peak_high=r.peak_high)
        rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb06_real_post_peak.csv", index=False)
    print(f"Real post-peak 1H episodes built: {len(df):,}")
    return df


def build_baseline_population(n_target, real_tickers):
    cache60, cache_daily = {}, {}
    candidates = []  # (ticker, date, daily_high)
    for ticker in real_tickers:
        dd = cache_daily.setdefault(ticker, load_daily(ticker))
        d60 = cache60.setdefault(ticker, load_60m(ticker))
        if dd is None or d60 is None:
            continue
        min_1h_date = d60.session_date.min()
        eligible = dd[dd.Date >= min_1h_date]
        for rr in eligible.itertuples():
            candidates.append((ticker, rr.Date, rr.High))

    print(f"Baseline candidate pool: {len(candidates):,} (ticker, day) pairs "
          f"across {len(real_tickers)} tickers")
    rng = np.random.RandomState(SEED)
    idx = rng.choice(len(candidates), size=min(n_target, len(candidates)), replace=False)
    sampled = [candidates[i] for i in idx]

    rows = []
    for ticker, date, daily_high in sampled:
        d = cache60[ticker]
        start_i = first_1h_bar_after(d, date)
        if start_i is None:
            continue
        m = compute_metrics(d, start_i, daily_high, impulse_range=None)
        if m is None:
            continue
        m.update(ticker=ticker, ref_date=str(date.date()), reference_high=daily_high)
        rows.append(m)
    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb06_baseline.csv", index=False)
    print(f"Baseline (unconditional) 1H episodes built: {len(df):,}")
    return df


def report(real_df, base_df):
    print("\n=== RQ-EMAPB-06: post-daily-peak 1H behavior vs. unconditional 1H baseline ===\n")
    print(f"{'metric':38}{'REAL (post-peak)':>20}{'BASELINE (random)':>20}")

    def fmt_line(label, real_val, base_val):
        print(f"{label:38}{real_val:>20}{base_val:>20}")

    fmt_line("n", f"{len(real_df):,}", f"{len(base_df):,}")
    fmt_line("median max_pullback_pct", f"{real_df.max_pullback_pct.median():.2f}%",
              f"{base_df.max_pullback_pct.median():.2f}%")
    fmt_line("median MFE_pct", f"{real_df.mfe_pct.median():.2f}%", f"{base_df.mfe_pct.median():.2f}%")
    fmt_line("median MAE_pct", f"{real_df.mae_pct.median():.2f}%", f"{base_df.mae_pct.median():.2f}%")
    fmt_line("% resumed within window", f"{real_df.resumed_within_window.mean()*100:.1f}%",
              f"{base_df.resumed_within_window.mean()*100:.1f}%")
    real_resumed = real_df[real_df.resumed_within_window]
    base_resumed = base_df[base_df.resumed_within_window]
    fmt_line("median bars_to_regain (if resumed)",
              f"{real_resumed.bars_to_regain.median():.1f}", f"{base_resumed.bars_to_regain.median():.1f}")

    print("\n--- Real population only: time to retrace X% of the A->peak move (diagnostic, no winner picked) ---")
    for lvl in FIB_LEVELS:
        col = f"bars_to_retrace_{int(lvl*1000)}"
        reached = real_df[col].notna()
        print(f"Fib {lvl*100:.1f}%: reached within window {reached.mean()*100:.1f}%  "
              f"median bars-to-reach (if reached) = {real_df.loc[reached, col].median():.1f}")


def main():
    real_df = build_real_population()
    real_tickers = sorted(real_df.ticker.unique())
    base_df = build_baseline_population(n_target=len(real_df), real_tickers=real_tickers)
    report(real_df, base_df)


if __name__ == "__main__":
    main()
