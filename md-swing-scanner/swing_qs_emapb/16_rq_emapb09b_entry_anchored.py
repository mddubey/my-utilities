"""RQ-EMAPB-09b -- Entry-anchored 1H timing (correction, 2026-10-05).

RQ-EMAPB-09 measured the 1H path starting right after A -- before any real entry under the
user's actual strategy (wait for a base to form, then break upward) would ever be taken. Two
problems that invalidated it for this purpose: (1) immediate_continuation episodes (26.6% of the
population) never form a base at all -- not the user's setup, shouldn't be in this analysis; (2)
even for episodes that do form a real base, the pre-break period is pre-entry noise.

This script anchors everything to the ACTUAL entry point: the exact 1H bar where the confirmed
daily base breaks upward (Close > peak_high, the same already-established resolution event from
RQ-EMAPB-07/08, now just localized to the hour). Only consolidation_resumption episodes have this
event at all -- consolidation_failure breaks DOWN, so the user's entry signal never fires there
(consistent with the user's own "outright failure = I never lost, I just never entered" framing).

Question: given the ORIGINAL A-day's CLV (known well before this entry), does it predict the
quality of the trade from the ACTUAL entry point forward?

Usage: python3 swing_qs_emapb/16_rq_emapb09b_entry_anchored.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
DAILY_DIR = "data/daily"
MIN_1H_DATE = pd.Timestamp("2023-10-23")
TIME_BUCKETS = [1, 2, 3, 4, 7, 14, 20]
BUCKET_LABELS = ["1H", "2H", "3H", "4H", "~Day+1 end", "~Day+2 end", "~Day+3 end"]


def load_daily(ticker):
    f = os.path.join(DAILY_DIR, f"{ticker}.csv")
    if not os.path.exists(f):
        return None
    d = pd.read_csv(f)
    if d.empty:
        return None
    d["Date"] = pd.to_datetime(d["Date"])
    return d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)


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
    return d.reset_index(drop=True)


def process_episode(r, daily, h1):
    peak_date = pd.Timestamp(r.peak_date)
    peak_match = daily.index[daily.Date == peak_date]
    if len(peak_match) == 0 or pd.isna(r.resolution_days_from_peak):
        return None
    peak_i = int(peak_match[0])
    resolution_i = peak_i + int(r.resolution_days_from_peak)
    if resolution_i >= len(daily):
        return None
    resolution_date = daily.Date.iloc[resolution_i]
    box_high = r.box_high  # FIX 2026-10-05: the real breakout trigger is the base's own high,
    box_low = r.box_low    # not the much higher, harder original peak_high (kept unused here)

    # locate the actual 1H bar where the base breaks upward (Close > box_high) -- search a
    # window bracketing the known daily resolution date for the exact hour
    day_start_match = h1.index[h1.session_date >= resolution_date - pd.Timedelta(days=1)]
    if len(day_start_match) == 0:
        return None
    search_start = int(day_start_match[0])
    search_end = min(search_start + 20, len(h1))  # ~3 trading days of buffer
    search = h1.iloc[search_start:search_end]
    break_idx = search.index[search.Close > box_high]
    if len(break_idx) == 0:
        return None
    break_i = int(break_idx[0])

    entry_i = break_i + 1  # tradable entry: the Open of the NEXT bar after confirmation
    if entry_i >= len(h1):
        return None
    entry_price = h1.Open.iloc[entry_i]

    end_i = min(entry_i + 25, len(h1))
    window = h1.iloc[entry_i:end_i].reset_index(drop=True)
    if window.empty:
        return None

    out = dict(entry_price=entry_price)
    out["post_entry_low_breach"] = bool(window.Low.min() < box_low) if pd.notna(box_low) else None
    for bars, label in zip(TIME_BUCKETS, BUCKET_LABELS):
        sub = window.iloc[:bars]
        if sub.empty:
            out[f"mfe_{label}"] = None
            out[f"mae_{label}"] = None
            continue
        out[f"mfe_{label}"] = (sub.High.max() / entry_price - 1) * 100
        out[f"mae_{label}"] = (sub.Low.min() / entry_price - 1) * 100
    return out


def main():
    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    pop = pop[(pop.outcome == "consolidation_resumption") &
              (pd.to_datetime(pop.a_entry_date) >= MIN_1H_DATE)].copy()
    print(f"consolidation_resumption episodes with 1H coverage: {len(pop):,}")

    rows = []
    cache_daily, cache_60m = {}, {}
    for n, r in enumerate(pop.itertuples()):
        daily = cache_daily.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_60m.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        res = process_episode(r, daily, h1)
        if res is None:
            continue
        res.update(ticker=r.ticker, a_entry_date=r.a_entry_date, clv_q=r.clv_q,
                    breached_a_day_low=r.breached_a_day_low)
        rows.append(res)
        if (n + 1) % 2000 == 0:
            print(f"  ...{n+1}/{len(pop):,} scanned, {len(rows):,} with a located entry bar")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb09b_entry_anchored.csv", index=False)
    print(f"\nEpisodes with a located 1H entry bar: {len(df):,}")

    df["clv_group"] = df.clv_q.map({"Q1": "unfavorable", "Q2": "unfavorable", "Q3": "middle",
                                      "Q4": "favorable", "Q5": "favorable"})

    print("\n=== POST-ENTRY MFE/MAE by time bucket x original A-day CLV group ===")
    for grp in ["unfavorable", "middle", "favorable"]:
        sub = df[df.clv_group == grp]
        print(f"\n--- CLV {grp} (n={len(sub):,}) ---")
        for label in BUCKET_LABELS:
            mfe = sub[f"mfe_{label}"].dropna()
            mae = sub[f"mae_{label}"].dropna()
            print(f"  {label:14} median MFE={mfe.median():+.2f}%  P75={mfe.quantile(.75):+.2f}%  "
                  f"median MAE={mae.median():+.2f}%")
        print(f"  % that breach the box low AFTER entry (post-entry stop-out risk): "
              f"{sub.post_entry_low_breach.mean()*100:.1f}%")

    print(f"\nWritten: {HERE}/rq_emapb09b_entry_anchored.csv")


if __name__ == "__main__":
    main()
