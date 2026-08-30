import pandas as pd
import pytest

import backtest
from backtest import (
    resistance_target, support_level, current_stop_level, check_exit, detect_entry,
    ATR_TRAIL_MULT, TRAIL_ENGAGE_PCT, CLIMAX_MIN_GAIN_PCT, CLIMAX_WEAK_CLOSE_PCT,
)


def _row(**kwargs):
    return pd.Series(kwargs)


# --- resistance_target / support_level ---

def test_resistance_target_picks_first_level_above_entry_in_pp_r1_r2_order():
    row = _row(pp=100, r1=105, r2=110)
    assert resistance_target(95, row) == 100  # pp itself already above entry
    assert resistance_target(102, row) == 105  # pp too low, r1 qualifies
    assert resistance_target(200, row) is None  # nothing above entry


def test_resistance_target_skips_nan_levels():
    row = _row(pp=float("nan"), r1=105, r2=110)
    assert resistance_target(95, row) == 105


def test_support_level_picks_first_level_below_entry_in_pp_s1_s2_order():
    row = _row(pp=100, s1=95, s2=90)
    assert support_level(105, row) == 100
    assert support_level(98, row) == 95
    assert support_level(80, row) is None


# --- current_stop_level ---

def test_current_stop_level_breakout_cont_is_chandelier_from_peak_close():
    state = dict(entry_price=100, peak_close=120, peak_high=125, structural_low=None, target=None)
    row = _row(atr14=2.0, ema21=110)
    expected = 120 - ATR_TRAIL_MULT * 2.0
    assert current_stop_level("breakout_cont", state, row) == expected


def test_current_stop_level_vcp_uses_structural_floor_before_engage():
    state = dict(entry_price=100, peak_close=100 * (TRAIL_ENGAGE_PCT - 0.001),  # not yet engaged
                 peak_high=101, structural_low=92, target=None)
    row = _row(atr14=2.0, ema21=110)
    assert current_stop_level("coiled_spring", state, row) == 92


def test_current_stop_level_vcp_switches_to_ema21_trail_after_engage():
    state = dict(entry_price=100, peak_close=100 * (TRAIL_ENGAGE_PCT + 0.01),  # engaged
                 peak_high=105, structural_low=92, target=None)
    row = _row(atr14=2.0, ema21=95)
    assert current_stop_level("coiled_spring", state, row) == max(92, 95)  # never below structural floor
    row_low_ema = _row(atr14=2.0, ema21=80)
    assert current_stop_level("coiled_spring", state, row_low_ema) == 92  # floor wins if ema21 dips under it


# --- check_exit: stop ---

