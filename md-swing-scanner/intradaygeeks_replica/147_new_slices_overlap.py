"""Overlap + combos of the new slices (user, 2026-10-10: 'check combos -- some are duplicates / overlapping'). Spec fixed before
running. Trades: revised frame (137) full stack, 10:15 candle, 1% target, stop <= 0.5%, ATR >= 2%. Conditions (as declared in 141/146):
  A open BELOW the 1H EMA34;  B live daily 8-EMA at least 0.5% BELOW the entry (price >= 0.5% above it);
  C already moved < 0.25 of a day's ATR (little spent before entry).
(1) overlap: share of trades with each, and pairwise agreement (how often two conditions are both true / both false) + correlation;
(2) every combination: alone, pairs, all three, none. Rs @1L / @1k, by year. Results only."""
import warnings, itertools
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "146_already_moved.py").read().split("\nH = ")[0])
Z["d8_live"] = 2 / 9 * Z.entry + 7 / 9 * Z.s8
Z["A"] = Z.open_vs_e34 < 0; Z["B"] = (Z.entry - Z.d8_live) / Z.entry * 100 >= 0.5; Z["C"] = Z.moved < 0.25
NM = {"A": "open below 1H EMA34", "B": "price >= 0.5% above daily 8-EMA", "C": "little already moved (< 0.25 ATR)"}
print(f"{len(Z)} trades | " + " | ".join(f"{k} {NM[k]}: {Z[k].mean()*100:.0f}%" for k in "ABC"))
print("\n| pair | both true | agree (both true or both false) | correlation |\n|---|---|---|---|")
for a, b in itertools.combinations("ABC", 2):
    print(f"| {a} & {b} | {(Z[a] & Z[b]).mean()*100:.0f}% | {(Z[a] == Z[b]).mean()*100:.0f}% | {Z[a].astype(int).corr(Z[b].astype(int)):+.2f} |")
H = "| combo | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
print("\n" + H); print(row("ALL (current stack)", Z))
for r_ in (1, 2, 3):
    for combo in itertools.combinations("ABC", r_):
        m = Z[list(combo)].all(axis=1); print(row(" + ".join(combo) + (" (" + NM[combo[0]] + ")" if r_ == 1 else ""), Z[m]))
print(row("none of A, B, C", Z[~Z[["A", "B", "C"]].any(axis=1)]))
print(row("A or C (fresh)", Z[Z.A | Z.C])); print(row("(A or C) or B (at least one)", Z[Z.A | Z.C | Z.B]))
