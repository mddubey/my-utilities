"""RQ-OX1-A -- Empirical Stock->Option Observability Feasibility Study (2026-09-22
handoff, critic-approved with refinements). The single approved next action for the
revived RQ-OX1 branch.

Revised objective (critic's exact wording): "Can underlying movement explain enough
of option movement to provide useful state observability in the absence of option
quotes?" -- evaluating OBSERVABILITY, not pricing accuracy.

Explicit guardrails (do NOT do any of this here): no IV inference, no Greeks
estimation, no Black-Scholes calibration, no beta optimization, no nonlinear curve
fitting, no ML regressors, no DTE-bucket optimization. This script's only job: is
there enough empirical structure in stock-vs-option movement to justify building
anything more sophisticated (OX1-B)?

Known, explicit ceiling on what this can answer (write this in, don't oversell it):
options_cache is EOD bhavcopy only. This CAN answer "does the option's daily economic
movement largely follow the underlying's daily movement" -- an upper-bound feasibility
gate. This CANNOT answer the actual MAXHEALTH problem (opening-auction execution,
first-minute gamma/IV effects, bid/ask spread, intraday repricing, slippage) -- no
intraday option data exists anywhere in this project (RQ-96 already parked for this
exact reason).

Population: real production breach events (both patterns, reusing
rq_a5_retest_dominance._detect_breakout -- the same dual-pattern breach definition
already validated today, Primed Gate for breakout_cont / legacy Entry Gate + vcp_breakout
for coiled_spring), F&O-eligible tickers only, full 5-year universe (require_regime=
False, big-population convention). For each breach event, tested across all 4 standing
moneyness x expiry combos (ATM/ITM x current/next) -- gives real DTE and moneyness
variety for stratification, not just the MAXHEALTH-specific ATM+current recipe. Real
contract selection and pricing reused directly from option_backtest.py's own
production functions (pick_contract/option_row/_real_spot/liquid/stock_close) -- not
reimplemented, per "verify formula against production source."

Per event x combo: S0/S1 = real (split-corrected) stock close on entry day and entry
day+1 (the option cache's own next trading day, via days_after()); O0/O1 = the SAME
contract's real EOD ClsPric on those same two dates. If day+1 has NO liquid print,
that is logged as a failure case (illiquid_day1), not silently walked forward to the
next liquid day -- OX1-A needs a strict day+1 window, unlike the existing swing-exit
convention (simulate_option_trade) which walks forward for a different purpose.

Three layers, exactly as the critic specified, in order:
  Layer 1 -- Sensitivity: beta = delta_O / delta_S, median/distribution.
  Layer 2 -- Stability: how much does beta DRIFT across strata (ATM vs ITM, DTE
             buckets, overnight-gap size, moneyness-transition flag)? Variance matters
             more than the mean (critic: "a beta of 2.1 is useless if it ranges from
             0.8 to 5.7").
  Layer 3 -- Decision observability: does the stock's own move-tercile predict the
             option's move-tercile (a 3x3 direction-classification agreement check
             vs the 33.3% random baseline), not a precision/MAE target.

Moneyness-drift audit (critic-added, explicit): entry moneyness bucket vs exit
moneyness bucket, flagged separately -- distinguishes "beta changed because the
instrument's regime changed" (e.g. ATM entry gapped into deep ITM) from "the mapping
itself is unstable."

Known limitation, flagged not worked around: this project's real option population is
100% calls (CE) -- no PE/bearish pattern exists yet (already-documented gap). Call vs
put stratification, which the critic asked for, is NOT testable on this population.

Precommitted success/failure criteria (critic's own wording, written before running):
  SUCCESS -> disposition VALIDATE: option movement substantially explained by stock
    movement; relationship reasonably stable within product strata; failures
    identifiable rather than random.
  FAILURE -> disposition CLOSE, no OX1-B: beta highly unstable; errors explode across
    ordinary regimes; no useful state classification emerges.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import numpy as np
import pandas as pd

import backtest
import option_backtest as ob
from pivots import daily_pivots
from daily_scan import _fo_tickers
from rq_a5_retest_dominance import _detect_breakout

MONEYNESS_EXPIRY_COMBOS = [("atm", "current"), ("atm", "next"), ("itm", "current"), ("itm", "next")]
DTE_BUCKETS = [(0, 10, "0-10d"), (10, 20, "10-20d"), (20, 40, "20-40d"), (40, 10_000, ">40d")]


def _moneyness_bucket(pct):
    if pct > 2:
        return "ITM"
    if pct < -2:
        return "OTM"
    return "ATM~"


def _dte_bucket(dte):
    for lo, hi, label in DTE_BUCKETS:
        if lo < dte <= hi:
            return label
    return "0d"


def gather(tickers, verbose=False):
    fo = set(_fo_tickers())
    tickers = [t for t in tickers if t in fo]
    rows = []
    n_breaches = 0
    n_combo_attempts = 0
    n_no_contract = 0
    n_entry_illiquid = 0
    n_day1_illiquid = 0

    for n, t in enumerate(tickers):
        if verbose and n % 25 == 0:
            print(f"  {n}/{len(tickers)} tickers, {n_breaches} breaches, {len(rows)} usable rows so far",
                  file=sys.stderr)
        try:
            df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for i in range(1, len(df) - 2):
            row = df.iloc[i]
            if row.corp_action_day:
                continue
            det = _detect_breakout(t, df, i)
            if det is None:
                continue
            pattern, trigger, bo_high, bo_close, bo_vol = det
            entry_date = row.Date
            n_breaches += 1

            S0 = ob._real_spot(t, entry_date, row.Close)
            next_dates = ob.days_after(entry_date)
            if not next_dates:
                continue
            next_date = next_dates[0]
            S1_fallback = ob.stock_close(t, next_date)
            if S1_fallback is None:
                continue
            S1 = ob._real_spot(t, next_date, S1_fallback)

            overnight_gap_pct = None
            if i + 1 < len(df) and df.iloc[i + 1].Date == next_date:
                overnight_gap_pct = (df.iloc[i + 1].Open / row.Close - 1) * 100

            for moneyness, expiry_choice in MONEYNESS_EXPIRY_COMBOS:
                n_combo_attempts += 1
                contract = ob.pick_contract(t, entry_date, S0, moneyness, expiry_choice)
                if contract is None:
                    n_no_contract += 1
                    continue
                expiry, strike, lot_size = contract

                entry_row = ob.option_row(t, entry_date, expiry, strike)
                if entry_row is None or not entry_row.ClsPric or not ob.liquid(entry_row):
                    n_entry_illiquid += 1
                    continue
                O0 = entry_row.ClsPric

                exit_row = ob.option_row(t, next_date, expiry, strike)
                day1_illiquid = exit_row is None or not exit_row.ClsPric or not ob.liquid(exit_row)
                if day1_illiquid:
                    n_day1_illiquid += 1
                    continue
                O1 = exit_row.ClsPric

                dte = ob.trading_days_between(entry_date, expiry)
                m_entry_pct = (S0 - strike) / S0 * 100
                m_exit_pct = (S1 - strike) / S1 * 100
                bucket_entry = _moneyness_bucket(m_entry_pct)
                bucket_exit = _moneyness_bucket(m_exit_pct)

                delta_S = S1 - S0
                delta_O = O1 - O0
                beta = delta_O / delta_S if delta_S else None

                rows.append(dict(
                    ticker=t, pattern=pattern, entry_date=entry_date, next_date=next_date,
                    moneyness=moneyness, expiry_choice=expiry_choice, dte=dte,
                    dte_bucket=_dte_bucket(dte),
                    S0=S0, S1=S1, O0=O0, O1=O1, delta_S=delta_S, delta_O=delta_O, beta=beta,
                    R_S=(S1 / S0 - 1) * 100, R_O=(O1 / O0 - 1) * 100,
                    moneyness_entry_pct=m_entry_pct, moneyness_exit_pct=m_exit_pct,
                    bucket_entry=bucket_entry, bucket_exit=bucket_exit,
                    moneyness_transition=bucket_entry != bucket_exit,
                    overnight_gap_pct=overnight_gap_pct,
                ))

    print(f"\nReal breach events scanned (F&O only): {n_breaches}", file=sys.stderr)
    print(f"Breach x moneyness/expiry combo attempts: {n_combo_attempts}", file=sys.stderr)
    print(f"  no contract available: {n_no_contract}", file=sys.stderr)
    print(f"  entry day illiquid/missing: {n_entry_illiquid}", file=sys.stderr)
    print(f"  day+1 illiquid/missing (FAILURE CASE, strict window, not walked forward): {n_day1_illiquid}",
          file=sys.stderr)
    print(f"  usable rows: {len(rows)}", file=sys.stderr)
    return pd.DataFrame(rows)


def report_layer1(df):
    print("\n" + "=" * 78)
    print("LAYER 1 -- Sensitivity: beta = delta_Option / delta_Stock")
    print("=" * 78)
    b = df.beta.dropna()
    print(f"n={len(b)}")
    print(f"median beta: {b.median():.3f}   mean: {b.mean():.3f}   std: {b.std():.3f}")
    print(f"quartiles: {b.quantile([0.1,0.25,0.5,0.75,0.9]).round(3).to_dict()}")
    corr_delta = df.delta_S.corr(df.delta_O)
    corr_pct = df.R_S.corr(df.R_O)
    print(f"corr(delta_S, delta_O) = {corr_delta:.3f}    corr(R_S%, R_O%) = {corr_pct:.3f}")


def report_layer2(df):
    print("\n" + "=" * 78)
    print("LAYER 2 -- Stability: does beta DRIFT across strata? (variance matters more than mean)")
    print("=" * 78)

    print("\n--- by moneyness x expiry (the 4 standing recipes) ---")
    for (m, e), g in df.groupby(["moneyness", "expiry_choice"]):
        b = g.beta.dropna()
        print(f"  {m:<4}/{e:<8} n={len(b):<6} median={b.median():+.3f}  IQR=[{b.quantile(.25):+.3f}, {b.quantile(.75):+.3f}]  std={b.std():.3f}")

    print("\n--- by DTE bucket ---")
    for label in [b[2] for b in DTE_BUCKETS]:
        g = df[df.dte_bucket == label]
        b = g.beta.dropna()
        if len(b) < 5:
            print(f"  {label:<8} n={len(b)} (too thin)")
            continue
        print(f"  {label:<8} n={len(b):<6} median={b.median():+.3f}  IQR=[{b.quantile(.25):+.3f}, {b.quantile(.75):+.3f}]  std={b.std():.3f}")

    print("\n--- by overnight-gap magnitude (terciles of |overnight_gap_pct|) ---")
    g = df.dropna(subset=["overnight_gap_pct"]).copy()
    g["gap_abs"] = g.overnight_gap_pct.abs()
    try:
        g["gap_bucket"] = pd.qcut(g.gap_abs, 3, labels=["small", "medium", "large"])
        for label, gg in g.groupby("gap_bucket", observed=True):
            b = gg.beta.dropna()
            print(f"  {label:<8} n={len(b):<6} median={b.median():+.3f}  IQR=[{b.quantile(.25):+.3f}, {b.quantile(.75):+.3f}]  std={b.std():.3f}")
    except ValueError:
        print("  not enough distinct values to bucket")

    print("\n--- MONEYNESS-DRIFT AUDIT: same bucket at entry/exit vs transitioned ---")
    for transitioned, g in df.groupby("moneyness_transition"):
        b = g.beta.dropna()
        label = "TRANSITIONED (e.g. ATM->ITM)" if transitioned else "same bucket throughout"
        print(f"  {label:<32} n={len(b):<6} median={b.median():+.3f}  IQR=[{b.quantile(.25):+.3f}, {b.quantile(.75):+.3f}]  std={b.std():.3f}")
    print("\n  entry->exit bucket transition matrix (count):")
    print(pd.crosstab(df.bucket_entry, df.bucket_exit))


def report_layer3(df):
    print("\n" + "=" * 78)
    print("LAYER 3 -- Decision observability: does the STOCK's move-tercile predict the")
    print("OPTION's move-tercile? (direction classification, not price precision)")
    print("=" * 78)
    d = df.dropna(subset=["R_S", "R_O"]).copy()
    d["S_tercile"] = pd.qcut(d.R_S, 3, labels=["down", "flat", "up"])
    d["O_tercile"] = pd.qcut(d.R_O, 3, labels=["down", "flat", "up"])
    ct = pd.crosstab(d.S_tercile, d.O_tercile)
    print("\nConfusion matrix (rows=stock tercile, cols=option tercile):")
    print(ct)
    agreement = (d.S_tercile.astype(str) == d.O_tercile.astype(str)).mean() * 100
    print(f"\nExact tercile agreement: {agreement:.1f}%  (random baseline = 33.3%)")
    # collapse "flat" as ambiguous -- report up/down directional agreement excluding flat/flat both extremes only
    extreme = d[d.S_tercile.isin(["up", "down"])]
    dir_agree = (extreme.S_tercile.astype(str) == extreme.O_tercile.astype(str)).mean() * 100
    print(f"Directional agreement on non-flat stock terciles only: {dir_agree:.1f}% (n={len(extreme)}, random baseline = 33.3%)")


def report_proxy_error(df):
    print("\n" + "=" * 78)
    print("DELIVERABLE -- absolute option-price error from a SIMPLE beta proxy")
    print("(no optimization: reuses the already-computed group medians, not fit/tuned)")
    print("=" * 78)
    global_beta = df.beta.dropna().median()
    print(f"\nGlobal median beta used as the single proxy coefficient: {global_beta:.3f}")

    d = df.dropna(subset=["beta", "O0", "O1", "delta_S"]).copy()
    d["O1_pred_global"] = d.O0 + global_beta * d.delta_S
    d["err_global"] = d.O1_pred_global - d.O1
    d["err_global_pct"] = d.err_global / d.O1 * 100

    strata_beta = d.groupby(["moneyness", "expiry_choice"]).beta.median()
    d = d.join(strata_beta.rename("strata_beta"), on=["moneyness", "expiry_choice"])
    d["O1_pred_strata"] = d.O0 + d.strata_beta * d.delta_S
    d["err_strata"] = d.O1_pred_strata - d.O1
    d["err_strata_pct"] = d.err_strata / d.O1 * 100

    for label, err_col, errpct_col in [("global-beta proxy", "err_global", "err_global_pct"),
                                         ("strata-conditional-beta proxy", "err_strata", "err_strata_pct")]:
        ae = d[err_col].abs()
        aep = d[errpct_col].abs()
        print(f"\n{label} (n={len(d)}):")
        print(f"  median abs error: Rs.{ae.median():.2f}   90th pct: Rs.{ae.quantile(.9):.2f}   95th pct: Rs.{ae.quantile(.95):.2f}")
        print(f"  median abs error %: {aep.median():.1f}%   90th pct: {aep.quantile(.9):.1f}%   95th pct: {aep.quantile(.95):.1f}%")


def report(df):
    print(f"\nRQ-OX1-A usable dataset: n={len(df)} (breach x moneyness/expiry combo rows)")
    print(f"Unique tickers: {df.ticker.nunique()}   Unique breach events: {df.groupby(['ticker','entry_date']).ngroups}")
    print(f"By pattern: {df.pattern.value_counts().to_dict()}")
    print("KNOWN LIMITATION: 100% calls (CE) -- no puts exist in this project's population, "
          "call/put stratification not testable.")

    report_layer1(df)
    report_layer2(df)
    report_layer3(df)
    report_proxy_error(df)


if __name__ == "__main__":
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    df = gather(tickers, verbose=True)
    df.to_csv("rq_ox1a_observability.csv", index=False)
    print("\nRaw dataset saved to rq_ox1a_observability.csv")
    report(df)
