"""RQ-QS-07A-P6 -- S Intervention Failure Anatomy (2026-09-30, critic-specified).

NOT another predictor search. NOT an intervention rescue. Uses ONLY
already-existing QS-A trajectory/realized-R variables (no new features, no
new candidate definitions, no threshold search) to determine WHICH
component of the already-observed S-vs-non-S relationship moved between
the successful pre-2025/2025 periods and the failed 2026 period (P5).

Critic's exact four candidate explanations, tested in order:
  (1) Opportunity/MFE deterioration -- did S-tagged trades stop generating
      as much peak favorable excursion in 2026?
  (2) MAE/stop interaction -- did the stop get hit more often, sooner, or
      with a materially different risk distance?
  (3) Giveback/retention deterioration -- P3's own finding was "S doesn't
      create more MFE, it improves retention." Did that retention
      advantage specifically disappear/reverse?
  (4) Population/ticker/episode concentration -- is the 2026 reversal being
      driven by a small cluster of tickers/episodes rather than a broad
      shift?

Comparison: S-tagged vs non-S (not vs. the S-inclusive baseline), across
three periods: pre-2025 (discovery), 2025, 2026 -- matching P5's own
pre-registered split exactly, no new period boundaries invented.

No intervention. No new S threshold. No rescue of the failed period. This
is a diagnostic reading of ALREADY-COLLECTED evidence, per critic's exact
framing.
"""
import sys, os
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd

OUT_DIR = "swing_qs_07a"

print("Loading the already-computed QS-A population (P4's realized-R, P5's period split)...", flush=True)
env = pd.read_csv(f"{OUT_DIR}/p4_baseline_positions.csv", parse_dates=["entry_date", "exit_date"])
env = env[env.final_r.notna()].copy()

env["period"] = np.select(
    [env.entry_date < "2025-01-01", env.entry_date < "2026-01-01"],
    ["pre-2025", "2025"], default="2026")
PERIODS = ["pre-2025", "2025", "2026"]


def episodes(sub):
    count = 0
    for t, g in sub.sort_values("entry_date").groupby("ticker"):
        dates = g.entry_date.tolist()
        if not dates:
            continue
        count += 1
        for i in range(1, len(dates)):
            if (dates[i] - dates[i - 1]).days > 10:
                count += 1
    return count


rows = []
print(f"\n{'='*120}\n(1) OPPORTUNITY -- D1/D3/D5 MFE, S-tagged vs non-S, by period\n{'='*120}")
for p in PERIODS:
    seg = env[env.period == p]
    s, ns = seg[seg.is_S], seg[~seg.is_S]
    print(f"\n-- {p} -- S n={len(s):,}  non-S n={len(ns):,}")
    for d in [1, 3, 5]:
        col = f"mfe_D{d}"
        print(f"   MFE D{d}: S={s[col].median():+.3f}R  non-S={ns[col].median():+.3f}R  gap={s[col].median()-ns[col].median():+.3f}")
        rows.append(dict(section="opportunity", period=p, metric=f"mfe_D{d}", s_val=s[col].median(), nons_val=ns[col].median()))

print(f"\n{'='*120}\n(2) STOP INTERACTION -- stop rate, day-of-stop timing, risk distance\n{'='*120}")
for p in PERIODS:
    seg = env[env.period == p]
    s, ns = seg[seg.is_S], seg[~seg.is_S]
    s_stop_rate = s.stopped_by_D15.notna().mean() * 100
    ns_stop_rate = ns.stopped_by_D15.notna().mean() * 100
    print(f"\n-- {p} -- stop rate: S={s_stop_rate:.1f}%  non-S={ns_stop_rate:.1f}%  gap={s_stop_rate-ns_stop_rate:+.1f}pp")
    rows.append(dict(section="stop_rate", period=p, metric="stop_rate_pct", s_val=s_stop_rate, nons_val=ns_stop_rate))
    for label, df in [("S", s), ("non-S", ns)]:
        stopped = df[df.stopped_by_D15.notna()]
        if len(stopped) < 10:
            continue
        early = (stopped.stopped_by_D15 <= 3).mean() * 100
        mid = ((stopped.stopped_by_D15 > 3) & (stopped.stopped_by_D15 <= 7)).mean() * 100
        late = (stopped.stopped_by_D15 > 7).mean() * 100
        print(f"   {label} stop timing: early(D1-3)={early:.1f}%  mid(D4-7)={mid:.1f}%  late(D8-15)={late:.1f}%  "
              f"median_day={stopped.stopped_by_D15.median():.1f}")
    s_risk, ns_risk = s.initial_risk_pct.median(), ns.initial_risk_pct.median()
    print(f"   median initial_risk_pct (stop distance): S={s_risk:.2f}%  non-S={ns_risk:.2f}%")
    rows.append(dict(section="risk_distance", period=p, metric="initial_risk_pct", s_val=s_risk, nons_val=ns_risk))

print(f"\n{'='*120}\n(3) RETENTION -- D3/D5/D10/D15 close, giveback (P3's own original finding was retention, not MFE)\n{'='*120}")
for p in PERIODS:
    seg = env[env.period == p]
    s, ns = seg[seg.is_S], seg[~seg.is_S]
    print(f"\n-- {p} --")
    for d in [3, 5, 10, 15]:
        col = f"close_r_D{d}"
        gap = s[col].median() - ns[col].median()
        print(f"   close_r D{d}: S={s[col].median():+.3f}R  non-S={ns[col].median():+.3f}R  gap={gap:+.3f}")
        rows.append(dict(section="retention", period=p, metric=f"close_r_D{d}", s_val=s[col].median(), nons_val=ns[col].median()))
    s_gb, ns_gb = s.giveback_from_mfe_pct.dropna(), ns.giveback_from_mfe_pct.dropna()
    s_full, ns_full = (s_gb >= 100).mean() * 100, (ns_gb >= 100).mean() * 100
    print(f"   giveback median: S={s_gb.median():.1f}%  non-S={ns_gb.median():.1f}%   "
          f"%100%-giveback: S={s_full:.1f}%  non-S={ns_full:.1f}%")
    rows.append(dict(section="retention", period=p, metric="giveback_median_pct", s_val=s_gb.median(), nons_val=ns_gb.median()))
    rows.append(dict(section="retention", period=p, metric="pct_100_giveback", s_val=s_full, nons_val=ns_full))

print(f"\n{'='*120}\n(4) POPULATION STRUCTURE -- 10D/20D/40D mix, ticker/episode concentration (S-tagged only)\n{'='*120}")
for p in PERIODS:
    s = env[(env.period == p) & env.is_S]
    print(f"\n-- {p} -- S n={len(s):,}")
    lb_mix = (s.entry_definition.value_counts(normalize=True) * 100).round(1).to_dict()
    print(f"   10D/20D/40D mix: {lb_mix}")
    n_tickers = s.ticker.nunique()
    n_episodes = episodes(s)
    top10_share = s.ticker.value_counts().head(10).sum() / len(s) * 100 if len(s) else np.nan
    print(f"   {n_tickers} distinct tickers, {n_episodes} episodes, top-10-ticker share={top10_share:.1f}%")
    rows.append(dict(section="structure", period=p, metric="n_tickers", s_val=n_tickers, nons_val=np.nan))
    rows.append(dict(section="structure", period=p, metric="n_episodes", s_val=n_episodes, nons_val=np.nan))
    rows.append(dict(section="structure", period=p, metric="top10_ticker_share_pct", s_val=top10_share, nons_val=np.nan))

pd.DataFrame(rows).to_csv(f"{OUT_DIR}/p6_failure_anatomy.csv", index=False)
print("\nDONE")
