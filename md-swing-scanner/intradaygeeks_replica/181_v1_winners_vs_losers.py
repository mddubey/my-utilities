"""What separates v1's winners from losers? (user, 2026-10-11.) DESCRIPTIVE scan, not a filter test. v1 without the Nifty filter (= 164,
178's variables), E1 and E2, above / below Nifty's 200-day. For each feature: median for targets vs stops and AUC = P(a target's value >
a stop's value) (0.5 = no separation), with a label-shuffle p-value (2,000 shuffles). Features known at entry + ONE after-entry
descriptor (Nifty's move 11:15 -> 15:15, close of the 14:15 hourly bar) to see whether winners are just market-down afternoons.
Any lead found here needs its own declared test. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
HERE = Path(__file__).resolve().parent
exec(open(HERE / "178_v1_what_is_200d.py").read().split("\ndef r(")[0])
import numpy as np
rng = np.random.default_rng(1)
n1515 = h[h.index.strftime("%H:%M") == "14:15"].Close; n1515.index = n1515.index.normalize()
V["NIFTY_AFTER"] = [(n1515.get(x, np.nan) / n1115.get(x, np.nan) - 1) * 100 for x in dt]
for c in ("dist", "stop", "liq_prev", "adx", "e34_6h", "ema34", "entry", "prev_open", "prev_close", "prev_high", "high", "low", "dayopen", "s8", "s34", "gap"):
    V["_" + c] = V.ix.map(B[c])
V["ema34_slope_6h"] = (V._ema34 / V._e34_6h - 1) * 100
V["daily8_over_34"] = (V._s8 / V._s34 - 1) * 100
V["prev_day_red"] = (V._prev_close < V._prev_open).astype(float)
V["entry_vs_prev_high"] = (V._entry / V._prev_high - 1) * 100
V["day_move_to_entry"] = (V._entry / V._dayopen - 1) * 100
V["candle_range"] = (V._high / V._low - 1) * 100
F = {"gap": "_gap", "ATR %": "atrp", "stop %": "_stop", "entry below 1H EMA34 %": "_dist", "open vs 1H EMA34 %": "ov", "candle body share": "bodyp",
     "candle range %": "candle_range", "1H EMA34 slope 6h %": "ema34_slope_6h", "daily 8 over 34 %": "daily8_over_34", "daily8 - EMA34 gap %": "dd",
     "ADX": "_adx", "liquidity (prev day)": "_liq_prev", "prev day red": "prev_day_red", "entry vs prev day high %": "entry_vs_prev_high",
     "move from day open to entry %": "day_move_to_entry", "India VIX": "V1", "Nifty ATR %": "V2", "Nifty follow-through": "V3",
     "Nifty 09:15 -> 11:15 %": "V4", "stock 20d vs Nifty %": "V5", "stock ATR5/ATR20": "V6", "Nifty vs 200d %": "V7",
     "AFTER ENTRY: Nifty 11:15 -> 15:15 %": "NIFTY_AFTER"}


def auc(a, b):
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 5 or len(b) < 5: return np.nan, np.nan
    allv = np.r_[a, b]; rk = pd.Series(allv).rank().values; u = rk[:len(a)].sum() - len(a) * (len(a) + 1) / 2; A = u / (len(a) * len(b))
    cnt = 0
    for _ in range(2000):
        p = rng.permutation(allv); r2 = pd.Series(p).rank().values; u2 = r2[:len(a)].sum() - len(a) * (len(a) + 1) / 2
        cnt += abs(u2 / (len(a) * len(b)) - 0.5) >= abs(A - 0.5)
    return A, cnt / 2000


for en in EX:
    X = V[V.ex == en]
    print(f"\n## {en} -- targets vs stops (AUC > 0.5 = targets have the HIGHER value; p = shuffle test)")
    print("| feature | ABOVE: target median | stop median | AUC | p | BELOW: target median | stop median | AUC | p |\n|---|---|---|---|---|---|---|---|---|")
    rows = []
    for nm, c in F.items():
        cells = []
        for reg in (True, False):
            G = X[X.n200 == reg]; t = G[G.o == "target"][c].astype(float).values; s = G[G.o == "stop"][c].astype(float).values
            A, p = auc(t, s); cells += [np.nanmedian(t), np.nanmedian(s), A, p]
        rows.append((nm, cells))
    for nm, c in sorted(rows, key=lambda r: -max(abs((r[1][2] if r[1][2] == r[1][2] else .5) - .5), abs((r[1][6] if r[1][6] == r[1][6] else .5) - .5))):
        print(f"| {nm} | {c[0]:.2f} | {c[1]:.2f} | {c[2]:.2f} | {c[3]:.3f} | {c[4]:.2f} | {c[5]:.2f} | {c[6]:.2f} | {c[7]:.3f} |")
    print(f"targets / stops: above {(X[X.n200 == True].o == 'target').sum()} / {(X[X.n200 == True].o == 'stop').sum()}, below {(X[X.n200 == False].o == 'target').sum()} / {(X[X.n200 == False].o == 'stop').sum()}")
