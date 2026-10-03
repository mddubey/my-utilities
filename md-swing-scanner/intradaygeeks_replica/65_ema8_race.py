"""User (2026-10-03): the textbook says skip when price is inside the EMAs (price above the 1H 8-EMA), but we have a fixed 1%
target, so the real question is whether the RISING 8-EMA gets into the 1% zone before price does. Spec fixed before running:
FRESH 1H 8-EMA = including the hour that closed at/before the alarm (the trigger itself is unchanged, same population as 62-64).
If price holds at entry the 8-EMA closes 2/9 of the gap per hour, so the gap after h hours = d8 * (7/9)^h. Groups (cut-offs
from that maths, not from results): A 8-EMA above entry | B already in the 1% zone (0-1% below; split 0-0.5 / 0.5-1) |
C enters within 1h (1-1.286%) | D within 2h (1.286-1.653%) | E later (>1.653%). Each split by a big prior fall (3-day
change <= -3%, the cut-off from 63, so that split is NOT pre-declared)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
src = open(HERE / "63_ema8_support_and_recent_fall.py").read().split('if __name__ == "__main__":')[0]
src = src.replace('e8 = hc.ewm(span=8, adjust=False).mean().shift(1)', 'e8 = hc.ewm(span=8, adjust=False).mean().shift(1); e8f = hc.ewm(span=8, adjust=False).mean()')
src = src.replace('E8 = e34.get(hs, np.nan), e8.get(hs, np.nan)', 'E8 = e34.get(hs, np.nan), e8.get(hs, np.nan); E8f = e8f.get(base + ((q + 1) * 30 // 60 - 1) * pd.Timedelta("60min"), np.nan)')
src = src.replace('d8=(qc - E8) / qc * 100,', 'd8=(qc - E8) / qc * 100, d8f=(qc - E8f) / qc * 100, alarm=(base + (q + 1) * pd.Timedelta("30min")).strftime("%H:%M"),')
src = src.replace('E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values', 'E8 = h.Close.ewm(span=8, adjust=False).mean().shift(1).values; E8F = h.Close.ewm(span=8, adjust=False).mean().values')
src = src.replace('d8=(qc - E8[i]) / qc * 100,', 'd8=(qc - E8[i]) / qc * 100, d8f=(qc - E8F[i]) / qc * 100, alarm="",')
src = src.replace('d8f=(qc - E8f)', 'dist=(E - qc) / E * 100, d8f=(qc - E8f)').replace('d8f=(qc - E8F[i])', 'dist=(E - qc) / E * 100, d8f=(qc - E8F[i])')
src = src.replace('alarm="",', 'alarm=(T[i] + pd.Timedelta("60min")).strftime("%H:%M"),')
assert src.count("dist=(E - qc)") == 2
assert src.count("d8f=") == 2 and "E8f = e8f" in src and "E8F =" in src
exec(compile(src, "63mod", "exec"))
CUT = [-np.inf, 0, 0.5, 1, 1 / (7 / 9), 1 / (7 / 9) ** 2, np.inf]
LAB = ["A 8-EMA above entry", "B1 in zone 0-0.5%", "B2 in zone 0.5-1%", "C enters within 1h", "D enters within 2h", "E later than 2h"]
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_")); t1 = sorted(p.stem for p in (HERE / "h1_cache").glob("*.csv"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), [])); B = pd.DataFrame(sum(p.map(gen_b, t1, chunksize=10), []))
    Z = pd.concat([A, B]); Z.to_csv(HERE / "ema8_race.csv", index=False)
