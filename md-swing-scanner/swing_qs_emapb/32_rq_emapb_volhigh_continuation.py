"""RQ-EMAPB-17/18 -- two open hypotheses from the chart audit, tested properly (2026-10-07).

Both are user-specified, pre-declared BEFORE seeing results (not data-mined), on the liquidity-
cleaned population (price>=Rs50, turnover>=Rs1cr/day, per the adopted standing filter).

RQ-17 -- "today's volume must be an N-day volume high": is the existing ratio-to-average gate
(vol_ratio_10d >= 1.5x) gameable during a general volume uptrend (ATLANTAA's actual failure mode --
its A-day volume was LOWER than the prior 2 days, yet still cleared 1.5x of an already-depressed
10-day average)? Test: among A-pass episodes, split by whether the A-day's volume is ALSO the
highest in the trailing 10 days (a genuine volume breakout) vs not, and compare outcomes.

RQ-18 -- "exclude continuation-style A-days": LLOYDSENGG's tagged A-day was a second leg of an
already-extended move; the real, more convincing breakout happened 5 trading days earlier and
fully qualified on its own. Different from the already-closed near-miss test (which asked about
days that almost-but-didn't qualify) -- this asks whether a FULLY QUALIFYING prior A-day existed
for the same ticker within the trailing 10 days, and whether that predicts a worse outcome ("this
is just riding an already-extended move" vs "this is a genuinely fresh setup").

Usage: python3 swing_qs_emapb/32_rq_emapb_volhigh_continuation.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_FLOOR = 50.0
TURNOVER_FLOOR_CR = 1.0
LOOKBACK_DAYS = 10


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    d["prior10high"] = d.High.rolling(LOOKBACK_DAYS).max().shift(1)
    d["prior10vol"] = d.Volume.rolling(LOOKBACK_DAYS).mean().shift(1)
    d["vol_ratio"] = d.Volume / d.prior10vol
    d["qualifies"] = (d.High > d.prior10high) & (d.vol_ratio >= 1.5) & (d.Close > d.Open)
    return d


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
    liq = pd.read_csv(f"{HERE}/rq_emapb_liquidity_tagged.csv")
    already_run_pct = (liq.entry_price / liq.box_high - 1) * 100
    liq = liq[already_run_pct.abs() <= 50].copy()
    liq["passes_liquidity"] = (liq.avg_turnover_cr >= TURNOVER_FLOOR_CR) & (liq.a_day_price >= PRICE_FLOOR)
    clean = liq[liq.passes_liquidity].copy()
    print(f"Liquidity-cleaned 3pm-entry population: {len(clean):,}")

    rows = []
    cache_d = {}
    for n, r in enumerate(clean.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        if daily is None:
            continue
        a_date = pd.Timestamp(r.a_entry_date)
        am = daily.index[daily.Date == a_date]
        if len(am) == 0 or int(am[0]) < LOOKBACK_DAYS:
            continue
        ia = int(am[0])

        a_day = daily.iloc[ia]
        prior_window = daily.iloc[max(0, ia - LOOKBACK_DAYS):ia]
        is_vol_high = a_day.Volume > prior_window.Volume.max() if not prior_window.empty else None

        lookback = daily.iloc[max(0, ia - LOOKBACK_DAYS):ia]
        had_prior_qualifying = bool(lookback.qualifies.any()) if not lookback.empty else False

        rows.append(dict(ticker=r.ticker, a_entry_date=r.a_entry_date,
                          is_vol_high=is_vol_high, had_prior_qualifying=had_prior_qualifying,
                          d1_close_ret=r.d1_close_ret))
        if (n + 1) % 3000 == 0:
            print(f"  ...{n+1:,}/{len(clean):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb_volhigh_continuation.csv", index=False)
    df["d1_close_pos"] = (df.d1_close_ret > 0).astype(int)
    print(f"\nn processed: {len(df):,}\n")

    print("=== RQ-17: is the A-day's volume also the highest in the trailing 10 days? ===")
    for label, mask in [("Is a 10-day volume high", df.is_vol_high == True),
                         ("NOT a 10-day volume high (ratio-gate only)", df.is_vol_high == False)]:
        g = df[mask]
        print(f"  {label:44} n={len(g):6,} ({len(g)/len(df)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")
    sub = df[df.is_vol_high.notna()]
    obs, p95, p = randomization_test(sub.d1_close_pos.values, (sub.is_vol_high == True).values)
    print(f"  randomization: observed={obs*100:+.2f}pp  null p95={p95*100:.2f}pp  p={p:.4f}")

    print("\n=== RQ-18: was there a FULLY QUALIFYING prior A-day in the trailing 10 days? ===")
    for label, mask in [("Fresh (no prior qualifying A-day)", ~df.had_prior_qualifying),
                         ("Continuation (a prior A-day already qualified)", df.had_prior_qualifying)]:
        g = df[mask]
        print(f"  {label:48} n={len(g):6,} ({len(g)/len(df)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")
    obs2, p95_2, p2 = randomization_test(df.d1_close_pos.values, df.had_prior_qualifying.values)
    print(f"  randomization: observed={obs2*100:+.2f}pp  null p95={p95_2*100:.2f}pp  p={p2:.4f}")


if __name__ == "__main__":
    main()
