"""Pre-breach detector -- tests P1-P6, P8 from SPEC.md (predictions frozen before this ran).
Prints tables; writes nothing except feature_tests_out.txt via shell redirect."""
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
YEARS = [2022, 2023, 2024, 2025, 2026]


def auc(score, y):
    """Mann-Whitney AUC; higher score should mean y=1."""
    s = pd.Series(score).reset_index(drop=True)
    y = pd.Series(y).astype(bool).reset_index(drop=True)
    m = s.notna()
    s, y = s[m], y[m]
    r = s.rank()
    n1, n0 = y.sum(), (~y).sum()
    if n1 == 0 or n0 == 0:
        return np.nan
    return (r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def logit_fit(X, y, l2=1e-3, iters=50):
    X = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(X.shape[1])
    for _ in range(iters):  # Newton / IRLS
        p = 1 / (1 + np.exp(-X @ w))
        g = X.T @ (p - y) + l2 * np.r_[0, w[1:]]
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(X.shape[1])
        w -= np.linalg.solve(H, g)
    return w


def logit_pred(w, X):
    X = np.column_stack([np.ones(len(X)), X])
    return 1 / (1 + np.exp(-X @ w))


def rate(s):
    return f"{s.mean()*100:.1f}% (n={len(s)})"


def main():
    p = pd.read_csv(OUT / "panel.csv", parse_dates=["date"])
    p["year"] = p.date.dt.year
    p["abs_ret_prev"] = p.ret_prev_pct.abs()
    below = p[~p.gap_through].copy()
    print(f"panel n={len(p)}  gap_through={p.gap_through.mean()*100:.1f}%  "
          f"touched(all)={p.touched.mean()*100:.1f}%  touched|opened-below={below.touched.mean()*100:.1f}%")

    # ---------------- P1 / F6 ----------------
    print("\n=== P1/F6: FIRE AUC, opened-below-trigger candidates, per year ===")
    print("| year | n | fire% | AUC dist_prev_close_pct | AUC dist_open_pct | AUC dist_open_atr | open−prev | atr−pct |")
    print("|---|---|---|---|---|---|---|---|")
    for yr in YEARS:
        d = below[below.year == yr]
        a_prev = auc(-d.dist_prev_close_pct, d.touched)
        a_open = auc(-d.dist_open_pct, d.touched)
        a_atr = auc(-d.dist_open_atr, d.touched)
        print(f"| {yr} | {len(d)} | {d.touched.mean()*100:.1f} | {a_prev:.3f} | {a_open:.3f} | {a_atr:.3f} | {a_open-a_prev:+.3f} | {a_atr-a_open:+.3f} |")

    # ---------------- P2 / F2 ----------------
    touch_below = below[below.touched].copy()
    touch_below["dist_t"] = pd.qcut(touch_below.dist_open_atr, 3, labels=["near", "mid", "far"])
    touch_below["gap_t"] = touch_below.groupby("dist_t", observed=True).gap_pct.transform(
        lambda s: pd.qcut(s, 3, labels=["low", "mid", "high"]))
    print("\n=== P2/F2: HOLD (close_above) among touchers that opened below trigger ===")
    print("| open-dist tercile | gap low | gap mid | gap high | high−low (pp) |")
    print("|---|---|---|---|---|")
    for dt, g in touch_below.groupby("dist_t", observed=True):
        rr = g.groupby("gap_t", observed=True).close_above.mean() * 100
        print(f"| {dt} | {rr['low']:.1f} | {rr['mid']:.1f} | {rr['high']:.1f} | {rr['high']-rr['low']:+.1f} |")
    gt = p[p.gap_through]
    print(f"gap-through opens close_above: {rate(gt.close_above)}   intraday touches close_above: {rate(touch_below.close_above)}")
    print("per-year high−low gap spread (pooled over distance terciles, within-tercile rates averaged):")
    for yr in YEARS:
        g = touch_below[touch_below.year == yr]
        sp = [(x[x.gap_t == 'high'].close_above.mean() - x[x.gap_t == 'low'].close_above.mean()) * 100
              for _, x in g.groupby("dist_t", observed=True)]
        print(f"  {yr}: n={len(g)} spreads={['%+.1f' % s for s in sp]}")

    # ---------------- P8 / F7 ----------------
    print("\n=== P8/F7: HOLD vs prior-day attention |ret_prev|, within gap terciles (touchers opened below) ===")
    touch_below["gap_t2"] = pd.qcut(touch_below.gap_pct, 3, labels=["low", "mid", "high"])
    touch_below["att_t"] = touch_below.groupby("gap_t2", observed=True).abs_ret_prev.transform(
        lambda s: pd.qcut(s, 3, labels=["low", "mid", "high"]))
    print("| gap tercile | attention low | mid | high | high−low (pp) |")
    print("|---|---|---|---|---|")
    for gtl, g in touch_below.groupby("gap_t2", observed=True):
        rr = g.groupby("att_t", observed=True).close_above.mean() * 100
        print(f"| {gtl} | {rr['low']:.1f} | {rr['mid']:.1f} | {rr['high']:.1f} | {rr['high']-rr['low']:+.1f} |")
    touch_below["vol_t"] = touch_below.groupby("gap_t2", observed=True).vol_ratio_prev.transform(
        lambda s: pd.qcut(s, 3, labels=["low", "mid", "high"]))
    print("secondary, vol_ratio_prev terciles:")
    for gtl, g in touch_below.groupby("gap_t2", observed=True):
        rr = g.groupby("vol_t", observed=True).close_above.mean() * 100
        print(f"  gap {gtl}: low {rr['low']:.1f} / mid {rr['mid']:.1f} / high {rr['high']:.1f}  ({rr['high']-rr['low']:+.1f})")

    # ---------------- P5 / F5 ----------------
    print("\n=== P5/F5: FIRE vs Nifty opening gap, within open-distance terciles (opened below) ===")
    below["dist_t"] = pd.qcut(below.dist_open_atr, 3, labels=["near", "mid", "far"])
    below["ng"] = pd.cut(below.nifty_gap_pct, [-99, -0.5, 0.5, 99], labels=["<-0.5", "flat", ">+0.5"])
    print("| open-dist tercile | nifty<-0.5 | flat | nifty>+0.5 | ratio up/down |")
    print("|---|---|---|---|---|")
    for dt, g in below.groupby("dist_t", observed=True):
        rr = g.groupby("ng", observed=True).touched.agg(["mean", "size"])
        print(f"| {dt} | {rr.loc['<-0.5','mean']*100:.1f} (n={rr.loc['<-0.5','size']}) | {rr.loc['flat','mean']*100:.1f} | "
              f"{rr.loc['>+0.5','mean']*100:.1f} (n={rr.loc['>+0.5','size']}) | {rr.loc['>+0.5','mean']/rr.loc['<-0.5','mean']:.2f}x |")

    # ---------------- P6: combined detector ----------------
    feats = ["dist_open_atr", "dist_open_pct", "gap_pct", "nifty_gap_pct", "atr_pct",
             "q_range_compression", "q_ema8_dist_pct", "q_atr_trend_15d", "q_narrowing_range",
             "freshness", "clv_prev", "abs_ret_prev", "vol_ratio_prev", "consolidation_days", "rsi_prev"]
    d = below.dropna(subset=feats + ["touched"]).copy()
    for f in feats:  # winsorize 1/99 using TRAIN quantiles only
        lo, hi = d.loc[d.year <= 2024, f].quantile([.01, .99])
        d[f] = d[f].clip(lo, hi)
    tr = d[d.year <= 2024]
    mu, sd = tr[feats].mean(), tr[feats].std()
    Z = (d[feats] - mu) / sd
    base_cols = ["dist_open_atr"]
    wb = logit_fit(Z.loc[tr.index, base_cols].values, tr.touched.values.astype(float))
    wf = logit_fit(Z.loc[tr.index, feats].values, tr.touched.values.astype(float))
    print("\n=== P6: combined FIRE detector, trained <=2024, OOS per year (opened below) ===")
    print("| year | n | fire% | AUC dist_open_atr only | AUC full model | gain | top-decile fire% (full) | top-decile fire% (dist only) |")
    print("|---|---|---|---|---|---|---|---|")
    for yr in [2025, 2026]:
        te = d[d.year == yr]
        pb = logit_pred(wb, Z.loc[te.index, base_cols].values)
        pf = logit_pred(wf, Z.loc[te.index, feats].values)
        ab, af = auc(pb, te.touched), auc(pf, te.touched)
        topf = te.touched.values[pf >= np.quantile(pf, .9)].mean() * 100
        topb = te.touched.values[pb >= np.quantile(pb, .9)].mean() * 100
        print(f"| {yr} | {len(te)} | {te.touched.mean()*100:.1f} | {ab:.3f} | {af:.3f} | {af-ab:+.3f} | {topf:.1f} | {topb:.1f} |")
    print("full-model standardized coefficients (train):")
    for f, w in sorted(zip(feats, wf[1:]), key=lambda x: -abs(x[1])):
        print(f"  {f:22s} {w:+.3f}")
    d.assign(score_full=logit_pred(wf, Z[feats].values), score_dist=logit_pred(wb, Z[base_cols].values))[
        ["ticker", "date", "score_full", "score_dist"]].to_csv(OUT / "detector_scores.csv", index=False)
    np.save(OUT / "detector_weights.npy", np.r_[wf])
    pd.DataFrame({"feat": feats, "mu": mu.values, "sd": sd.values}).to_csv(OUT / "detector_norm.csv", index=False)

    # ---------------- P3 / P4: intraday (74 sessions) ----------------
    it = pd.read_csv(OUT / "intraday_features.csv", parse_dates=["date"])
    print(f"\n=== intraday window: n={len(it)} candidate-days, {it.date.nunique()} sessions ===")
    for chk, dist_col, excl in [("09:25", "dist_0925_pct", "already_touched_by_0925"),
                                ("09:20", "dist_0920_pct", "already_touched_by_0920")]:
        x = it[~it[excl]].copy()
        x = x[x[dist_col] > 0]
        print(f"  at {chk}: live not-yet-fired n={len(x)}, fire-after rate={x.touched_5m.mean()*100:.1f}%")
    x = it[~it.already_touched_by_0925 & (it.dist_0925_pct > 0)].dropna(subset=["rvol_0925"]).copy()
    x["dq"] = pd.qcut(x.dist_0925_pct, 5, labels=[f"D{k}" for k in range(1, 6)])
    x["rq"] = x.groupby("dq", observed=True).rvol_0925.transform(lambda s: pd.qcut(s, 5, labels=False, duplicates="drop"))
    print("\n=== P3/F3: FIRE after 09:25 by rvol_0925 quintile within dist_0925 quintile ===")
    print("| dist quintile (D1=nearest) | median dist% | rvol Q1 | Q2 | Q3 | Q4 | Q5 | Q5/Q1 |")
    print("|---|---|---|---|---|---|---|---|")
    for dq, g in x.groupby("dq", observed=True):
        rr = g.groupby("rq").touched_5m.mean() * 100
        print(f"| {dq} | {g.dist_0925_pct.median():.2f} | " + " | ".join(f"{v:.1f}" for v in rr.values) +
              f" | {rr.iloc[-1]/rr.iloc[0] if rr.iloc[0] else np.inf:.2f}x |")
    h = it[it.touched_5m & it.held30.notna() & ~it.already_touched_by_0925].dropna(subset=["rvol_0925"]).copy()
    h["held30"] = h.held30.astype(bool)
    h["rq"] = pd.qcut(h.rvol_0925, 5, labels=False, duplicates="drop")
    print("HOLD (held30) by rvol_0925 quintile among later touchers: " +
          " / ".join(f"Q{k+1} {v*100:.1f}%" for k, v in h.groupby("rq").held30.mean().items()) + f"  (n={len(h)}, overall {h.held30.mean()*100:.1f}%)")

    y = it[~it.already_touched_by_0920 & (it.dist_0920_pct > 0)].dropna(subset=["bar1_clv"]).copy()
    y["dq"] = pd.qcut(y.dist_0920_pct, 5, labels=[f"D{k}" for k in range(1, 6)])
    y["cq"] = y.groupby("dq", observed=True).bar1_clv.transform(lambda s: pd.qcut(s.rank(method="first"), 3, labels=["low", "mid", "high"]))
    print("\n=== P4/F4: FIRE after 09:20 by first-bar CLV tercile within dist_0920 quintile ===")
    print("| dist quintile | CLV low | mid | high | high/low |")
    print("|---|---|---|---|---|")
    for dq, g in y.groupby("dq", observed=True):
        rr = g.groupby("cq", observed=True).touched_5m.mean() * 100
        print(f"| {dq} | {rr['low']:.1f} | {rr['mid']:.1f} | {rr['high']:.1f} | {rr['high']/rr['low'] if rr['low'] else np.inf:.2f}x |")
    h2 = it[it.touched_5m & it.held30.notna() & ~it.already_touched_by_0920].dropna(subset=["bar1_clv"]).copy()
    h2["held30"] = h2.held30.astype(bool)
    h2["cq"] = pd.qcut(h2.bar1_clv.rank(method="first"), 3, labels=["low", "mid", "high"])
    print("HOLD (held30) by bar1_clv tercile among later touchers: " +
          " / ".join(f"{k} {v*100:.1f}%" for k, v in h2.groupby("cq", observed=True).held30.mean().items()) + f"  (n={len(h2)})")
    print(f"overall held30 among all touchers in window: {it[it.touched_5m].held30.dropna().astype(bool).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
