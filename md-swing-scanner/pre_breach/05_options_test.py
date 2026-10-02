"""Pre-breach detector -- P7: blind ATM call at the open vs entry at the real touch, on real
NSE bhavcopy legs (03_option_legs.py). 1R = premium paid. Exits identical across arms:
E1 = day-T close, E2 = T+1 open. Friction haircuts 0/2/5% of premium round trip.

Detector score = SPEC P6's distance-only logistic (score_dist) -- P6 showed the full daily
model adds nothing OOS, so the simpler score is the honest one. Gap-through opens (fire is
known at 09:15) get score 1.0; for them blind == touch by construction.
"""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
FRICTIONS = [0.0, 0.02, 0.05]


def stack(r):
    r = pd.Series(r).dropna()
    if len(r) == 0:
        return dict(n=0)
    w, l = r[r > 0], r[r <= 0]
    return dict(n=len(r), meanR=r.mean(), medR=r.median(), win=(r > 0).mean() * 100,
                mw25=(r >= .25).mean() * 100, q50=(r >= .5).mean() * 100, full=(r >= 1).mean() * 100,
                payoff=(w.mean() / abs(l.mean())) if len(w) and len(l) and l.mean() != 0 else np.nan)


def fmt(label, s):
    if s["n"] == 0:
        return f"| {label} | 0 | | | | | | | |"
    return (f"| {label} | {s['n']} | {s['meanR']:+.3f} | {s['medR']:+.3f} | {s['win']:.1f} | {s['mw25']:.1f} | "
            f"{s['q50']:.1f} | {s['full']:.1f} | {s['payoff']:.2f} |")


def book(df, rcol, k):
    """Per-day capital-constrained book: top-k by score each day, equal premium each.
    Daily R = sum of the k positions' R (each position risks 1R = its premium)."""
    picks = df.sort_values("score", ascending=False).groupby("date").head(k)
    daily = picks.groupby("date")[rcol].sum()
    cum = daily.cumsum()
    dd = (cum - cum.cummax()).min()
    streak = cur = 0
    for v in daily.values:
        cur = cur + 1 if v < 0 else 0
        streak = max(streak, cur)
    return dict(days=len(daily), trades=len(picks), totalR=daily.sum(), perTradeR=picks[rcol].mean(),
                maxDD=dd, worstStreak=streak)


def main():
    legs = pd.read_csv(OUT / "option_legs.csv", parse_dates=["date"])
    panel = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    sc = pd.read_csv(OUT / "detector_scores.csv", parse_dates=["date"])
    d = legs.merge(panel[["ticker", "date", "touched", "gap_through", "close_above", "dist_open_pct",
                          "dist_open_atr"]], on=["ticker", "date"], how="inner", validate="1:1")
    assert len(d) == len(legs), (len(d), len(legs))
    d = d.merge(sc[["ticker", "date", "score_dist"]], on=["ticker", "date"], how="left", validate="1:1")
    d["score"] = np.where(d.gap_through, 1.0, d.score_dist)
    d = d.dropna(subset=["score"])
    d["year"] = d.date.dt.year
    print(f"option candidate-days n={len(d)}  touched={d.touched.mean()*100:.1f}%  gap_through={d.gap_through.mean()*100:.1f}%")
    t = d[d.touched]
    print(f"touch-price clamp rate on touched days: {t.touch_clamped.mean()*100:.1f}% "
          f"(gap-through excluded: {t[~t.gap_through].touch_clamped.mean()*100:.1f}%)")
    print(f"median entry premium as % of spot: {(d.opt_open/d.open_real*100).median():.2f}%   median DTE {d.dte.median():.0f}")

    for ex, col in [("E1 day-T close", "opt_close"), ("E2 T+1 open", "opt_next_open")]:
        d["R_blind"] = d[col] / d.opt_open - 1
        d["R_touch"] = np.where(d.touched, d[col] / d.opt_touch - 1, np.nan)
        for f in FRICTIONS:
            d[f"Rb_{f}"] = d.R_blind - f
            d[f"Rt_{f}"] = d.R_touch - f
        print(f"\n################ {ex} ################")
        print("\nPer-trade R stack, 0% friction (1R = premium)")
        print("| arm | n | meanR | medR | win>0 % | >=0.25R % | >=0.5R % | >=1R % | payoff |")
        print("|---|---|---|---|---|---|---|---|---|")
        print(fmt("blind, all candidates", stack(d.R_blind)))
        print(fmt("  of which fired", stack(d[d.touched].R_blind)))
        print(fmt("  of which missed", stack(d[~d.touched].R_blind)))
        d["dec"] = d.groupby("year").score.transform(lambda s: s.rank(pct=True))
        top = d[d.dec >= 0.9]
        print(fmt("blind, top-decile score", stack(top.R_blind)))
        print(fmt("blind, opened <=0.5% below", stack(d[(~d.gap_through) & (d.dist_open_pct <= 0.5)].R_blind)))
        print(fmt("touch, all touchers", stack(d.R_touch)))
        print(fmt("touch, intraday touch only", stack(d[d.touched & ~d.gap_through].R_touch)))
        print(fmt("gap-through (blind==touch)", stack(d[d.gap_through].R_blind)))

        print("\nPer year, per-trade meanR (0% / 5% friction): blind-all | blind-top-decile | touch-all")
        print("| year | blind-all | blind-top10% | touch-all | touch n | top10% fire rate |")
        print("|---|---|---|---|---|---|")
        for yr, g in d.groupby("year"):
            tp = g[g.dec >= .9]
            print(f"| {yr} | {g.R_blind.mean():+.3f} / {g['Rb_0.05'].mean():+.3f} | {tp.R_blind.mean():+.3f} / {tp['Rb_0.05'].mean():+.3f} | "
                  f"{g.R_touch.mean():+.3f} / {g['Rt_0.05'].mean():+.3f} | {g.touched.sum()} | {tp.touched.mean()*100:.1f}% |")

        print("\nCapital-constrained daily book (top-K by score per day; touch arm ranks that day's touchers by the same score)")
        print("| year | K | friction | blind totalR | blind R/trade | blind maxDD | blind worst day-streak | touch totalR | touch R/trade | touch maxDD | touch worst streak |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        for yr, g in d.groupby("year"):
            for k in [1, 3, 5]:
                for f in [0.0, 0.05]:
                    b = book(g, f"Rb_{f}", k)
                    tt = book(g[g.touched], f"Rt_{f}", k)
                    print(f"| {yr} | {k} | {int(f*100)}% | {b['totalR']:+.1f} | {b['perTradeR']:+.3f} | {b['maxDD']:.1f} | {b['worstStreak']} | "
                          f"{tt['totalR']:+.1f} | {tt['perTradeR']:+.3f} | {tt['maxDD']:.1f} | {tt['worstStreak']} |")
    d.to_csv(OUT / "options_test_rows.csv", index=False)


if __name__ == "__main__":
    main()
