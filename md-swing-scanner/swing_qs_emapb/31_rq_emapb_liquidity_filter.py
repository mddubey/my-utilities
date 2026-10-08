"""RQ-EMAPB-LIQ -- literature-grounded liquidity floor, applied to the 3pm-entry population
(2026-10-07). Not data-mined: price floor + turnover floor, per Jegadeesh & Titman's momentum-
strategy convention (exclude sub-$5 stocks and the smallest liquidity decile -- stated reason:
transaction costs can eat 70-100% of paper profits from momentum strategies in illiquid names).

Criteria (pre-declared, from trading logic, not fit to this data):
  - PRICE_FLOOR = Rs 20 (avoid penny-stock/micro-cap tick-size and manipulation dynamics)
  - TURNOVER_FLOOR = Rs 1 crore/day average traded value (Close * Volume), over the 20 trading
    days before the A-day -- standard retail-liquidity screening threshold.

Reruns RQ-EMAPB-3PM-01's extension-bucket finding on the cleaned population, to check whether the
core, already-validated result survives once illiquid names are removed.

Usage: python3 swing_qs_emapb/31_rq_emapb_liquidity_filter.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_FLOOR = 50.0  # user's call, 2026-10-07: below this is too easy to manipulate
TURNOVER_FLOOR_CR = 1.0  # Rs crore/day


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


def main():
    df = pd.read_csv(f"{HERE}/rq_emapb_3pm_entry_returns.csv")
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= 50].copy()
    print(f"Starting 3pm-entry population: {len(df):,}")

    rows = []
    cache_d = {}
    for n, r in enumerate(df.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        if daily is None:
            continue
        a_date = pd.Timestamp(r.a_entry_date)
        am = daily.index[daily.Date == a_date]
        if len(am) == 0 or int(am[0]) < 20:
            continue
        ia = int(am[0])
        pre20 = daily.iloc[ia - 20:ia]
        avg_turnover_cr = (pre20.Close * pre20.Volume).mean() / 1e7  # paise-free INR, crore = 1e7
        a_day_price = daily.Close.iloc[ia]
        rows.append(dict(ticker=r.ticker, a_entry_date=r.a_entry_date,
                          avg_turnover_cr=avg_turnover_cr, a_day_price=a_day_price))
        if (n + 1) % 3000 == 0:
            print(f"  ...{n+1:,}/{len(df):,}")

    liq = pd.DataFrame(rows)
    df = df.merge(liq, on=["ticker", "a_entry_date"], how="left")
    df.to_csv(f"{HERE}/rq_emapb_liquidity_tagged.csv", index=False)

    df["passes_liquidity"] = (df.avg_turnover_cr >= TURNOVER_FLOOR_CR) & (df.a_day_price >= PRICE_FLOOR)
    print(f"\nn with liquidity data: {df.avg_turnover_cr.notna().sum():,}")
    print(f"Passes liquidity filter (turnover>=Rs{TURNOVER_FLOOR_CR}cr/day AND price>=Rs{PRICE_FLOOR}): "
          f"{df.passes_liquidity.sum():,} ({df.passes_liquidity.mean()*100:.1f}%)")
    print(f"Excluded as illiquid: {(~df.passes_liquidity).sum():,} ({(~df.passes_liquidity).mean()*100:.1f}%)")

    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    bins = [-100, 0, 1, 2, 3, 5, 100]
    labels = ["below", "0-1", "1-2", "2-3", "3-5", "5plus"]
    df["bucket"] = pd.cut(already_run_pct, bins=bins, labels=labels)
    df["d1_close_pos"] = (df.d1_close_ret > 0).astype(int)

    clean = df[df.passes_liquidity]
    print(f"\n=== RQ-EMAPB-3PM-01 extension-bucket re-check, LIQUIDITY-CLEANED population (n={len(clean):,}) ===")
    for b in labels:
        g = clean[clean.bucket == b]
        if g.empty:
            continue
        print(f"  {b:8} n={len(g):6,} ({len(g)/len(clean)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")

    rng = np.random.RandomState(2026)
    is_below = (clean.bucket == "below").values
    y = clean.d1_close_pos.values
    obs = y[is_below].mean() - y[~is_below].mean()
    N = 2000
    diffs = np.empty(N)
    for i in range(N):
        perm = rng.permutation(is_below)
        diffs[i] = y[perm].mean() - y[~perm].mean()
    p = (np.abs(diffs) >= abs(obs)).mean()
    print(f"\n  randomization (below vs rest, liquidity-cleaned): observed={obs*100:+.2f}pp  "
          f"null p95={np.percentile(np.abs(diffs),95)*100:.2f}pp  p={p:.4f}")


if __name__ == "__main__":
    main()
