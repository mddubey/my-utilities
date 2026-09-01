import pandas as pd

CLOSE_NEAR_HIGH_PCT = 0.70   # close sits in top 30% of day's range — not specified in source spec, my pick
VOL_SURGE_MIN = 1.20         # volume must be >=20% above yesterday's, not just "more"
BREAKOUT_MIN_PCT = 1.005     # close must clear yesterday's high by >=0.5%, not just any amount
VOL_ZSCORE_WINDOW = 8        # ADOPTED (2026-08-31): a 20-day trailing window can straddle two
                              # different phases — an active prior move plus the quiet base that
                              # followed it — and the prior move's volume inflates the mean/std
                              # enough to mute a genuinely strong NEW volume day (real case:
                              # AUROPHARMA 2026-08-31 initially scored z=0.23 against a stale
                              # 20d window that still included an unrelated earlier spike, vs
                              # z=+2.17 against just the 14-day quiet base that actually followed
                              # it). Full-backtest sweep of windows 20/15/12/10/8/5: ALL metrics
                              # improve 20->8 (ALL: n 677->808, win 58.3%->60.1%, conc 30.7%->
                              # 25.2%; VCP: conc 37.5%->30.7%), then flatten — 8 is the shortest
                              # window that captures the full gain on BOTH patterns jointly
                              # (Breakout Cont's concentration specifically improves at 8/5, not
                              # at 10-15). Drought-only trades: 0 unlocked at every window —
                              # orthogonal to the regime-gate drought, general quality fix only.
# Coiled Spring/VCP lives entirely in vcp.py now — the single-5-day-window version that
# used to live here was a much-too-loose simplification of the real pattern (checked
# directly against the standard Minervini VCP/Trend-Template definition, 2026-08-30:
# missing the long-term trend confirmation, the multi-week multi-contraction structure,
# and relative strength vs the universe). It gets its own dedicated gate, not reused
# base_filters_pass/checklist_pass — those were built for Breakout Continuation.

