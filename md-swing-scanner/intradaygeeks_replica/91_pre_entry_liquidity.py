"""Pre-entry liquidity thinness (user, 2026-10-06, PNGJL): the daily-ADTV filter (>= Rs10cr) is a day-level floor;
it doesn't catch a stock that trades in sparse, lumpy bursts intraday (PNGJL: 300-2,800 shares/5min-bar pre-entry,
then 27,916 on the spike bar that blew the stop out to 3.7R). Spec pre-declared before looking at any result:

  FEATURE (two versions, one per set -- can only test on hourly granularity for set b, see data/README.md:
  intraday_5m/ starts 2026-06, intraday_60m/ goes back to 2023-10, so there is no 5-min history for the 3-year set):
    a_full (30m, 5-min bars): avg volume of the 12 5-min bars in the 1 hour immediately before the signal candle
      starts, divided by that stock's own expected 5-min bar volume (prior-day 20-day avg daily volume / 75 bars/day).
    b (1H, hourly bars): volume of the ONE hourly bar immediately before the signal hour, divided by expected hourly
      volume (prior-day 20-day avg daily volume / 6 bars/day).
  Both are a RELATIVE thinness ratio (actual / expected), not an absolute level, so it's comparable across stocks of
  different sizes. Pre-declared bucket: tercile split on the ratio, thinnest third = candidate concern.
  Also recorded for set a_full only (no 1H equivalent): % of the pre-entry 5-min bars with High == Low (zero
  intrabar range -- closest 5-min-bar proxy to 'ticked at one price for minutes').

  Population: the SAME checklist-passing population already used for scripts 72-88 (prev_hour_context.csv, sets
  a_full + b, current-rules filter from script 72 -- i.e. current rules, ALL setups, minus already-green-hour-skipped
  late setups). Outcome = the file's own `ret` (%) and `why` (target/stop/stall), unchanged.
  Report: baseline / kept (middle+thick two-thirds) / removed (thinnest third), mean ret% and stop-rate, BOTH sets,
  by month (a_full) and year (b). Promoted only if it helps in both; otherwise exploratory / descriptive only.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR, DAILY_DIR
HERE = Path(__file__).resolve().parent


def current_rules():
    # verbatim from 72_pivots.py (same population as every other filter test on these rules)
    d = pd.read_csv(HERE / "prev_hour_context.csv")
    d = d[d.set.isin(["a_full", "b"])].copy()
    late = np.where(d.set == "b", d.alarm == 11, d.alarm.isin([4, 5]))
    return d[~(late & d.grp.str.startswith("B"))].reset_index(drop=True)


def adv20(t, before):
    f = DAILY_DIR / f"{t}.csv"
    if not f.exists(): return np.nan
    d = pd.read_csv(f, index_col=0, parse_dates=True)
    d = d[d.index < before]
    if len(d) < 20: return np.nan
    return d.Volume.tail(20).mean()


def feature_5m(t, date, alarm):
    """avg volume + %zero-range of the 12 5-min bars in the hour before the signal candle starts."""
    f = INTRADAY_5M_DIR / f"{t}.csv"
    if not f.exists(): return np.nan, np.nan
    m = pd.read_csv(f, index_col=0)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    d = pd.Timestamp(date)
    candle_start = d + pd.Timedelta("9h15min") + alarm * pd.Timedelta("30min")
    win = m[(m.index >= candle_start - pd.Timedelta("60min")) & (m.index < candle_start)]
    if len(win) < 8: return np.nan, np.nan   # require most of the hour present
    a = adv20(t, d)
    ratio = win.Volume.mean() / (a / 75) if a and a > 0 else np.nan
    zero_pct = (win.High == win.Low).mean() * 100
    return ratio, zero_pct


def feature_1h(t, date, alarm):
    """volume of the ONE hourly bar immediately before the signal hour."""
    f = HERE / "h1_cache" / f"{t}.csv"
    if not f.exists(): return np.nan
    h = pd.read_csv(f, index_col=0, parse_dates=True)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    d = pd.Timestamp(date)
    hs = d + pd.Timedelta(hours=int(alarm), minutes=15)
    pos = {k: i for i, k in enumerate(h.index)}
    i = pos.get(hs)
    if i is None or i < 1: return np.nan
    a = adv20(t, d)
    return h.Volume.iloc[i - 1] / (a / 6) if a and a > 0 else np.nan


def run(name, x, feat_fn, extra=False):
    print(f"\n=== {name}: computing pre-entry liquidity feature for {len(x)} setups ===")
    ratios, zeros = [], []
    for _, r in x.iterrows():
        if extra:
            ratio, z = feat_fn(r.ticker, r.date, int(r.alarm))
        else:
            ratio, z = feat_fn(r.ticker, r.date, int(r.alarm)), np.nan
        ratios.append(ratio); zeros.append(z)
    x = x.copy(); x["liq_ratio"] = ratios
    if extra: x["zero_pct"] = zeros
    x = x.dropna(subset=["liq_ratio"])
    n_zero = (x.liq_ratio <= 0).sum()
    x = x[x.liq_ratio > 0]   # a 0-volume hourly bar for a liquid-filtered candidate is a cache gap, not real zero liquidity
    print(f"{len(x)} setups with a usable feature ({n_zero} dropped as zero-volume cache gaps)")
    x["tercile"] = pd.qcut(x.liq_ratio, 3, labels=["thin", "mid", "thick"], duplicates="drop")
    return x


if __name__ == "__main__":
    pop = current_rules()
    a = pop[pop.set == "a_full"].copy()
    b = pop[pop.set == "b"].copy()

    a = run("a_full (30m, 5-min)", a, feature_5m, extra=True)
    b = run("b (1H, 3-year)", b, feature_1h, extra=False)

    def summarize(x, by):
        rows = []
        for label, g in [("BASELINE (all)", x), ("REMOVED (thin third)", x[x.tercile == "thin"]),
                          ("KEPT (mid+thick two-thirds)", x[x.tercile != "thin"])]:
            rows.append(dict(bucket=label, n=len(g), mean_ret=g.ret.mean(), win_pct=(g.ret > 0).mean() * 100,
                              stop_pct=(g.why == "stop").mean() * 100))
        print(pd.DataFrame(rows).to_string(index=False))
        print(f"-- by {by} --")
        piv = x.groupby([by, "tercile"], observed=True).ret.mean().unstack()
        print(piv.round(3).to_string())

    x_a = a.copy(); x_a["month"] = pd.to_datetime(x_a.date).dt.strftime("%Y-%m")
    print("\n--- SET a_full (30m, Jun-Sep 2026) ---")
    summarize(x_a, "month")
    print(f"\nzero-range %% by tercile:\n{a.groupby('tercile', observed=True).zero_pct.mean().round(1).to_string()}")

    x_b = b.copy(); x_b["year"] = pd.to_datetime(x_b.date).dt.year
    print("\n--- SET b (1H, 3-year) ---")
    summarize(x_b, "year")


def jumpiness_5m(t, date, alarm):
    """Within the SAME pre-entry 1-hour window (12 bars): does volume being thin coincide with a 'stalls then
    jumps' price signature -- a few flat/near-flat bars punctuated by one outsized range bar -- rather than
    smoothly-distributed activity? Pure price-action check, no outcome/P&L involved."""
    f = INTRADAY_5M_DIR / f"{t}.csv"
    if not f.exists(): return np.nan, np.nan
    m = pd.read_csv(f, index_col=0)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    d = pd.Timestamp(date)
    candle_start = d + pd.Timedelta("9h15min") + alarm * pd.Timedelta("30min")
    win = m[(m.index >= candle_start - pd.Timedelta("60min")) & (m.index < candle_start)]
    if len(win) < 8: return np.nan, np.nan
    rng = (win.High - win.Low)
    nz = rng[rng > 0]
    if len(nz) < 3: return np.nan, np.nan
    jump_ratio = rng.max() / nz.median()           # max bar range vs typical non-zero bar range -- "one bar did most of the moving"
    max_bar_share = rng.max() / rng.sum() if rng.sum() > 0 else np.nan   # share of the HOUR's total range in a single bar
    return jump_ratio, max_bar_share


if True:
    print("\n\n=== JUMP-THEN-STALL CHECK (price action only, no outcome) -- set a_full ===")
    jr, mbs = [], []
    for _, r in a.iterrows():
        j, s = jumpiness_5m(r.ticker, r.date, int(r.alarm))
        jr.append(j); mbs.append(s)
    a2 = a.copy(); a2["jump_ratio"] = jr; a2["max_bar_share"] = mbs
    a2 = a2.dropna(subset=["jump_ratio"])
    print(f"{len(a2)} setups")
    print(a2.groupby("tercile", observed=True)[["jump_ratio", "max_bar_share", "zero_pct"]].median().round(2).to_string())
    print("\n(mean, for comparison)")
    print(a2.groupby("tercile", observed=True)[["jump_ratio", "max_bar_share", "zero_pct"]].mean().round(2).to_string())


def post_entry_jumpiness_5m(t, date, alarm):
    """Holding-period (entry to 15:15 same day) price action: does the PRE-entry thinness tercile forecast a
    jumpier / spikier SESSION AFTER entry -- the actual PNGJL story (thin 09:15-10:45, spike at 11:20)."""
    f = INTRADAY_5M_DIR / f"{t}.csv"
    if not f.exists(): return np.nan, np.nan, np.nan
    m = pd.read_csv(f, index_col=0)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    d = pd.Timestamp(date)
    entry_t = d + pd.Timedelta("9h15min") + (alarm + 1) * pd.Timedelta("30min")
    win = m[(m.index >= entry_t) & (m.index < d + pd.Timedelta("15h15min"))]
    if len(win) < 10: return np.nan, np.nan, np.nan
    rng = win.High - win.Low
    nz = rng[rng > 0]
    if len(nz) < 5: return np.nan, np.nan, np.nan
    jump_ratio = rng.max() / nz.median()
    max_bar_share = rng.max() / rng.sum() if rng.sum() > 0 else np.nan
    vol_med = win.Volume.replace(0, np.nan).median()
    vol_max_mult = win.Volume.max() / vol_med if vol_med and vol_med > 0 else np.nan   # how many x the biggest post-entry bar is vs typical
    return jump_ratio, max_bar_share, vol_max_mult


if True:
    print("\n\n=== DOES PRE-ENTRY THINNESS PREDICT A POST-ENTRY JUMP? (set a_full) ===")
    jr2, mbs2, vmx = [], [], []
    for _, r in a.iterrows():
        j, s, v = post_entry_jumpiness_5m(r.ticker, r.date, int(r.alarm))
        jr2.append(j); mbs2.append(s); vmx.append(v)
    a3 = a.copy(); a3["post_jump_ratio"] = jr2; a3["post_max_bar_share"] = mbs2; a3["post_vol_max_mult"] = vmx
    a3 = a3.dropna(subset=["post_jump_ratio"])
    print(f"{len(a3)} setups")
    print(a3.groupby("tercile", observed=True)[["post_jump_ratio", "post_max_bar_share", "post_vol_max_mult"]].median().round(2).to_string())
    print("\n(mean, for comparison)")
    print(a3.groupby("tercile", observed=True)[["post_jump_ratio", "post_max_bar_share", "post_vol_max_mult"]].mean().round(2).to_string())
    print("\n90th percentile (tail -- the PNGJL-style event):")
    print(a3.groupby("tercile", observed=True)[["post_jump_ratio", "post_vol_max_mult"]].quantile(0.9).round(2).to_string())
