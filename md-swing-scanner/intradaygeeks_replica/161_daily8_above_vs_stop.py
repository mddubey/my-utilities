"""Why don't 'daily 8-EMA ABOVE the entry' trades do better? (user, 2026-10-10: 'price went up to get rejected by the daily 8-EMA and
took my stop on the way'). Spec fixed before running. v1 trades A + B, E1 and E2, where the live daily 8-EMA is above the entry.
Split: the 8-EMA sits INSIDE our risk (between entry and stop) vs ABOVE our stop. Also: after entry (same day), did price go up and
TOUCH the daily 8-EMA (high >= it)? Outcomes for each. Hourly bars. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
touch = {}
for t, g in B.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        k = pd.Timestamp(f"{r.date} 10:15"); rest = h[(h.index > k) & (h.index.normalize() == k.normalize())]
        touch[ix] = bool(len(rest)) and bool((rest.High >= (2 / 9 * rest.Close + 7 / 9 * r.s8)).any())
B["touch8"] = pd.Series(touch)
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]; Y["d8"] = bb.D8.values; Y["stp"] = bb.high.values; Y["ent"] = bb.entry.values; Y["touch8"] = bb.touch8.values
    A = Y[Y.d8 > Y.ent]
    print(f"\n## {en}: trades with the daily 8-EMA ABOVE the entry: {len(A)} of {len(Y)}\n" + H)
    print(row("ALL with 8-EMA above entry", A))
    print(row("8-EMA INSIDE our risk (between entry and stop)", A[A.d8 <= A.stp])); print(row("8-EMA ABOVE our stop", A[A.d8 > A.stp]))
    print(row("  ...price later TOUCHED the daily 8-EMA", A[A.touch8])); print(row("  ...never touched it", A[~A.touch8]))
    S = A[A.o == "stop"]
    print(f"stops in this group: {len(S)}; of them the 8-EMA was ABOVE our stop in {(S.d8 > S.stp).mean()*100:.0f}% | for comparison, all trades in this group: {(A.d8 > A.stp).mean()*100:.0f}%")