def test_check_exit_fires_stop_when_close_below_current_stop_level():
    state = dict(entry_price=100, peak_close=110, peak_high=112, structural_low=None, target=None)
    row = _row(Close=110 - ATR_TRAIL_MULT * 2.0 - 0.01, Open=109, High=111, Low=108, Volume=1000,
               atr14=2.0, ema21=105, vol_max_run=1000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason == "stop"


def test_check_exit_no_exit_when_close_holds_above_stop_and_below_target():
    state = dict(entry_price=100, peak_close=110, peak_high=112, structural_low=None, target=None)
    row = _row(Close=109, Open=108, High=110, Low=107, Volume=500,
               atr14=2.0, ema21=105, vol_max_run=1000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason is None


# --- check_exit: moving target ratchets up only, never down (regression test —
# this is exactly the class of bug the pivot-as-decision-point experiment hit) ---

def test_moving_target_ratchets_up_never_down():
    state = dict(entry_price=100, peak_close=105, peak_high=106, structural_low=None, target=110)
    # today's fresh pivot level is LOWER than the existing target
    row_lower = _row(Close=103, Open=102, High=104, Low=101, Volume=500,
                      atr14=1.0, ema21=100, vol_max_run=1000, pp=105, r1=float("nan"), r2=float("nan"))
    _, updated = check_exit("breakout_cont", state, row_lower)
    assert updated["target"] == 110  # unchanged — never loosens

    # a later day's fresh pivot is HIGHER — target should ratchet up
    row_higher = _row(Close=103, Open=102, High=104, Low=101, Volume=500,
                       atr14=1.0, ema21=100, vol_max_run=1000, pp=115, r1=float("nan"), r2=float("nan"))
    _, updated2 = check_exit("breakout_cont", updated, row_higher)
    assert updated2["target"] == 115


def test_check_exit_fires_resistance_when_close_reaches_target():
    state = dict(entry_price=100, peak_close=105, peak_high=106, structural_low=None, target=110)
    row = _row(Close=111, Open=109, High=112, Low=108, Volume=500,
               atr14=1.0, ema21=100, vol_max_run=1000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason == "resistance"


# --- check_exit: climax — must NOT fire on an entry-like day (the real v17 bug) ---

def test_climax_does_not_fire_before_min_gain_threshold():
    # position barely above entry (not yet up CLIMAX_MIN_GAIN_PCT) but today looks exactly
    # like a textbook climax candle (fresh high, heaviest volume, weak close) — this is
    # precisely the false-positive pattern that fired on day 1-2 of a trade in v17
    state = dict(entry_price=100, peak_close=101, peak_high=101, structural_low=None, target=None)
    row = _row(Close=102.1, Open=100, High=105, Low=102, Volume=10000,
               atr14=1.0, ema21=100, vol_max_run=10000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason != "climax"


def test_climax_fires_when_extended_and_volume_climax_and_weak_close():
    entry_price = 100
    state = dict(entry_price=entry_price, peak_close=entry_price * CLIMAX_MIN_GAIN_PCT,
                 peak_high=entry_price * CLIMAX_MIN_GAIN_PCT, structural_low=None, target=None)
    # fresh high, heaviest volume of the run, closes in the bottom of the day's range
    row = _row(Close=131, Open=130, High=140, Low=129, Volume=50000,
               atr14=1.0, ema21=100, vol_max_run=50000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    day_range = row.High - row.Low
    close_pos = (row.Close - row.Low) / day_range
    assert close_pos <= CLIMAX_WEAK_CLOSE_PCT  # sanity-check the fixture itself is a weak close
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason == "climax"


def test_climax_does_not_fire_on_strong_close():
    entry_price = 100
    state = dict(entry_price=entry_price, peak_close=entry_price * CLIMAX_MIN_GAIN_PCT,
                 peak_high=entry_price * CLIMAX_MIN_GAIN_PCT, structural_low=None, target=None)
    row = _row(Close=139, Open=130, High=140, Low=129, Volume=50000,  # closes NEAR the high
               atr14=1.0, ema21=100, vol_max_run=50000, pp=float("nan"), r1=float("nan"), r2=float("nan"))
    reason, _ = check_exit("breakout_cont", state, row)
    assert reason != "climax"


# --- detect_entry: branching order and regime gating (heavier deps monkeypatched) ---

def test_detect_entry_prefers_breakout_cont_when_both_could_fire(monkeypatch):
    monkeypatch.setattr(backtest, "entry_signal", lambda row: True)
    monkeypatch.setattr(backtest, "market_trending", lambda *a, **k: True)
    monkeypatch.setattr(backtest, "stage2_trend_template", lambda *a, **k: True)
    monkeypatch.setattr(backtest, "vcp_breakout", lambda *a, **k: (100, 90))
    rows = pd.DataFrame([{"Date": pd.Timestamp("2024-01-01")}])
    result = detect_entry("TEST", rows, 0)
    assert result == ("breakout_cont", None)


def test_detect_entry_falls_through_to_vcp_when_breakout_signal_absent(monkeypatch):
    monkeypatch.setattr(backtest, "entry_signal", lambda row: False)
    monkeypatch.setattr(backtest, "market_trending", lambda *a, **k: True)
    monkeypatch.setattr(backtest, "stage2_trend_template", lambda *a, **k: True)
    monkeypatch.setattr(backtest, "vcp_breakout", lambda *a, **k: (100, 90))
    rows = pd.DataFrame([{"Date": pd.Timestamp("2024-01-01")}])
    result = detect_entry("TEST", rows, 0)
    assert result == ("coiled_spring", 90)


def test_detect_entry_blocked_by_regime_gate_even_if_pattern_would_fire(monkeypatch):
    monkeypatch.setattr(backtest, "entry_signal", lambda row: True)
    monkeypatch.setattr(backtest, "market_trending", lambda *a, **k: False)  # regime gate closed
    rows = pd.DataFrame([{"Date": pd.Timestamp("2024-01-01")}])
    assert detect_entry("TEST", rows, 0) is None


def test_detect_entry_none_when_neither_pattern_fires(monkeypatch):
    monkeypatch.setattr(backtest, "entry_signal", lambda row: False)
    monkeypatch.setattr(backtest, "stage2_trend_template", lambda *a, **k: False)
    rows = pd.DataFrame([{"Date": pd.Timestamp("2024-01-01")}])
    assert detect_entry("TEST", rows, 0) is None


# --- simulate_ticker: corp-action right-censoring (integration test) ---

def test_corp_action_day_right_censors_open_position(monkeypatch):
    """A trade open when a corp_action_day fires must close at the PRIOR day's price,
    not the corrupted day's — and no fresh entry should be evaluated on that day either."""
    dates = pd.date_range("2024-01-01", periods=5, freq="D", name="Date")
    df = pd.DataFrame({
        "Close": [100.0, 105.0, 200.0, 205.0, 206.0],  # day 2 is an unadjusted-looking demerger gap
        "Open": [99.0, 104.0, 199.0, 204.0, 205.0],
        "High": [101.0, 106.0, 201.0, 206.0, 207.0],
        "Low": [98.0, 103.0, 198.0, 203.0, 204.0],
        "Volume": [1000, 1000, 1000, 1000, 1000],
        "atr14": [1.0, 1.0, 1.0, 1.0, 1.0],
        "ema21": [100.0, 100.0, 100.0, 100.0, 100.0],
        "vol_max_run": [1000, 1000, 1000, 1000, 1000],
        "pp": [float("nan")] * 5, "r1": [float("nan")] * 5, "r2": [float("nan")] * 5,
        "corp_action_day": [False, False, True, False, False],
    }, index=dates)

    call_count = {"n": 0}

    def fake_detect_entry(ticker, rows, i):
        call_count["n"] += 1
        if i == 0:
            return "breakout_cont", None
        return None  # never re-enter after the forced close

    monkeypatch.setattr(backtest, "detect_entry", fake_detect_entry)
    trades = backtest.simulate_ticker("TEST", df, use_resistance=True)

    assert len(trades) == 1
    t = trades[0]
    assert t["exit_reason"] == "corp_action"
    assert t["exit_price"] == 105.0  # prior day's close, NOT the 200.0 gap day
    assert t["exit_date"] == dates[1]
    # a fresh entry must not have been evaluated ON the corrupted day itself
    assert call_count["n"] < len(df)
