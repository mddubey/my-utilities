"""Translates the stock-level buffer-sweep results (floor_buffer_sweep.py) through real
option prices for ITM+current and ATM+current -- the two variants actually relevant to how this
gets traded. Reuses option_backtest.simulate_option_trade() unmodified: it only needs
ticker/entry_date/exit_date/entry_price/pnl_pct(stock, informational) per trade, which is
exactly the shape buffer_sweep's flat/ride CSVs are already in."""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import option_backtest


def to_option(df):
    df = df.copy()
    df["entry_date"] = pd.to_datetime(df.entry_date)
    df["exit_date"] = pd.to_datetime(df.exit_date)
    df["open_at_end"] = df.get("exit_reason", "") == "open_at_end"
    results, skipped = [], 0
    for _, trade in df.iterrows():
        r = option_backtest.simulate_option_trade(trade, "itm", "current")
        r2 = option_backtest.simulate_option_trade(trade, "atm", "current")
        if r is None and r2 is None:
            skipped += 1
        if r is not None:
            r["variant"] = "ITM+current"
            results.append(r)
        if r2 is not None:
            r2["variant"] = "ATM+current"
            results.append(r2)
    print(f"  ({skipped} trades had no valid liquid contract for either variant)")
    return pd.DataFrame(results)


def summarize(df, label):
    for variant in ["ITM+current", "ATM+current"]:
        sub = df[df.variant == variant]
        if sub.empty:
            print(f"{label} / {variant}: no trades")
            continue
        print(f"{label} / {variant}: n={len(sub)}  win {(sub.pnl_pct>0).mean()*100:.1f}%  "
              f"median {sub.pnl_pct.median():.2f}%  mean {sub.pnl_pct.mean():.2f}%")


if __name__ == "__main__":
    buffer_pct_bp = sys.argv[1] if len(sys.argv) > 1 else "10"  # matches int(b*1000) naming, e.g. 10 = 1.0%

    flat = pd.read_csv("runs/buffer_sweep_flat.csv")
    ride = pd.read_csv(f"runs/buffer_sweep_ride_{buffer_pct_bp}.csv")

    print("=== FLAT (sell at day1 open) -> options ===")
    flat_opt = to_option(flat)
    flat_opt.to_csv("runs/buffer_sweep_flat_opt.csv", index=False)
    summarize(flat_opt, "FLAT")

    print(f"\n=== RIDE buffer={int(buffer_pct_bp)/10:.1f}% -> options ===")
    ride_opt = to_option(ride)
    ride_opt.to_csv(f"runs/buffer_sweep_ride_{buffer_pct_bp}_opt.csv", index=False)
    summarize(ride_opt, "RIDE")
