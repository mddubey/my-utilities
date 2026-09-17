"""Shared research-script utilities (2026-09-17, RQ-48/Update 48).

Introduced after finding that concentration() was independently re-defined in 19
separate research scripts, all sharing the same bug: a fixed top-10-trades count
that mechanically understates concentration for large n and overstates it for
small n (see FINDINGS.md, "Concentration metric bug" entry). Every NEW research
script should import from here rather than pasting its own helper defs.

Existing (frozen) research scripts are NOT being retrofitted wholesale -- per the
critic's "Versioned Metrics" governance (Update 48), concentration_v1 stays
available for reproducing old reports exactly; concentration_v2 (aliased here as
concentration) is the one new work should use.
"""
import numpy as np
import pandas as pd


def expectancy(pnl):
    """(win_rate * mean_win) + (loss_rate * mean_loss), on a pandas Series of % pnl."""
    pnl = pd.Series(pnl).dropna()
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    wr = len(wins) / len(pnl) if len(pnl) else float("nan")
    return wr * (wins.mean() if len(wins) else 0) + (1 - wr) * (losses.mean() if len(losses) else 0)


def win_rate(pnl):
    pnl = pd.Series(pnl).dropna()
    return (pnl > 0).mean() * 100 if len(pnl) else float("nan")


def concentration_v1(pnl):
    """HISTORICAL ONLY. Fixed top-10-trades count -- do not use in new research.
    Kept only so old critic write-ups / FINDINGS.md entries can be reproduced exactly."""
    s = pd.Series(pnl).dropna().abs()
    total = s.sum()
    return s.sort_values(ascending=False).head(10).sum() / total * 100 if total else float("nan")


def concentration_v2(pnl):
    """Production research metric. Top max(10, 10% of n) trades by |pnl| / total |pnl|.
    Scale-invariant (unlike v1): a 576-row population and its own 66-row sub-bucket
    now report comparable numbers instead of the sub-bucket looking artificially
    riskier purely because it has fewer rows to dilute the fixed top-10 against."""
    s = pd.Series(pnl).dropna().abs()
    total = s.sum()
    if not total:
        return float("nan")
    n = max(10, int(len(s) * 0.10))
    return s.sort_values(ascending=False).head(n).sum() / total * 100


concentration = concentration_v2  # the default for new work


def gini(pnl):
    """Gini coefficient of |pnl| across trades -- sample-size invariant, no arbitrary
    top-k cutoff. 0 = every trade contributes equally; 1 = one trade owns everything.
    Research-only diagnostic (critic, Update 48) -- complements, does not replace,
    concentration_v2."""
    s = np.sort(pd.Series(pnl).dropna().abs().values)
    n = len(s)
    if n == 0 or s.sum() == 0:
        return float("nan")
    cum = np.cumsum(s)
    return (n + 1 - 2 * (cum.sum() / cum[-1])) / n


def bootstrap_ci(pnl, statistic=win_rate, n_boot=2000, ci=0.90, seed=42):
    """Bootstrap confidence interval for a statistic (default win_rate) over a pnl
    Series. Use before trusting a small-n bucket result (critic, Update 48: "n=66 is
    exactly the kind of bucket where one regime can distort things -- I'd bootstrap
    it before believing it")."""
    pnl = pd.Series(pnl).dropna().values
    rng = np.random.default_rng(seed)
    n = len(pnl)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    boots = [statistic(pd.Series(rng.choice(pnl, size=n, replace=True))) for _ in range(n_boot)]
    lo_q, hi_q = (1 - ci) / 2, 1 - (1 - ci) / 2
    return statistic(pd.Series(pnl)), np.quantile(boots, lo_q), np.quantile(boots, hi_q)
