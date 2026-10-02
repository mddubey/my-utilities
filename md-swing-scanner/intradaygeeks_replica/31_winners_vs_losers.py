"""Can ANY combination of pre-entry features separate winners from losers OUT OF SAMPLE? Spec fixed 2026-10-02.
Set: 1H-close trades (15's filter, 2024-26, n~38k). Train < 2025-07-01, test >= 2025-07-01 (never seen in fitting).
Winner = R >= 0.25 (project's Meaningful Win). Features: everything known at entry (19 cues + 17 splits + new daily
ret5/ret20/room-to-20d-extreme), direction-signed so '+' = with the trade.
 1. Univariate: train quintile cutpoints; does the train top-vs-bottom ordering hold in test? (test spread, t)
 2. Multivariate (numpy only): ridge regression on ret% (clipped +/-3) and an additive quintile score.
    Test metrics: AUC for winner (0.5 = random), Spearman(score, ret), mean ret%/R of top 20% & 10% vs baseline."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
HERE = Path(__file__).resolve().parent
SPLIT = pd.Timestamp("2025-07-01")


def daily_feats(args):
    t, g = args
    d = load(t); d = d[["High", "Low", "Close"]]
    c = d.Close
    f = pd.DataFrame({"ret5": c.pct_change(5), "ret20": c.pct_change(20),
                      "hi20": d.High.rolling(20).max(), "lo20": d.Low.rolling(20).min()}).shift(1)   # prior close
    out = []
    for r in g.itertuples():
        x = f.loc[r.date] if r.date in f.index else None
        out.append((r.Index, *(x.values if x is not None else [np.nan] * 4)))
    return out


def build():
    C = pd.read_csv(HERE / "cues_1h_close.csv", parse_dates=["date"])
    S = pd.read_csv(HERE / "splits_1h_close.csv")[["ticker", "ts", "hadx", "dadx", "d_piv", "w_piv"]]
    X = C.merge(S, on=["ticker", "ts"], how="left")
    assert len(X) == len(C)
    from multiprocessing import Pool
    with Pool(6) as p: rows = sum(p.map(daily_feats, list(X.groupby("ticker"))), [])
    F = pd.DataFrame(rows, columns=["i", "ret5", "ret20", "hi20", "lo20"]).set_index("i")
    X = X.join(F)
    s = np.where(X.side == "long", 1, -1)
    X["is_short"] = (s == -1).astype(float)
    X["hour"] = pd.to_datetime(X.bar_ts).dt.hour + pd.to_datetime(X.bar_ts).dt.minute / 60
    for c in ("stock_so", "nifty_so", "sector_so", "ret5", "ret20"): X[c + "_s"] = X[c] * s
    X["rsi_s"] = (X.rsi1h - 50) * s
    X["room20"] = np.where(s == 1, X.hi20 / X.entry - 1, 1 - X.lo20 / X.entry) * 100
    X["stop_norm"] = X.stop_pct / X.avg_1h_range_pct
    X["vwap_with_f"] = X.vwap_with.astype(float)
    X["d8_touch"] = (X.dstate == "touch").astype(float)
    for c in ("d_piv", "w_piv"):
        for v in ("room1+", "within1", "through"): X[f"{c}_{v}"] = (X[c] == v).astype(float)
    X["logprice"] = np.log(X.entry)
    return X


FEATS = ["is_short", "hour", "adx", "hadx", "dadx", "close_past_ema", "stop_pct", "stop_norm", "bar_range_pct",
         "avg_1h_range_pct", "wick_past_ema_pct", "d8_ext_vs_d8_pct", "d8_touch", "stock_so_s", "nifty_so_s", "sector_so_s",
         "rvol", "vwap_with_f", "atrp", "gap_s", "rsi_s", "ret5_s", "ret20_s", "room20", "logprice",
         "d_piv_room1+", "d_piv_within1", "d_piv_through", "w_piv_room1+", "w_piv_within1", "w_piv_through"]


def auc(score, y):
    r = pd.Series(score).rank().values; n1 = y.sum(); n0 = len(y) - n1
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


if __name__ == "__main__":
    X = build(); X.to_csv(HERE / "winners_losers_features_1h.csv", index=False)
    X["win"] = (X.R >= 0.25).astype(int)
    tr, te = X[X.date < SPLIT].copy(), X[X.date >= SPLIT].copy()
    print(f"train {len(tr)} ({tr.date.min().date()}..{tr.date.max().date()}) win {tr.win.mean()*100:.1f}% | "
          f"test {len(te)} ({te.date.min().date()}..{te.date.max().date()}) win {te.win.mean()*100:.1f}% mean {te.ret.mean():+.3f}%")
    # 1. univariate replication
    print("\n1. UNIVARIATE: top-vs-bottom quintile spread in mean ret%, direction chosen on TRAIN, measured on TEST")
    print("| feature | train spread | test spread (same direction) | test t | replicates? |\n|---|---|---|---|---|")
    uni = []
    for f in FEATS:
        a, b = tr[[f, "ret"]].dropna(), te[[f, "ret"]].dropna()
        if a[f].nunique() <= 2:
            hi, lo = a[a[f] == a[f].max()].ret, a[a[f] == a[f].min()].ret
            thi, tlo = b[b[f] == a[f].max()].ret, b[b[f] == a[f].min()].ret
        else:
            q = a[f].quantile([.2, .8]).values
            hi, lo = a[a[f] >= q[1]].ret, a[a[f] <= q[0]].ret
            thi, tlo = b[b[f] >= q[1]].ret, b[b[f] <= q[0]].ret
        sp = hi.mean() - lo.mean(); sgn = np.sign(sp)
        tsp = (thi.mean() - tlo.mean()) * sgn
        tt = tsp / np.sqrt(thi.var() / len(thi) + tlo.var() / len(tlo)) if len(thi) > 30 and len(tlo) > 30 else np.nan
        uni.append((f, sp, tsp, tt))
    for f, sp, tsp, tt in sorted(uni, key=lambda z: -abs(z[1])):
        print(f"| {f} | {sp:+.3f} | {tsp:+.3f} | {tt:+.2f} | {'YES' if tt > 2 else ('weak' if tt > 0 else 'no')} |")
    # 2. multivariate
    tr2, te2 = tr.dropna(subset=FEATS), te.dropna(subset=FEATS)
    mu, sd = tr2[FEATS].mean(), tr2[FEATS].std().replace(0, 1)
    Ztr, Zte = ((tr2[FEATS] - mu) / sd).values, ((te2[FEATS] - mu) / sd).values
    ytr = tr2.ret.clip(-3, 3).values
    A = np.c_[np.ones(len(Ztr)), Ztr]; lam = 10.0
    w = np.linalg.solve(A.T @ A + lam * np.eye(A.shape[1]), A.T @ ytr)
    s_ridge = np.c_[np.ones(len(Zte)), Zte] @ w
    s_add = np.zeros(len(te2)); s_add_tr = np.zeros(len(tr2))
    for f in FEATS:
        if tr2[f].nunique() <= 2:
            m = tr2.groupby(f).ret.mean(); s_add += te2[f].map(m).fillna(0).values - tr2.ret.mean()
        else:
            cuts = np.unique(tr2[f].quantile([.2, .4, .6, .8]).values)
            qt, qe = np.digitize(tr2[f], cuts), np.digitize(te2[f], cuts)
            m = pd.Series(tr2.ret.values).groupby(qt).mean()
            s_add += pd.Series(qe).map(m).fillna(tr2.ret.mean()).values - tr2.ret.mean()
    print(f"\n2. MULTIVARIATE on TEST (n={len(te2)}, baseline mean {te2.ret.mean():+.3f}%, meanR {te2.R.mean():+.3f}, win {te2.win.mean()*100:.1f}%)")
    print("| model | AUC winner | Spearman(score, ret) | top 20%: n / mean% / meanR / win% | top 10%: mean% / meanR | bottom 20% mean% |\n|---|---|---|---|---|---|")
    for nm, sc in (("ridge regression", s_ridge), ("additive quintile score", s_add)):
        sc = pd.Series(sc, index=te2.index); rk = sc.rank(pct=True)
        t20, t10, b20 = te2[rk >= .8], te2[rk >= .9], te2[rk <= .2]
        print(f"| {nm} | {auc(sc.values, te2.win.values):.3f} | {sc.corr(te2.ret, method='spearman'):+.3f} | {len(t20)} / {t20.ret.mean():+.3f} / {t20.R.mean():+.3f} / {t20.win.mean()*100:.1f} | "
              f"{t10.ret.mean():+.3f} / {t10.R.mean():+.3f} | {b20.ret.mean():+.3f} |")
        te2[f"score_{nm[:5]}"] = sc
    for nm in ("score_ridge", "score_addit"):
        top = te2[te2[nm].rank(pct=True) >= .8]
        print(f"  {nm} top 20% by month: " + " ".join(f"{k}:{v:+.2f}" for k, v in top.groupby(top.date.dt.to_period('Q')).ret.mean().items())
              + f" | by side: " + str(top.groupby("side").ret.mean().round(3).to_dict()))
    print("\nridge weights (standardized, ret% per 1 sd), largest:", ", ".join(f"{f} {v:+.3f}" for f, v in sorted(zip(FEATS, w[1:]), key=lambda z: -abs(z[1]))[:8]))
