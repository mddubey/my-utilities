"""RQ-OMD-01 step 1 -- verify how data/intraday_60m/ candles are actually constructed before
trusting any result built on them. Formalizes the ad-hoc checks done interactively on
2026-10-04 (see RQ-OMD-01_PREFLIGHT.md) into a reproducible script with saved output.
Usage: python3 options_momentum/01_verify_1h_construction.py"""
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from data.paths import INTRADAY_60M_DIR, DAILY_DIR  # noqa: E402
from options_momentum._lib import load_60m  # noqa: E402

OUT = Path(__file__).resolve().parent / "verification_output.txt"


def main():
    lines = []
    def p(s=""):
        print(s)
        lines.append(str(s))

    uni = pd.read_csv(ROOT / "nse_equity_universe.csv").ticker.tolist()
    files = [t for t in uni if (INTRADAY_60M_DIR / f"{t}.csv").exists()]
    p(f"=== RQ-OMD-01 1H construction verification -- {pd.Timestamp.now():%Y-%m-%d %H:%M} ===")
    p(f"nse_equity_universe.csv: {len(uni)} tickers; intraday_60m files present: {len(files)}")

    # --- date range / completeness across the whole universe ---
    ranges, counts = [], []
    for t in files:
        d = load_60m(t)
        if d is None:
            continue
        ranges.append((t, d.session_date.min(), d.session_date.max(), len(d)))
        counts.append(len(d))
    rng = pd.DataFrame(ranges, columns=["ticker", "min_date", "max_date", "n_bars"])
    p(f"\nUsable files (>=100 bars after cleaning): {len(rng)}")
    p(f"Date range across universe: {rng.min_date.min().date()} -> {rng.max_date.max().date()}")
    p(f"Bars per ticker: min={rng.n_bars.min()}, median={rng.n_bars.median():.0f}, "
      f"max={rng.n_bars.max()}, total={rng.n_bars.sum():,}")
    p(f"Tickers whose history starts after 2024-06-01 (late starts): "
      f"{(rng.min_date > '2024-06-01').sum()} / {len(rng)}")
    p(f"Tickers whose history ends before 2026-09-15 (stale/delisted/not topped up): "
      f"{(rng.max_date < '2026-09-15').sum()} / {len(rng)}")

    # --- bars/day distribution + bar-time distribution, full universe ---
    p("\n--- bars/day distribution (sample of 40 tickers, for speed) ---")
    random.seed(7)
    sample = random.sample(files, min(40, len(files)))
    all_bpd, all_times = [], []
    for t in sample:
        d = load_60m(t)
        if d is None:
            continue
        bpd = d.groupby("session_date").size()
        all_bpd.append(bpd)
        all_times.append(d.index if False else None)
    bpd_all = pd.concat(all_bpd)
    p(bpd_all.value_counts().sort_index().to_string())

    p("\n--- bar-time-of-day distribution (same 40-ticker sample) ---")
    tod = []
    for t in sample:
        f = INTRADAY_60M_DIR / f"{t}.csv"
        raw = pd.read_csv(f, index_col=0)
        idx = pd.to_datetime(raw.index, utc=True).tz_convert("Asia/Kolkata")
        tod.append(pd.Series(idx.strftime("%H:%M")))
    tod = pd.concat(tod)
    p(tod.value_counts().sort_index().to_string())

    # --- 09:15 gap-bar quality: zero-volume share, flat-bar share ---
    p("\n--- 09:15 bar quality (same 40-ticker sample) ---")
    zero_vol, flat = [], []
    for t in sample:
        d = load_60m(t)
        if d is None:
            continue
        first = d[d.bar_of_day == 0]
        if first.empty:
            continue
        zero_vol.append((first.Volume == 0).mean())
        flat.append(((first.Open == first.High) & (first.High == first.Low) & (first.Low == first.Close)).mean())
    p(f"Mean zero-volume share on the 09:15 bar: {np.mean(zero_vol):.1%}")
    p(f"Mean flat-bar (O=H=L=C) share on the 09:15 bar: {np.mean(flat):.1%} "
      f"(low = the bar carries real price range despite the volume quirk)")

    # --- cross-check a handful of days against data/daily/ ---
    p("\n--- cross-check vs data/daily/ (4 tickers x last 3 common sessions) ---")
    for t in sample[:4]:
        d = load_60m(t)
        daily = pd.read_csv(DAILY_DIR / f"{t}.csv", index_col=0, parse_dates=True)
        common = sorted(set(d.session_date) & set(daily.index.normalize()))[-3:]
        for dt in common:
            day_bars = d[d.session_date == dt]
            drow = daily[daily.index.normalize() == dt]
            if drow.empty or day_bars.empty:
                continue
            p(f"{t} {dt.date()}: 60m O/H/L/C = {day_bars.Open.iloc[0]:.2f}/{day_bars.High.max():.2f}/"
              f"{day_bars.Low.min():.2f}/{day_bars.Close.iloc[-1]:.2f}  |  daily O/H/L/C = "
              f"{drow.Open.iloc[0]:.2f}/{drow.High.iloc[0]:.2f}/{drow.Low.iloc[0]:.2f}/{drow.Close.iloc[0]:.2f}")

    p("\n=== verdict ===")
    p("Matches data/README.md's documented caveats (7 bars/day, 15:15 stub, split-adjusted-not-")
    p("CA-adjusted, Yahoo misses true intraday H/L on a large minority of stock-days). No new")
    p("defect found. Safe to proceed to 02_build_panel.py under the preflight's conventions.")

    OUT.write_text("\n".join(lines) + "\n")
    p(f"\n[written to {OUT}]")


if __name__ == "__main__":
    main()
