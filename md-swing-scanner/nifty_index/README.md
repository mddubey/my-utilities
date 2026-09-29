# nifty_index/

Standalone NIFTY / BankNifty index swing-strategy explorations (Connors RSI2 and
Double-7, pivot and support/resistance entry-exit timing, strike checks, and the live
`nifty_index_signal_checker.py`). **Not part of the stock scanner** — no shared imports,
not critic-reviewed, own research log in `nifty_index_swing_strategy.md`.

Run from inside this folder. Scripts read `../data_cache/_NIFTY.csv` (and
`_BANKNIFTY.csv`) and `../options_cache/`, and write their output CSVs here.
`nifty_index_position.json` (the signal checker's one-position state file) is
gitignored, like `open_positions.csv` in the parent.
