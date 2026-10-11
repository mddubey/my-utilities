"""RQ-EMAPB-19 -- Breakout Effort/Result Proportionality (critic-specified, 2026-10-11).

Hypothesis: a breakout is less trustworthy when its price-range expansion is large relative to
its TURNOVER (traded value) expansion -- not raw volume vs a flat average (which ATLANTAA and
FORCEMOT both showed is gameable by a quiet rolling baseline and doesn't account for the stock's
own price scale/volatility), but turnover expansion normalized against the stock's own recent
range/volatility.

Frozen, pre-registered per critic -- no threshold sweep, no modification to the existing 1.5x
volume gate during this test:
  - Baselines: median over the 20 completed trading sessions before A-day, EXCLUDING A-day itself
    (median, not mean, to avoid the same "quiet rolling average" problem RQ-17 was built to catch).
  - turnover_multiple = A-day traded value (Close*Volume) / median(prior-20-day traded value)
  - True Range (TR) = day's range including any gap vs prior close, as a % of prior close:
    TR_pct = (max(High, prevClose) - min(Low, prevClose)) / prevClose * 100
  - range_multiple = A-day TR_pct / median(prior-20-day TR_pct)
  - Q = turnover_multiple / range_multiple  (Q~1: proportional; Q<1: range expanded more than
    turnover; Q>1: turnover expanded more than range)
  - Candle quality (retained separately, not folded into Q): CLV (already computed elsewhere),
    body_pct_of_range, upper_wick_pct_of_range.
  - Guardrail: if the prior-20-day baseline (turnover or TR) is zero/missing, the observation is
    INVALID -- excluded, never assigned an extreme Q score.

Pre-registered outputs: Q vs D1-close return/win-rate (continuous + the one fixed Q<1 vs Q>=1
split, no cutoff search afterward), MAE/MFE/downside tails by group, year-by-year check.

Usage: python3 swing_qs_emapb/33_rq_emapb19_effort_result_proportionality.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
PRICE_FLOOR = 50.0
TURNOVER_FLOOR_CR = 1.0
BASELINE_DAYS = 20


def load_daily(ticker):
    f = f"data/daily/{ticker}.csv"
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d.Date)
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    d["prev_close"] = d.Close.shift(1)
    d["tr_pct"] = (pd.concat([d.High, d.prev_close], axis=1).max(axis=1) -
                   pd.concat([d.Low, d.prev_close], axis=1).min(axis=1)) / d.prev_close * 100
    d["turnover"] = d.Close * d.Volume
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
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    already_run_pct = (liq.entry_price / liq.box_high - 1) * 100
    liq = liq[already_run_pct.abs() <= 50].copy()
    liq["passes_liquidity"] = (liq.avg_turnover_cr >= TURNOVER_FLOOR_CR) & (liq.a_day_price >= PRICE_FLOOR)
    clean = liq[liq.passes_liquidity].merge(pop[["ticker", "a_entry_date", "clv"]],
                                             on=["ticker", "a_entry_date"], how="left")
    print(f"Liquidity-cleaned 3pm-entry population: {len(clean):,}")

    rows = []
    cache_d = {}
    for n, r in enumerate(clean.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        if daily is None:
            continue
        a_date = pd.Timestamp(r.a_entry_date)
        am = daily.index[daily.Date == a_date]
        if len(am) == 0 or int(am[0]) < BASELINE_DAYS:
            continue
        ia = int(am[0])
        a_day = daily.iloc[ia]
        prior = daily.iloc[ia - BASELINE_DAYS:ia]

        med_turnover = prior.turnover.median()
        med_tr = prior.tr_pct.median()
        if pd.isna(med_turnover) or med_turnover <= 0 or pd.isna(med_tr) or med_tr <= 0:
            continue  # guardrail: invalid baseline, excluded not extreme-scored
        if pd.isna(a_day.tr_pct) or pd.isna(a_day.turnover):
            continue

        turnover_multiple = a_day.turnover / med_turnover
        range_multiple = a_day.tr_pct / med_tr
        q = turnover_multiple / range_multiple

        rng_ = a_day.High - a_day.Low
        body_pct_of_range = (abs(a_day.Close - a_day.Open) / rng_ * 100) if rng_ > 0 else np.nan
        upper_wick_pct_of_range = ((a_day.High - max(a_day.Open, a_day.Close)) / rng_ * 100) if rng_ > 0 else np.nan

        rows.append(dict(ticker=r.ticker, a_entry_date=r.a_entry_date,
                          turnover_multiple=turnover_multiple, range_multiple=range_multiple, q=q,
                          clv=r.clv, body_pct_of_range=body_pct_of_range,
                          upper_wick_pct_of_range=upper_wick_pct_of_range,
                          d1_close_ret=r.d1_close_ret))
        if (n + 1) % 3000 == 0:
            print(f"  ...{n+1:,}/{len(clean):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb19_proportionality.csv", index=False)
    df["d1_close_pos"] = (df.d1_close_ret > 0).astype(int)
    print(f"\nn valid: {len(df):,}\n")

    print("=== Q distribution ===")
    print(df.q.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))

    print("\n=== Q quintiles vs D1-close outcome (descriptive, continuous relationship) ===")
    df["q_quintile"] = pd.qcut(df.q, 5, labels=["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"])
    for ql in ["Q1 (lowest)", "Q2", "Q3", "Q4", "Q5 (highest)"]:
        g = df[df.q_quintile == ql]
        print(f"  {ql:14} n={len(g):6,}  D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")

    print("\n=== Pre-registered fixed split: Q<1 vs Q>=1 ===")
    for label, mask in [("Q < 1 (range expanded more than turnover)", df.q < 1),
                         ("Q >= 1 (turnover kept pace or exceeded range)", df.q >= 1)]:
        g = df[mask]
        print(f"  {label:48} n={len(g):6,} ({len(g)/len(df)*100:4.1f}%)  "
              f"D1close={g.d1_close_ret.median():+.2f}% / {(g.d1_close_ret>0).mean()*100:.1f}% pos")
    obs, p95, p = randomization_test(df.d1_close_pos.values, (df.q >= 1).values)
    print(f"  randomization: observed={obs*100:+.2f}pp  null p95={p95*100:.2f}pp  p={p:.4f}")

    print("\n=== Risk context: MAE/MFE proxy not available here (D1-close only in this population) ===")
    print("  (full MAE/MFE would require re-pulling 1H paths -- deferred unless Q shows a real effect)")

    print("\n=== Year-by-year check ===")
    df["year"] = pd.to_datetime(df.a_entry_date).dt.year
    for yr, g in df.groupby("year"):
        if len(g) < 100:
            continue
        below = g[g.q < 1]; above = g[g.q >= 1]
        print(f"  {yr}  n={len(g):6,}  Q<1: {len(below):5,} D1close%pos={  (below.d1_close_ret>0).mean()*100:5.1f}%   "
              f"Q>=1: {len(above):5,} D1close%pos={(above.d1_close_ret>0).mean()*100:5.1f}%")

    print("\n=== FORCEMOT A-day Q (the motivating example) ===")
    fm = df[df.ticker == "FORCEMOT"]
    print(fm[["a_entry_date", "turnover_multiple", "range_multiple", "q", "d1_close_ret"]].to_string(index=False))


if __name__ == "__main__":
    main()
