"""End-of-day review: what did EVERY setup of the day do -- the plan's pick, the ENTERs not taken, and everything the rules
skipped (EMA8 zone, chased / 2:1 gone at look time, dead, strong-green-hour skip, stop > 0.5%)? Continuous-improvement
log for the intraday shorts (user, 2026-10-04).

Run after the close, once eod_checklist.sh has refreshed the 5-min cache:
    python3 89_eod_review.py              # the last session in the 5-min cache
    python3 89_eod_review.py 2026-10-05   # a given day
    python3 89_eod_review.py --summary    # only the running summary by category

How: replays the live scan (38, --rr 0 so stops > 0.5% are kept and labelled) at the plan's look times -- 10:50 (the
10:45 candle, standup over), 11:16, 11:46 and 12:16 (12:15 is not traded, logged for learning) -- then walks every setup
on the 5-min cache: entry at the candle close, stop = candle high, target = entry - 1%, out 5 h after entry or at 15:15.
For the 10:45 candle it also walks the entry at the 10:50 look price (what plan B actually trades).
Appends to eod_review_log.csv (one row per setup per alarm; re-running a day replaces that day's rows)."""
import subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from data.paths import INTRADAY_5M_DIR
HERE = Path(__file__).resolve().parent
LOG = HERE / "eod_review_log.csv"
COST = 0.085                                   # ~Rs85 per Rs1 lakh MIS round trip (estimate until contract notes)
LOOKS = ["10:50", "11:16", "11:46", "12:16"]


def read5(t):
    m = pd.read_csv(INTRADAY_5M_DIR / f"{t}.csv", index_col=0)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    return m


def walk(m, day, t_from, px, stop):
    """outcome of a short from px at t_from: stop / target (-1%) / stall (5 h or 15:15)"""
    b = m[(m.index >= t_from) & (m.index.normalize() == day) & (m.index < day + pd.Timedelta("15h15min"))]
    if b.empty or px >= stop: return "stop", -(stop - px) / px * 100 if px < stop else 0.0, ""
    for ts, r in b.iterrows():
        if r.High >= stop: return "stop", -(stop - px) / px * 100, f"{ts + pd.Timedelta('5min'):%H:%M}"
        if r.Low <= px * 0.99: return "target", 1.0, f"{ts + pd.Timedelta('5min'):%H:%M}"
        if ts + pd.Timedelta("5min") >= t_from + pd.Timedelta("5h"): return "stall", (px - r.Close) / px * 100, f"{ts + pd.Timedelta('5min'):%H:%M}"
    return "stall", (px - b.Close.iloc[-1]) / px * 100, "15:15"


def category(r):
    s = str(r.status)
    if s.startswith("INFO (opening rejection"): return "info: opening rejection" if r.stop_pct <= 0.5 else "info: opening rejection, stop > 0.5%"
    if s.startswith("INFO (green"): return "info: green candle" if r.stop_pct <= 0.5 else "info: green candle, stop > 0.5%"
    if r.stop_pct > 0.5: return "skip: stop > 0.5% (2:1 rule)"
    if s.startswith("SKIP (strong green"): return "skip: strong green hour"
    if s.startswith("SKIP (EMA8"): return "skip: EMA8 0.4-0.6% zone"
    if s.startswith("SKIP (2:1 gone"): return "skip: chased (2:1 gone at look)"
    if s.startswith("DEAD"): return "dead at look time"
    return "ENTER"


