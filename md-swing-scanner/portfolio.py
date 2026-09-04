import heapq

import pandas as pd

TOTAL_CAPITAL = 100_000


def simulate_lots(trades, total_capital=TOTAL_CAPITAL):
    """Event-driven, cash-only portfolio allocator (rewritten 2026-09-03 — Portfolio
    Engine v2, replacing the old schedule()+simulate_lots() two-stage design).

    The old design pre-filtered trades through schedule()'s fixed MAX_CONCURRENT=3
    slot gate BEFORE this function ever saw them — a cap applied independent of
    capital entirely. That produced a real, disqualifying pathology, caught by the
    round-6 outside critique and independently confirmed against this same
    session's equity-side capital-timeline fix (same root cause, same wrong
    borrowed assumption): "increasing capital should never make an otherwise
    affordable trade impossible" is a basic invariant a portfolio allocator must
    hold, and the fixed-slot gate violated it — real numbers at ₹1L/₹1.5L/₹2L on
    the current ITM-next set came back +315.6% / -92.3% / +208.0%, wildly
    non-monotonic, driven entirely by which unrelated trades got bumped in/out of
    the 3 slots as capital changed, not by any real difference in strategy quality
    (documented in FINDINGS.md's "Near-miss ranking signal" neighboring section —
    see the new entry alongside it for the full before/after).

    Fix: drop the slot gate entirely. This function was ALREADY a correct,
    event-driven cash-only allocator on its own (rewritten 2026-08-31 for the
    shared-cash-pool fix) — the only bug was something upstream filtering its
    input first. Every trade is now considered in entry-date order; a trade is
    skipped ONLY if the shared cash pool can't afford even 1 lot right now, not
    because of an arbitrary concurrent-position count. If a real concurrency
    constraint is wanted later (e.g., reserving cash for next month's ITM
    premiums, the original real-world reasoning behind "3"), model it as an
    explicit cash reserve, not a trade-count cap — a count-based cap can never
    satisfy the invariant above, no matter what the count is.

    Still fixed 1 lot per trade, never scaled up with available balance — a
    separate sizing-policy question, unchanged here."""
    balance = total_capital
    occupied = []  # heap of (exit_date, capital_deployed, rupee_pnl) — locked-up capital + its outcome
    rows = []

    def release_expired(before_date):
        nonlocal balance
        while occupied and occupied[0][0] < before_date:
            _, deployed, pnl = heapq.heappop(occupied)
            balance += deployed + pnl

    for _, t in trades.sort_values("entry_date").iterrows():
        release_expired(t.entry_date)

        cost_per_lot = t.lot_size * t.entry_opt_price
        n_lots = 1  # fixed 1 lot per trade, never scale up with available balance
        capital_deployed = n_lots * cost_per_lot
        if balance < capital_deployed:
            continue  # can't afford even 1 lot from the shared pool right now — skip

        balance -= capital_deployed  # locked up for the life of the position
        rupee_pnl = n_lots * t.lot_size * (t.exit_opt_price - t.entry_opt_price)
        heapq.heappush(occupied, (t.exit_date, capital_deployed, rupee_pnl))

        rows.append(dict(
            ticker=t.ticker, entry_date=t.entry_date, exit_date=t.exit_date,
            lot_size=t.lot_size, n_lots=n_lots, capital_deployed=capital_deployed,
            rupee_pnl=rupee_pnl, cash_after_entry=balance,
        ))

    release_expired(pd.Timestamp.max)  # settle whatever's still open at data end
    return pd.DataFrame(rows), balance


if __name__ == "__main__":
    # ITM+next-month is the standing decision (see README.md/FINDINGS.md) — NOT
    # runs/option_trades.csv, a stale 86-trade file left over from before v28 that
    # the old __main__ pointed at (caught 2026-09-03 while compiling the round-6
    # critic submission).
    trades = pd.read_csv("runs/opt_v28_itm_next.csv", parse_dates=["entry_date", "exit_date"])
    print(f"{len(trades)} candidate trades (ITM+next-month, v28)")

    log, final_capital = simulate_lots(trades)
    print(f"{len(log)} taken (affordable from the shared cash pool), "
          f"{len(trades) - len(log)} skipped (couldn't afford even 1 lot at the time)")

    print(f"\nfinal capital: Rs.{final_capital:,.0f}  (started Rs.{TOTAL_CAPITAL:,.0f})")
    print(f"return: {(final_capital/TOTAL_CAPITAL - 1)*100:.1f}%")
    print(f"win rate: {(log.rupee_pnl > 0).mean()*100:.1f}%")
    print(f"biggest single win / loss: Rs.{log.rupee_pnl.max():,.0f} / Rs.{log.rupee_pnl.min():,.0f}")

    net_gain = log.rupee_pnl.sum()
    top10 = log.rupee_pnl.sort_values(ascending=False).head(10).sum()
    print(f"top-10 concentration: {top10/net_gain*100:.1f}% of net gain"
          if net_gain else "top-10 concentration: n/a (net gain is zero)")

    log.to_csv("runs/lot_trades.csv", index=False)
