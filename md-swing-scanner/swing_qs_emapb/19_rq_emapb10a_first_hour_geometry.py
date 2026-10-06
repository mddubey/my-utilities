"""RQ-EMAPB-10A -- First-hour resumption mechanics, candidate trigger event (critic-specified,
2026-10-06). Population restricted to the 1,870 CLV>=0.80, valid-daily-box episodes whose first
qualifying 1H Close > box_high occurs in the FIRST hour of observation (RQ-09's superior group,
69.5% hold rate). Question: what is the earliest mechanically observable event within that hour
that distinguishes the 69.5% stable holds from the 30.5% rejections?

Resolution caveat, stated explicitly per critic's "time/order of touch -> high -> close" ask: our
data is 1H OHLC, not sub-bar/tick data, so the literal intra-hour sequencing of touch/high/close
is not directly observable. What IS observable from OHLC: the bar's shape (open/high/low/close
positions relative to box_high, body/wick geometry, close location within its own hour's range)
and the immediately following bar's behavior (does price stay away from box_high or return to
test it). This is reported as the best available proxy, limitation stated up front.

No threshold optimization. No trigger proposed -- descriptive distributions only, split by the
already-known hold/reject outcome.

Usage: python3 swing_qs_emapb/19_rq_emapb10a_first_hour_geometry.py
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

from data.paths import INTRADAY_60M_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_1H_DATE = pd.Timestamp("2023-10-23")
BOX_CONFIRM_DAYS = 3


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
    fh = pd.read_csv(f"{HERE}/rq_emapb09_first_hour.csv")
    fh = fh[fh.bar_num_from_obs_start == 1].copy()
    print(f"First-hour-cross population: {len(fh):,}")

    pop = pd.read_csv(f"{HERE}/rq_emapb08_joint.csv")
    fh = fh.merge(pop[["ticker", "a_entry_date", "box_high", "peak_date", "consolidation_start_days"]],
                  on=["ticker", "a_entry_date"], how="left")

    rows = []
    cache_d, cache_h = {}, {}
    for n, r in enumerate(fh.itertuples()):
        daily = cache_d.setdefault(r.ticker, load_daily(r.ticker))
        h1 = cache_h.setdefault(r.ticker, load_60m(r.ticker))
        if daily is None or h1 is None:
            continue
        peak_date = pd.Timestamp(r.peak_date)
        pm = daily.index[daily.Date == peak_date]
        if len(pm) == 0 or pd.isna(r.consolidation_start_days):
            continue
        peak_i = int(pm[0])
        consolidation_start_i = peak_i + int(r.consolidation_start_days)
        box_span_end = consolidation_start_i + BOX_CONFIRM_DAYS
        if box_span_end >= len(daily):
            continue
        obs_start_date = daily.Date.iloc[box_span_end]
        box_high = r.box_high

        osm = h1.index[h1.session_date >= obs_start_date]
        if len(osm) == 0:
            continue
        obs_start_i = int(osm[0])
        cross_bar = h1.iloc[obs_start_i]
        if cross_bar.Close <= box_high:
            continue  # sanity: must actually be the cross bar (first-hour by construction)

        O, H, L, C = cross_bar.Open, cross_bar.High, cross_bar.Low, cross_bar.Close
        bar_range = H - L
        open_vs_box_pct = (O / box_high - 1) * 100
        low_vs_box_pct = (L / box_high - 1) * 100
        high_vs_box_pct = (H / box_high - 1) * 100
        close_vs_box_pct = (C / box_high - 1) * 100
        body_pct_of_range = (abs(C - O) / bar_range * 100) if bar_range > 0 else np.nan
        close_location_in_bar = ((C - L) / bar_range) if bar_range > 0 else np.nan
        dipped_below_box_intrabar = bool(L < box_high)

        # immediate post-breach behavior: the very next 1H bar of trading (same or next session)
        next_i = obs_start_i + 1
        post_pullback_pct, post_held = np.nan, None
        if next_i < len(h1):
            nb = h1.iloc[next_i]
            post_pullback_pct = (nb.Low / box_high - 1) * 100
            post_held = bool(nb.Low > box_high)

        rows.append(dict(
            ticker=r.ticker, a_entry_date=r.a_entry_date,
            open_vs_box_pct=open_vs_box_pct, low_vs_box_pct=low_vs_box_pct,
            high_vs_box_pct=high_vs_box_pct, close_vs_box_pct=close_vs_box_pct,
            body_pct_of_range=body_pct_of_range, close_location_in_bar=close_location_in_bar,
            dipped_below_box_intrabar=dipped_below_box_intrabar,
            post_pullback_pct=post_pullback_pct, post_held=post_held,
            held_3bars=r.held_3bars,
        ))
        if (n + 1) % 500 == 0:
            print(f"  ...{n+1}/{len(fh):,}")

    df = pd.DataFrame(rows)
    df.to_csv(f"{HERE}/rq_emapb10a_first_hour_geometry.csv", index=False)
    df = df.dropna(subset=["held_3bars"])
    print(f"\nn processed: {len(df):,}\n")

    def compare(field, fmt="{:+.2f}"):
        held = df[df.held_3bars][field].dropna()
        rej = df[~df.held_3bars][field].dropna()
        print(f"  {field:28} held(n={len(held):4,}): median=" + fmt.format(held.median()) +
              f"   rejected(n={len(rej):4,}): median=" + fmt.format(rej.median()))

    print("=== Cross-bar geometry: held (69.5% group) vs rejected (30.5% group) ===")
    compare("open_vs_box_pct")
    compare("low_vs_box_pct")
    compare("high_vs_box_pct")
    compare("close_vs_box_pct")
    compare("body_pct_of_range")
    compare("close_location_in_bar", fmt="{:.3f}")

    print(f"\n  dipped below box intrabar (held):     {df[df.held_3bars].dipped_below_box_intrabar.mean()*100:.1f}%")
    print(f"  dipped below box intrabar (rejected): {df[~df.held_3bars].dipped_below_box_intrabar.mean()*100:.1f}%")

    print("\n=== Immediate next-bar behavior ===")
    compare("post_pullback_pct")
    print(f"  next bar stays above box_high (held):     {df[df.held_3bars].post_held.mean()*100:.1f}%")
    print(f"  next bar stays above box_high (rejected): {df[~df.held_3bars].post_held.mean()*100:.1f}%")

    print(f"\nWritten: {HERE}/rq_emapb10a_first_hour_geometry.csv")


if __name__ == "__main__":
    main()
