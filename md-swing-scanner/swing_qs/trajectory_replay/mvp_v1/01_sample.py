"""QS Trajectory Replay -- Minimum Viable Replay, Step 1: Sampling (critic-approved
spec, section D). Deterministic stratified sample, 100 candidates, drawn BEFORE
looking at any 5-min trajectory. 25 early-period + 25 mid-period + 25 late-period
+ 25 random (from whatever remains), no selection on eventual return, ticker, visual
attractiveness, or memorability. AEGISLOG is NOT included here -- it stays a separate,
explicitly-labeled illustrative sanity example, excluded from inference.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np

SCRATCH = '/private/tmp/claude-501/-Users-mdubey-workspace-personal-my-utilities/02f38c07-7b2d-41a9-b384-7a6bf68604dd/scratchpad'
OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SEED = 42
GAP_BAD_THRESHOLD_PCT = 2.343

feat = pd.read_csv(f'{SCRATCH}/qs_litfeat_full.csv', parse_dates=['entry_date'])
feat['v01_pass'] = ~((feat.base_duration == 0) & (feat.gap_to_trigger_pct > GAP_BAD_THRESHOLD_PCT))

cache_files = set(f[:-4] for f in os.listdir('intraday_cache') if f.endswith('.csv'))
pool = feat[feat.v01_pass & feat.entry_date.between('2026-06-10', '2026-09-23')
            & feat.ticker.isin(cache_files)].copy()
pool = pool.drop_duplicates(subset=['ticker', 'entry_date', 'entry_definition']).reset_index(drop=True)
print(f"Eligible pool: {len(pool)} candidates, {pool.ticker.nunique()} tickers")

# tertile split by calendar date, not by row count -- a real early/mid/late period split
d_min, d_max = pool.entry_date.min(), pool.entry_date.max()
span = (d_max - d_min) / 3
early_cut = d_min + span
mid_cut = d_min + 2 * span
print(f"Window {d_min.date()} to {d_max.date()}  |  early<{early_cut.date()}  mid<{mid_cut.date()}")

early_pool = pool[pool.entry_date < early_cut]
mid_pool = pool[(pool.entry_date >= early_cut) & (pool.entry_date < mid_cut)]
late_pool = pool[pool.entry_date >= mid_cut]
print(f"early_pool={len(early_pool)}  mid_pool={len(mid_pool)}  late_pool={len(late_pool)}")

rng = np.random.RandomState(SEED)

def draw(sub_pool, n, exclude_idx):
    avail = sub_pool[~sub_pool.index.isin(exclude_idx)]
    n = min(n, len(avail))
    return avail.sample(n=n, random_state=rng)

picked = pd.DataFrame()
early_sample = draw(early_pool, 25, picked.index)
picked = pd.concat([picked, early_sample])
mid_sample = draw(mid_pool, 25, picked.index)
picked = pd.concat([picked, mid_sample])
late_sample = draw(late_pool, 25, picked.index)
picked = pd.concat([picked, late_sample])
random_sample = draw(pool, 25, picked.index)  # from the WHOLE remaining pool, not stratified
picked = pd.concat([picked, random_sample])

early_sample = early_sample.assign(stratum='early')
mid_sample = mid_sample.assign(stratum='mid')
late_sample = late_sample.assign(stratum='late')
random_sample = random_sample.assign(stratum='random')
sample = pd.concat([early_sample, mid_sample, late_sample, random_sample]).reset_index(drop=True)
sample['trade_id'] = sample.index

print(f"\nFinal sample: n={len(sample)}")
print(sample.stratum.value_counts())
print(f"Unique tickers in sample: {sample.ticker.nunique()}")

sample[['trade_id', 'stratum', 'ticker', 'entry_date', 'entry_definition']].to_csv(
    f'{OUT_DIR}/sample_100.csv', index=False)
print(f"\nSaved sample_100.csv")
