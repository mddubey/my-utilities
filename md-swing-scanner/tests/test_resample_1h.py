import pandas as pd
import pytest

from resample_1h import SESSION_OPEN, resample_session_1h, resample_1h


def _five_min(day, start="09:15", n=75, base=100.0):
    """n consecutive 5-min bars for one NSE session, stored the way intraday_cache
    does (UTC index). Prices step up by 1 per bar so every aggregate is predictable."""
    start_ts = pd.Timestamp(f"{day} {start}", tz="Asia/Kolkata")
    idx = pd.date_range(start_ts, periods=n, freq="5min").tz_convert("UTC")
    px = [base + i for i in range(n)]
    return pd.DataFrame(
        {"Open": px, "High": [p + 0.5 for p in px], "Low": [p - 0.5 for p in px],
         "Close": [p + 0.25 for p in px], "Volume": [10] * n},
        index=pd.DatetimeIndex(idx, name="Datetime"),
    )


def test_bins_anchor_at_0915_and_full_session_gives_seven_bars():
    out = resample_1h(_five_min("2026-07-13"))

    assert len(out) == 7
    assert [ts.strftime("%H:%M") for ts in out.index] == [
        "09:15", "10:15", "11:15", "12:15", "13:15", "14:15", "15:15"]
    assert str(out.index.tz) == "Asia/Kolkata"
    assert out.n_bars.tolist() == [12, 12, 12, 12, 12, 12, 3]
    assert out.complete.tolist() == [True] * 7


def test_ohlcv_aggregation_first_max_min_last_sum():
    out = resample_1h(_five_min("2026-07-13"))
    first = out.iloc[0]

    # bars 0..11 -> opens 100..111, highs 100.5..111.5, lows 99.5..110.5, close of bar 11 = 111.25
    assert first.Open == 100.0
    assert first.High == 111.5
    assert first.Low == 99.5
    assert first.Close == 111.25
    assert first.Volume == 120


def test_stub_bar_is_the_1515_to_1530_tail():
    out = resample_1h(_five_min("2026-07-13"))
    stub = out.iloc[-1]

    assert stub.name.strftime("%H:%M") == "15:15"
    assert stub.Open == 172.0
    assert stub.Close == 174.25
    assert stub.n_bars == 3


def test_merge_stub_folds_tail_into_1415_bar():
    out = resample_1h(_five_min("2026-07-13"), stub="merge")
    last = out.iloc[-1]

    assert len(out) == 6
    assert last.name.strftime("%H:%M") == "14:15"
    assert last.n_bars == 15
    assert last.Close == 174.25
    assert last.High == 174.5
    assert last.complete


def test_drop_stub_removes_tail():
    out = resample_1h(_five_min("2026-07-13"), stub="drop")

    assert len(out) == 6
    assert out.index[-1].strftime("%H:%M") == "14:15"


def test_missing_five_min_bars_mark_bin_incomplete():
    df = _five_min("2026-07-13")
    df = df.drop(df.index[3])  # 09:30 bar missing

    out = resample_1h(df)

    assert out.iloc[0].n_bars == 11
    assert not out.iloc[0].complete
    assert out.complete.iloc[1:].all()


def test_session_ending_at_1510_has_no_stub_bar_and_full_1415_bin():
    df = _five_min("2026-07-13", n=72)  # last bar 15:10, stub 15:15-15:25 absent

    out = resample_1h(df)

    assert len(out) == 6
    assert out.iloc[-1].name.strftime("%H:%M") == "14:15"
    assert out.iloc[-1].n_bars == 12
    assert out.complete.all()


def test_session_ending_at_1515_has_partial_stub_marked_incomplete():
    df = _five_min("2026-07-13", n=73)  # last bar 15:15, stub has 1 of 3 bars

    out = resample_1h(df)

    assert len(out) == 7
    assert out.iloc[-1].n_bars == 1
    assert not out.iloc[-1].complete


