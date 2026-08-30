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
    """Real rupee sizing: each of the MAX_CONCURRENT slots gets an equal share of
    capital, buys as many WHOLE lots as it can afford at entry, and skips the
    trade entirely if it can't afford even 1 lot. Leftover cash (after buying
    whole lots) just sits idle in that slot until the position closes."""
    balances = [total_capital / MAX_CONCURRENT] * MAX_CONCURRENT
    free_slots = list(range(MAX_CONCURRENT))
    occupied = []  # heap of (exit_date, slot_index)
    rows = []

    for _, t in admitted.sort_values("entry_date").iterrows():
        while occupied and occupied[0][0] < t.entry_date:
            _, slot = heapq.heappop(occupied)
            free_slots.append(slot)
        if not free_slots:
            continue  # shouldn't happen if `admitted` already respects MAX_CONCURRENT
        slot = free_slots.pop()

        cost_per_lot = t.lot_size * t.entry_opt_price
        n_lots = 1  # fixed 1 lot per trade, never scale up with available balance
        if balances[slot] < cost_per_lot:
            free_slots.append(slot)  # can't afford even 1 lot — skip, slot stays free
            continue

        rupee_pnl = n_lots * t.lot_size * (t.exit_opt_price - t.entry_opt_price)
        balances[slot] += rupee_pnl
        heapq.heappush(occupied, (t.exit_date, slot))

        rows.append(dict(
            ticker=t.ticker, entry_date=t.entry_date, exit_date=t.exit_date,
            lot_size=t.lot_size, n_lots=n_lots, capital_deployed=n_lots * cost_per_lot,
            rupee_pnl=rupee_pnl, slot=slot, slot_balance_after=balances[slot],
        ))

    return pd.DataFrame(rows), sum(balances)


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
