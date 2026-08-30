import pandas as pd

import market_regime
from market_regime import _compute_adx, market_trending, NIFTY_ADX_MIN


def test_adx_high_on_a_strongly_trending_series():
    n = 60
    high = pd.Series([100 + i * 2 for i in range(n)], dtype=float)
    low = high - 5
    close = high - 2
    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    adx, plus_di, minus_di = _compute_adx(df)
    assert adx.iloc[-1] > 25
    assert plus_di.iloc[-1] > minus_di.iloc[-1]  # a rising series should show +DI dominant


def test_adx_low_on_a_flat_choppy_series():
    n = 60
    import math
    high = pd.Series([100 + 2 * math.sin(i) for i in range(n)], dtype=float)
    low = high - 5
    close = high - 2
    df = pd.DataFrame({"High": high, "Low": low, "Close": close})
    adx, _, _ = _compute_adx(df)
    assert adx.iloc[-1] < 20


def _fake_regime_frame(rows):
    """rows: list of (date_str, close, adx14, plus_di14, minus_di14, sma200)."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame({
        "Close": [r[1] for r in rows], "adx14": [r[2] for r in rows],
        "plus_di14": [r[3] for r in rows], "minus_di14": [r[4] for r in rows],
        "sma200": [r[5] for r in rows],
    }, index=idx)


def test_market_trending_false_before_any_data(monkeypatch):
    frame = _fake_regime_frame([("2024-01-10", 100, 25, 20, 15, 90)])
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame)
    assert not market_trending(pd.Timestamp("2024-01-01"))


def test_market_trending_uses_most_recent_prior_trading_day(monkeypatch):
    frame = _fake_regime_frame([
        ("2024-01-05", 100, 25, 20, 15, 90),
        ("2024-01-12", 100, 10, 20, 15, 90),  # choppy the following week
    ])
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame)
    # a weekend/holiday date with no exact row should fall back to the last available day
    assert market_trending(pd.Timestamp("2024-01-08"))  # still sees 01-05's ADX=25
    assert not market_trending(pd.Timestamp("2024-01-12"))  # now sees 01-12's ADX=10


def test_market_trending_plain_threshold(monkeypatch):
    frame = _fake_regime_frame([
        ("2024-01-05", 100, NIFTY_ADX_MIN - 1, 20, 15, 90),
        ("2024-01-06", 100, NIFTY_ADX_MIN, 20, 15, 90),
    ])
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame)
    assert not market_trending(pd.Timestamp("2024-01-05"))
    assert market_trending(pd.Timestamp("2024-01-06"))


def test_market_trending_require_rising(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    adx_flat = [25] * 10
    adx_rising = [20, 21, 22, 23, 24, 25, 26, 27, 28, 29]
    frame_flat = pd.DataFrame({"Close": [100] * 10, "adx14": adx_flat,
                               "plus_di14": [20] * 10, "minus_di14": [15] * 10,
                               "sma200": [90] * 10}, index=dates)
    frame_rising = pd.DataFrame({"Close": [100] * 10, "adx14": adx_rising,
                                  "plus_di14": [20] * 10, "minus_di14": [15] * 10,
                                  "sma200": [90] * 10}, index=dates)

    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_flat)
    assert market_trending(dates[-1], require_rising=True)  # flat but not falling -> still >=

    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_rising)
    assert market_trending(dates[-1], require_rising=True)  # genuinely rising


def test_market_trending_require_uptrend(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    frame_up = pd.DataFrame({"Close": [100, 100], "adx14": [25, 25],
                              "plus_di14": [30, 30], "minus_di14": [10, 10],
                              "sma200": [90, 90]}, index=dates)
    frame_down = pd.DataFrame({"Close": [100, 100], "adx14": [25, 25],
                                "plus_di14": [10, 10], "minus_di14": [30, 30],
                                "sma200": [90, 90]}, index=dates)
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_up)
    assert market_trending(dates[-1], require_uptrend=True)
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_down)
    assert not market_trending(dates[-1], require_uptrend=True)


def test_market_trending_require_above_sma200(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=2, freq="D")
    frame_above = pd.DataFrame({"Close": [100, 100], "adx14": [25, 25],
                                 "plus_di14": [20, 20], "minus_di14": [15, 15],
                                 "sma200": [90, 90]}, index=dates)
    frame_below = pd.DataFrame({"Close": [100, 100], "adx14": [25, 25],
                                 "plus_di14": [20, 20], "minus_di14": [15, 15],
                                 "sma200": [110, 110]}, index=dates)
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_above)
    assert market_trending(dates[-1], require_above_sma200=True)
    monkeypatch.setattr(market_regime, "_regime_frame", lambda: frame_below)
    assert not market_trending(dates[-1], require_above_sma200=True)
