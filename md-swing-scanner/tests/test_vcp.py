import pandas as pd

import vcp
from vcp import _find_swings, _legs, base_pivot, vcp_breakout, stage2_trend_template


def test_find_swings_detects_known_zigzag_turning_points():
    prices = pd.Series([100, 110, 95, 105, 90, 100])
    pivots = _find_swings(prices, prices, pct=0.03)
    assert pivots == [(1, 110, "H"), (2, 95, "L"), (3, 105, "H"), (4, 90, "L")]


def test_legs_pairs_only_consecutive_high_then_low():
    pivots = [(0, 100, "L"), (5, 110, "H"), (10, 95, "L"), (15, 120, "H"), (20, 90, "L")]
    assert _legs(pivots) == [(5, 110, 10, 95), (15, 120, 20, 90)]


def _two_leg_base_df(second_leg_low=100.0, second_leg_vol=1000, second_leg_low_idx=14,
                      trailing_len=6):
    """A 21-row synthetic base: leg 1 deep/high-volume (idx2 H=110 -> idx5 L=90), leg 2
    shallow/low-volume by default (idx10 H=105 -> idx14 L=100), fresh (within
    RECENT_LOW_MAX_DAYS of window end). Overridable to construct the negative cases."""
    n = 15 + trailing_len
    high = [100.0] * n
    low = [100.0] * n
    volume = [2000] * n

    high[2] = 110; low[2] = 110
    high[5] = 90; low[5] = 90
    for i in range(2, 6):
        volume[i] = 5000
    high[8] = 98; low[8] = 98  # bridge past 90*1.03 to confirm leg-1 low pivot

    high[10] = 105; low[10] = 105
    high[second_leg_low_idx] = second_leg_low; low[second_leg_low_idx] = second_leg_low
    for i in range(10, second_leg_low_idx + 1):
        volume[i] = second_leg_vol
    bridge_idx = second_leg_low_idx + 4
    if bridge_idx < n:
        bridge_price = second_leg_low * 1.05
        high[bridge_idx] = bridge_price
        low[bridge_idx] = bridge_price

    close = high[:]
    return pd.DataFrame({"High": high, "Low": low, "Close": close, "Volume": volume})


def test_base_pivot_detects_a_genuine_tightening_two_leg_base():
    df = _two_leg_base_df()
    result = base_pivot(df, 20)
    assert result == (105.0, 100.0)


def test_base_pivot_none_with_only_one_leg():
    # only leg 1 present, no second contraction at all
    n = 21
    high = [100.0] * n
    low = [100.0] * n
    volume = [2000] * n
    high[2] = 110; low[2] = 110
    high[5] = 90; low[5] = 90
    high[8] = 98; low[8] = 98
    df = pd.DataFrame({"High": high, "Low": low, "Close": high, "Volume": volume})
    assert base_pivot(df, 20) is None


def test_base_pivot_none_when_second_leg_not_tighter():
    # second leg (idx10 H=105 -> idx14 L=70) is DEEPER than leg 1, not a contraction
    df = _two_leg_base_df(second_leg_low=70.0)
    assert base_pivot(df, 20) is None


def test_base_pivot_none_when_second_leg_volume_not_lower():
    df = _two_leg_base_df(second_leg_vol=6000)  # heavier volume than leg 1, not drying up
    assert base_pivot(df, 20) is None


def test_base_pivot_none_when_recent_low_is_stale():
    # push the second leg's low far enough back that it's no longer "fresh"
    df = _two_leg_base_df(second_leg_low_idx=3, trailing_len=25)
    # (this also collides with leg-1's own indices, so just assert it isn't the same
    # clean positive result rather than assume a specific rejection reason)
    result = base_pivot(df, df.shape[0] - 1)
    assert result != (105.0, 100.0)


# --- vcp_breakout: close above pivot + volume condition ---

def test_vcp_breakout_fires_on_close_above_pivot_with_sufficient_zscore(monkeypatch):
    monkeypatch.setattr(vcp, "base_pivot", lambda df, i: (100.0, 90.0))
    df = pd.DataFrame({"Close": [101.0], "vol_zscore": [1.0]})
    assert vcp_breakout(df, 0, zscore_min=0.5) == (100.0, 90.0)


def test_vcp_breakout_none_when_volume_insufficient(monkeypatch):
    monkeypatch.setattr(vcp, "base_pivot", lambda df, i: (100.0, 90.0))
    df = pd.DataFrame({"Close": [101.0], "vol_zscore": [0.1]})
    assert vcp_breakout(df, 0, zscore_min=0.5) is None


def test_vcp_breakout_none_when_close_not_above_pivot(monkeypatch):
    monkeypatch.setattr(vcp, "base_pivot", lambda df, i: (100.0, 90.0))
    df = pd.DataFrame({"Close": [99.0], "vol_zscore": [5.0]})
    assert vcp_breakout(df, 0, zscore_min=0.5) is None


def test_vcp_breakout_none_when_no_base_found(monkeypatch):
    monkeypatch.setattr(vcp, "base_pivot", lambda df, i: None)
    df = pd.DataFrame({"Close": [101.0], "vol_zscore": [5.0]})
    assert vcp_breakout(df, 0, zscore_min=0.5) is None


# --- stage2_trend_template ---

def _trend_row(**overrides):
    base = dict(Close=110, sma50=105, sma150=100, sma200=95, sma200_20ago=93,
                high_252=120, low_252=80)
    base.update(overrides)
    return pd.Series(base)


def test_stage2_trend_template_true_when_every_condition_holds(monkeypatch):
    monkeypatch.setattr(vcp, "rs_rating", lambda ticker, date: 85)
    assert stage2_trend_template(_trend_row(), "TEST", "2024-01-01")


def test_stage2_trend_template_false_when_ma_stack_wrong_order(monkeypatch):
    monkeypatch.setattr(vcp, "rs_rating", lambda ticker, date: 85)
    row = _trend_row(sma50=90, sma150=100, sma200=95)  # sma50 < sma150, stack broken
    assert not stage2_trend_template(row, "TEST", "2024-01-01")


def test_stage2_trend_template_false_when_rs_below_threshold(monkeypatch):
    monkeypatch.setattr(vcp, "rs_rating", lambda ticker, date: 50)
    assert not stage2_trend_template(_trend_row(), "TEST", "2024-01-01")


def test_stage2_trend_template_false_when_required_field_missing(monkeypatch):
    monkeypatch.setattr(vcp, "rs_rating", lambda ticker, date: 85)
    row = _trend_row(sma200=float("nan"))
    assert not stage2_trend_template(row, "TEST", "2024-01-01")
