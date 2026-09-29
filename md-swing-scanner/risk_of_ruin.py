"""Deterministic, capacity-constrained R-multiple comparison — the standing methodology
used repeatedly since 2026-09-07 (Equity-side exit shape research) for comparing two
trade populations fairly when they have different trade COUNTS (a raw win-rate/median
comparison can't adjudicate "more trades at similar quality" vs "fewer trades at higher
quality" — this can). Reused for the Fixed-R exit rejection (2026-09-20) and the
Freshness<=0.40 capacity validation (2026-09-20) — this is the first time it's been
saved as a real, reusable module instead of rebuilt from scratch each time.

Methodology, unchanged from every prior use:
1. Convert pnl_pct to an R-multiple: R = pnl_pct / risk_pct_at_entry (the trade's own
   real risk at entry — e.g. entry-to-structural-stop distance — never a fixed guess).
2. Sort all trades by entry_date, chronologically.
3. Simulate a deterministic max-N-concurrent-positions cap: admit a new trade only if
   fewer than N are currently open, strict first-come-first-served by entry date, NO
   ranking or scoring of any kind (deliberate — avoids lookahead/selection-bias risk
   from picking "the best" candidate when several compete for the same open slot).
4. From the admitted trades' R sequence (exit-date order): cumulative R, max drawdown
   (off the R-equity curve), worst losing streak (consecutive-loss R sum).
"""
import pandas as pd
import numpy as np


def to_r_multiples(trades_df, risk_pct_col="risk_pct"):
    """trades_df must have pnl_pct and risk_pct_col (each trade's own real risk-at-entry,
    in percent, always positive). Returns a copy with an added 'r_multiple' column."""
    df = trades_df.copy()
    df["r_multiple"] = df["pnl_pct"] / df[risk_pct_col]
    return df


def capacity_constrained_backtest(trades_df, max_concurrent):
    """trades_df must have entry_date, exit_date, r_multiple. Deterministic FCFS
    admission by entry_date, no ranking. Returns a dict: n_total, n_admitted,
    cumulative_r, max_drawdown_r, worst_streak_r, worst_streak_n."""
    df = trades_df.sort_values("entry_date").reset_index(drop=True)
    open_positions = []  # list of exit_date for currently-open admitted trades
    admitted = []
    for _, row in df.iterrows():
        open_positions = [d for d in open_positions if d > row["entry_date"]]
        if len(open_positions) < max_concurrent:
            open_positions.append(row["exit_date"])
            admitted.append(row)
    adm = pd.DataFrame(admitted).sort_values("exit_date").reset_index(drop=True)
    if adm.empty:
        return dict(n_total=len(df), n_admitted=0, cumulative_r=0.0,
                    max_drawdown_r=0.0, worst_streak_r=0.0, worst_streak_n=0)

    equity = adm["r_multiple"].cumsum()
    peak = equity.cummax()
    dd = (equity - peak).min()

    # worst losing streak: longest run of consecutive r_multiple<=0, by its own R sum
    worst_streak_r = 0.0
    worst_streak_n = 0
    cur_r, cur_n = 0.0, 0
    for r in adm["r_multiple"]:
        if r <= 0:
            cur_r += r
            cur_n += 1
            if cur_r < worst_streak_r:
                worst_streak_r = cur_r
                worst_streak_n = cur_n
        else:
            cur_r, cur_n = 0.0, 0

    return dict(n_total=len(df), n_admitted=len(adm), cumulative_r=equity.iloc[-1],
                max_drawdown_r=dd, worst_streak_r=worst_streak_r, worst_streak_n=worst_streak_n)


def compare_at_slots(trades_df, slots=(3, 5, 10, 20, 50), risk_pct_col="risk_pct"):
    """Convenience wrapper: run capacity_constrained_backtest at several slot counts,
    return a DataFrame, one row per slot count."""
    r_df = to_r_multiples(trades_df, risk_pct_col)
    rows = []
    for n in slots:
        res = capacity_constrained_backtest(r_df, n)
        res["max_concurrent"] = n
        rows.append(res)
    return pd.DataFrame(rows)
