"""Isolated research only (2026-09-14+). RQ-43A -- VCP Stop Geometry Audit, critic's
priority item after the SMA21/Family-C work. Production is currently asymmetric:
Breakout Continuation uses a 3xATR trailing stop, VCP/Coiled Spring uses the real
structural base low (capped at MAX_INITIAL_RISK_PCT=0.08, Minervini's published max-risk
rule) -- has never been audited whether that asymmetry is actually justified.

Critic's exact prediction: BC's structural low is much WIDER than 3xATR (already found:
median ~14.8% vs ~8.7%); VCP's structural low should be roughly SIMILAR to ATR, because
VCP's base geometry is already volatility-compressed by construction (a tightening base
by definition sits close to price). If true, the asymmetry is justified; if false, VCP
has the same "accidentally positional" problem BC's structural stop had, undetected so far
because nobody's checked.

Measures for every VCP live-equivalent trade (base_pivot() + intraday-equivalent High
cross, no vol_zscore gate, LAST_LEG_TOLERANCE=0.40 matching production, freshness<=0.40):
structural stop distance %, 3xATR distance % (hypothetical, for comparison only -- VCP
doesn't actually use this), ratio structural/ATR, MAE, stop-out rate, holding
distribution (median/p90/max), and real win/expectancy performance -- all with
MAX_HOLD_DAYS=15 already applied, since that's now a permanent part of check_exit().
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots
from vcp import base_pivot
from live_checkpoint import _percentile_from_breaks, RSI_PCT_BREAKS, MOMENTUM_PCT_BREAKS

TRIGGER_CLEARANCE = 1.005
MAX_INITIAL_RISK_PCT = 0.08

daily_cache = {}


def load_daily(ticker):
    if ticker not in daily_cache:
        daily_cache[ticker] = backtest.load(ticker, daily_pivots).reset_index()
    return daily_cache[ticker]


def freshness(rsi14, mom20):
    if pd.isna(rsi14) or pd.isna(mom20):
        return None
    return 0.5 * _percentile_from_breaks(rsi14, RSI_PCT_BREAKS) + 0.5 * _percentile_from_breaks(mom20, MOMENTUM_PCT_BREAKS)


def simulate(daily, i, trigger, structural_low_capped):
    """Real production VCP exit: check_exit('coiled_spring', ...) with MAX_HOLD_DAYS=15
    already baked into check_exit() itself -- no need to add it separately here."""
    state = dict(entry_price=trigger, peak_close=trigger, peak_high=trigger,
                  structural_low=structural_low_capped, target=None, days_held=0)
    mae_r = 0.0
    atr_entry = daily.iloc[i].atr14
    R = backtest.ATR_TRAIL_MULT * atr_entry if atr_entry else None
    exit_price, exit_reason, hold_days = None, None, None
    for j in range(i + 1, len(daily)):
        row = daily.iloc[j]
        if R:
            mae_r = max(mae_r, (trigger - row.Low) / R)
        if row.corp_action_day:
            exit_price, exit_reason = state["peak_close"], "corp_action"
            hold_days = j - i
            break
        exit_reason_here, state = backtest.check_exit("coiled_spring", state, row, use_resistance=True)
        if exit_reason_here is not None:
            exit_price, exit_reason, hold_days = row.Close, exit_reason_here, j - i
            break
    if exit_price is None:
        exit_price, exit_reason, hold_days = daily.iloc[-1].Close, "open_at_end", len(daily) - 1 - i
    return dict(pnl_pct=(exit_price / trigger - 1) * 100, exit_reason=exit_reason, hold_days=hold_days, mae_r=mae_r)


def run():
    df = pd.read_csv("runs/vcp_live_equiv_tol_0.4.csv", parse_dates=["entry_date"])
    print(f"n (VCP live-equivalent, tol=0.4) = {len(df)}")

    rows = []
    for idx, r in enumerate(df.itertuples(), 1):
        if idx % 1000 == 0:
            print(f"  {idx}/{len(df)}", flush=True)
        daily = load_daily(r.ticker)
        match = daily.index[daily.Date == r.entry_date]
        if len(match) == 0:
            continue
        i = match[0]
        row = daily.iloc[i]

        rsi14 = row.get("rsi14", None)
        close_20ago = row.get("close_20ago", None)
        mom20 = ((row.Close / close_20ago - 1) * 100) if close_20ago else None
        fscore = freshness(rsi14, mom20)

        base = base_pivot(daily, i)
        if base is None:
            continue
        pivot, structural_low = base
        trigger = pivot * TRIGGER_CLEARANCE
        structural_low_capped = max(structural_low, trigger * (1 - MAX_INITIAL_RISK_PCT))

        atr_entry = row.atr14
        if not atr_entry or pd.isna(atr_entry):
            continue
        struct_dist_pct = (trigger - structural_low_capped) / trigger * 100
        atr_dist_pct = (backtest.ATR_TRAIL_MULT * atr_entry) / trigger * 100
        ratio = struct_dist_pct / atr_dist_pct if atr_dist_pct else None
        capped_by_8pct = abs(structural_low_capped - structural_low) > 0.01

        res = simulate(daily, i, trigger, structural_low_capped)
        rows.append(dict(ticker=r.ticker, entry_date=r.entry_date, freshness_score=fscore,
                          struct_dist_pct=struct_dist_pct, atr_dist_pct=atr_dist_pct, ratio=ratio,
                          capped_by_8pct=capped_by_8pct, **res))

    out = pd.DataFrame(rows)
    out.to_csv("runs/vcp_stop_geometry_audit.csv", index=False)
    print(f"n with data = {len(out)}\n")

    print("=== Full population (all freshness) ===")
    report(out)
    fresh = out.dropna(subset=["freshness_score"])
    fresh = fresh[fresh.freshness_score <= 0.40]
    print(f"\n=== Freshness<=0.40 subset (n={len(fresh)}) ===")
    report(fresh)


def report(sub):
    print(f"  n = {len(sub)}")
    print(f"  structural stop distance %: median={sub.struct_dist_pct.median():.2f}  mean={sub.struct_dist_pct.mean():.2f}")
    print(f"  3xATR distance % (hypothetical): median={sub.atr_dist_pct.median():.2f}  mean={sub.atr_dist_pct.mean():.2f}")
    print(f"  ratio structural/ATR: median={sub.ratio.median():.2f}  mean={sub.ratio.mean():.2f}")
    print(f"  structural WIDER than 3xATR in: {(sub.ratio > 1).mean()*100:.1f}% of trades")
    print(f"  capped by the 8%-max-risk rule in: {sub.capped_by_8pct.mean()*100:.1f}% of trades")
    print(f"  mean MAE (R-multiples, R=3xATR): {sub.mae_r.mean():.3f}")
    wins = sub[sub.pnl_pct > 0].pnl_pct
    losses = sub[sub.pnl_pct <= 0].pnl_pct
    wr = len(wins) / len(sub) * 100
    exp = (wr / 100) * (wins.mean() if len(wins) else 0) + (1 - wr / 100) * (losses.mean() if len(losses) else 0)
    stop_pct = (sub.exit_reason == "stop").mean() * 100
    cap_pct = (sub.exit_reason == "max_hold_cap").mean() * 100
    print(f"  win={wr:.1f}%  median={sub.pnl_pct.median():+.2f}%  expectancy={exp:+.3f}%")
    print(f"  stop-out rate={stop_pct:.1f}%  hit-max-hold-cap rate={cap_pct:.1f}%")
    print(f"  hold days (median/p90/max): {sub.hold_days.median():.0f}/{sub.hold_days.quantile(0.9):.0f}/{sub.hold_days.max():.0f}")


if __name__ == "__main__":
    run()
