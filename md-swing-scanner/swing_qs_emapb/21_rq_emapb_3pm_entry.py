"""RQ-EMAPB-3PM-01 -- realistic ~3pm entry clock + extension-above-box_high buckets (2026-10-06).

User's real execution constraint: trades are realistically placed around 3pm, not the instant
box_high breaks. Everything tested earlier this week (first-hour vs later-hour cross, instant-entry
MFE/MAE, EMA8 pullback) assumed near-instant execution. This rebuilds the baseline around the
actual constraint and tests whether chasing price that has already run above box_high by 3pm is
rewarded or punished.

Population: the FULLY UNFILTERED resumption population (no CLV gate, no gap condition) -- entry day
= first day after box confirmation where price has closed above box_high at any point up to and
including the 14:15 hourly bar (the ~3pm print). Entry price = that bar's Close.

Rule #22 data-quality note: ~1.4% of rows have an impossible entry_price/box_high ratio from
unadjusted corporate actions (stock splits/bonuses -- e.g. BAJFINANCE's mid-2024 1:4 split causing
box_high and entry_price to be pulled from inconsistently-adjusted series). Excluded via
|extension|>50% before any aggregate -- always re-check this filter still catches new instances
before trusting a future rerun.

Usage: python3 swing_qs_emapb/21_rq_emapb_3pm_entry.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
ENTRY_BAR_TIME = "14:15"  # the ~3pm hourly bar (covers 14:15-15:15); close of this bar = realistic fill
EXTENSION_OUTLIER_CUTOFF = 50  # |already_run_pct| beyond this is a data artifact, not a real move


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
    d["bar_time"] = d.index.strftime("%H:%M")
    return d.reset_index(drop=True)


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def build(pop):
    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        peak_date = pd.Timestamp(r.peak_date)
        pm = daily.index[daily.Date == peak_date]
        if len(pm) == 0 or pd.isna(r.consolidation_start_days):
            continue
        peak_i = int(pm[0]); consolidation_start_i = peak_i + int(r.consolidation_start_days)
        box_span_end = consolidation_start_i + 3
        if box_span_end >= len(daily):
            continue
        obs_start_date = daily.Date.iloc[box_span_end]
        box_high = r.box_high

        osm = h1.index[h1.session_date >= obs_start_date]
        if len(osm) == 0:
            continue
        search = h1.iloc[osm[0]:osm[0] + 300]
        search_upto3 = search[search.bar_time <= ENTRY_BAR_TIME]
        ci = search_upto3.index[search_upto3.Close > box_high]
        if len(ci) == 0:
            continue
        entry_day = h1.session_date.iloc[int(ci[0])]
        pm3 = h1.index[(h1.session_date == entry_day) & (h1.bar_time == ENTRY_BAR_TIME)]
        if len(pm3) == 0:
            continue
        entry_i = int(pm3[0])
        entry_price = h1.Close.iloc[entry_i]

        dm = daily.index[daily.Date == entry_day]
        if len(dm) == 0:
            continue
        iD = int(dm[0])
        if iD + 1 >= len(daily):
            continue
        day_close = daily.Close.iloc[iD]
        d1_open = daily.Open.iloc[iD + 1]; d1_close = daily.Close.iloc[iD + 1]
        d1_date = daily.Date.iloc[iD + 1]

        end_mask = h1.index[(h1.session_date > d1_date)]
        end_i = int(end_mask[0]) if len(end_mask) else len(h1)
        window = h1.iloc[entry_i:end_i]
        peak_price = window.High.max() if not window.empty else entry_price
        mae_price = window.Low.min() if not window.empty else entry_price

        rows.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high, entry_price=entry_price,
            day_close_ret=(day_close / entry_price - 1) * 100,
            d1_open_ret=(d1_open / entry_price - 1) * 100,
            d1_close_ret=(d1_close / entry_price - 1) * 100,
            peak_ret=(peak_price / entry_price - 1) * 100,
            mae_ret=(mae_price / entry_price - 1) * 100,
        ))
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop):,}")
    return pd.DataFrame(rows)


def randomization_test(y, group_bool, n=2000, seed=2026):
    rng = np.random.RandomState(seed)
    obs = y[group_bool].mean() - y[~group_bool].mean()
    diffs = np.empty(n)
    for i in range(n):
        perm = rng.permutation(group_bool)
        diffs[i] = y[perm].mean() - y[~perm].mean()
    p = (np.abs(diffs) >= abs(obs)).mean()
    return obs, np.percentile(np.abs(diffs), 95), p


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop_all = pop[(pop.outcome == "consolidation_resumption") &
                  (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"Fully unfiltered resumption population with 1H coverage: {len(pop_all):,}")

    df = build(pop_all)
    df.to_csv(f"{HERE}/rq_emapb_3pm_entry_returns.csv", index=False)
    print(f"\nn processed (3pm-entry): {len(df):,}\n")

    df["already_run_pct"] = (df.entry_price / df.box_high - 1) * 100
    before = len(df)
    df = df[df.already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"Excluded {before - len(df)} corporate-action data artifacts "
          f"(|already_run_pct|>{EXTENSION_OUTLIER_CUTOFF}%). n={len(df):,} remain.\n")

    df["below"] = df.already_run_pct < 0
    df["d1_close_pos"] = (df.d1_close_ret > 0).astype(int)
    bins = [-100, 0, 1, 2, 3, 5, 100]
    labels = ["below_box_high", "0-1pct", "1-2pct", "2-3pct", "3-5pct", "5pct_plus"]
    df["bucket"] = pd.cut(df.already_run_pct, bins=bins, labels=labels)

    print("=== Extension-above-box_high buckets (D1-close win rate) ===")
    for b in labels:
        g = df[df.bucket == b]
        if g.empty:
            continue
        print(f"  {b:16} n={len(g):6,} ({len(g)/len(df)*100:4.1f}%)  "
              f"D1open={g.d1_open_ret.median():+.2f}%/{(g.d1_open_ret>0).mean()*100:.1f}%  "
              f"D1close={g.d1_close_ret.median():+.2f}%/{(g.d1_close_ret>0).mean()*100:.1f}%  "
              f"peak={g.peak_ret.median():+.2f}%  worst={g.mae_ret.median():+.2f}%")

    y = df.d1_close_pos.values
    is_below = df.below.values
    obs, p95, p = randomization_test(y, is_below)
    print(f"\n=== Randomization: below_box_high vs rest, D1-close win rate ===")
    print(f"observed={obs*100:+.2f}pp  null p95={p95*100:.2f}pp  p={p:.4f}")

    pop_clv = pop[["ticker", "a_entry_date", "clv"]]
    dfc = df.merge(pop_clv, on=["ticker", "a_entry_date"], how="left")
    print("\n=== Robustness: by CLV band ===")
    for label, mask in [("CLV>=0.80", dfc.clv >= 0.80), ("CLV<0.80", dfc.clv < 0.80)]:
        g = dfc[mask]
        obs, p95, p = randomization_test(g.d1_close_pos.values, g.below.values)
        print(f"  {label:10} n={len(g):6,}  observed={obs*100:+.2f}pp  null p95={p95*100:.2f}pp  p={p:.4f}")

    dfc["year"] = pd.to_datetime(dfc.a_entry_date).dt.year
    print("\n=== Robustness: by year (not pooled) ===")
    for yr, g in dfc.groupby("year"):
        if len(g) < 200:
            continue
        below_rate = g[g.below].d1_close_pos.mean() * 100
        rest_rate = g[~g.below].d1_close_pos.mean() * 100
        print(f"  {yr}  n={len(g):6,}  below={below_rate:.1f}%  rest={rest_rate:.1f}%  "
              f"spread={below_rate-rest_rate:+.1f}pp")


if __name__ == "__main__":
    main()
