"""Daily 8-EMA + another level at the same place = instant support? (user, 2026-10-10). Spec fixed before running. v1 trades (A + B,
E1 and E2). Among trades whose live daily 8-EMA sits 0-1% below the entry (right under 0-0.3% / in the path 0.3-1%): CONFLUENCE =
at least one other level within 0.2% of the daily 8-EMA's price (1H EMA8, daily PP, S1, S2, previous day low) vs ALONE. Also which
partner level. Results only."""
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
exec(open(Path(__file__).resolve().parent / "157_support_cluster.py").read().split('print(f"v1 trades')[0])
OTH = {"1H EMA8": "H8", "PP": "PP", "S1": "S1", "S2": "S2", "PDL": "PDL"}
H = "| group | setups | days | target % (avg Rs) | stall % (avg Rs) | stop % (avg Rs) | Rs/trade @1L | @1k risk | @1L 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|---|---|"
for en in EX:
    Y = X0[(X0.ex == en) & (((X0.ov >= -0.5) & (X0.ov < 0)) | ((X0.ov >= 0) & (X0.atrp >= 3)))].copy()
    bb = B.loc[Y.ix]; gap = ((bb.entry - bb.D8) / bb.entry * 100).values
    Y["zone"] = np.where((gap >= 0) & (gap < 0.3), "under", np.where((gap >= 0.3) & (gap < 1.0), "path", "other"))
    near = {k: (abs(bb[c].values - bb.D8.values) / bb.D8.values * 100 <= 0.2) for k, c in OTH.items()}
    Y["conf"] = np.any(np.vstack(list(near.values())), axis=0)
    for k in OTH: Y["n_" + k] = near[k]
    print(f"\n## {en}\n" + H)
    for z, zn in (("under", "daily 8-EMA RIGHT UNDER (0-0.3%)"), ("path", "daily 8-EMA IN THE PATH (0.3-1%)")):
        Z = Y[Y.zone == z]
        print(row(f"{zn}, ALONE", Z[~Z.conf])); print(row(f"{zn}, + CONFLUENCE", Z[Z.conf]))
        for k in OTH:
            if Z["n_" + k].sum() >= 20: print(row(f"   ... with {k} at the same place", Z[Z["n_" + k]]))
    print(row("(reference) daily 8-EMA not 0-1% below", Y[Y.zone == "other"]))
