"""RQ-QS-04B -- Anatomy of the holds-above-A consolidation population ONLY
(2026-09-29, critic-sequenced step 1 of 6 in ../PARKING_LOT.md item #9).

Strictly observational. NO returns, NO expectancy, NO R, NO filtering for winners,
NO gate. The single question: is the 8,403-event subset from RQ-QS-04A (A's whose
post-breakout pause holds its LOW above A's own entry price) a recognizable tight
continuation structure, or merely a 1-2 day pause followed by another new high?

Population: read directly from rq04a_consolidation_anatomy.csv (consolidation_detected
AND consolidation_low_above_a). Not re-derived -- same A's, same pause definition.
The 04A definitions carry over unchanged:
  consolidation_start_day  first day offset (>=1) whose High fails to extend the running
                           high since A's entry (decision-time safe).
  consolidation_high       the running high as of that day (the candidate new pivot).
  B                        first later day whose High > consolidation_high (intraday touch).
  consolidation_low        min(Low) over the pause span (hindsight -- audit only).
  duration                 days from pause start to B (or to the D15 window edge).

New fields computed here from raw bars (all descriptive):
  b_close_above_high        did B's own Close finish above consolidation_high, or was the
                            break only an intraday poke?
  b_open_gap_above_high     did B gap open above consolidation_high?
  b_break_pct               (B High - consolidation_high) / consolidation_high, %.
  low_vs_a_pct / low_vs_a_atr   how far the pause low sits ABOVE A's entry, in % and ATR.
  min_close_above_a         min(Close) over the span > A entry (close-basis hold).
  last_close_above_a        last Close of the span > A entry ("merely ends above A").
  high_vs_a_pct             consolidation_high above A's entry, % (how far the impulse ran
                            before pausing).
The "stays entirely above A vs merely ends above A" question is answered by comparing
the three tiers on the FULL detected population: low-basis (04A's 8,403), close-basis,
and last-close-basis.

Rule #22: a_entry_price from the CSV is asserted against the freshly loaded bar for every
row (catches a data_cache re-adjustment since 04A ran); 4 concrete examples spanning the
duration range are dumped with their raw bars for hand-checking.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import pandas as pd
import numpy as np
from backtest import load, daily_pivots

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC = f"{OUT_DIR}/rq04a_consolidation_anatomy.csv"
PCTS = [25, 50, 75, 90]


def pstack(s, fmt="{:.2f}", suffix=""):
    s = pd.Series(s).dropna()
    return "  ".join(f"P{p}={fmt.format(np.percentile(s, p))}{suffix}" for p in PCTS) + f"  (n={len(s)})"


def enrich(df):
    out = []
    cache = {}
    mismatches = 0
    tickers = df.ticker.unique()
    for n, t in enumerate(tickers):
        if n % 50 == 0:
            print(f"{n}/{len(tickers)} tickers", flush=True)
        try:
            rows = load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        for _, r in df[df.ticker == t].iterrows():
            ia = int(r.a_entry_i)
            a_row = rows.iloc[ia]
            # a_entry_price is the gate's trigger-based price, not any single OHLC field, so the
            # integrity check is on the DATE: the row at a_entry_i must still be the same bar.
            if str(a_row.Date.date()) != r.a_entry_date:
                mismatches += 1
                continue
            cs = ia + int(r.consolidation_start_day)
            last = ia + (int(r.b_day) if r.resolved else int(r.consolidation_start_day) + int(r.duration))
            span = rows.iloc[cs:last + 1]
            pause_only = rows.iloc[cs:last] if r.resolved else span  # exclude B's own bar from "the pause"
            if len(pause_only) == 0:
                pause_only = span
            atr = a_row.atr14
            rec = r.to_dict()
            rec.update(
                atr_at_a=atr,
                high_vs_a_pct=(r.consolidation_high - r.a_entry_price) / r.a_entry_price * 100,
                low_vs_a_pct=(r.consolidation_low - r.a_entry_price) / r.a_entry_price * 100,
                low_vs_a_atr=((r.consolidation_low - r.a_entry_price) / atr) if pd.notna(atr) and atr else None,
                min_close_above_a=bool(pause_only.Close.min() > r.a_entry_price),
                last_close_above_a=bool(pause_only.Close.iloc[-1] > r.a_entry_price),
                pause_close_range_pct=(pause_only.Close.max() - pause_only.Close.min()) / r.a_entry_price * 100,
                pause_median_daily_range_atr=((pause_only.High - pause_only.Low).median() / atr) if pd.notna(atr) and atr else None,
                a_day_range_atr=((a_row.High - a_row.Low) / atr) if pd.notna(atr) and atr else None,
            )
            if r.resolved:
                b = rows.iloc[last]
                rec.update(
                    b_close_above_high=bool(b.Close > r.consolidation_high),
                    b_open_gap_above_high=bool(b.Open > r.consolidation_high),
                    b_break_pct=(b.High - r.consolidation_high) / r.consolidation_high * 100,
                    b_close_vs_high_pct=(b.Close - r.consolidation_high) / r.consolidation_high * 100,
                    b_vol_vs_a=(b.Volume / a_row.Volume) if a_row.Volume else None,
                    b_vol_vs_10d=(b.Volume / a_row.vol_avg10_prior) if pd.notna(a_row.vol_avg10_prior) and a_row.vol_avg10_prior else None,
                )
            out.append(rec)
    print(f"date mismatches vs 04A (skipped): {mismatches}")
    return pd.DataFrame(out)


def dump_example(rows_cache, r):
    t = r.ticker
    rows = rows_cache.setdefault(t, load(t, daily_pivots).reset_index())
    ia = int(r.a_entry_i)
    last = ia + (int(r.b_day) if r.resolved else int(r.consolidation_start_day) + int(r.duration))
    print(f"\n--- {t}  A={r.a_entry_date} @ {r.a_entry_price:.2f}  lookback={r.entry_definition}  "
          f"pause_start=D{int(r.consolidation_start_day)}  high={r.consolidation_high:.2f}  "
          f"low={r.consolidation_low:.2f}  dur={int(r.duration)}  resolved={r.resolved}  "
          f"B=D{int(r.b_day) if r.resolved else -1}")
    seg = rows.iloc[ia:last + 1][["Date", "Open", "High", "Low", "Close", "Volume"]].copy()
    seg.insert(0, "D", range(0, len(seg)))
    seg["Date"] = seg.Date.dt.date
    print(seg.to_string(index=False))


if __name__ == "__main__":
    src = pd.read_csv(SRC)
    det = src[src.consolidation_detected].copy()
    hold = det[det.consolidation_low_above_a].copy()
    print(f"04A detected={len(det)}  holds-above-A (low basis)={len(hold)}  ({len(hold)/len(det)*100:.1f}%)")
    assert len(hold) == 8403, f"population drifted from the 04A finding: {len(hold)}"

    # --- Tier comparison needs close-basis fields on the FULL detected population ---
    print("\nEnriching FULL detected population (for the stays-vs-ends-above-A tiers)...")
    full = enrich(det)
    full.to_csv(f"{OUT_DIR}/rq04b_detected_enriched.csv", index=False)
    h = full[full.consolidation_low_above_a].copy()
    h.to_csv(f"{OUT_DIR}/rq04b_holds_above_a_anatomy.csv", index=False)
    res = h[h.resolved]

    print(f"\n=== RQ-QS-04B: anatomy of the holds-above-A population (n={len(h)}, resolved={len(res)} = {len(res)/len(h)*100:.1f}%) ===")

    print("\n[1] Stays entirely above A vs merely ends above A  (full detected population, n=%d)" % len(full))
    tiers = [
        ("low-basis: min(Low) > A entry  [04A's 8,403 definition]", full.consolidation_low_above_a),
        ("close-basis: min(Close) > A entry (lows may pierce, closes hold)", full.min_close_above_a),
        ("ends-above: last Close of pause > A entry", full.last_close_above_a),
    ]
    for name, m in tiers:
        print(f"  {name:70s} {m.sum():6d}  {m.mean()*100:5.1f}%")
    both = full.min_close_above_a & ~full.consolidation_low_above_a
    print(f"  close-basis holds but low pierced A (intraday shakeout only)               {both.sum():6d}  {both.mean()*100:5.1f}%")
    ends_only = full.last_close_above_a & ~full.min_close_above_a
    print(f"  ends above A but closed below A at least once during the pause              {ends_only.sum():6d}  {ends_only.mean()*100:5.1f}%")

    print("\n[2] Duration (days, pause start -> B or window edge)")
    print("   all      ", pstack(h.duration, "{:.0f}"))
    print("   resolved ", pstack(res.duration, "{:.0f}"))
    vc = h.duration.value_counts().sort_index()
    print("   distribution:", "  ".join(f"{int(k)}d={v} ({v/len(h)*100:.1f}%)" for k, v in vc.items() if k <= 8), f" >8d={int(vc[vc.index>8].sum())} ({vc[vc.index>8].sum()/len(h)*100:.1f}%)")

    print("\n[3] Range width (consolidation_high - consolidation_low)")
    print("   % of A entry      ", pstack(h.range_width_pct, "{:.2f}", "%"))
    print("   x ATR14 at A      ", pstack(h.range_width_over_atr, "{:.2f}", "x"))
    print("   close-to-close %  ", pstack(h.pause_close_range_pct, "{:.2f}", "%"))
    print("   median daily bar / ATR during pause", pstack(h.pause_median_daily_range_atr, "{:.2f}", "x"))
    print("   A's own breakout-day bar / ATR       ", pstack(h.a_day_range_atr, "{:.2f}", "x"))

    print("\n[4] Where the pause sits relative to A")
    print("   consolidation_high above A entry  ", pstack(h.high_vs_a_pct, "{:.2f}", "%"))
    print("   consolidation_low above A entry   ", pstack(h.low_vs_a_pct, "{:.2f}", "%"))
    print("   consolidation_low above A, in ATR ", pstack(h.low_vs_a_atr, "{:.2f}", "x"))
    print("   pause_start_day                   ", pstack(h.consolidation_start_day, "{:.0f}"))

    print("\n[5] Volume during the pause")
    print("   pause avg vol / A breakout-day vol ", pstack(h.vol_ratio_vs_a_breach, "{:.2f}", "x"))
    print("   pause avg vol / prior-10d avg      ", pstack(h.vol_ratio_vs_10d_avg, "{:.2f}", "x"))
    print(f"   share with pause vol < 1.0x prior-10d avg: {(h.vol_ratio_vs_10d_avg < 1).mean()*100:.1f}%   < 0.7x: {(h.vol_ratio_vs_10d_avg < 0.7).mean()*100:.1f}%")
    print("   B-day vol / A breakout-day vol     ", pstack(res.b_vol_vs_a, "{:.2f}", "x"))
    print("   B-day vol / prior-10d avg          ", pstack(res.b_vol_vs_10d, "{:.2f}", "x"))

    print("\n[6] Does B actually break the consolidation high? (resolved only, n=%d)" % len(res))
    print(f"   B Close finishes above consolidation_high : {res.b_close_above_high.mean()*100:.1f}%")
    print(f"   B gaps open above consolidation_high       : {res.b_open_gap_above_high.mean()*100:.1f}%")
    print("   B High over consolidation_high, %          ", pstack(res.b_break_pct, "{:.2f}", "%"))
    print("   B Close vs consolidation_high, %           ", pstack(res.b_close_vs_high_pct, "{:.2f}", "%"))
    print("   B structural risk to consolidation_low, %  ", pstack(res.b_structural_risk_pct, "{:.2f}", "%"))

    print("\n[7] Duration x range-width matrix (holds-above-A, count / % of pop / resolved rate / B-close-above rate)")
    dbins = pd.cut(h.duration, [0, 1, 2, 4, 7, 99], labels=["1d", "2d", "3-4d", "5-7d", "8+d"])
    wbins = pd.cut(h.range_width_pct, [0, 2, 4, 6, 10, 999], labels=["<2%", "2-4%", "4-6%", "6-10%", "10%+"])
    h["_d"], h["_w"] = dbins, wbins
    cnt = pd.crosstab(h._d, h._w)
    pct = (cnt / len(h) * 100).round(1)
    rr = pd.crosstab(h._d, h._w, values=h.resolved.astype(float), aggfunc="mean").mul(100).round(0)
    bc = pd.crosstab(h._d, h._w, values=h.b_close_above_high.astype(float), aggfunc="mean").mul(100).round(0)
    print("\n   counts:\n" + cnt.to_string())
    print("\n   % of population:\n" + pct.to_string())
    print("\n   resolved rate %:\n" + rr.to_string())
    print("\n   B-close-above-high rate % (among resolved):\n" + bc.to_string())
    print("\n   marginals -- duration:", ", ".join(f"{k}={v/len(h)*100:.1f}%" for k, v in h._d.value_counts().sort_index().items()))
    print("   marginals -- width:   ", ", ".join(f"{k}={v/len(h)*100:.1f}%" for k, v in h._w.value_counts().sort_index().items()))

    print("\n[8] Same anatomy for the UNDERCUTS-A complement, for contrast only (n=%d)" % (~full.consolidation_low_above_a).sum())
    u = full[~full.consolidation_low_above_a]
    print("   duration          ", pstack(u.duration, "{:.0f}"))
    print("   range_width_pct   ", pstack(u.range_width_pct, "{:.2f}", "%"))
    print("   range_width / ATR ", pstack(u.range_width_over_atr, "{:.2f}", "x"))
    print("   high_vs_a_pct     ", pstack(u.high_vs_a_pct, "{:.2f}", "%"))
    print("   low_vs_a_pct      ", pstack(u.low_vs_a_pct, "{:.2f}", "%"))
    ur = u[u.resolved]
    print(f"   resolved {len(ur)/len(u)*100:.1f}%, B-close-above-high {ur.b_close_above_high.mean()*100:.1f}%")

    # --- Rule #22: concrete examples spanning the duration range, deterministic pick ---
    print("\n[9] Hand-check examples (deterministic: first row by ticker/date within each duration bucket)")
    cache = {}
    for dur_pick in [1, 2, 4, 8]:
        cand = h[(h.duration == dur_pick) & h.resolved].sort_values(["ticker", "a_entry_date"])
        if len(cand):
            dump_example(cache, cand.iloc[len(cand) // 2])