# universal gates, from the user's Chartink screener (recovered separately — this
# part of the source ChatGPT conversation fell in the PDF's blank pages)
#
# Per-filter leave-one-out ablation (2026-08-30, 210-stock universe, 21mo), using
# MEDIAN pnl_pct as the comparison metric — the mean/expectancy version of this same
# test is unreliable here: top-10-of-~200 trades run 800-1000% of total summed pnl_pct
# in every variant tested, so a mean-based comparison mostly measures which rare
# long-holding outlier trades got let in, not real filter quality. Findings:
#   - RSI_MIN/RSI_MAX: real, confirmed (on THIS 210-stock/21mo pre-v27 run) — removing
#     it flips the median trade from a winner to a loser (+0.82% -> -0.51%). Keep.
#     Superseded below for RSI_MAX specifically — re-swept in isolation on v27's full
#     500-stock/5yr data and that finding no longer holds; the two runs aren't directly
#     comparable (different universe, window, and this session's other v27 changes).
#   - MOMENTUM_20D_MIN: looked critical under the naive mean-based test (removing it
#     flipped expectancy negative) but that was the concentration artifact talking —
#     median is IDENTICAL with or without it (+0.82% both ways). Not proven to add edge.
#   - EMA34_RISING_DAYS_MIN: weak positive on median (+0.82% -> +0.65% if removed)
#     while nearly doubling trade count. Marginal either way.
#   - MIN_TRADED_VALUE: median actually improves if this is REMOVED (+0.82% -> +1.09%,
#     better win rate too) — this stock-side floor may be redundant with the separate
#     options-side OI/volume liquidity check that already gates the actual trade.
# Despite that, all four are kept as-is: this is a daily scanner meant to surface a
# small, manually-reviewable candidate list, not a backtest-optimization target on its
# own — dropping MOMENTUM/MIN_TRADED_VALUE alone would ~5x the monthly signal count
# (197 -> 1047 trades over the same period), which defeats the actual point of the
# tool even where the backtest edge case for keeping them is weak. Revisit only if the
# opposite problem shows up (too few signals), not to chase a marginal median gain.
RSI_MIN = 55
RSI_MAX = 80  # ADOPTED (2026-09-01, was 68). A round-5 outside-critique correction: VCP's
              # "no RSI ceiling needed, even RSI>72 is fine" finding does NOT transfer to
              # Breakout Continuation just because they share the same RSI number — VCP at
              # RSI 75 usually means weeks of quiet basing (elevated only because today is
              # breakout day); Breakout Cont at RSI 75 can mean 5-6 days already run. Swept
              # BC's OWN ceiling in isolation instead of inferring from VCP: 68(current)/72/
              # 75/80/85/100(no real cap), full v27 backtest each time, Breakout Cont trades
              # only. Win rate holds ~67-69% throughout; median holds/improves; concentration
              # drops monotonically 52.2%->26.5%->24.3%->16.4%->15.7%->16.5% and flattens
              # right at 80 (85/100 statistically indistinguishable from 80 on every metric)
              # — same real-improvement-then-plateau shape as vcp.LAST_LEG_TOLERANCE and
              # VOL_ZSCORE_WINDOW. Sample triples (211->767 BC trades) — real, not thin: only
              # ~90 of those are poached from VCP (VCP's own n drops 713->663, its own
              # win/median/concentration barely move, 61.6%->61.7%/62.1%, ~2.9% flat,
              # 19.5%->22.0%), the rest fire under NEITHER pattern today. Checked the poached
              # trades two ways before trusting this: (1) 31 same-day relabelings — win rate
              # identical (64.5%->64.5%), only 1 trade flips each direction (PAYTM 2024-11-08:
              # VCP's structural-low stop hit on a -11.2% dip to 753 five days in; BC's much
              # wider 3xATR chandelier absorbed the same dip and rode it to a +6.2% resistance
              # exit two weeks later — both patterns' stop mechanics are correct, sourced,
              # intentionally different designs, see current_stop_level, not a bug); (2) 26
              # scheduling-cascade pre-emptions (an earlier BC entry now consumes the ticker's
              # slot before the later VCP setup could ever form) — these actually skew
              # favorable, 84.6% win for the earlier BC entry vs a hypothetical 57.7% for the
              # VCP setup it displaced.
EMA34_RISING_DAYS_MIN = 9      # out of the trailing 10 — persistent trend, not just "currently above"
MIN_TRADED_VALUE = 1_000_000_000  # Rs.100cr, 20-day avg Close*Volume — liquidity floor
MOMENTUM_20D_MIN = 1.05        # close must be >=5% above its level 20 trading days ago


def ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def atr(df, period=14):
    tr = pd.concat([
        df.High - df.Low,
        (df.High - df.Close.shift()).abs(),
        (df.Low - df.Close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def build_indicators(df):
    df = df.copy()
    df["ema8"] = ema(df.Close, 8)
    df["ema21"] = ema(df.Close, 21)  # VCP's published trailing-stop MA (Minervini: trail 10/21-EMA post-engage)
    df["ema34"] = ema(df.Close, 34)
    df["rsi14"] = rsi(df.Close, 14)
    df["atr14"] = atr(df, 14)
    df["vol_yday"] = df.Volume.shift(1)
    df["vol_avg3"] = df.Volume.rolling(3).mean()
    df["vol_avg10_prior"] = df.Volume.shift(3).rolling(10).mean()
    df["vol_avg10"] = df.Volume.rolling(10).mean()
    df["high_prev"] = df.High.shift(1)
    df["high10_prior"] = df.High.shift(1).rolling(10).max()
    df["range5_high"] = df.High.shift(1).rolling(5).max()  # PRIOR 5 days only — must exclude today,
    df["range5_low"] = df.Low.shift(1).rolling(5).min()    # else today's own high/low can never be exceeded
    df["atr14_60ago"] = df.atr14.shift(60)
    df["vol_declining5"] = (df.Volume.diff() < 0).rolling(5).sum() == 5
    df["ema34_rising10"] = (df.ema34 > df.ema34.shift(1)).rolling(10).sum()
    df["traded_value_sma20"] = (df.Close * df.Volume).rolling(20).mean()
    df["close_20ago"] = df.Close.shift(20)
    # Minervini-style long-term trend template inputs, for the VCP/Coiled Spring rebuild
    df["sma50"] = df.Close.rolling(50).mean()
    df["sma150"] = df.Close.rolling(150).mean()
    df["sma200"] = df.Close.rolling(200).mean()
    df["sma200_20ago"] = df.sma200.shift(20)  # for "200MA trending up for at least a month"
    df["high_252"] = df.High.rolling(252).max()
    df["low_252"] = df.Low.rolling(252).min()
    # z-score volume (prior VOL_ZSCORE_WINDOW days, excludes today — same no-lookahead
    # convention as the rest of this file), for testing as an alternative to the flat
    # "1.2x yesterday" checklist item
    vol_prior = df.Volume.shift(1).rolling(VOL_ZSCORE_WINDOW)
    df["vol_mean20_prior"] = vol_prior.mean()
    df["vol_std20_prior"] = vol_prior.std()
    df["vol_zscore"] = (df.Volume - df.vol_mean20_prior) / df.vol_std20_prior
    return df


def checklist_pass(row):
    day_range = row.High - row.Low
    close_near_high = day_range > 0 and (row.Close - row.Low) / day_range >= CLOSE_NEAR_HIGH_PCT
    conditions = [
        row.Close > row.ema8,
        row.Volume >= VOL_SURGE_MIN * row.vol_yday,
        close_near_high,
        row.Close >= BREAKOUT_MIN_PCT * row.high_prev,
    ]
    return sum(bool(c) for c in conditions) == 4  # all 4 checkable items (5th, options-OI, excluded — no data)


def base_filters_pass(row):
    """Universal gates applying to every entry, regardless of which pattern fires."""
    trend_bullish = row.Close > row.ema34 and row.ema8 > row.ema34
    rsi_band = RSI_MIN < row.rsi14 < RSI_MAX
    ema34_persistent = row.ema34_rising10 >= EMA34_RISING_DAYS_MIN
    liquid_enough = row.traded_value_sma20 >= MIN_TRADED_VALUE
    momentum_20d = row.Close >= MOMENTUM_20D_MIN * row.close_20ago
    return trend_bullish and rsi_band and ema34_persistent and liquid_enough and momentum_20d


VOL_ZSCORE_MIN = 1.5  # replaces a flat "1.5x avg volume" ratio — verified via a full
                      # sensitivity sweep (2026-08-30): win rate 68%->79%, median +1.87%
                      # ->+2.44%, concentration improved (105%->93%), not a cherry-pick —
                      # a flat ratio ignores how much THIS stock's volume normally varies


def breakout_continuation(row):
    return row.Close > row.high10_prior and pd.notna(row.vol_zscore) and row.vol_zscore >= VOL_ZSCORE_MIN


def reject_theta_trap(row):
    tiny_body = abs(row.Close - row.Open) / row.Close < 0.005
    atr_shrinking = pd.notna(row.atr14_60ago) and row.atr14 < 0.7 * row.atr14_60ago
    return bool(tiny_body and row.vol_declining5 and atr_shrinking)


def entry_signal(row):
    """Breakout Continuation eligibility only. Coiled Spring/VCP is a fully separate
    entry path (vcp.py) with its own trend-template + multi-contraction gate — it does
    not go through this checklist at all."""
    required = ["ema34", "vol_avg10_prior", "high10_prior", "atr14_60ago",
                "ema34_rising10", "traded_value_sma20", "close_20ago"]
    if row[required].isna().any():
        return False
    if not base_filters_pass(row):
        return False
    if not checklist_pass(row):
        return False
    if reject_theta_trap(row):
        return False
    return breakout_continuation(row)