def summary():
    if not LOG.exists(): print("no review log yet"); return
    L = pd.read_csv(LOG)
    print(f"\n=== running summary: {L.date.nunique()} day(s), {len(L)} setups (outcome from the candle close; Rs per Rs 1 lakh) ===")
    rows = []
    for k, g in L.groupby("category"):
        rows.append([k, len(g), f"{(g.outcome == 'target').mean()*100:.0f}", f"{(g.outcome == 'stall').mean()*100:.0f}",
                     f"{(g.outcome == 'stop').mean()*100:.0f}", f"{g.ret.mean()*1000:+.0f}", f"{(g.ret.mean() - COST)*1000:+.0f}"])
    print(pd.DataFrame(rows, columns=["category", "n", "target%", "stall%", "stop%", "Rs gross", "Rs net"]).to_string(index=False))
    # 2026-10-08 (user): clear path vs a support / pivot between entry and the 1% target (scan column in_path, telemetry)
    if "in_path" in L and L.in_path.notna().any():
        p = L[L.in_path.notna() & (L.in_path != "?")]
        rows = []
        for k, g in p.groupby(p.in_path == "-"):
            rows.append(["clear path" if k else "level in the way", len(g), f"{(g.outcome == 'target').mean()*100:.0f}",
                         f"{(g.outcome == 'stall').mean()*100:.0f}", f"{(g.outcome == 'stop').mean()*100:.0f}",
                         f"{g.ret.mean()*1000:+.0f}", f"{(g.ret.mean() - COST)*1000:+.0f}"])
        print("by path (all categories):")
        print(pd.DataFrame(rows, columns=["path", "n", "target%", "stall%", "stop%", "Rs gross", "Rs net"]).to_string(index=False))
    def _split(title, frame, key, names):
        rows = [[names[k], len(g), f"{(g.outcome == 'target').mean()*100:.0f}", f"{(g.outcome == 'stall').mean()*100:.0f}",
                 f"{(g.outcome == 'stop').mean()*100:.0f}", f"{g.ret.mean()*1000:+.0f}", f"{(g.ret.mean() - COST)*1000:+.0f}"]
                for k, g in frame.groupby(key)]
        if rows: print(title); print(pd.DataFrame(rows, columns=["group", "n", "target%", "stall%", "stop%", "Rs gross", "Rs net"]).to_string(index=False))
    # EMA8-direction split removed 2026-10-08 (user; script 75 closed it); ema8_falling still in the log
    # THIN split removed 2026-10-08 (user: nothing actionable); liq_L / warn still in the log
    pk = L[L.plan_pick == True]
    if len(pk):
        r = pk.ret_plan.fillna(pk.ret)
        print(f"plan picks: {len(pk)} | target {(pk.outcome_plan.fillna(pk.outcome) == 'target').mean()*100:.0f}% | Rs gross {r.mean()*1000:+.0f} net {(r.mean() - COST)*1000:+.0f}")


