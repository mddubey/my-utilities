import pandas as pd

import signals
from signals import (
    ema, rsi, atr, checklist_pass, base_filters_pass, breakout_continuation,
    reject_theta_trap, entry_signal, VOL_ZSCORE_MIN, RSI_MIN, RSI_MAX,
)


def _row(**kwargs):
    return pd.Series(kwargs)


# --- indicators ---

def test_ema_of_constant_series_equals_the_constant():
    s = pd.Series([50.0] * 20)
    result = ema(s, 8)
    assert abs(result.iloc[-1] - 50.0) < 1e-9


def test_rsi_approaches_100_on_a_strictly_rising_series():
    s = pd.Series(range(1, 50), dtype=float)
    result = rsi(s, 14)
    assert result.iloc[-1] > 95


def test_rsi_approaches_0_on_a_strictly_falling_series():
    s = pd.Series(range(50, 1, -1), dtype=float)
    result = rsi(s, 14)
    assert result.iloc[-1] < 5


def test_atr_on_flat_no_gap_days_equals_the_daily_range():
    # High-Low is constant and there are no overnight gaps -> true range == High-Low every day
    df = pd.DataFrame({"High": [110.0] * 20, "Low": [100.0] * 20, "Close": [105.0] * 20})
    result = atr(df, 14)
    assert abs(result.iloc[-1] - 10.0) < 1e-6


# --- checklist_pass ---

def test_checklist_pass_true_when_all_four_conditions_hold():
    row = _row(Close=110, ema8=100, Volume=150, vol_yday=100, High=112, Low=100, high_prev=109)
    assert checklist_pass(row)


def test_checklist_pass_false_when_volume_condition_fails():
    row = _row(Close=110, ema8=100, Volume=105, vol_yday=100, High=112, Low=100, high_prev=109)
    assert not (checklist_pass(row))


def test_checklist_pass_false_when_close_not_near_high():
    row = _row(Close=110, ema8=100, Volume=150, vol_yday=100, High=130, Low=100, high_prev=109)
    assert not (checklist_pass(row))


# --- base_filters_pass ---

def _passing_base_row(**overrides):
    base = dict(Close=110, ema34=100, ema8=105, rsi14=(RSI_MIN + RSI_MAX) / 2,
                ema34_rising10=10, traded_value_sma20=2_000_000_000, close_20ago=100)
    base.update(overrides)
    return _row(**base)


def test_base_filters_pass_true_on_a_clean_qualifying_row():
    assert base_filters_pass(_passing_base_row())


def test_base_filters_pass_false_when_rsi_outside_band():
    assert not (base_filters_pass(_passing_base_row(rsi14=RSI_MAX + 1)))


def test_base_filters_pass_false_when_liquidity_floor_not_met():
    assert not (base_filters_pass(_passing_base_row(traded_value_sma20=1)))


# --- breakout_continuation (z-score volume) ---

def test_breakout_continuation_requires_both_new_high_and_volume_zscore():
    row_ok = _row(Close=110, high10_prior=105, vol_zscore=VOL_ZSCORE_MIN + 0.1)
    assert breakout_continuation(row_ok)

    row_weak_volume = _row(Close=110, high10_prior=105, vol_zscore=VOL_ZSCORE_MIN - 0.1)
    assert not (breakout_continuation(row_weak_volume))

    row_no_new_high = _row(Close=100, high10_prior=105, vol_zscore=VOL_ZSCORE_MIN + 1)
    assert not (breakout_continuation(row_no_new_high))

    row_nan_zscore = _row(Close=110, high10_prior=105, vol_zscore=float("nan"))
    assert not (breakout_continuation(row_nan_zscore))


# --- reject_theta_trap ---

def test_reject_theta_trap_true_on_tiny_body_declining_volume_shrinking_atr():
    row = _row(Close=100.0, Open=99.7, vol_declining5=True, atr14=1.0, atr14_60ago=2.0)
    assert reject_theta_trap(row)


def test_reject_theta_trap_false_when_body_is_not_tiny():
    row = _row(Close=100.0, Open=95.0, vol_declining5=True, atr14=1.0, atr14_60ago=2.0)
    assert not (reject_theta_trap(row))


def test_reject_theta_trap_false_when_atr_not_shrinking():
    row = _row(Close=100.0, Open=99.7, vol_declining5=True, atr14=2.0, atr14_60ago=2.0)
    assert not (reject_theta_trap(row))


# --- entry_signal: missing-data guard + composition (heavier sub-checks monkeypatched) ---

def test_entry_signal_false_when_required_field_missing():
    row = _row(ema34=float("nan"), vol_avg10_prior=1, high10_prior=1, atr14_60ago=1,
               ema34_rising10=1, traded_value_sma20=1, close_20ago=1)
    assert not (entry_signal(row))


def test_entry_signal_true_only_when_every_sub_check_passes(monkeypatch):
    row = _row(ema34=1, vol_avg10_prior=1, high10_prior=1, atr14_60ago=1,
               ema34_rising10=1, traded_value_sma20=1, close_20ago=1)
    monkeypatch.setattr(signals, "base_filters_pass", lambda r: True)
    monkeypatch.setattr(signals, "checklist_pass", lambda r: True)
    monkeypatch.setattr(signals, "reject_theta_trap", lambda r: False)
    monkeypatch.setattr(signals, "breakout_continuation", lambda r: True)
    assert entry_signal(row)

    monkeypatch.setattr(signals, "reject_theta_trap", lambda r: True)  # theta trap rejects it
    assert not (entry_signal(row))
