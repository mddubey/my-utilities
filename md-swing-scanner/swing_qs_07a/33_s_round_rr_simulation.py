"""RQ-QS-07A-BT1-S-RR2 -- Same real day-by-day path simulation as
32_s_bt1_rr_simulation.py, but with plain round-number stop/target
percentages instead of ATR-multiples (2026-10-02, user-directed
simplification -- ATR-scaled stop/target produced unintuitive absolute
sizes, e.g. 4x ATR implied an ~18% target for a median-ATR stock, far
beyond what this population's real upside percentiles support; round
numbers are easier to reason about directly against the real reachability
check already run: +10% reached 13.8% of the time, -5% breached 32.1% of
the time, both from `s_bt1_combo.csv`/`event_matrix.csv`'s real
max_return_d3/adverse_d3).

Same mechanics as script 32: entry = T0's own Close (validated proxy for
"around 3pm", see FINDINGS.md), stop/target checked via the real High/Low
path over T+1..T+3 in day order (stop checked before target if both trigger
the same day -- conservative convention), exit at T+3 close if neither
triggers. Pre-declared pairs (stop%, target%): (3,9), (4,12), (5,10),
(5,15) -- a deliberate small sweep, not picked after seeing results.

CONCLUSION THIS SCRIPT LED TO (logged in FINDINGS.md): every pair produces
a similar, small mean R (+0.047 to +0.080) -- translated into real %-of-
capital terms (mean R x stop%), this is only ~0.2-0.25% expected gain per
trade, likely at or below realistic round-trip trading costs (STT + stamp
+ exchange charges + slippage). Win rate (37.6-44.7%) is NOT the relevant
number here -- flagged directly by the user ("win rate means nothing if
it's just giving you 1% at the end of the day") -- plain S's edge is too
thin to trade as currently defined.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd, numpy as np
from backtest import load, daily_pivots

s = pd.read_csv('swing_qs_07a/s_bt1_combo.csv', parse_dates=['date'])
PAIRS = [(3,9), (4,12), (5,10), (5,15)]  # (stop%, target%)

grouped = dict(tuple(s.groupby('ticker')))
rows_out = []
for n, t in enumerate(grouped):
    if n % 400 == 0:
        print(f'{n}/{len(grouped)}', flush=True)
    idf = load(t, daily_pivots)
    close, high, low = idf.Close, idf.High, idf.Low
    sub = grouped[t]
    for r in sub.itertuples():
        if r.date not in idf.index:
            continue
        pos = idf.index.get_loc(r.date)
        if pos + 3 >= len(idf):
            continue
        entry = close.iloc[pos]
        result = {}
        for sp, tp in PAIRS:
            stop_level = entry * (1 - sp/100)
            target_level = entry * (1 + tp/100)
            outcome = None
            for d in [1,2,3]:
                lo, hi = low.iloc[pos+d], high.iloc[pos+d]
                if lo <= stop_level:
                    outcome = 'stop'; break
                if hi >= target_level:
                    outcome = 'target'; break
            if outcome is None:
                outcome = 'neither'
                r_mult = (close.iloc[pos+3]-entry)/(entry*sp/100)
            elif outcome == 'stop':
                r_mult = -1.0
            else:
                r_mult = tp/sp
            result[f'outcome_{sp}_{tp}'] = outcome
            result[f'r_{sp}_{tp}'] = r_mult
        rows_out.append(dict(ticker=t, date=r.date, **result))

sim = pd.DataFrame(rows_out)
sim.to_csv('swing_qs_07a/s_round_rr_simulation.csv', index=False)
print(f'{len(sim):,} rows')
for sp, tp in PAIRS:
    oc, rm = sim[f'outcome_{sp}_{tp}'], sim[f'r_{sp}_{tp}']
    print(f'Stop={sp}%/Target={tp}% : target {(oc=="target").mean()*100:5.1f}%  stop {(oc=="stop").mean()*100:5.1f}%  neither {(oc=="neither").mean()*100:5.1f}%  | win%={ (rm>0).mean()*100:5.1f}%  mean R={rm.mean():+.3f}  median R={rm.median():+.3f}')