if __name__ == "__main__":
    if "--summary" in sys.argv: summary(); sys.exit()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    day = pd.Timestamp(args[0]) if args else read5("RELIANCE").index.max().normalize()
    D = f"{day:%Y-%m-%d}"
    print(f"EOD review {D}: replaying the scan at {', '.join(LOOKS)} (this takes ~1 min)...", flush=True)
    frames = []; nears = []
    for lk in LOOKS:
        subprocess.run([sys.executable, str(HERE / "38_alarm_scan_1h_close.py"), "--replay", D, lk, "--rr", "0"],
                       cwd=HERE, capture_output=True, text=True)
        f = HERE / "replays" / f"alarm_scan_30m_{day:%Y%m%d}_{lk.replace(':', '')}.csv"
        if f.exists() and f.stat().st_size > 5:
            x = pd.read_csv(f)
            if len(x): frames.append(x.assign(look=lk))
        fn = f.with_name("near_" + f.name)
        if fn.exists() and fn.stat().st_size > 5:
            y = pd.read_csv(fn)
            if len(y): nears.append(y.assign(look=lk))
    if not frames and not nears:
        print("no setups at any alarm today"); summary(); sys.exit()
    R = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["ticker", "cend", "status", "stop_pct"])
    R["alarm"] = R.cend
    R = R.drop_duplicates(["ticker", "alarm"])                 # one row per setup per alarm
    R["category"] = R.apply(category, axis=1) if len(R) else []
    # 2026-10-08 (user): NEAR MISSES -- failed exactly one check (not colour), stop <= 0.5% only (tradeable under 2:1).
    # Entry = candle close, stop = candle high, same walk. category "near: <check>"; ema8_falling kept for the
    # rolling-over question (HINDCOPPER 10-08: trend miss, EMA8 0.28% above EMA34 and falling 8h, hit target).
    if nears:
        N = pd.concat(nears, ignore_index=True).drop_duplicates(["ticker", "cend"])
        N = N[N.stop_pct <= 0.5].rename(columns={"close": "entry", "high": "stop"})
        N["alarm"] = N.cend; N["status"] = "NEAR (" + N.colour + ")"; N["category"] = "near: " + N.missed
        N["now"] = N.entry; N["ema8_below_pct"] = np.nan
        R = pd.concat([R, N], ignore_index=True)
    cache = {}
    out = []
    for _, r in R.iterrows():
        if r.ticker not in cache: cache[r.ticker] = read5(r.ticker)
        m = cache[r.ticker]
        cend = day + pd.Timedelta(hours=int(r.alarm[:2]), minutes=int(r.alarm[3:]))
        o, ret, at = walk(m, day, cend, r.entry, r.stop)
        rec = dict(date=D, alarm=r.alarm, ticker=r.ticker, category=r.category, status=r.status, entry=r.entry, stop=r.stop,
                   stop_pct=r.stop_pct, ema8_below_pct=r.get("ema8_below_pct", np.nan), below_ema_pct=r.below_ema_pct,
                   outcome=o, ret=round(ret, 3), exit_at=at, look_price=r.now,
                   in_path=r.get("in_path", np.nan), liq_L=r.get("liq_L", np.nan), warn=r.get("warn", np.nan),
                   colour=r.get("colour", np.nan), ema8_vs_ema34_pct=r.get("ema8_vs_ema34_pct", np.nan),
                   ema8_falling=r.get("ema8_falling", np.nan))
        if r.alarm == "10:45" and r.category == "ENTER":      # plan B trades the 10:45 candle at the look price
            o2, ret2, at2 = walk(m, day, day + pd.Timedelta("10h50min"), r.now, r.stop)
            rec.update(outcome_plan=o2, ret_plan=round(ret2, 3))
        out.append(rec)
    T = pd.DataFrame(out)
    # plan B's one trade: first alarm (10:45 -> 11:15 -> 11:45) with an ENTER, closest to the EMA (the scan's FIRST COME order)
    T["plan_pick"] = False
    for al in ("10:45", "11:15", "11:45"):
        c = T[(T.alarm == al) & (T.category == "ENTER")].sort_values("below_ema_pct")
        if len(c): T.loc[c.index[0], "plan_pick"] = True; break
    show = T.assign(Rs=(T.ret * 1000).round(0).astype(int)).sort_values(["alarm", "category"])
    print(show[["alarm", "ticker", "category", "plan_pick", "entry", "stop", "stop_pct", "ema8_below_pct", "in_path", "outcome", "exit_at", "Rs"]].to_string(index=False))
    pk = T[T.plan_pick]
    if len(pk):
        r = pk.iloc[0]; rp = r.get("ret_plan", np.nan)
        print(f"\nPLAN B pick: {r.ticker} ({r.alarm}) -> {r.get('outcome_plan', r.outcome) if pd.notna(rp) else r.outcome}, "
              f"Rs {(rp if pd.notna(rp) else r.ret)*1000:+.0f} gross")
    else:
        print("\nPLAN B: no tradeable setup today")
    live = HERE / "live_watch_log.csv"
    if live.exists():
        lw = pd.read_csv(live); lw = lw[lw.date == D]
        if len(lw): print("your logged trades today:\n" + lw[["ticker", "user_entry", "exit", "exit_reason", "gross_pct"]].to_string(index=False))
    old = pd.read_csv(LOG) if LOG.exists() else pd.DataFrame()
    if len(old): old = old[old.date != D]
    pd.concat([old, T], ignore_index=True).to_csv(LOG, index=False)
    print(f"logged {len(T)} setups to {LOG.name}")
    summary()
