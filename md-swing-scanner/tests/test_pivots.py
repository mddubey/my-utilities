import pandas as pd

from pivots import weekly_pivots, daily_pivots


def _daily_df(rows):
    """rows: list of (date_str, High, Low, Close)."""
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {"High": [r[1] for r in rows], "Low": [r[2] for r in rows], "Close": [r[3] for r in rows]},
        index=idx,
    )


def test_weekly_pivots_formula_and_no_lookahead():
    # week 1: Mon 2024-01-01 .. Fri 2024-01-05 -> H=110, L=90, C=100 (last close of the week)
    # week 2: Mon 2024-01-08 .. Fri 2024-01-12 -> should see week 1's pivots, not week 2's own
    df = _daily_df([
        ("2024-01-01", 105, 95, 100),
        ("2024-01-02", 108, 98, 102),
        ("2024-01-03", 110, 90, 95),
        ("2024-01-04", 106, 96, 101),
        ("2024-01-05", 107, 97, 100),  # week 1 close
        ("2024-01-08", 200, 180, 190),  # week 2 — very different range
        ("2024-01-09", 205, 185, 195),
    ])
    levels = weekly_pivots(df)
    pp = (110 + 90 + 100) / 3
    r1 = 2 * pp - 90
    s1 = 2 * pp - 110
    r2 = pp + (110 - 90)
    s2 = pp - (110 - 90)

    for date in ("2024-01-08", "2024-01-09"):
        row = levels.loc[date]
        assert row.pp == pp
        assert row.r1 == r1
        assert row.s1 == s1
        assert row.r2 == r2
        assert row.s2 == s2

    # week 1 itself must NOT have week 1's own pivots available (shift(1) — no lookahead)
    assert pd.isna(levels.loc["2024-01-01"].pp)


def test_daily_pivots_formula_and_no_lookahead():
    df = _daily_df([
        ("2024-01-01", 110, 90, 100),
        ("2024-01-02", 120, 80, 105),
    ])
    levels = daily_pivots(df)
    assert pd.isna(levels.loc["2024-01-01"].pp)  # first day has no prior day
    pp = (110 + 90 + 100) / 3
    row = levels.loc["2024-01-02"]
    assert row.pp == pp
    assert row.r1 == 2 * pp - 90
    assert row.s1 == 2 * pp - 110
    assert row.r2 == pp + (110 - 90)
    assert row.s2 == pp - (110 - 90)
