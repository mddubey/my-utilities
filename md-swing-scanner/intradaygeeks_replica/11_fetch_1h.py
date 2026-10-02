"""Fetch ~730 days of Yahoo 60-minute bars for the full NSE EQ universe into this scratch folder
(h1_cache/). Read-only against production: uses fetch_prices._chunked_download, writes nothing outside
this folder. Usage: python3 11_fetch_1h.py <slice_index> <n_slices> [period] [--topup]
--topup: only existing files, merge the last <period> (e.g. 30d) of 60m bars into them."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch_prices import _chunked_download

HERE = Path(__file__).parent
OUT = HERE / "h1_cache"; OUT.mkdir(exist_ok=True)
k, n = int(sys.argv[1]), int(sys.argv[2])
uni = pd.read_csv(HERE.parent / "nse_equity_universe.csv").ticker.tolist()
TOPUP = "--topup" in sys.argv
todo = [t for t in uni[k::n] if TOPUP == (OUT / f"{t}.csv").exists()]   # topup: existing files only; else: missing only
print(f"slice {k}/{n}: {len(todo)} to fetch", flush=True)
for i in range(0, len(todo), 50):
    part = todo[i:i + 50]
    dfs = _chunked_download([f"{t}.NS" for t in part], period=sys.argv[3] if len(sys.argv) > 3 else "730d", interval="60m", group_by="ticker")
    for t, d in dfs.items():
        d = d.dropna(subset=["Close"]) if not d.empty else d
        if not d.empty:
            if TOPUP:
                old = pd.read_csv(OUT / f"{t}.csv", index_col=0)
                old.index = pd.to_datetime(old.index, utc=True); d.index = pd.to_datetime(d.index, utc=True)
                d = pd.concat([old, d]); d = d[~d.index.duplicated(keep="last")].sort_index()
            d.to_csv(OUT / f"{t}.csv")
    print(f"  slice {k}: {min(i + 50, len(todo))}/{len(todo)}", flush=True)
print(f"slice {k} done", flush=True)
