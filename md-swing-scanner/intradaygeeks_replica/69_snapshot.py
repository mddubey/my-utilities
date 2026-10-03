"""Draw the 1H chart AS IT LOOKED at an alarm time (user, 2026-10-04): finished hourly bars + the hourly bar so far
(half-formed at :45, finished at :15), the 1H 34-EMA / 8-EMA the scan uses (EMA of finished hourly closes), and the
entry / stop / target / 2:1-limit lines, with the candle-rule verdict. Display only.
  python3 69_snapshot.py KNACK 2026-09-30 10:45 [11:15 ...]   text + chart drawn inline in iTerm2 (nothing saved)
  add --save to also write snapshots/KNACK_20260930_1045.png
Checks shown: red, high >= EMA34, close < EMA34 within 0.5%, EMA8 < EMA34, stop <= 0.5% (2:1). The daily checks
(daily 8-EMA, ADX, VWAP, ATR, traded value) are NOT re-checked here -- the scan does those."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import base64, io, os
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent; OUT = HERE / "snapshots"


def hour_key(idx):
    d = idx.normalize(); return d + pd.Timedelta("9h15min") + ((idx - d - pd.Timedelta("9h15min")) // pd.Timedelta("60min")) * pd.Timedelta("60min")


def snapshot(t, day, hhmm):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0, parse_dates=True)
    m.index = m.index.tz_convert("Asia/Kolkata").tz_localize(None)
    asof = pd.Timestamp(f"{day} {hhmm}"); hs = hour_key(pd.DatetimeIndex([asof - pd.Timedelta("1min")]))[0]
    m = m[m.index < asof]
    hk = hour_key(m.index)
    H = m.groupby(hk).agg(O=("Open", "first"), H=("High", "max"), L=("Low", "min"), C=("Close", "last"))
    done = H[H.index < hs]; cur = H.loc[hs]
    e34 = done.C.ewm(span=34, adjust=False).mean(); e8 = done.C.ewm(span=8, adjust=False).mean()
    E, E8 = e34.iloc[-1], e8.iloc[-1]
    entry, stop = cur.C, cur.H; tgt = entry * 0.99; lim = entry * 1.005; risk = (stop - entry) / entry * 100
    half = asof - hs < pd.Timedelta("60min")
    checks = [("red (close < open)", cur.C < cur.O, f"{cur.C:.2f} vs {cur.O:.2f}"),
              ("high touched 1H EMA34", cur.H >= E, f"{cur.H:.2f} vs {E:.2f}"),
              ("closed below 1H EMA34", cur.C < E, f"{cur.C:.2f} vs {E:.2f}"),
              ("close within 0.5% of EMA34", 0 < (E - cur.C) / E * 100 <= 0.5, f"{abs(E - cur.C) / E * 100:.2f}% {'below' if cur.C < E else 'ABOVE'} the EMA"),
              ("1H EMA8 < EMA34", E8 < E, f"{E8:.2f} vs {E:.2f}"),
              ("stop <= 0.5% (2:1)", risk <= 0.5, f"{risk:.2f}% -> {1 / risk if risk > 0 else 0:.2f} : 1" if risk > 0 else "n/a")]
    ok = all(c[1] for c in checks)
    first_fail = next((c for c in checks if not c[1]), None)
    verdict = "SETUP: short at close (daily checks not shown)" if ok else f"NO TRADE: {first_fail[0]} fails ({first_fail[2]})"
    # plot: last ~2.5 sessions of finished bars + current bar
    show = done.tail(16); n = len(show)
    fig, (ax, tx) = plt.subplots(2, 1, figsize=(13, 9), gridspec_kw=dict(height_ratios=[4, 1]))
    for i, (ts, b) in enumerate(show.iterrows()):
        col = "#26a69a" if b.C >= b.O else "#ef5350"
        ax.vlines(i, b.L, b.H, color=col, lw=1.2); ax.add_patch(plt.Rectangle((i - .3, min(b.O, b.C)), .6, max(abs(b.C - b.O), 1e-6), color=col))
    col = "#26a69a" if cur.C >= cur.O else "#ef5350"
    ax.vlines(n, cur.L, cur.H, color=col, lw=1.5, ls="--" if half else "-")
    ax.add_patch(plt.Rectangle((n - .3, min(cur.O, cur.C)), .6, max(abs(cur.C - cur.O), 1e-6), facecolor=col if not half else "none",
                               edgecolor=col, hatch="//" if half else None, lw=1.5))
    xs = list(range(n)) + [n]
    ax.plot(xs, list(e34.tail(n).values) + [E], color="#f9a825", lw=2, label=f"1H EMA34 (used: {E:.2f})")
    ax.plot(xs, list(e8.tail(n).values) + [E8], color="#555", lw=1.5, label=f"1H EMA8 (used: {E8:.2f})")
    for y, c, lab in ((stop, "#c62828", f"stop = bar high {stop:.2f} ({risk:.2f}%)"), (entry, "#1565c0", f"entry = bar close {entry:.2f}"),
                      (tgt, "#2e7d32", f"target -1% {tgt:.2f}"), (lim, "#9e9e9e", f"2:1 limit for stop {lim:.2f}")):
        ax.axhline(y, color=c, ls=":" if c == "#9e9e9e" else "--", lw=1); ax.text(n + .45, y, lab, color=c, va="center", fontsize=9)
    labels = [f"{ts:%d %b %H:%M}" if ts.hour == 9 else f"{ts:%H:%M}" for ts in show.index] + [f"{hs:%H:%M}\n(so far)" if half else f"{hs:%H:%M}"]
    ax.set_xticks(xs); ax.set_xticklabels(labels, fontsize=8, rotation=0)
    ax.set_xlim(-1, n + 4.5)
    lo = min(show.L.min(), tgt) * 0.998; hi = max(show.H.max(), stop) * 1.002; ax.set_ylim(lo, hi)
    state = f"hourly bar {hs:%H:%M}-{hs + pd.Timedelta('60min'):%H:%M} " + (f"HALF-FORMED (as seen at {hhmm})" if half else f"FINISHED (at {hhmm})")
    ax.set_title(f"{t}  {day}  alarm {hhmm} IST  |  {state}\nbar so far: O {cur.O:.2f}  H {cur.H:.2f}  L {cur.L:.2f}  C {cur.C:.2f}", fontsize=11, loc="left")
    txt = "\n".join(f"{'OK  ' if c[1] else 'FAIL'}  {c[0]}: {c[2]}" for c in checks) + f"\n\n{verdict}"
    tx.axis("off"); tx.text(0.0, 1.0, txt, transform=tx.transAxes, fontsize=10, family="monospace", va="top")
    ax.legend(loc="upper left", fontsize=9); ax.grid(alpha=.25)
    fig.tight_layout(); buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110); plt.close(fig); png = buf.getvalue()
    bars = show.tail(5).assign(EMA34=e34.tail(5).values, EMA8=e8.tail(5).values)
    print(f"\n{t}  {day}  alarm {hhmm}  |  {state}")
    print("last finished hourly bars (EMA = value after that bar closed):")
    print(bars.rename(columns={"O": "Open", "H": "High", "L": "Low", "C": "Close"}).round(2).to_string())
    print(f"bar so far {hs:%H:%M}: O {cur.O:.2f} H {cur.H:.2f} L {cur.L:.2f} C {cur.C:.2f} | EMA34 used {E:.2f}, EMA8 used {E8:.2f}")
    print(f"entry {entry:.2f}  stop {stop:.2f} ({risk:.2f}%)  target {tgt:.2f}  2:1 limit for stop {lim:.2f}")
    print(txt)
    if os.environ.get("LC_TERMINAL") == "iTerm2" or os.environ.get("TERM_PROGRAM") == "iTerm.app":
        sys.stdout.write(f"\033]1337;File=inline=1;width=100%;preserveAspectRatio=1:{base64.b64encode(png).decode()}\a\n"); sys.stdout.flush()
    if "--save" in sys.argv:
        OUT.mkdir(exist_ok=True); p = OUT / f"{t}_{day.replace('-', '')}_{hhmm.replace(':', '')}.png"; p.write_bytes(png); print(f"saved {p}")


if __name__ == "__main__":
    t, day, *times = [a for a in sys.argv[1:] if a != "--save"]
    for hhmm in times: snapshot(t, day, hhmm)
