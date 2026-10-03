"""Yahoo native 60-minute bars for the full NSE equity universe -> data/intraday_60m/ (moved 2026-10-03 from
intradaygeeks_replica/11_fetch_1h.py + h1_cache/; the old paths are symlinks). Uses fetch_prices._chunked_download.
See data/README.md for coverage and caveats. Usage: python3 data/fetch_intraday_60m.py <slice_index> <n_slices> [period] [--topup]
--topup: only existing files, merge the last <period> (e.g. 30d) of 60m bars into them."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from fetch_prices import _chunked_download

OUT = ROOT / "data" / "intraday_60m"; OUT.mkdir(exist_ok=True)
k, n = int(sys.argv[1]), int(sys.argv[2])
uni = pd.read_csv(ROOT / "nse_equity_universe.csv").ticker.tolist()
TOPUP = "--topup" in sys.argv
todo = [t for t in uni[k::n] if TOPUP == (OUT / f"{t}.csv").exists()]   # topup: existing files only; else: missing only
if TOPUP:   # 2026-10-03: skip stocks already holding the latest real NSE session (last 60m bar starts 15:15 IST, or 14:15 for F&O names after the closing auction began 2026-08-03)
    from fetch_prices import _latest_nifty_session, _safe_today
    from data.paths import holds_full_session
    session = _latest_nifty_session(pd.Timestamp(_safe_today()))
    if session is not None:
        n0 = len(todo); todo = [t for t in todo if not holds_full_session(OUT / f"{t}.csv", session, "14:15")]
        print(f"latest NSE session {session.date()}: {n0 - len(todo)} already hold it, skipped", flush=True)
print(f"slice {k}/{n}: {len(todo)} to fetch", flush=True)
for i in range(0, len(todo), 50):
    part = todo[i:i + 50]
    dfs = _chunked_download([f"{t}.NS" for t in part], period=sys.argv[3] if len(sys.argv) > 3 else "730d", interval="60m", group_by="ticker")
    for t, d in dfs.items():
        d = d.dropna(subset=["Close"]) if not d.empty else d
        if not d.empty:
            d.index = pd.to_datetime(d.index, utc=True)
            if TOPUP:
                old = pd.read_csv(OUT / f"{t}.csv", index_col=0)
                old.index = pd.to_datetime(old.index, utc=True); d.index = pd.to_datetime(d.index, utc=True)
                d = pd.concat([old, d]); d = d[~d.index.duplicated(keep="last")].sort_index()
            d.to_csv(OUT / f"{t}.csv")
    print(f"  slice {k}: {min(i + 50, len(todo))}/{len(todo)}", flush=True)
print(f"slice {k} done", flush=True)
