"""Does entering NEAR the daily 34-EMA (on 1H candles) beat waiting for the daily close?
Spec fixed BEFORE running (2026-10-01):

Window: only days covered by Yahoo 60m history (~Oct 2024 - Sep 2026). Daily data from backtest.load().
Day-level filters, all known at the prior close (T-1):
  long : EMA8_{t-1} > EMA34_{t-1}, ADX14_{t-1} > 25, Open_t > EMA34_{t-1} (price comes DOWN into the EMA)
  short: EMA8_{t-1} < EMA34_{t-1}, ADX14_{t-1} > 25, Open_t < EMA34_{t-1}
  touch: some 1H bar today reaches EMA34_{t-1}.
Weekly 8-EMA (last completed week) state is measured AT ENTRY TIME using only lows/highs seen so far:
  touch = week-to-date extreme so far within 0.5% of wEMA8 and entry on the right side of it;
  below/above wrong side = excluded. Results reported for weekly-touch and for touch+untested.
Entries (one position per ticker, first variant to fire is irrelevant: each variant simulated separately):
  V0 DAILY CLOSE (today's method): day closes back across the EMA with a candle in trade direction;
     buy at the daily close, stop = day's low (short: high). Also shown: the heavy subset (stop > 1.5x ADR20).
  V1 LIMIT AT EMA: buy at EMA34_{t-1} on the touch, stop fixed 1% / 2% / 3% beyond the EMA.
     If the touch hour's own range also reaches the stop, it counts as stopped (order inside an hour unknown).
  V2 1H REJECTION: after the touch, buy at the close of the first 1H candle that closes back across the EMA;
     stop = day's extreme so far (the wick is KNOWN at entry). No such hourly close that day = no trade.
Exit (same for all): target = nearest prior swing high above entry (short: swing low below), swings K=3,
  252-day lookback, using ONLY swings already confirmed by t-1 (fixes a 2-day look-ahead in 09/10's target).
  Fixed stop, no trailing. Rest of entry day walked on 1H bars (stop checked before target), later days on
  daily bars (stop first if both touched). Max hold 10 sessions after entry day -> exit at that close.
  Setups with a corp_action_day inside the hold window are dropped. Hours whose day-close disagrees with the
  daily close by >2% (Yahoo split rescaling) are dropped.
Outcome: % return gross of costs, and R = return / initial stop distance.
"""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backtest import load
from market_regime import _compute_adx

HERE = Path(__file__).parent
H1 = HERE / "h1_cache"
K, LOOKBACK, HOLD, ADX_MIN = 3, 252, 10, 25
STOPS = (1.0, 2.0, 3.0)


def swings(h, l, k=K):
    n = len(h); sh = np.zeros(n, bool); sl = np.zeros(n, bool)
    for i in range(k, n - k):
        if h[i] == h[i - k:i + k + 1].max(): sh[i] = True
        if l[i] == l[i - k:i + k + 1].min(): sl[i] = True
    return sh, sl


def find_target(i, entry, s, sh, sl, h, l, causal=True):
    hi = i - 1 - K if causal else i - 1          # swing at j is confirmed only after bar j+K
    for j in range(hi, max(0, i - LOOKBACK), -1):
        if s == 1 and sh[j] and h[j] > entry: return h[j]
        if s == -1 and sl[j] and l[j] < entry: return l[j]
    return None


def walk(s, entry, stop, tgt, bars_today, i, h, l, c):
    """bars_today: remaining 1H bars of entry day (after the fill bar). Returns exit_px, reason, days."""
    def hit(hi, lo):
        adv, fav = (lo, hi) if s == 1 else (hi, lo)
        if (adv <= stop) if s == 1 else (adv >= stop): return stop, "stop"
        if tgt is not None and ((fav >= tgt) if s == 1 else (fav <= tgt)): return tgt, "target"
        return None
    for hi, lo in bars_today:
        r = hit(hi, lo)
        if r: return r[0], r[1], 0
    for d in range(1, HOLD + 1):
        r = hit(h[i + d], l[i + d])
        if r: return r[0], r[1], d
    return c[i + HOLD], "max_hold", HOLD


def load_h1(t):
    p = H1 / f"{t}.csv"
    if not p.exists(): return None
    x = pd.read_csv(p, index_col=0)
    x.index = pd.to_datetime(x.index, utc=True).tz_convert("Asia/Kolkata")
    x = x[(x.Volume > 0) | (x.High != x.Low)]
    x["day"] = x.index.normalize().tz_localize(None)
    return x


