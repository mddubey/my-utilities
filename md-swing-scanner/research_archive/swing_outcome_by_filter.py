"""Isolated research only (2026-09-12). Does the SAME entry population (honest,
base_filters_pass + intraday breach, no checklist_pass) also show a better SWING/STOCK
outcome -- using the real multi-day check_exit() logic (resistance/stop/climax), not the
day+1-open metric everything else today has used -- when filtered by RSI/momentum
freshness or consolidation days? Two fully separate strategies, two fully separate exit
mechanisms, same entry filters tested against both.
"""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

import backtest
from pivots import daily_pivots

TRIGGER_CLEARANCE = 1.005


def simulate_swing(ticker, entry_i, entry_price, rows):
    state = dict(entry_price=entry_price, peak_close=entry_price, peak_high=entry_price,
                 structural_low=0.0, target=None)
    for j in range(entry_i + 1, len(rows)):
        row = rows.iloc[j]
        if row.corp_action_day:
            prev = rows.iloc[j - 1]
            return dict(exit_date=prev.Date, exit_price=state["peak_close"],
                       exit_reason="corp_action", holding_days=j - entry_i, open_at_end=False)
        exit_reason, state = backtest.check_exit("breakout_cont", state, row, use_resistance=True)
        if exit_reason is not None:
            return dict(exit_date=row.Date, exit_price=row.Close, exit_reason=exit_reason,
                       holding_days=j - entry_i, open_at_end=False)
    last = rows.iloc[-1]
    return dict(exit_date=last.Date, exit_price=last.Close, exit_reason="open",
               holding_days=len(rows) - 1 - entry_i, open_at_end=True)


def run():
    feat = pd.read_csv("runs/consolidation_and_room.csv", parse_dates=["entry_date"])
    feat = feat.dropna(subset=["consolidation_days"]).copy()
    feat["rsi_pct"] = feat.yday_rsi14.rank(pct=True)
    feat["mom_pct"] = feat.yday_momentum_20d.rank(pct=True)
    feat["freshness"] = 0.5 * feat.rsi_pct + 0.5 * feat.mom_pct

    cache = {}
    results = []
    for _, r in feat.iterrows():
        if r.ticker not in cache:
            cache[r.ticker] = backtest.load(r.ticker, daily_pivots).reset_index()
        rows = cache[r.ticker]
        idx = rows.index[rows.Date == r.entry_date]
        if len(idx) == 0:
            continue
        i = idx[0]
        trigger_price = rows.iloc[i].high10_prior * TRIGGER_CLEARANCE
        out = simulate_swing(r.ticker, i, trigger_price, rows)
        pnl_pct = (out["exit_price"] / trigger_price - 1) * 100
        results.append(dict(ticker=r.ticker, entry_date=r.entry_date, freshness=r.freshness,
                           consolidation_days=r.consolidation_days, pnl_pct=pnl_pct,
                           holding_days=out["holding_days"], exit_reason=out["exit_reason"],
                           open_at_end=out["open_at_end"]))

    out_df = pd.DataFrame(results)
    out_df.to_csv("runs/swing_outcome_by_filter.csv", index=False)
    closed = out_df[~out_df.open_at_end]

    def stats(sub, label):
        c = sub[~sub.open_at_end]
        win = (c.pnl_pct > 0).mean() * 100
        med = c.pnl_pct.median()
        hold = c.holding_days.median()
        reasons = c.exit_reason.value_counts(normalize=True).mul(100).round(1).to_dict()
        print(f"  {label} (n={len(c)}, {sub.open_at_end.sum()} still open): win {win:.1f}%  median {med:.2f}%  "
              f"median hold {hold:.0f}d  exits {reasons}")

    print(f"n = {len(out_df)} ({out_df.open_at_end.sum()} still open at data end)")
    print(f"\n=== BASELINE (all) ===")
    stats(out_df, "all")

    print(f"\n=== By FRESHNESS ===")
    stats(out_df[out_df.freshness <= out_df.freshness.quantile(0.25)], "fresh (bottom 25%)")
    stats(out_df[out_df.freshness > out_df.freshness.quantile(0.75)], "extended (top 25%)")

    print(f"\n=== By CONSOLIDATION DAYS ===")
    stats(out_df[out_df.consolidation_days <= 2], "0-2 days")
    stats(out_df[out_df.consolidation_days >= 6], "6+ days")

    print(f"\n=== Combined ===")
    combo_good = out_df[(out_df.freshness <= out_df.freshness.quantile(0.25)) & (out_df.consolidation_days >= 6)]
    combo_bad = out_df[(out_df.freshness > out_df.freshness.quantile(0.75)) & (out_df.consolidation_days <= 2)]
    stats(combo_good, "fresh AND consolidated 6+")
    stats(combo_bad, "extended AND no consolidation")


if __name__ == "__main__":
    run()