def test_bars_never_straddle_sessions():
    two_days = pd.concat([_five_min("2026-07-13"), _five_min("2026-07-14", base=500.0)])

    out = resample_1h(two_days)

    assert len(out) == 14
    assert out.index[6].date() == pd.Timestamp("2026-07-13").date()
    assert out.index[7].date() == pd.Timestamp("2026-07-14").date()
    assert out.iloc[7].Open == 500.0
    assert out.session.iloc[7] == pd.Timestamp("2026-07-14").date()


def test_session_invariants_hold_against_source_bars():
    src = _five_min("2026-07-13")
    out = resample_1h(src)
    src_ist = src.tz_convert("Asia/Kolkata")

    assert out.High.max() == src_ist.High.max()
    assert out.Low.min() == src_ist.Low.min()
    assert out.Open.iloc[0] == src_ist.Open.iloc[0]
    assert out.Close.iloc[-1] == src_ist.Close.iloc[-1]
    assert out.Volume.sum() == src_ist.Volume.sum()


def test_bar_before_session_open_is_rejected():
    df = _five_min("2026-07-13", start="09:00", n=5)

    with pytest.raises(ValueError, match="before session open"):
        resample_1h(df)


def test_resample_session_1h_handles_one_session_only():
    df = _five_min("2026-07-13").tz_convert("Asia/Kolkata")

    out = resample_session_1h(df)

    assert len(out) == 7
    assert SESSION_OPEN == "09:15"


# --- Closing Auction Session (CAS, 2026-08-03): F&O names stop continuous trading at 15:15 ---

def test_fo_post_cas_session_has_six_full_bins_and_no_stub():
    out = resample_1h(_five_min("2026-08-05"), fo=True)

    assert len(out) == 6
    assert out.index[-1].strftime("%H:%M") == "14:15"
    assert out.n_bars.tolist() == [12] * 6
    assert out.complete.all()
    assert out.iloc[-1].Close == 171.25  # bar 71 = 15:10 bar, the last continuous print
    assert (out.session_close == "15:15").all()


def test_fo_post_cas_drops_auction_residue_bars_at_and_after_1515():
    df = _five_min("2026-08-05", n=73)  # ends with a thin 15:15 bar

    out = resample_1h(df, fo=True)

    assert len(out) == 6
    assert out.iloc[-1].Close == 171.25
    assert out.iloc[-1].High == 171.5


def test_fo_pre_cas_keeps_full_session_with_stub():
    out = resample_1h(_five_min("2026-07-13"), fo=True)

    assert len(out) == 7
    assert (out.session_close == "15:30").all()


def test_non_fo_post_cas_keeps_full_session_with_stub():
    out = resample_1h(_five_min("2026-08-05"), fo=False)

    assert len(out) == 7
    assert out.iloc[-1].n_bars == 3


def test_fo_frame_spanning_cas_start_switches_session_close_per_day():
    two_days = pd.concat([_five_min("2026-07-31"), _five_min("2026-08-03", base=500.0)])

    out = resample_1h(two_days, fo=True)

    assert out[out.session == pd.Timestamp("2026-07-31").date()].shape[0] == 7
    assert out[out.session == pd.Timestamp("2026-08-03").date()].shape[0] == 6


def test_ticker_resolves_fo_membership(monkeypatch):
    import resample_1h as mod
    monkeypatch.setattr(mod, "FO_UNIVERSE", {"RELIANCE"})

    fo_out = mod.resample_1h(_five_min("2026-08-05"), ticker="RELIANCE")
    other_out = mod.resample_1h(_five_min("2026-08-05"), ticker="KAJARIACER")

    assert len(fo_out) == 6
    assert len(other_out) == 7


def test_explicit_fo_overrides_ticker_lookup(monkeypatch):
    import resample_1h as mod
    monkeypatch.setattr(mod, "FO_UNIVERSE", {"RELIANCE"})

    out = mod.resample_1h(_five_min("2026-08-05"), ticker="RELIANCE", fo=False)

    assert len(out) == 7