def run_ticker(t):
    hb = load_h1(t)
    if hb is None or hb.empty: return []
    try:
        df = load(t).reset_index()
    except FileNotFoundError:
        return []
    if len(df) < LOOKBACK + 40: return []
    o, h, l, c = (df[k].values for k in ("Open", "High", "Low", "Close"))
    e8 = df.Close.ewm(span=8, adjust=False).mean().shift(1).values
    e34 = df.Close.ewm(span=34, adjust=False).mean().shift(1).values
    adx = _compute_adx(df.set_index("Date"))[0].shift(1).values
    adr = ((df.High - df.Low) / df.Close * 100).rolling(20).mean().shift(1).values
    s_ = df.set_index("Date").Close
    we8 = s_.resample("W-FRI").last().dropna().ewm(span=8, adjust=False).mean().shift(1) \
        .reindex(s_.index, method="ffill").values
    wk = df.Date.dt.to_period("W-FRI")
    wlo_prev = df.groupby(wk).Low.cummin().groupby(wk).shift(1).values   # week-to-date low BEFORE today
    whi_prev = df.groupby(wk).High.cummax().groupby(wk).shift(1).values
    ca = df.corp_action_day.fillna(False).values.astype(bool)
    sh, sl = swings(h, l)
    groups = {d: g for d, g in hb.groupby("day")}
    first_h1 = hb.day.min()
    rows = []
    busy = {}
    for i in range(LOOKBACK, len(df) - HOLD - 1):
        dt = df.Date.iloc[i]
        if dt < first_h1 or np.isnan(e34[i]) or np.isnan(adx[i]) or np.isnan(we8[i]) or adx[i] <= ADX_MIN:
            continue
        if e8[i] > e34[i] and o[i] > e34[i] and l[i] <= e34[i]: s = 1
        elif e8[i] < e34[i] and o[i] < e34[i] and h[i] >= e34[i]: s = -1
        else: continue
        if ca[i:i + HOLD + 1].any(): continue
        g = groups.get(dt)
        if g is None or abs(g.Close.iloc[-1] / c[i] - 1) > 0.02: continue
        H, L, C = g.High.values, g.Low.values, g.Close.values
        tb = np.argmax(L <= e34[i]) if s == 1 else np.argmax(H >= e34[i])
        if not ((L[tb] <= e34[i]) if s == 1 else (H[tb] >= e34[i])): continue   # 1H never reaches it
        ema = e34[i]
        base = dict(ticker=t, date=dt, side="long" if s == 1 else "short", adx=adx[i], adr=adr[i])

        def wstate(price, ext_so_far):
            if s == 1:
                if price < we8[i]: return "wrong"
                w = min(ext_so_far, wlo_prev[i]) if not np.isnan(wlo_prev[i]) else ext_so_far
                return "touch" if w <= we8[i] * 1.005 else "untested"
            if price > we8[i]: return "wrong"
            w = max(ext_so_far, whi_prev[i]) if not np.isnan(whi_prev[i]) else ext_so_far
            return "touch" if w >= we8[i] * 0.995 else "untested"

        def record(var, entry, stop, rest, ws, extra=None):
            if busy.get(var, -1) >= i: return
            risk = (entry - stop) * s
            if risk <= 0: return
            for causal in (True, False) if var == "V0" else (True,):
                tgt = find_target(i, entry, s, sh, sl, h, l, causal)
                px, why, d = walk(s, entry, stop, tgt, rest, i, h, l, c)
                ret = (px - entry) / entry * 100 * s
                rows.append({**base, "variant": var if causal else "V0_leaky_target", "weekly": ws,
                             "entry": entry, "stop_pct": risk / entry * 100, "exit": why, "days": d,
                             "ret_pct": ret, "R": ret / (risk / entry * 100), "has_target": tgt is not None,
                             **(extra or {})})
                if causal: busy[var] = i + d

        # V0: daily-close confirmation
        if (s == 1 and c[i] > ema and c[i] > o[i]) or (s == -1 and c[i] < ema and c[i] < o[i]):
            stop = l[i] if s == 1 else h[i]
            heavy = abs(c[i] - stop) / c[i] * 100 > 1.5 * adr[i]
            record("V0", c[i], stop, [], wstate(c[i], l[i] if s == 1 else h[i]), {"heavy": heavy})
        # V1: limit at the EMA, fixed stop
        ext_tb = L[:tb + 1].min() if s == 1 else H[:tb + 1].max()
        for sp in STOPS:
            stop = ema * (1 - s * sp / 100)
            ws = wstate(ema, ema if s == 1 else ema)
            if (L[tb] <= stop) if s == 1 else (H[tb] >= stop):   # touch hour also reached the stop
                if busy.get(f"V1_{sp:g}", -1) < i:
                    rows.append({**base, "variant": f"V1_{sp:g}", "weekly": ws, "entry": ema, "stop_pct": sp,
                                 "exit": "stop_same_hour", "days": 0, "ret_pct": -sp, "R": -1.0, "has_target": True})
                    busy[f"V1_{sp:g}"] = i
                continue
            record(f"V1_{sp:g}", ema, stop, list(zip(H[tb + 1:], L[tb + 1:])), ws)
        # V2: first hourly close back across the EMA at/after the touch hour
        for b in range(tb, len(C)):
            if (s == 1 and C[b] > ema) or (s == -1 and C[b] < ema):
                stop = L[:b + 1].min() if s == 1 else H[:b + 1].max()
                record("V2", C[b], stop, list(zip(H[b + 1:], L[b + 1:])), wstate(C[b], stop),
                       {"entry_hour": g.index[b].strftime("%H:%M"), "above_ema_pct": (C[b] / ema - 1) * 100 * s})
                break
    return rows


if __name__ == "__main__":
    from multiprocessing import Pool
    tickers = sorted(p.stem for p in H1.glob("*.csv"))
    out = []
    with Pool(6) as pool:
        for k, r in enumerate(pool.imap_unordered(run_ticker, tickers, chunksize=8), 1):
            out.extend(r)
            if k % 200 == 0: print(f"  {k}/{len(tickers)} tickers", flush=True)
    res = pd.DataFrame(out)
    res.to_csv(HERE / "ema34_entry_1h_results.csv", index=False)
    print(f"rows {len(res)} from {len(tickers)} tickers", flush=True)
