"""RQ-QS-07A-4 -- Relative-Strength Proxy Audit (2026-09-29, critic-specified,
cheap interim test before any full RS/sector infrastructure build).

QUESTION (critic's exact framing): does relative performance -- stock minus
market -- add information BEYOND the absolute trend-strength family already
found in 05_/07A-3R? Is a stock strong because it's genuinely idiosyncratic,
or just participating in a broad market move?

SCOPE, deliberately narrow per critic's explicit instruction ("don't explode
this into dozens of windows"): stock_ret_5d, market_ret_5d, stock-minus-market
5D; stock_ret_20d, market_ret_20d, stock-minus-market 20D. Market = NIFTY
(data_cache/_NIFTY.csv), the same index-level source already used in RQ-06D.

MARKET-RELATIVE ONLY, NOT sector-relative -- per critic's explicit guardrail:
"Don't call stock-minus-Nifty 'relative strength' and pretend it solves the
sector question... If not [reliable historical sector data], start with
market-relative as a proxy, explicitly labelled as such." This project's only
sector mapping (`_sectors.csv`) is a single CURRENT snapshot applied across 5
years -- the exact same point-in-time problem already disclosed for
nifty500_universe.csv (RQ-QS-07U) -- so it is NOT "already safely available"
and sector-relative is correctly out of scope for this pass.

Frozen population: same full Cohort A + matched controls as 05_/07A-3R
(identical seed=42 reconstruction). No threshold optimization, no composite
score, no filtering -- distribution comparison only, same discipline as every
other 07A script.

Reuses stock_ret_5d/stock_ret_20d directly from precursor_features.csv (as
ret_5d/ret_20d) -- not recomputed.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
OUT_DIR = "swing_qs_07a"
SEED = 42

print("Reconstructing Cohort A + matched controls (identical to 03_/05_/07_)...", flush=True)
df = pd.read_csv(f"{OUT_DIR}/event_matrix.csv", parse_dates=["date"])
P95_MFE = np.percentile(df.max_return_d3, 95)
df["cohort_a"] = df.max_return_d3 >= P95_MFE
df["cohort_b"] = df.close_ret_d3 >= np.percentile(df.close_ret_d3, 95)
df["liq_decile"] = df.groupby("date")["traded_value_sma20"].transform(
    lambda x: pd.qcut(x, 10, labels=False, duplicates="drop"))

rng = np.random.RandomState(SEED)
noncohort = df[~df.cohort_a & ~df.cohort_b]
pool_by_key = noncohort.groupby(["date", "liq_decile"]).apply(lambda g: g.index.tolist(), include_groups=False)

def draw_control(row):
    pool = pool_by_key.get((row["date"], row["liq_decile"]))
    return pool[rng.randint(len(pool))] if pool else None

a = df[df.cohort_a].copy()
control_idx = a.apply(draw_control, axis=1)
a = a[control_idx.notna()].copy()
controls = df.loc[control_idx.dropna().astype(int)].copy()
a["group"], controls["group"] = "cohort_a", "control"
work = pd.concat([a[["ticker", "date", "group", "liq_decile", "fo_eligible"]],
                    controls[["ticker", "date", "group", "liq_decile", "fo_eligible"]]], ignore_index=True)
print(f"Cohort A: {len(a):,}  Controls: {len(controls):,}")

# NOTE (2026-09-29): originally merged ret_5d/ret_20d back in from
# precursor_features.csv on (ticker,date,group) -- caught via Rule #22 (an
# unexpected row-count jump, 102,837 -> 114,299 controls) that this key is NOT
# unique: the same control stock-day legitimately gets drawn as a match for
# multiple different cohort A events (random sampling with replacement from a
# same-date/same-decile pool), and BOTH sides of that merge carried the same
# duplicate structure -- a classic many-to-many join multiplying rows, the
# same class of bug RQ-QS-06C hit earlier tonight for a different reason.
# Fixed by recomputing directly, per-ticker, instead of merging on a
# non-unique key -- avoids the risk entirely rather than hunting for a unique
# key that doesn't naturally exist here.
from backtest import load, daily_pivots
print("Computing stock 5D/20D returns directly (avoiding the non-unique-key merge)...", flush=True)
cache = {}
ret_rows = []
for n, r in enumerate(work.itertuples()):
    if n % 40000 == 0:
        print(f"  {n}/{len(work)}", flush=True)
    if r.ticker not in cache:
        try:
            cache[r.ticker] = load(r.ticker, daily_pivots)
        except FileNotFoundError:
            cache[r.ticker] = None
    idf = cache[r.ticker]
    if idf is None or r.date not in idf.index:
        ret_rows.append((np.nan, np.nan)); continue
    pos = idf.index.get_loc(r.date)
    close = idf.Close.iloc[pos]
    c5 = idf.Close.iloc[pos - 5] if pos >= 5 else np.nan
    c20 = idf.Close.iloc[pos - 20] if pos >= 20 else np.nan
    ret_rows.append(((close / c5 - 1) * 100 if pd.notna(c5) else np.nan,
                       (close / c20 - 1) * 100 if pd.notna(c20) else np.nan))
work["ret_5d"], work["ret_20d"] = zip(*ret_rows)

print("Computing NIFTY (market) 5D/20D returns...", flush=True)
nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)
nifty["market_ret_5d"] = (nifty.Close / nifty.Close.shift(5) - 1) * 100
nifty["market_ret_20d"] = (nifty.Close / nifty.Close.shift(20) - 1) * 100
mkt = nifty[["market_ret_5d", "market_ret_20d"]].reset_index().rename(columns={nifty.index.name or "index": "date"})
mkt.columns = ["date", "market_ret_5d", "market_ret_20d"]

work = work.merge(mkt, on="date", how="left")
work["stock_minus_market_5d"] = work.ret_5d - work.market_ret_5d
work["stock_minus_market_20d"] = work.ret_20d - work.market_ret_20d

matched_market = work.market_ret_5d.notna().sum()
print(f"Matched to a real NIFTY trading date: {matched_market:,} of {len(work):,}")

work.to_csv(f"{OUT_DIR}/relative_strength_proxy.csv", index=False)


def pstack(s, fmt="{:.2f}"):
    s = pd.Series(s).dropna()
    if len(s) == 0:
        return "n=0"
    return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s):,})"


FEATS = ["ret_5d", "market_ret_5d", "stock_minus_market_5d",
          "ret_20d", "market_ret_20d", "stock_minus_market_20d"]

print("\n" + "=" * 100 + "\nMARKET-RELATIVE MOMENTUM -- Cohort A vs matched control (whole population)\n" + "=" * 100)
ca, ct = work[work.group == "cohort_a"], work[work.group == "control"]
for f in FEATS:
    ca_med, ct_med = ca[f].median(), ct[f].median()
    print(f"  {f:24s} cohort_a: {pstack(ca[f])}   control: {pstack(ct[f])}   gap={ca_med-ct_med:+.2f}")

print("\n" + "=" * 100 + "\nTHE KEY QUESTION: does stock-minus-market add info beyond absolute momentum?\n"
      "Comparing the GAP SIZE for absolute vs relative, at each horizon\n" + "=" * 100)
for horizon in ["5d", "20d"]:
    abs_gap = ca[f"ret_{horizon}"].median() - ct[f"ret_{horizon}"].median()
    rel_gap = ca[f"stock_minus_market_{horizon}"].median() - ct[f"stock_minus_market_{horizon}"].median()
    mkt_gap = ca[f"market_ret_{horizon}"].median() - ct[f"market_ret_{horizon}"].median()
    print(f"  {horizon}: absolute stock return gap={abs_gap:+.2f}   "
          f"market return gap (should be ~0 -- same dates, matched)={mkt_gap:+.2f}   "
          f"stock-minus-market gap={rel_gap:+.2f}")

print("\n" + "=" * 100 + "\nSame comparison, stratified by liquidity tercile and F&O (per 07A-3R's own finding)\n" + "=" * 100)
work["liq_tercile"] = pd.cut(work.liq_decile, [-1, 2, 6, 9], labels=["low(0-2)", "mid(3-6)", "high(7-9)"])
for strat_col, label, order in [("liq_tercile", "Liquidity tercile", ["low(0-2)", "mid(3-6)", "high(7-9)"]),
                                   ("fo_eligible", "F&O eligibility", [True, False])]:
    print(f"\n-- {label} --")
    for v in order:
        sub_ca = work[(work.group == "cohort_a") & (work[strat_col] == v)]
        sub_ct = work[(work.group == "control") & (work[strat_col] == v)]
        if len(sub_ca) < 30 or len(sub_ct) < 30:
            print(f"  {v}: too thin, skipped")
            continue
        g5 = sub_ca.stock_minus_market_5d.median() - sub_ct.stock_minus_market_5d.median()
        g20 = sub_ca.stock_minus_market_20d.median() - sub_ct.stock_minus_market_20d.median()
        print(f"  {v}: n_cohort={len(sub_ca):,}  stock_minus_market_5d gap={g5:+.2f}  "
              f"stock_minus_market_20d gap={g20:+.2f}")
