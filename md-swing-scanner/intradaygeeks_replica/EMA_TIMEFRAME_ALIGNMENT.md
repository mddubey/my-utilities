# "Daily-34 EMA ≈ Weekly-8 EMA" (and similar pairs) — verified, not taken on faith

User's claim (2026-09-30): a stock taking support at its 34-EMA on a smaller timeframe is
"coincidentally" also near its 8-EMA on the next bigger timeframe — checked against
published multi-timeframe MA conversion math, then against real price data, both smaller
(faster) and bigger (this project's actual trading horizon) pairs.

**Standard conversion rule** (published, not folklore): to translate an EMA period from
one timeframe to another, multiply/divide by how many bars of the smaller timeframe fit
in one bar of the bigger one.

## Results, all six pairs checked (real price data, `backtest.load()` daily history /
## `intraday_cache.py` 5-min bars resampled with market-aligned boundaries, 5 tickers:
## RELIANCE/TCS/INFY/HDFCBANK/ITC)

| Pair (smaller-34 vs bigger-8) | Theoretical mismatch | Mean abs % diff (range) | Correlation (range) |
|---|---|---|---|
| 15min vs 1H | 6.2% off | 0.06–0.12% | 0.999–1.000 |
| Weekly vs Monthly | 2.3% off (closest theory) | 1.39–3.11% (**loosest empirical**) | 0.953–0.988 |
| Daily vs Weekly | 17.6% off | 0.36–0.45% | 0.997–1.000 |
| 30min vs 4H | 88% off | 0.27–0.65% | 0.983–0.996 |
| 1H vs Daily | 39–65% off | 0.37–1.16% | 0.954–0.990 |

**Verdict**: real, not folklore, for anything at daily resolution or finer — the two EMAs
track within ~0.1–1.2% of each other, correlation 0.95+, regardless of how far off the
theoretical bar-count math says they should be. EMA curves are just forgiving to nearby
period choices once smoothing dominates.

**Breaks down at weekly/monthly** — theoretically the closest-matched pair of the six, but
empirically the loosest by a wide margin. Likely cause: far fewer data points (250 weekly
bars over 5 years) and much more information per bar at that resolution (a monthly close
can jump several percent on one earnings report), so regime noise shows up directly as
EMA divergence. **Don't assume this generalizes to position/swing timeframes** just
because it held cleanly on the faster pairs.

**Practical implication for this project's actual horizon (intraday/short swing, not
position trading)**: safe to treat a smaller-timeframe-34 support test and the next
bigger-timeframe-8 support test as close to the same signal, not two independent
confirmations, for any pair at daily resolution or faster. Don't extend that assumption to
weekly/monthly without re-checking.

INFY was consistently the loosest-tracking ticker across every intraday pair tested — not
universal, worth spot-checking on a wider ticker sample before leaning on this for any
real filter design.

No production files touched, no backtest built on this yet — purely a verification pass
on whether the cross-timeframe EMA claim itself is real before it gets used for anything.
