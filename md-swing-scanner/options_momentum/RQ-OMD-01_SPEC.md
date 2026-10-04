# RQ-OMD-01 — Stock-Level Fast-Move Behaviour Map

Frozen as given by the user, 2026-10-04. Verbatim.

## Objective

Determine whether the broad stock universe contains repeatable short-horizon price
behaviours where a meaningful directional move is followed by another meaningful
directional move quickly enough to be potentially useful for a long directional option.

This is not yet an entry strategy. We are trying to discover the underlying phenomenon
first.

## 1. Population

Use the broadest clean stock population supported by the 1H dataset.

Do not restrict to: F&O stocks, optionable stocks, NIFTY 500, breakout stocks, high-volume
stocks, any technical-indicator-defined universe.

The implementer should report the actual: ticker count, date range, total 1H observations,
observations per ticker, missingness/completeness, any obvious survivorship/universe
limitations.

F&O classification can be added as a reporting split only, not as a discovery filter.

## 2. Primary data

1H candles are the primary discovery dataset. Daily data is useful for broader context.
5-minute data is not the primary discovery dataset; it will later be used to inspect the
mechanics of anything interesting found here.

Before calculating results, verify exactly how the 1H candles are constructed, particularly:
session boundaries, first-hour candle, last/partial candle, timestamps, gaps/missing bars,
corporate-action treatment.

## 3. What we actually want to measure

For every completed 1H observation, measure the stock's prior movement and then what happens
afterward. The key is to look at both continuation and reversal.

For a directional move into time T, measure forward behaviour: forward return, maximum
favorable excursion, maximum adverse excursion, time to reach subsequent highs/lows, amount
of the initial move retained, whether the next move continues in the same direction, whether
the move reverses, whether it stalls.

**Speed.** Do not reduce everything to eventual return. We specifically want to know: how
quickly does the stock produce a meaningful subsequent move? Report the path over
progressively longer horizons supported by the data rather than selecting one horizon in
advance (e.g. next 1H / 2H / 3H / remainder of session / next day). The point is mapping the
decay of the phenomenon, not optimizing which one looks best.

## 4. Condition the analysis on the stock's own movement

Do not simply ask "after stocks that went up 2%, what happened?" — that heavily favours
volatile stocks. Characterize the preceding move relative to the same stock's own historical
behaviour. Bucket prior 1H directional movement into broad historical magnitude/abnormality
groups and examine what happens afterward, using a simple, predeclared framework — do not
optimize the bucket boundaries. Show the full distribution. No assumption that either
direction should continue.

## 5. Crucially: separate the behaviours

Classify what happens after the initial movement into broad behavioural types:

- **A. Immediate continuation** — the stock continues directionally soon after the initial move.
- **B. Immediate reversal** — the stock gives back/reverses the move quickly.
- **C. Stall** — the stock doesn't meaningfully continue or reverse.
- **D. Delayed continuation** — the stock eventually moves further, but only after a
  meaningful period of dead time.

This distinction is central to the project. A stock moving +4% over the following two days is
not equivalent to one that moves +2% in the next hour and another +2% in the following hour —
for an options product those are economically very different.

## 6. Look at timing structure, not just returns

For each behaviour, report distributions of: initial move → subsequent move; initial move →
time to meaningful continuation; initial move → adverse excursion before continuation. This
should let us answer: when a stock starts moving unusually hard, does it tend to keep moving
immediately, reverse, or simply take its time? That's the actual discovery question.

## 7. No strategy construction yet

Explicitly do not do any of: entry rule, stop-loss optimization, profit target optimization,
option strike selection, DTE optimization, indicator shopping, breakout detection, F&O
filter, volume filter (unless needed purely for descriptive segmentation), threshold search
for the "best" move, machine learning, backtest of an options strategy.

The output is a behaviour map, not a trading system.

## One-line implementer instruction

Using the broadest clean stock universe available in the 1H dataset, map what happens after
unusually large stock-relative directional 1H movements — measuring continuation, reversal,
stall, magnitude, speed, MFE/MAE and time-to-move across the next several 1H horizons —
without restricting to F&O or constructing/optimizing a trading strategy.

## Expected result

Something that allows a specific next decision: "There is / is not a robust fast directional
phenomenon worth investigating further." If there is one, investigate what causes/defines
that state and how to enter it. If not, move to another market-behaviour family rather than
forcing an options strategy out of it.
