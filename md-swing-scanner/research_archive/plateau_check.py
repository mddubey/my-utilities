"""Isolated research only (2026-09-12). Two things: (1) add sector_rs to the full
14,225-trade population (already validated for VCP trades elsewhere in this project --
checking here for the raw-trigger breakout_cont population instead). (2) A real plateau
check for RSI/momentum/sector_rs -- sweep several percentile thresholds, not just the one
quartile cut already shown, to confirm these are smooth, broad gradients and not a lucky
single-point spike."""
import warnings
warnings.filterwarnings("ignore")

import pandas as pd

from sector_strength import sector_rs

THRESHOLDS = [0.10, 0.20, 0.25, 0.30, 0.40, 0.50]


def add_sector_rs(df):
    secs, rss = [], []
    for _, r in df.iterrows():
        try:
            sec, rs = sector_rs(r.ticker, r.entry_date)
        except Exception:
            sec, rs = None, None
        secs.append(sec)
        rss.append(rs)
    df = df.copy()
    df["sector"] = secs
    df["sector_rs"] = rss
    return df


def plateau_sweep(df, feat, label, higher_is_fresh=False):
    print(f"\n=== {label} plateau sweep (feature: {feat}) ===")
    sub = df.dropna(subset=[feat])
    for pct in THRESHOLDS:
        cutoff = sub[feat].quantile(pct if not higher_is_fresh else 1 - pct)
        fresh = sub[sub[feat] <= cutoff] if not higher_is_fresh else sub[sub[feat] >= cutoff]
        win = (fresh.day1_pnl_pct > 0).mean() * 100
        med = fresh.day1_pnl_pct.median()
        print(f"  bottom {int(pct*100)}% (n={len(fresh)}): win {win:.1f}%  median {med:.2f}%")


if __name__ == "__main__":
    feat = pd.read_csv("runs/pre_entry_feature_check.csv", parse_dates=["entry_date"])
    print("Computing sector_rs for all", len(feat), "rows...")
    feat = add_sector_rs(feat)
    feat.to_csv("runs/pre_entry_feature_check_with_sector.csv", index=False)

    baseline_win = (feat.day1_pnl_pct > 0).mean() * 100
    baseline_med = feat.day1_pnl_pct.median()
    print(f"\nbaseline (n={len(feat)}): win {baseline_win:.1f}%  median {baseline_med:.2f}%")

    plateau_sweep(feat, "yday_rsi14", "RSI (lower = fresher)")
    plateau_sweep(feat, "yday_momentum_20d", "Momentum (lower = fresher)")
    plateau_sweep(feat, "sector_rs", "Sector RS (HIGHER = stronger sector)", higher_is_fresh=True)
