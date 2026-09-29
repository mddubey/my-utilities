"""RQ-53, volume + displacement version (2026-09-18) -- direct response to the user
catching that breakout_failure_confirmation_cost.py tested pure price-drop-and-hold,
which this project already tested (as "close back below entry pivot", 2026-09-07)
and REJECTED: it can't distinguish a genuine failure from a normal retest in a
trade that's still going to win (that old rule caught 30-48% of real winners).

The research pulled earlier (mainstream TA + SMC/ICT) says the real discriminator
is volume (a genuine breakdown sells off on real volume; a shallow "liquidity grab"
reverses on weak/declining volume) and displacement (SMC/ICT: a strong-bodied
reversal candle vs a small, shallow probe -- this project's own `body_atr`, already
validated as a fragility predictor elsewhere).

Same population/entry/signal-bar mechanism as breakout_failure_confirmation_cost.py
(base_filters_pass + real intraday breach, FAILURE_THRESHOLD=0.5% below trigger to
locate WHEN a decline is happening -- price still needed to say "look here", just
not to say "is this real"). At that signal bar, instead of waiting 2 more bars for
price to stay down, check:
  - vol_ratio: signal bar's Volume vs the mean of the 3 bars just before it
    (is this decline happening on unusually heavy volume, or on drift/no volume?)
  - body_atr: |Close-Open| of the signal bar / yesterday's daily atr14 (displacement)

Two questions: (1) do these actually separate "confirmed" (real, persists 2 more
bars) from "reversed" (recovers) trades -- discriminating power, like the original
fragility check; (2) does a volume/body_atr-gated exit rule beat the price-only
2-bar-wait version on blended swing expectancy.
"""
import warnings
warnings.filterwarnings("ignore")

import sys

import pandas as pd

import backtest
import signals
from pivots import daily_pivots
from research.metrics import expectancy, win_rate
from breakout_failure_confirmation_cost import _load_intraday, simulate_swing, TRIGGER_CLEARANCE

SIGNAL_DROP = 0.005
CONFIRM_BARS = 2


def gather(tickers, verbose=False):
    rows = []
    for n, t in enumerate(tickers):
        if verbose and n % 100 == 0:
            print(f"  {n}/{len(tickers)} tickers, {len(rows)} signal fires so far", file=sys.stderr)
        try:
            daily_df = backtest.load(t, daily_pivots).reset_index()
        except FileNotFoundError:
            continue
        intraday_df, naive_day = _load_intraday(t)
        if intraday_df is None:
            continue
        intraday_dates = set(naive_day.unique())

        for i in range(len(daily_df) - 1):
            row = daily_df.iloc[i]
            if row.corp_action_day or pd.isna(row.high10_prior) or pd.isna(row.atr14):
                continue
            date_norm = pd.Timestamp(row.Date).normalize()
            if date_norm not in intraday_dates:
                continue
            if not signals.base_filters_pass(row):
                continue

            trigger_price = row.high10_prior * TRIGGER_CLEARANCE
            day_bars = intraday_df[naive_day == date_norm].reset_index(drop=True)
            if day_bars.empty or day_bars.High.max() < trigger_price:
                continue

            breach_idx = day_bars.High.ge(trigger_price).idxmax()
            threshold = trigger_price * (1 - SIGNAL_DROP)

            signal_idx = None
            for k in range(breach_idx, len(day_bars)):
                if day_bars.Close.iloc[k] < threshold:
                    signal_idx = k
                    break
            if signal_idx is None:
                continue

            remaining = day_bars.Close.iloc[signal_idx + 1: signal_idx + 1 + CONFIRM_BARS]
            if len(remaining) < CONFIRM_BARS:
                continue  # unconfirmable, same exclusion as before

            confirmed = bool((remaining < threshold).all())

            sig_bar = day_bars.iloc[signal_idx]
            prior_bars = day_bars.iloc[max(0, signal_idx - 3):signal_idx]
            prior_vol_mean = prior_bars.Volume.mean() if len(prior_bars) and prior_bars.Volume.mean() > 0 else None
            vol_ratio = (sig_bar.Volume / prior_vol_mean) if prior_vol_mean else None
            body_atr = abs(sig_bar.Close - sig_bar.Open) / row.atr14

            rows.append(dict(
                ticker=t, date=row.Date, trigger_price=trigger_price,
                signal_price=sig_bar.Close, confirmed=confirmed,
                vol_ratio=vol_ratio, body_atr=body_atr,
                swing_pnl=simulate_swing(daily_df, i, trigger_price),
                immediate_exit_pnl=(sig_bar.Close / trigger_price - 1) * 100,
            ))
    return pd.DataFrame(rows)


