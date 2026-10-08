"""RQ-EMAPB-15C -- B2-only structural exit vs no-exit vs simple benchmark, CORRECTED (2026-10-07).

Fixes a real timing bug found in the first attempt: B2 confirmations land on D1 (56.5%), D2
(26.6%), or D3 (16.9%) within the window used in RQ-15B. Comparing "exit at confirmation" against
"hold to a FIXED D2 close" was invalid for the 43.5% of B2 trades confirming on D2 or D3, since
that fixed snapshot lands at-or-before their actual confirmation -- not a genuine "held through
the failure" comparison. This version extends the terminal "hold" horizon to D5 close, safely past
the latest possible confirmation (D3), for a fair comparison.

Three predeclared paths (critic-specified), same population, same frozen rule:
  A. B2-only structural exit: ignore B1 entirely (hold through), exit B2 at confirmation
     (fill = box_high), hold A/C to the D5 terminal.
  B. No structural exit at all: hold everyone to the D5 terminal.
  C. Simple benchmark: exit everyone at D1 close (not confirmation-time-dependent, unaffected by
     the horizon bug).

Also isolates the clean B2-only sub-comparison directly: exit-at-confirmation vs hold-to-D5,
for the B2 group alone, since that's the actual question the aggregate policies are built from.

Usage: python3 swing_qs_emapb/30_rq_emapb15c_policy_comparison.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
ENTRY_BAR_TIME = "14:15"
EXTENSION_OUTLIER_CUTOFF = 50
UP_MOVE_THRESHOLD_PCT = 1.0
RETEST_SEARCH_DAYS = 3   # frozen from RQ-15B -- B1/B2/A/C classification unchanged
TERMINAL_DAYS = 5        # extended -- safely past the latest possible confirmation (D3)


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


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop_all = pop[(pop.outcome == "consolidation_resumption") &
                  (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"Fully unfiltered resumption population with 1H coverage: {len(pop_all):,}")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(pop_all.itertuples()):
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
        if iD + TERMINAL_DAYS >= len(daily):
            continue
        d1_close = daily.Close.iloc[iD + 1]
        d_term_close = daily.Close.iloc[iD + TERMINAL_DAYS]
        retest_window_end_date = daily.Date.iloc[iD + RETEST_SEARCH_DAYS]

        end_mask_term = h1.index[(h1.session_date > daily.Date.iloc[iD + TERMINAL_DAYS])]
        end_i_term = int(end_mask_term[0]) if len(end_mask_term) else len(h1)
        window = h1.iloc[entry_i:end_i_term].reset_index(drop=True)
        if window.empty:
            continue

        # classification window: entry through RETEST_SEARCH_DAYS (frozen, matches RQ-15B)
        class_end_mask = window.session_date <= retest_window_end_date
        class_window = window[class_end_mask]

        up_threshold_price = entry_price * (1 + UP_MOVE_THRESHOLD_PCT / 100)
        up_idx = class_window.index[class_window.High >= up_threshold_price]
        reached_up_move = len(up_idx) > 0

        out = dict(ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high, entry_price=entry_price,
                   d1_close_ret=(d1_close / entry_price - 1) * 100,
                   d_term_close_ret=(d_term_close / entry_price - 1) * 100)

        if reached_up_move:
            up_i = int(up_idx[0])
            after_up = class_window.loc[class_window.index > up_i]
            retest_idx = after_up.index[after_up.Low <= box_high]
            if len(retest_idx) > 0:
                retest_i = int(retest_idx[0])
                retest_session = window.session_date.iloc[retest_i]
                out["group"] = "B1" if retest_session == entry_day else "B2"
                out["exit_at_confirm_ret"] = (box_high / entry_price - 1) * 100
            else:
                out["group"] = "C"
        else:
            out["group"] = "A"

        rows.append(out)
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb15c_policy_comparison.csv", index=False)
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"\nn={len(df):,}\n")
    print(df.group.value_counts())

    df["ret_policyA"] = np.where(df.group == "B2", df.exit_at_confirm_ret, df.d_term_close_ret)
    df["ret_policyB"] = df.d_term_close_ret
    df["ret_policyC"] = df.d1_close_ret

    print(f"\n=== Three predeclared exit policies, terminal horizon = D{TERMINAL_DAYS} close ===")
    for col, label in [("ret_policyA", "A. B2-only structural exit (ignore B1)"),
                        ("ret_policyB", "B. No structural exit (hold all to D term)"),
                        ("ret_policyC", "C. Simple benchmark (exit all at D1 close)")]:
        s = df[col].dropna()
        print(f"{label}")
        print(f"  n={len(s):,}  median={s.median():+.2f}%  mean={s.mean():+.2f}%  "
              f"pct_positive={(s>0).mean()*100:.1f}%  worst(1%ile)={s.quantile(.01):.2f}%  "
              f"worst(5%ile)={s.quantile(.05):.2f}%\n")

    print(f"=== Clean, isolated B2 sub-comparison: exit-at-confirmation vs hold-to-D{TERMINAL_DAYS} ===")
    b2 = df[df.group == "B2"]
    print(f"n={len(b2):,}")
    print(f"  Exit at confirmation: median={b2.exit_at_confirm_ret.median():+.2f}%  "
          f"pct_pos={(b2.exit_at_confirm_ret>0).mean()*100:.1f}%")
    print(f"  Hold to D{TERMINAL_DAYS} close (from entry): median={b2.d_term_close_ret.median():+.2f}%  "
          f"pct_pos={(b2.d_term_close_ret>0).mean()*100:.1f}%")
    pct_better_to_hold = (b2.d_term_close_ret > b2.exit_at_confirm_ret).mean() * 100
    print(f"  % of B2 cases where holding to D{TERMINAL_DAYS} was BETTER than exiting at confirmation: {pct_better_to_hold:.1f}%")


if __name__ == "__main__":
    main()
