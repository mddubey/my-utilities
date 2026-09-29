"""RQ-A5 -- Breakout Dominance Loss / Breakout Retest Failure Signature (2026-09-22).

Status: Approved, Tier A Candidate -> Research. P1 (ahead of O'Neil Benchmark v1.0,
VCP Trust Gap, any Type-B/RQ-77 detector work). Bounded 5-step telemetry-only plan --
NO thresholds, NO gate, NO production wiring, NO parameter sweep.

Origin: real, live, n=1 observation (2026-09-21/22) -- GRANULES cleared a real prior
resistance high on massive volume (7.85M), then 4 trading days later printed a
marginal fresh high on 73% less volume, closed weak, and gave back the entire
breakout gain. AEGISLOG was live-testing an analogous level, which prompted the
question -- this RQ is NOT about either specific trade, it's a new mechanism
hypothesis.

Core hypothesis: among breakout trades (breakout_cont AND coiled_spring both -- no
VCP-specific requirement, this applies generically to any breakout) that make a
fresh high within Day+1..Day+5 after the original breakout, some lose institutional
dominance on that retest (weak close + falling volume vs. the breakout day itself)
-- an early fake-breakout signature. Distinct from:
  - RQ-S1 (supply exhaustion): pre-breakout, volume drying during the base, already
    closed-negative. This is POST-breakout.
  - Weak Breach: the breakout day itself closing weak. This REQUIRES the breakout
    day to have made a fresh high (production entry criteria already enforce this)
    -- the failure shows up later, on the retest.

Breakout definition, per pattern (verify-against-production-source discipline):
  - breakout_cont: primed_engine.detect_primed_entry() -- the canonical Primed Gate
    trigger-touch (row.High >= high10_prior*1.005), trigger_price IS the entry price.
  - coiled_spring: backtest.detect_entry() (legacy Entry Gate, require_regime=False)
    + vcp.vcp_breakout() for the real base pivot. VCP was NOT migrated to Primed Gate
    (see PARKING_LOT.md item 1, standing "don't touch VCP" hold) -- this stays on its
    existing legacy definition, per the 2026-09-20 governance split (Primed Gate is
    BC-only; VCP/coiled_spring untouched).
  require_regime=False matches this project's "big population for daily-only tests"
  convention (population choice memory) -- regime gate is a live-admission concern,
  not a detection-quality one.

Population convention: report BOTH the full population and the Freshness<=0.40
subset (per "condition on established filters first" -- freshness_score computed off
the PRIOR day's row, i-1, matching the corrected no-lookahead convention fixed
2026-09-17/18).

Two ingredients, tested SEPARATELY (Steps 2/3) before any interaction (Step 4) --
critic explicitly rejected hand-picking a volume-ratio cutoff, so both continuous
features are reported in QUARTILES, not swept for a threshold:
  - Ingredient A (Price Failure): high_extension_pct (does the retest even clear the
    breakout high meaningfully) and close_position_pct (does the retest day hold its
    own gain intraday).
  - Ingredient B (Volume Dominance Loss): volume_ratio_breakout = V_retest /
    V_breakout -- compared to the ORIGINAL BREAKOUT day's volume specifically, not
    average volume, not the run's max volume.
  - Gain Retention (new feature, O'Neil-adjacent): (Close_retest - Close_breakout) /
    (Close_breakout - trigger) -- how much of the breakout day's gain over its own
    trigger is still held by the retest day. GRANULES-shaped: strongly negative when
    the retest gives back the whole move.

Anchor-leakage caution (Research Integrity Rule #10, re-applied -- do NOT skip):
predictors are fixed at the RETEST day (close_position_pct, volume_ratio_breakout,
high_extension_pct, gain_retention -- all reference the breakout day or the retest
day's own range, never reach forward). The OUTCOME measurement starts from the
RETEST DAY'S OWN CLOSE forward (ret_d1, ret_d2, opt_d1_open), never reaches back to
the original entry/trigger price. This is the exact failure mode that already
invalidated close-vs-trigger, candle quality, and upper-wick this week (see
FINDINGS.md's Rule #10 sections) -- do not recreate it here.

Outcome window: immediate outcomes only (ret_d1/ret_d2 stock close-to-close, plus an
FO-scoped opt_d1_open options-style number) -- deliberately NOT this project's
standard 15-day swing expectancy metric (per the approved spec: meant to catch
something fast enough to matter for an options decision, not to re-derive the whole
swing exit architecture).

"Type-A / fake-breakout" operational label (this script's own definition, not an
established project term elsewhere): ret_d1 < 0 -- the retest day's own close-to-
close Day+1 return is negative. Used only to report a monotonic frequency rate per
quartile, per the spec's exact phrasing; win_rate/expectancy on ret_d1/ret_d2/
opt_d1_open are reported alongside as the primary numbers.

5-step plan (all run from one event table, matching this project's existing
gather()+report() script shape):
  1. Build the Day+1-Day+5 retest event table (gather())
  2. Price-only signal: high_extension_pct + close_position_pct (report_price_only())
  3. Volume-only signal: volume_ratio_breakout (report_volume_only())
  4. Interaction: weak close x low volume (report_interaction())
  5. Evaluate against immediate outcomes only (built into every report() above --
     ret_d1/ret_d2/opt_d1_open on every cut, no separate step needed)
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import vcp
from pivots import daily_pivots
from primed_engine import detect_primed_entry
from daily_scan import _fo_tickers
from live_checkpoint import _freshness_score
from research.metrics import expectancy, win_rate

RETEST_WINDOW = 5
FRESH_CUTOFF = 0.40


def _detect_breakout(ticker, df, i):
    """Returns (pattern, trigger, breakout_high, breakout_close, breakout_volume) or
    None. See module docstring for the per-pattern breakout definition and why they
    differ (Primed Gate for BC, legacy Entry Gate + vcp_breakout for VCP)."""
    row = df.iloc[i]
    bc = detect_primed_entry(ticker, df, i)
    if bc is not None:
        trigger, _structural_low = bc
        return "breakout_cont", trigger, row.High, row.Close, row.Volume
    candidate = backtest.detect_entry(ticker, df, i, require_regime=False)
    if candidate is not None and candidate[0] == "coiled_spring":
        vb = vcp.vcp_breakout(df, i)
        if vb is not None:
            pivot, _structural_low = vb
            return "coiled_spring", pivot, row.High, row.Close, row.Volume
    return None


def gather(tickers, verbose=False):
    rows = []
    n_breakouts = 0
    n_no_retest = 0
    for n, t in enumerate(tickers):
        if verbose and n % 50 == 0:
            print(f"  {n}/{len(tickers)} tickers, {n_breakouts} breakouts, "
                  f"{len(rows)} retest events so far", file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        n_rows = len(df)
        for i in range(1, n_rows - RETEST_WINDOW - 2):
            row = df.iloc[i]
            if row.corp_action_day:
                continue
            det = _detect_breakout(t, df, i)
            if det is None:
                continue
            pattern, trigger, bo_high, bo_close, bo_vol = det
            if not bo_vol:
                continue
            n_breakouts += 1

            fresh = _freshness_score(df.iloc[i - 1])
            is_fresh = fresh is not None and fresh <= FRESH_CUTOFF

            retest_idx = None
            for j in range(i + 1, i + 1 + RETEST_WINDOW):
                if df.iloc[j].corp_action_day:
                    break
                if df.iloc[j].High > bo_high:
                    retest_idx = j
                    break
            if retest_idx is None:
                n_no_retest += 1
                continue

            rj = df.iloc[retest_idx]
            day_range = rj.High - rj.Low
            close_position_pct = (rj.Close - rj.Low) / day_range * 100 if day_range > 0 else None
            volume_ratio_breakout = rj.Volume / bo_vol
            high_extension_pct = (rj.High - bo_high) / bo_high * 100
            close_vs_breakout_close = (rj.Close / bo_close - 1) * 100
            denom = bo_close - trigger
            gain_retention = (rj.Close - bo_close) / denom if denom else None

            j1, j2 = retest_idx + 1, retest_idx + 2
            ret_d1 = ret_d2 = opt_d1_open = None
            if j1 < n_rows and not df.iloc[j1].corp_action_day:
                ret_d1 = (df.iloc[j1].Close / rj.Close - 1) * 100
                opt_d1_open = (df.iloc[j1].Open / rj.Close - 1) * 100
            if j2 < n_rows and not df.iloc[j2].corp_action_day and ret_d1 is not None:
                ret_d2 = (df.iloc[j2].Close / rj.Close - 1) * 100

            rows.append(dict(
                ticker=t, pattern=pattern, breakout_date=row.Date, retest_date=rj.Date,
                is_fresh=is_fresh, freshness=fresh,
                days_after_breakout=retest_idx - i,
                high_extension_pct=high_extension_pct,
                close_position_pct=close_position_pct,
                volume_ratio_breakout=volume_ratio_breakout,
                close_vs_breakout_close=close_vs_breakout_close,
                gain_retention=gain_retention,
                ret_d1=ret_d1, ret_d2=ret_d2, opt_d1_open=opt_d1_open,
            ))

    df_out = pd.DataFrame(rows)
    print(f"\nTotal real breakouts scanned (both patterns, require_regime=False): {n_breakouts}",
          file=sys.stderr)
    print(f"NO_RETEST (no fresh high above the breakout High within Day+1..Day+5): "
          f"{n_no_retest} ({n_no_retest / n_breakouts * 100:.1f}%)" if n_breakouts else "",
          file=sys.stderr)
    print(f"Retest events (this event table): {len(df_out)} "
          f"({len(df_out) / n_breakouts * 100:.1f}% of all breakouts)" if n_breakouts else "",
          file=sys.stderr)
    return df_out


def _fake_rate(g):
    d1 = g.ret_d1.dropna()
    return (d1 < 0).mean() * 100 if len(d1) else float("nan")


def _line(label, g, fo_tickers):
    d1 = g.ret_d1.dropna()
    d2 = g.ret_d2.dropna()
    opt = g[g.ticker.isin(fo_tickers)].opt_d1_open.dropna()
    print(f"  {label:<28} n={len(g):<5} fake_rate={_fake_rate(g):5.1f}%  "
          f"d1 win={win_rate(d1):5.1f}%/exp={expectancy(d1):+.3f}%  "
          f"d2 win={win_rate(d2):5.1f}%/exp={expectancy(d2):+.3f}%  "
          f"opt(d+1open) win={win_rate(opt):5.1f}%/exp={expectancy(opt):+.3f}% (n={len(opt)})")


def _by_quartile(df, feat, fo_tickers, label):
    d = df.dropna(subset=[feat]).copy()
    try:
        d["bucket"] = pd.qcut(d[feat], 4, duplicates="drop")
    except ValueError:
        print(f"\n=== {label} ({feat}): not enough distinct values to bucket ===")
        return
    print(f"\n=== {label} ({feat}), quartiles ===")
    for b, g in d.groupby("bucket", observed=True):
        _line(str(b), g, fo_tickers)


def report_price_only(df, fo_tickers):
    print("\n" + "=" * 70)
    print("STEP 2 -- Price-only signal")
    print("=" * 70)
    _by_quartile(df, "close_position_pct", fo_tickers, "Close position in retest day's own range")

    print("\n=== High Extension (descriptive buckets, not optimized) ===")
    bins = [-1e9, 0, 1, 3, 1e9]
    labels = ["<0% (no real retest*)", "0-1% (marginal poke)", "1-3% (small continuation)", ">3% (real continuation)"]
    d = df.copy()
    d["bucket"] = pd.cut(d.high_extension_pct, bins=bins, labels=labels)
    for lb in labels:
        g = d[d.bucket == lb]
        if len(g):
            _line(lb, g, fo_tickers)
    print("  (*shouldn't occur by construction -- retest_idx requires High > breakout_high;"
          " a <0% bucket here would mean a data issue, sanity check)")

    print("\n=== Gain Retention (new feature), quartiles ===")
    _by_quartile(df, "gain_retention", fo_tickers, "Gain Retention")


def report_volume_only(df, fo_tickers):
    print("\n" + "=" * 70)
    print("STEP 3 -- Volume-only signal (Volume Ratio = V_retest / V_breakout)")
    print("=" * 70)
    _by_quartile(df, "volume_ratio_breakout", fo_tickers, "Volume Ratio vs breakout day")


def report_interaction(df, fo_tickers):
    print("\n" + "=" * 70)
    print("STEP 4 -- Interaction: weak close x low volume")
    print("=" * 70)
    d = df.dropna(subset=["close_position_pct", "volume_ratio_breakout"]).copy()
    close_med = d.close_position_pct.median()
    vol_med = d.volume_ratio_breakout.median()
    d["weak_close"] = d.close_position_pct <= close_med
    d["low_volume"] = d.volume_ratio_breakout <= vol_med
    for wc in (False, True):
        for lv in (False, True):
            g = d[(d.weak_close == wc) & (d.low_volume == lv)]
            label = f"close={'weak' if wc else 'strong'}/vol={'low' if lv else 'high'}"
            _line(label, g, fo_tickers)


def report(df, fo_tickers):
    print(f"\nRQ-A5 event table, n={len(df)}")
    print(f"By pattern: {df.pattern.value_counts().to_dict()}")
    print(f"Overall fake_rate (ret_d1<0): {_fake_rate(df):.1f}%")
    _line("ALL (baseline)", df, fo_tickers)

    fresh_df = df[df.is_fresh]
    print(f"\n--- Freshness<=0.40 subset (n={len(fresh_df)}, "
          f"{len(fresh_df) / len(df) * 100:.1f}% of table) ---")
    _line("FRESH ONLY (baseline)", fresh_df, fo_tickers)

    for pop_label, pop in [("FULL population", df), ("Freshness<=0.40 subset", fresh_df)]:
        print(f"\n{'#'*70}\n# {pop_label} (n={len(pop)})\n{'#'*70}")
        report_price_only(pop, fo_tickers)
        report_volume_only(pop, fo_tickers)
        report_interaction(pop, fo_tickers)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    fo = _fo_tickers()
    event_df = gather(tickers, verbose=True)
    event_df.to_csv("rq_a5_retest_dominance.csv", index=False)
    print("\nRaw event table saved to rq_a5_retest_dominance.csv")
    report(event_df, fo)
