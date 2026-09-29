"""RQ-QS-06D -- Contemporaneous-State Diagnostic (2026-09-29, critic-specified).

PRE-REGISTERED AS A ONE-PASS DIAGNOSTIC, per critic's explicit instruction: "not
'keep adding information until something separates.'" Three, and only three,
feature families -- volume state, volatility state, market context -- chosen
because they stay close to the mechanism already observed in 06B/06C (is the move
being accepted/expanded with participation and volatility, or exhausting), not
because they're the most promising options in the abstract. Explicitly NOT adding
relative-strength/sector infra or intraday data this pass (critic's own words).

DECISION RULE, pre-declared before running: if these variables show meaningful,
directionally consistent, reasonably early separation -> justifies a narrowly
defined predictive/harvesting experiment. If not -> prediction is closed for this
branch (reactive deterioration anatomy, RQ-QS-06E, becomes the path instead). No
model, no feature stacking, no threshold search regardless of outcome.

Same discipline as 06C: predictors censored at each landmark, archetype labels are
future truth used only for evaluation, label-leakage checked (all 3 new predictor
families use price/volume/ATR/Nifty state ON or BEFORE the landmark day -- none
reference exit_r or max_r_15d, the quantities the archetype labels are built from).

Reuses `walk_full()` from rq_qs_06b (verbatim) and the same landmarks (+0.5/0.75/
1.0/1.5/2.0R) and archetype join as 06C -- same join-key fix (entry_definition
included) applied from the start this time, not rediscovered.

New predictors, all computed AT the landmark day using only that day and earlier:
  volume_ratio_landmark   Volume_on_landmark_day / vol_avg10_prior (production's
                           own prior-window volume baseline, reused not re-derived)
  volume_trend_3d         correlation of day-index vs Volume over the up-to-3 days
                           ending at the landmark (same convention as 04A/04B's
                           range_contracting_corr)
  atr_expansion           atr14 at landmark / atr14_60ago (production's own
                           60-day-back ATR reference, reused) -- >1 = volatility
                           has expanded since 60 days before entry, <1 = contracted
  day_range_over_atr      (High-Low) on the landmark day / atr14 that day
  nifty_return_3d         NIFTY's own close-to-close % return over the 3 sessions
                           ending on the landmark date (index-level regime context)
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib.util import spec_from_file_location, module_from_spec
_spec = spec_from_file_location("rq_qs_06b", os.path.join(os.path.dirname(os.path.abspath(__file__)), "rq_qs_06b_favorable_state_trajectory.py"))
rq_qs_06b = module_from_spec(_spec)
_spec.loader.exec_module(rq_qs_06b)
walk_full = rq_qs_06b.walk_full

from backtest import load
from pivots import daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
LANDMARKS = [0.5, 0.75, 1.0, 1.5, 2.0]
PRIMARY = ["burst_then_exhaustion", "persistent_continuation"]


def contemporaneous(rows, entry_i, days, level, nifty):
    hit = next((d for d in days if d["mfe_so_far"] >= level), None)
    if hit is None:
        return None
    d0 = hit["day"]
    k = entry_i + d0  # absolute row index of the landmark day
    row = rows.iloc[k]

    vol_ratio = (row.Volume / row.vol_avg10_prior) if pd.notna(row.vol_avg10_prior) and row.vol_avg10_prior else None
    atr_exp = (row.atr14 / row.atr14_60ago) if pd.notna(row.atr14_60ago) and row.atr14_60ago else None
    day_range_atr = ((row.High - row.Low) / row.atr14) if pd.notna(row.atr14) and row.atr14 else None

    lo = max(0, k - 2)
    vol_span = rows.iloc[lo:k + 1].Volume
    vol_trend = float(np.corrcoef(np.arange(len(vol_span)), vol_span)[0, 1]) if len(vol_span) >= 3 else None

    date = row.Date
    nifty_ret_3d = None
    if date in nifty.index:
        pos = nifty.index.get_loc(date)
        if pos >= 3:
            nifty_ret_3d = (nifty.Close.iloc[pos] / nifty.Close.iloc[pos - 3] - 1) * 100

    return dict(volume_ratio_landmark=vol_ratio, volume_trend_3d=vol_trend,
                 atr_expansion=atr_exp, day_range_over_atr=day_range_atr,
                 nifty_return_3d=nifty_ret_3d)


if __name__ == "__main__":
    nifty = pd.read_csv("data_cache/_NIFTY.csv", index_col=0, parse_dates=True)

    labels = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06b_state_trajectory.csv")[
        ["ticker", "entry_date", "entry_definition", "archetype", "eventual_exit_r", "eventual_max_r_15d"]]
    env = pd.read_csv("swing_qs/trajectory_replay/rq_qs_06_envelope.csv")
    src = env.merge(labels, on=["ticker", "entry_date", "entry_definition"], how="inner")
    assert len(src) == len(env), f"join not 1:1: {len(src)} vs {len(env)}"
    src["entry_date"] = pd.to_datetime(src.entry_date)
    print(f"{len(src)} trades with archetype labels")

    cache = {}
    recs = []
    for n, r in enumerate(src.itertuples()):
        if n % 5000 == 0:
            print(f"{n}/{len(src)}", flush=True)
        rows = cache.setdefault(r.ticker, load(r.ticker, daily_pivots).reset_index())
        m = rows.index[rows.Date == r.entry_date]
        if len(m) == 0:
            continue
        entry_i = m[0]
        days, exit_reason, exit_day = walk_full(rows, entry_i, r.entry_price, r.initial_risk_pct)
        if not days:
            continue
        for level in LANDMARKS:
            pred = contemporaneous(rows, entry_i, days, level, nifty)
            if pred is None:
                continue
            rec = dict(ticker=r.ticker, entry_date=r.entry_date.date(), level=level,
                        archetype=r.archetype)
            rec.update(pred)
            recs.append(rec)

    df = pd.DataFrame(recs)
    df.to_csv(f"{OUT_DIR}/rq_qs_06d_contemporaneous.csv", index=False)
    print(f"\n{len(df)} landmark-observations\n")

    prim = df[df.archetype.isin(PRIMARY)]
    print(f"Primary comparison population: n={len(prim)}\n")

    def pstack(s, fmt="{:.2f}"):
        s = pd.Series(s).dropna()
        if len(s) == 0:
            return "n=0"
        return f"P25={fmt.format(np.percentile(s,25))} P50={fmt.format(np.percentile(s,50))} P75={fmt.format(np.percentile(s,75))} (n={len(s)})"

    PRED_FIELDS = ["volume_ratio_landmark", "volume_trend_3d", "atr_expansion", "day_range_over_atr", "nifty_return_3d"]

    print("=" * 100)
    print("CONTEMPORANEOUS-STATE SEPARABILITY TIMELINE")
    print("=" * 100)
    for level in LANDMARKS:
        sub = prim[prim.level == level]
        b = sub[sub.archetype == "burst_then_exhaustion"]
        p = sub[sub.archetype == "persistent_continuation"]
        print(f"\n--- Landmark: first +{level}R  (burst n={len(b)}, persistent n={len(p)}) ---")
        for field in PRED_FIELDS:
            bm, pm = b[field].median(), p[field].median()
            b_iqr = (b[field].quantile(.25), b[field].quantile(.75))
            p_iqr = (p[field].quantile(.25), p[field].quantile(.75))
            overlap = not (b_iqr[1] < p_iqr[0] or p_iqr[1] < b_iqr[0])
            print(f"  {field:24s} burst: {pstack(b[field])}   persistent: {pstack(p[field])}   "
                  f"gap={abs(bm-pm):.3f}  overlap={overlap}")

    print("\n" + "=" * 100)
    print("For context: all 5 archetypes at +1.0R")
    print("=" * 100)
    sub1 = df[df.level == 1.0]
    for arch, grp in sub1.groupby("archetype"):
        print(f"  {arch:24s} n={len(grp):6d}  " + "  ".join(f"{f}_med={grp[f].median():.2f}" for f in PRED_FIELDS))
