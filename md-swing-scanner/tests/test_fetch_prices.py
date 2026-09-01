from datetime import date, datetime

import pandas as pd

import fetch_prices
from fetch_prices import IST


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
    # pin "now" to match the fixture's last date, so safe_today == the fetched data's own
    # max date and _recover_safe_today's "still behind safe_today" check doesn't fire a
    # second (unmocked-for-here) download call — real "now" would always be years ahead
    # of this fixture's 2024 dates otherwise.
    monkeypatch.setattr(fetch_prices, "_now_ist", lambda: datetime(2024, 1, 5, 16, 0, tzinfo=IST))

    def fake_download(yf_tickers, **kwargs):
        assert "period" in kwargs
        return _multi_index_df(yf_tickers, dates)

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["NEWCO"])
    assert result == {"new": ["NEWCO"], "updated": [], "current": [], "empty": []}
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
    result = fetch_prices.fetch_all(["EXISTS"])
    assert result == {"new": [], "updated": ["EXISTS"], "current": [], "empty": []}
    written = pd.read_csv(tmp_path / "EXISTS.csv", index_col="Date", parse_dates=True)
    assert len(written) == 6  # 5 old + only the 1 genuinely new day (01-06)
    assert not written.index.duplicated().any()
    assert written.index.is_monotonic_increasing


def test_fetch_all_recovers_nan_close_on_last_day_of_wide_range(tmp_path, monkeypatch):
    """The actual incident (2026-09-02): a real, reproducible yfinance quirk where the
    SAME ticker/date's Close comes back NULL when that date is the tail row of a wider
    multi-day range request, but correct when requested as a narrow single-day range on
    its own. A shared batch start date (the minimum last-cached-date across the whole
    existing_tickers batch) means even one stale ticker widens the request for
    everyone, so this could silently drop today's data for tickers that were otherwise
    fully current. _recover_safe_today re-queries narrowly for anything still missing
    safe_today after the main fetch."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fetch_prices, "_now_ist", lambda: datetime(2026, 9, 1, 16, 0, tzinfo=IST))
    old_dates = pd.date_range(end="2026-08-28", periods=4, freq="D")  # last cached: 08-28
    _multi_index_df(["A.NS"], old_dates)["A.NS"].to_csv(tmp_path / "A.csv")

    calls = []

    def fake_download(yf_tickers, **kwargs):
        calls.append(kwargs.get("start"))
        if kwargs.get("start") == "2026-08-29":
            # wide range (the main fetch) — the real bug: the tail day's Close is null
            wide_dates = pd.date_range("2026-08-29", periods=4, freq="D")  # 08-29..09-01
            df = _multi_index_df(yf_tickers, wide_dates)
            df.loc[wide_dates[-1], ("A.NS", "Close")] = float("nan")
            return df
        elif kwargs.get("start") == "2026-09-01":
            # narrow single-day recovery request — same date, correct value this time
            return _multi_index_df(yf_tickers, pd.date_range("2026-09-01", periods=1))
        raise AssertionError(f"unexpected start kwarg: {kwargs.get('start')}")

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["A"])
    assert result == {"new": [], "updated": ["A"], "current": [], "empty": []}
    written = pd.read_csv(tmp_path / "A.csv", index_col="Date", parse_dates=True)
    assert pd.Timestamp("2026-09-01") in written.index
    assert not pd.isna(written.loc["2026-09-01", "Close"])
    assert calls == ["2026-08-29", "2026-09-01"]  # main wide fetch, then one narrow recovery


def test_fetch_all_existing_ticker_already_current_is_a_no_op(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    old_dates = pd.date_range("2024-01-01", periods=5, freq="D")
    _multi_index_df(["CURRENT.NS"], old_dates)["CURRENT.NS"].to_csv(tmp_path / "CURRENT.csv")

    def fake_download(yf_tickers, **kwargs):
        # nothing newer than what's already cached
        return _multi_index_df(yf_tickers, pd.date_range("2024-01-05", periods=1, freq="D"))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["CURRENT"])
    assert result == {"new": [], "updated": [], "current": ["CURRENT"], "empty": []}
    written = pd.read_csv(tmp_path / "CURRENT.csv", index_col="Date", parse_dates=True)
    assert len(written) == 5  # unchanged


def test_fetch_all_marks_empty_when_new_ticker_has_no_data(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)

    def fake_download(yf_tickers, **kwargs):
        return _multi_index_df(yf_tickers, pd.DatetimeIndex([]))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["DELISTED"])
    assert result == {"new": [], "updated": [], "current": [], "empty": ["DELISTED"]}
    assert not (tmp_path / "DELISTED.csv").exists()


def test_fetch_all_weekend_run_reports_current_not_fetched(tmp_path, monkeypatch):
    """The exact scenario that caused real confusion (2026-08-30): running on a
    weekend/holiday with an already-current cache must be reported as 'current', not
    lumped in with tickers that genuinely got new rows."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    old_dates = pd.date_range("2024-01-01", periods=5, freq="D")  # last cached day: 01-05
    for t in ("A", "B"):
        _multi_index_df([f"{t}.NS"], old_dates)[f"{t}.NS"].to_csv(tmp_path / f"{t}.csv")

    def fake_download(yf_tickers, **kwargs):
        # yfinance genuinely has nothing newer than 01-05 (e.g. a weekend)
        return _multi_index_df(yf_tickers, pd.DatetimeIndex([]))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["A", "B"])
    assert result == {"new": [], "updated": [], "current": ["A", "B"], "empty": []}


