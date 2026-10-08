"""RQ-EMAPB-15B -- Exit-at-confirmation characterization (critic-specified, 2026-10-07).

RQ-15A established there's no price-depth stop that separates failures from survivors. The
structural failure rule itself (entry -> +1% excursion -> retest box_high) is already validated
as an outcome classifier (RQ-14a). This RQ asks: if we actually EXIT the instant that failure
confirms (assumed fill = box_high, modeling a resting stop placed at the level), what does the
realized trade distribution look like -- is the signal timely enough to function as the real exit,
despite not being a usable initial stop?

Measures, per critic's spec:
1. Exit return at B confirmation (box_high vs entry), B1/B2 separately.
2. Further adverse movement AFTER confirmation (next bar, confirmation-day close, next day's
   close) -- does holding past confirmation make things worse, or would you have been fine anyway?
3. How much winner profit was given back before confirmation (MFE before confirm vs exit-at-confirm).
4. C (survivor) trades at matching checkpoints (D0 close, D1 close, D2 close) for a clean comparison.
5. Provisional realized-R: payoff ratio using confirmed-failure loss as the risk reference, since no
   price-based stop exists yet -- stated explicitly as provisional, not a final risk convention.

Usage: python3 swing_qs_emapb/29_rq_emapb15b_exit_at_confirmation.py
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
UP_MOVE_THRESHOLD_PCT = 1.0  # frozen from RQ-14a


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
        if iD + 3 >= len(daily):  # need D0,D1,D2,D3 for after-confirmation tracking
            continue
        d_dates = [daily.Date.iloc[iD], daily.Date.iloc[iD + 1], daily.Date.iloc[iD + 2], daily.Date.iloc[iD + 3]]
        d_closes = [daily.Close.iloc[iD], daily.Close.iloc[iD + 1], daily.Close.iloc[iD + 2], daily.Close.iloc[iD + 3]]

        end_mask = h1.index[(h1.session_date > d_dates[3])]
        end_i = int(end_mask[0]) if len(end_mask) else len(h1)
        window = h1.iloc[entry_i:end_i].reset_index(drop=True)
        if window.empty:
            continue

        up_threshold_price = entry_price * (1 + UP_MOVE_THRESHOLD_PCT / 100)
        up_idx = window.index[window.High >= up_threshold_price]
        reached_up_move = len(up_idx) > 0

        out = dict(ticker=r.ticker, a_entry_date=r.a_entry_date, box_high=box_high, entry_price=entry_price,
                   d0_close_ret=(d_closes[0] / entry_price - 1) * 100,
                   d1_close_ret=(d_closes[1] / entry_price - 1) * 100,
                   d2_close_ret=(d_closes[2] / entry_price - 1) * 100)

        if reached_up_move:
            up_i = int(up_idx[0])
            after_up = window.iloc[up_i + 1:]
            retest_idx = after_up.index[after_up.Low <= box_high]
            if len(retest_idx) > 0:
                retest_i = int(retest_idx[0])
                retest_session = window.session_date.iloc[retest_i]
                group = "B1" if retest_session == entry_day else "B2"
                mfe_before_confirm = (window.iloc[:retest_i + 1].High.max() / entry_price - 1) * 100
                exit_at_confirm_ret = (box_high / entry_price - 1) * 100

                post = window.iloc[retest_i + 1:]
                next_bar_ret = ((post.Close.iloc[0] / entry_price - 1) * 100) if not post.empty else np.nan
                confirm_day = retest_session
                cdm = daily.index[daily.Date == confirm_day]
                post_day_close_ret, next_day_after_confirm_ret, mae_after_confirm_3td = np.nan, np.nan, np.nan
                if len(cdm):
                    icd = int(cdm[0])
                    post_day_close_ret = (daily.Close.iloc[icd] / entry_price - 1) * 100
                    if icd + 1 < len(daily):
                        next_day_after_confirm_ret = (daily.Close.iloc[icd + 1] / entry_price - 1) * 100
                    if icd + 3 < len(daily):
                        # worst close over the 3 trading days following confirmation
                        mae_after_confirm_3td = (daily.Close.iloc[icd+1:icd+4].min() / entry_price - 1) * 100

                out.update(group=group, mfe_before_confirm=mfe_before_confirm,
                           exit_at_confirm_ret=exit_at_confirm_ret,
                           given_back=mfe_before_confirm - exit_at_confirm_ret,
                           next_bar_after_confirm_ret=next_bar_ret,
                           confirm_day_close_ret=post_day_close_ret,
                           next_day_after_confirm_ret=next_day_after_confirm_ret,
                           worst_close_3td_after_confirm=mae_after_confirm_3td)
            else:
                out["group"] = "C"
        else:
            out["group"] = "A"

        rows.append(out)
        if (n + 1) % 5000 == 0:
            print(f"  ...{n + 1:,}/{len(pop_all):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb15b_exit_at_confirmation.csv", index=False)
    already_run_pct = (df.entry_price / df.box_high - 1) * 100
    df = df[already_run_pct.abs() <= EXTENSION_OUTLIER_CUTOFF].copy()
    print(f"\nn={len(df):,}\n")
    print(df.group.value_counts())

    for g in ["B1", "B2"]:
        sub = df[df.group == g]
        print(f"\n=== {g} (n={len(sub):,}) -- exit-at-confirmation economics ===")
        print(f"  Exit-at-confirm return (vs entry):     median={sub.exit_at_confirm_ret.median():+.2f}%  "
              f"%positive={ (sub.exit_at_confirm_ret>0).mean()*100:.1f}%")
        print(f"  MFE before confirm:                    median={sub.mfe_before_confirm.median():+.2f}%")
        print(f"  Given back (MFE - exit-at-confirm):     median={sub.given_back.median():+.2f}%")
        print(f"  Next bar after confirm:                 median={sub.next_bar_after_confirm_ret.median():+.2f}%")
        print(f"  Confirmation day's own close:            median={sub.confirm_day_close_ret.median():+.2f}%")
        print(f"  Next day after confirm's close:          median={sub.next_day_after_confirm_ret.median():+.2f}%")
        print(f"  Worst close in 3 days after confirm:      median={sub.worst_close_3td_after_confirm.median():+.2f}%")
        held_vs_exit = (sub.next_day_after_confirm_ret < sub.exit_at_confirm_ret).mean() * 100
        print(f"  % where holding past confirm to next-day close was WORSE than exiting at confirm: {held_vs_exit:.1f}%")

    print("\n=== C (survivors) at matching daily checkpoints, from entry ===")
    c = df[df.group == "C"]
    for col, label in [("d0_close_ret", "D0 close"), ("d1_close_ret", "D1 close"), ("d2_close_ret", "D2 close")]:
        print(f"  {label:10} median={c[col].median():+.2f}%  %positive={(c[col]>0).mean()*100:.1f}%")

    print("\n=== Provisional payoff ratio (exit-at-confirm loss as the risk reference) ===")
    fail = pd.concat([df[df.group == "B1"].exit_at_confirm_ret, df[df.group == "B2"].exit_at_confirm_ret])
    avg_loss = fail[fail < 0].mean()
    avg_win = c[c.d1_close_ret > 0].d1_close_ret.mean()
    print(f"  avg confirmed-failure exit loss: {avg_loss:+.2f}%   avg survivor(C) D1-close winner gain: {avg_win:+.2f}%")
    print(f"  provisional payoff ratio: {abs(avg_win/avg_loss):.2f}")


if __name__ == "__main__":
    main()
