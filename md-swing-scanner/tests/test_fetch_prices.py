import pandas as pd

import fetch_prices


def _multi_index_df(tickers, dates):
    """Mimics yfinance's actual group_by='ticker' return shape — a MultiIndex-columned
    frame (Ticker, Price) even for a single ticker (verified directly against the real
    library, 2026-08-30 — an earlier version of fetch_prices.py assumed single-ticker
    requests 'collapse' to a plain frame, which is false and broke the brand-new-ticker
    path; this fixture guards against that regressing)."""
    cols = pd.MultiIndex.from_product([tickers, ["Open", "High", "Low", "Close", "Volume"]],
                                       names=["Ticker", "Price"])
    data = {}
    for i, t in enumerate(tickers):
        for field in ["Open", "High", "Low", "Close", "Volume"]:
            data[(t, field)] = [100.0 + i + j for j in range(len(dates))]
    return pd.DataFrame(data, index=pd.DatetimeIndex(dates, name="Date"), columns=cols)


def test_fetch_all_brand_new_ticker_fetches_full_period(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    dates = pd.date_range("2024-01-01", periods=5, freq="D")

    def fake_download(yf_tickers, **kwargs):
        assert "period" in kwargs
        return _multi_index_df(yf_tickers, dates)

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    ok, empty = fetch_prices.fetch_all(["NEWCO"])
    assert ok == ["NEWCO"] and empty == []
    written = pd.read_csv(tmp_path / "NEWCO.csv", index_col="Date", parse_dates=True)
    assert len(written) == 5


def test_fetch_all_existing_ticker_appends_only_new_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    old_dates = pd.date_range("2024-01-01", periods=5, freq="D")
    _multi_index_df(["EXISTS.NS"], old_dates)["EXISTS.NS"].to_csv(tmp_path / "EXISTS.csv")

    new_dates = pd.date_range("2024-01-04", periods=3, freq="D")  # overlaps 01-04, 01-05

    def fake_download(yf_tickers, **kwargs):
        assert "start" in kwargs
        return _multi_index_df(yf_tickers, new_dates)

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    ok, empty = fetch_prices.fetch_all(["EXISTS"])
    assert ok == ["EXISTS"]
    written = pd.read_csv(tmp_path / "EXISTS.csv", index_col="Date", parse_dates=True)
    assert len(written) == 6  # 5 old + only the 1 genuinely new day (01-06)
    assert not written.index.duplicated().any()
    assert written.index.is_monotonic_increasing


def test_fetch_all_existing_ticker_already_current_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    old_dates = pd.date_range("2024-01-01", periods=5, freq="D")
    _multi_index_df(["CURRENT.NS"], old_dates)["CURRENT.NS"].to_csv(tmp_path / "CURRENT.csv")

    def fake_download(yf_tickers, **kwargs):
        # nothing newer than what's already cached
        return _multi_index_df(yf_tickers, pd.date_range("2024-01-05", periods=1, freq="D"))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    ok, empty = fetch_prices.fetch_all(["CURRENT"])
    assert ok == ["CURRENT"]  # up to date counts as success, not a failure
    written = pd.read_csv(tmp_path / "CURRENT.csv", index_col="Date", parse_dates=True)
    assert len(written) == 5  # unchanged


def test_fetch_all_marks_empty_when_new_ticker_has_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)

    def fake_download(yf_tickers, **kwargs):
        return _multi_index_df(yf_tickers, pd.DatetimeIndex([]))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    ok, empty = fetch_prices.fetch_all(["DELISTED"])
    assert ok == [] and empty == ["DELISTED"]
    assert not (tmp_path / "DELISTED.csv").exists()
