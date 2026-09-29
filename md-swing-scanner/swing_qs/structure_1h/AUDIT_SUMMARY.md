# Pre-breakout 1H structure audit — 88 events (7 excluded)

Descriptive only. Cliff's delta: + means the first group sits higher. Spearman rho vs mfe_r and D5_close_r over all events.


## confirmed six vs rest  (n=6 vs 82)

| feature | median A | median B | Cliff's delta |
|---|---|---|---|
| bars_in_lookback | 30.000 | 30.000 | +0.00 |
| n_entry_day_bars_before_breach | 0.500 | 1.000 | -0.01 |
| entry_day_open_gap_pct | -0.142 | 0.248 | -0.15 |
| range_contraction_6v24 | 0.855 | 0.910 | -0.20 |
| range_contraction_12v18 | 0.810 | 0.987 | -0.37 |
| last_session_range_vs_prior5 | 0.783 | 0.917 | -0.35 |
| consolidation_width_pct_12 | 2.659 | 2.831 | -0.12 |
| consolidation_width_pct_30 | 4.439 | 5.070 | -0.20 |
| trigger_vs_lookback_high_pct | 0.516 | 0.543 | -0.23 |
| trigger_vs_last_swing_high_pct | 1.421 | 1.167 | +0.11 |
| trigger_vs_last_swing_low_pct | 2.977 | 2.794 | +0.06 |
| last_close_vs_trigger_pct | -1.793 | -1.255 | -0.24 |
| close_position_in_lookback_range | 0.735 | 0.892 | -0.46 |
| n_swing_highs | 7.500 | 7.000 | +0.36 |
| n_swing_lows | 7.000 | 6.000 | +0.28 |
| n_alternations | 10.000 | 9.000 | +0.22 |
| higher_lows_run | 3.000 | 2.000 | +0.18 |
| lower_highs_run | 1.500 | 1.000 | +0.09 |
| efficiency_ratio_30 | 0.133 | 0.242 | -0.30 |
| up_bar_fraction_30 | 0.533 | 0.533 | +0.10 |
| net_move_30_pct | 1.620 | 3.122 | -0.29 |

## reached 0.25R by D5 vs not  (n=77 vs 11)

| feature | median A | median B | Cliff's delta |
|---|---|---|---|
| bars_in_lookback | 30.000 | 30.000 | +0.00 |
| n_entry_day_bars_before_breach | 0.000 | 2.000 | -0.33 |
| entry_day_open_gap_pct | 0.219 | 0.349 | -0.30 |
| range_contraction_6v24 | 0.906 | 0.891 | +0.02 |
| range_contraction_12v18 | 0.986 | 0.937 | +0.04 |
| last_session_range_vs_prior5 | 0.902 | 0.803 | +0.02 |
| consolidation_width_pct_12 | 2.979 | 2.533 | +0.20 |
| consolidation_width_pct_30 | 5.205 | 3.678 | +0.36 |
| trigger_vs_lookback_high_pct | 0.543 | 0.500 | +0.06 |
| trigger_vs_last_swing_high_pct | 1.199 | 0.633 | +0.35 |
| trigger_vs_last_swing_low_pct | 2.878 | 2.436 | +0.28 |
| last_close_vs_trigger_pct | -1.321 | -1.335 | -0.14 |
| close_position_in_lookback_range | 0.881 | 0.886 | -0.01 |
| n_swing_highs | 7.000 | 7.000 | -0.05 |
| n_swing_lows | 6.000 | 7.000 | -0.06 |
| n_alternations | 9.000 | 11.000 | -0.12 |
| higher_lows_run | 2.000 | 2.000 | -0.05 |
| lower_highs_run | 1.000 | 1.000 | +0.06 |
| efficiency_ratio_30 | 0.231 | 0.280 | -0.09 |
| up_bar_fraction_30 | 0.533 | 0.500 | +0.20 |
| net_move_30_pct | 3.063 | 2.597 | +0.06 |

## Rank correlation with outcome axes (all events)

| feature | rho vs mfe_r | rho vs D5_close_r | rho vs max_giveback_r |
|---|---|---|---|
| bars_in_lookback | +nan | +nan | +nan |
| n_entry_day_bars_before_breach | -0.03 | +0.02 | -0.03 |
| entry_day_open_gap_pct | +0.04 | -0.02 | -0.11 |
| range_contraction_6v24 | -0.15 | +0.09 | -0.27 |
| range_contraction_12v18 | -0.11 | +0.07 | -0.21 |
| last_session_range_vs_prior5 | -0.18 | +0.05 | -0.36 |
| consolidation_width_pct_12 | +0.02 | +0.14 | -0.34 |
| consolidation_width_pct_30 | +0.20 | +0.18 | -0.12 |
| trigger_vs_lookback_high_pct | -0.10 | -0.10 | -0.08 |
| trigger_vs_last_swing_high_pct | +0.04 | +0.11 | -0.13 |
| trigger_vs_last_swing_low_pct | -0.16 | -0.01 | -0.25 |
| last_close_vs_trigger_pct | +0.13 | +0.12 | +0.02 |
| close_position_in_lookback_range | +0.11 | +0.14 | -0.11 |
| n_swing_highs | +0.05 | +0.00 | +0.06 |
| n_swing_lows | -0.09 | -0.18 | +0.07 |
| n_alternations | -0.03 | -0.15 | +0.09 |
| higher_lows_run | +0.27 | +0.18 | +0.02 |
| lower_highs_run | -0.08 | -0.12 | +0.17 |
| efficiency_ratio_30 | +0.12 | +0.05 | +0.06 |
| up_bar_fraction_30 | +0.18 | +0.14 | -0.11 |
| net_move_30_pct | +0.13 | +0.05 | +0.03 |

## The confirmed six, raw

| ticker | entry_date | breach_time | n_entry_day_bars_before_breach | range_contraction_6v24 | consolidation_width_pct_12 | trigger_vs_last_swing_high_pct | higher_lows_run | lower_highs_run | n_alternations | efficiency_ratio_30 | mfe_r |
|---|---|---|---|---|---|---|---|---|---|---|---|
| TECHM | 2026-07-13 | 11:05 | 1 | 0.59 | 3.75 | 1.95 | 4 | 1 | 11 | 0.29 | 2.97 |
| LODHA | 2026-07-01 | 13:15 | 4 | 0.95 | 4.34 | 0.09 | 4 | 1 | 12 | 0.50 | 4.22 |
| SONACOMS | 2026-07-16 | 11:40 | 2 | 1.20 | 2.42 | 1.50 | 3 | 2 | 10 | 0.02 | 2.41 |
| PPLPHARMA | 2026-07-27 | 09:55 | 0 | 0.51 | 2.90 | 2.44 | 2 | 1 | 9 | 0.07 | 1.91 |
| INDGN | 2026-08-28 | 10:10 | 0 | 0.88 | 1.95 | 1.18 | 1 | 2 | 10 | 0.00 | 2.02 |
| HINDZINC | 2026-08-03 | 10:00 | 0 | 0.83 | 2.30 | 1.35 | 3 | 2 | 9 | 0.20 | 4.90 |
