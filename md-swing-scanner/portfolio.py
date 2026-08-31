import heapq
import math

import pandas as pd

MAX_CONCURRENT = 3
TOTAL_CAPITAL = 100_000


def schedule(trades):
    """Greedy interval scheduling: admit a candidate trade only if fewer than
    MAX_CONCURRENT positions are open on its entry_date. First-come-first-served,
    no queueing — a signal that can't be taken is simply skipped, not deferred."""
    trades = trades.sort_values("entry_date").reset_index(drop=True)
    occupied = []  # min-heap of exit_date for currently open slots
    admitted, skipped = [], []

    for _, t in trades.iterrows():
        while occupied and occupied[0] < t.entry_date:
            heapq.heappop(occupied)
        if len(occupied) < MAX_CONCURRENT:
            heapq.heappush(occupied, t.exit_date)
            admitted.append(t)
        else:
            skipped.append(t)

    return pd.DataFrame(admitted), pd.DataFrame(skipped)


def simulate_lots(admitted, total_capital=TOTAL_CAPITAL):
    """Real rupee sizing, ONE shared cash pool (rewritten 2026-08-31 — the original
    split total_capital into MAX_CONCURRENT equal, independent per-slot balances,
    which meant a trade's affordability depended on the arbitrary slot it happened
    to be scheduled into, not on the portfolio's real total cash. Verified this was
    a genuine artifact: at ₹1L vs ₹1.5L on the same ATM-next trade set, realized
    return went +126.0% -> -8.1% -> +128.2% at ₹2L, purely from which slot each
    trade landed in changing as the split boundaries moved — money is fungible in
    a real brokerage account, so it should be here too.

    Capital is actually locked out of `balance` while a position is open (deducted
    at entry, returned + realized P&L at exit) — the concurrency cap (at most
    MAX_CONCURRENT positions open at once) still comes entirely from `schedule()`
    upstream; this function only adds the capital constraint on top. Still fixed
    1 lot per trade, never scaled up with available balance — that's a separate
    sizing-policy question, deliberately not changed in the same pass as the
    capital-pooling fix (one variable at a time)."""
    balance = total_capital
    occupied = []  # heap of (exit_date, capital_deployed, rupee_pnl) — locked-up capital + its outcome
    rows = []

    def release_expired(before_date):
        nonlocal balance
        while occupied and occupied[0][0] < before_date:
            _, deployed, pnl = heapq.heappop(occupied)
            balance += deployed + pnl

    for _, t in admitted.sort_values("entry_date").iterrows():
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
    trades = pd.read_csv("runs/option_trades.csv", parse_dates=["entry_date", "exit_date"])
    admitted, skipped = schedule(trades)
    print(f"{len(admitted)} admitted (time-slot available), {len(skipped)} skipped (all 3 slots busy)")

    log, final_capital = simulate_lots(admitted)
    print(f"{len(log)} trades actually taken (affordable), "
          f"{len(admitted) - len(log)} skipped (couldn't afford even 1 lot)")

    print(f"\nfinal capital: Rs.{final_capital:,.0f}  (started Rs.{TOTAL_CAPITAL:,.0f})")
    print(f"return: {(final_capital/TOTAL_CAPITAL - 1)*100:.1f}%")
    print(f"win rate: {(log.rupee_pnl > 0).mean()*100:.1f}%")
    print(f"biggest single win / loss: Rs.{log.rupee_pnl.max():,.0f} / Rs.{log.rupee_pnl.min():,.0f}")

    log.to_csv("runs/lot_trades.csv", index=False)