def test_fetch_all_same_day_rerun_skips_the_network_call_entirely(tmp_path, monkeypatch):
    """Already fetched through today (or later) — a rerun must not call yf.download at
    all, since a future start date can never have data. Distinct from the
    weekend/holiday case above, where the network still has to be asked."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    dates_through_today = pd.date_range(end=pd.Timestamp(date.today()), periods=5, freq="D")
    _multi_index_df(["A.NS"], dates_through_today)["A.NS"].to_csv(tmp_path / "A.csv")

    def fake_download(yf_tickers, **kwargs):
        raise AssertionError("should not have called yf.download for a same-day rerun")

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["A"])
    assert result == {"new": [], "updated": [], "current": ["A"], "empty": []}


def test_fetch_all_before_safe_hour_does_not_cache_todays_row(tmp_path, monkeypatch):
    """The actual incident (2026-08-31): a fetch before SAME_DAY_SAFE_HOUR returned a
    real-looking (non-null) Close for today that Yahoo hadn't finished settling yet —
    silently wrong by ~1%, and since the cache is purely incremental, it would have
    been stuck forever. Before the safe hour, today's row must not be written at all,
    so a later same-day run can still pick it up once it's actually safe."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    today = date(2026, 8, 31)
    monkeypatch.setattr(fetch_prices, "_now_ist", lambda: datetime(2026, 8, 31, 15, 59, tzinfo=IST))
    old_dates = pd.date_range(end="2026-08-28", periods=4, freq="D")  # last cached: 08-28
    _multi_index_df(["A.NS"], old_dates)["A.NS"].to_csv(tmp_path / "A.csv")

    def fake_download(yf_tickers, **kwargs):
        # yfinance returns a real-looking (not null) row for today, still in flux
        return _multi_index_df(yf_tickers, pd.DatetimeIndex([pd.Timestamp(today)]))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["A"])
    assert result == {"new": [], "updated": [], "current": ["A"], "empty": []}
    written = pd.read_csv(tmp_path / "A.csv", index_col="Date", parse_dates=True)
    assert written.index.max() == pd.Timestamp("2026-08-28")  # today NOT appended


def test_fetch_all_at_safe_hour_caches_todays_row(tmp_path, monkeypatch):
    """Same setup as above, but at/after SAME_DAY_SAFE_HOUR — now safe to trust."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    today = date(2026, 8, 31)
    monkeypatch.setattr(fetch_prices, "_now_ist", lambda: datetime(2026, 8, 31, 16, 0, tzinfo=IST))
    old_dates = pd.date_range(end="2026-08-28", periods=4, freq="D")
    _multi_index_df(["A.NS"], old_dates)["A.NS"].to_csv(tmp_path / "A.csv")

    def fake_download(yf_tickers, **kwargs):
        return _multi_index_df(yf_tickers, pd.DatetimeIndex([pd.Timestamp(today)]))

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["A"])
    assert result == {"new": [], "updated": ["A"], "current": [], "empty": []}
    written = pd.read_csv(tmp_path / "A.csv", index_col="Date", parse_dates=True)
    assert written.index.max() == pd.Timestamp("2026-08-31")


def test_fetch_all_new_ticker_before_safe_hour_drops_todays_row(tmp_path, monkeypatch):
    """The new-ticker (full history) path is exposed to the exact same risk — a brand
    new ticker's freshly-pulled 5y history can still end with an unsettled today."""
    monkeypatch.setattr(fetch_prices, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(fetch_prices, "_now_ist", lambda: datetime(2026, 8, 31, 12, 0, tzinfo=IST))
    dates = pd.date_range(end="2026-08-31", periods=5, freq="D")

    def fake_download(yf_tickers, **kwargs):
        return _multi_index_df(yf_tickers, dates)

    monkeypatch.setattr(fetch_prices.yf, "download", fake_download)
    result = fetch_prices.fetch_all(["NEWCO"])
    assert result == {"new": ["NEWCO"], "updated": [], "current": [], "empty": []}
    written = pd.read_csv(tmp_path / "NEWCO.csv", index_col="Date", parse_dates=True)
    assert len(written) == 4  # 5 fetched, today (08-31) dropped as unsafe
    assert written.index.max() == pd.Timestamp("2026-08-30")