def quartile_table(df, col, label_col="confirmed", n_q=4):
    d = df.dropna(subset=[col]).copy()
    d["q"] = pd.qcut(d[col], n_q, duplicates="drop", labels=False)
    return d.groupby("q").agg(
        n=(col, "size"), lo=(col, "min"), hi=(col, "max"),
        confirmed_rate=(label_col, "mean"), swing_exp=("swing_pnl", expectancy),
    )


def main():
    tickers = pd.read_csv("nifty500_universe.csv", header=None)[0].tolist()
    print(f"Gathering signal fires from {len(tickers)} tickers...", file=sys.stderr)
    df = gather(tickers, verbose=True)
    print(f"\n{len(df)} signal fires total ({df.confirmed.sum()} confirmed / {(~df.confirmed).sum()} reversed)")
    print(f"vol_ratio available for {df.vol_ratio.notna().sum()} (dropped when the first 3 bars of the day had zero volume)")

    corr_vol = df[["vol_ratio", "confirmed"]].dropna().corr().iloc[0, 1]
    corr_body = df[["body_atr", "confirmed"]].dropna().corr().iloc[0, 1]
    print(f"\nDiscriminating power vs the already-known confirmed/reversed label "
          f"(does the signal-bar's volume/displacement predict which one this is?):")
    print(f"  vol_ratio  vs confirmed: corr={corr_vol:+.3f}")
    print(f"  body_atr   vs confirmed: corr={corr_body:+.3f}")

    print(f"\nvol_ratio quartiles (signal-bar Volume / mean of prior 3 bars) -- "
          f"confirmed_rate should rise left-to-right if volume is a real breakdown signal:")
    print(quartile_table(df, "vol_ratio").to_string())

    print(f"\nbody_atr quartiles (signal-bar |Close-Open| / yesterday's atr14, the displacement proxy) -- "
          f"confirmed_rate should rise left-to-right if a bigger reversal candle means a more real move:")
    print(quartile_table(df, "body_atr").to_string())

    # Direct rule test: exit at signal bar ONLY if vol_ratio and body_atr both clear a cutoff
    # (top-half of each, i.e. above their own median) -- else hold to baseline (treat as noise).
    d = df.dropna(subset=["vol_ratio", "body_atr"]).copy()
    vol_med, body_med = d.vol_ratio.median(), d.body_atr.median()
    d["vd_gate_fires"] = (d.vol_ratio >= vol_med) & (d.body_atr >= body_med)
    print(f"\nVolume+displacement-gated exit rule (fires only when vol_ratio>={vol_med:.2f} "
          f"AND body_atr>={body_med:.2f}, both above their own median -- else holds to baseline), "
          f"n={len(d)}:")
    gated_exit = d.immediate_exit_pnl.where(d.vd_gate_fires, d.swing_pnl)
    print(f"  do nothing (baseline)              exp={expectancy(d.swing_pnl):+.3f}%  n={len(d)}")
    print(f"  vol+displacement-gated exit         exp={expectancy(gated_exit):+.3f}%  n={len(d)}  "
          f"(fires on {d.vd_gate_fires.sum()}/{len(d)} = {d.vd_gate_fires.mean()*100:.1f}%)")
    fired = d[d.vd_gate_fires]
    not_fired = d[~d.vd_gate_fires]
    print(f"  -- of the {len(fired)} it fires on: baseline (if held) would have been exp={expectancy(fired.swing_pnl):+.3f}%, "
          f"win={win_rate(fired.swing_pnl):.1f}%  (this is the population it's cutting -- should be bad)")
    print(f"  -- of the {len(not_fired)} it leaves alone: baseline exp={expectancy(not_fired.swing_pnl):+.3f}%, "
          f"win={win_rate(not_fired.swing_pnl):.1f}%  (this is the population it's NOT touching -- should be fine)")

    df.to_csv("breakout_failure_volume_displacement.csv", index=False)
    print("\nRaw dataset saved to breakout_failure_volume_displacement.csv")


if __name__ == "__main__":
    main()
