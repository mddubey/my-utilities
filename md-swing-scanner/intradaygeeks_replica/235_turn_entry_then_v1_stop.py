"""TURN ENTRY, THEN v1's STOP ONCE THE CANDLE IS KNOWN (user, 2026-10-17: 'start with 0.5% but after the first candle is formed we know
the exact stop'; 'the v1's candle ... that rejection is ideally what we are entering late'). Spec fixed before running:
  Trades: 233's FAIR group unchanged (891 entries: v1 stock-days, daily 8 not in the path, sold 0.1% below the touch high).
  The v1 candle = the 09:15-aligned hourly candle holding the entry. Line = the 1H EMA34 fixed for that hour.
  A  0.5% stop all day (233).
  B  0.5% until the hour closes, then stop = min(0.5% stop, that hour's high + 0.05%) -- tighten only (FIX: the hour high can come BEFORE
     the entry, when price broke down through the line earlier in the hour and came back up to it; the first run widened those).
  C  B, and exit at the hour close if the candle closed back ABOVE the line.
  D  0.5% all day, exit at the hour close if the candle closed above the line.
  E  (user's logic) at the hour close KEEP only if the candle is a v1 rejection (red, close below the line) with stop = hour high + 0.05%;
     otherwise exit at the hour close.
  F  (user's ACTUAL rule, 2026-10-17 clarification) 0.5% stop; at the hour close, IF the candle is a confirmed v1 rejection (red, close
     below the line) AND its high + 0.05% is below the 0.5% stop -> trail the stop to that high; otherwise keep 0.5% and stay in (no exit).
  1% target, else out at the 15:15 close; stop first on a tie. Net Rs per Rs1 lakh / per Rs1k risk (initial 0.5%), target / stall / stop /
  hour-close exit, by month, top-10 days removed, by entry hour. Hand check KALYANKJIL 2026-10-16 (raw event, no day filters)."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
from data.paths import INTRADAY_60M_DIR
COST = 0.085; TICK = 0.0005


def run(args):
    t, g = args
    m = read5_official(t); md = m.index.normalize()
    h = pd.read_csv(INTRADAY_60M_DIR / f"{t}.csv", index_col=0)
    h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None); h = h[~h.index.duplicated()].sort_index().dropna(subset=["Close"])
    e34 = h.Close.ewm(span=34, adjust=False).mean(); out = []
    for _, r in g.iterrows():
        x = m[md == pd.Timestamp(r.date)]; ts = x.index; hm = ts.strftime("%H:%M").values
        O, H, L, C = x.Open.values, x.High.values, x.Low.values, x.Close.values
        j = np.where(hm == r.t_entry)[0]; lasts = np.where(hm <= "15:10")[0]
        if not len(j) or not len(lasts): continue
        j, last = j[0], lasts[-1]; e = r.entry; tg = e * 0.99
        hs = ts[j].floor("60min") + pd.Timedelta("15min")
        if hs > ts[j]: hs -= pd.Timedelta("60min")
        hb = np.where((ts >= hs) & (ts < hs + pd.Timedelta("60min")))[0]; he = hb[-1]
        prev = e34[e34.index <= hs - pd.Timedelta("60min")]
        if not len(prev): continue
        line = prev.iloc[-1]; hh = H[hb].max(); ho, hc = O[hb[0]], C[he]
        rejection = (hc < ho) and (hc < line); closed_above = hc >= line
        rec = dict(ticker=t, date=r.date, t_entry=r.t_entry, entry=e, hour=hs.strftime("%H:%M"), line=line, hour_high=hh, hour_close=hc,
                   rejection=rejection, closed_above=closed_above)

        def go(tighten, exit_rule):
            s = e * 1.005
            for k in range(j + 1, last + 1):
                if H[k] >= s: return (e - s) / e * 100, "stop"
                if L[k] <= tg: return 1.0, "target"
                if k == he:
                    if exit_rule == "above" and closed_above: return (e - C[k]) / e * 100, "hour exit"
                    if exit_rule == "not_rej" and not rejection: return (e - C[k]) / e * 100, "hour exit"
                    if tighten == "if_rej":
                        if rejection: s = min(s, hh * (1 + TICK))
                    elif tighten: s = min(s, hh * (1 + TICK))   # FIX 2026-10-17: the hour high can sit BEFORE the entry (above 0.5%) -> never widen
            if j >= he:   # entry in the hour's last bar: the hour-close decision happens at the entry bar's close
                pass
            return (e - C[last]) / e * 100, "stall"
        if j == he:   # hour already closed at the entry bar: apply the decision before walking
            for nm, tight, ex in (("A", False, None), ("B", True, None), ("C", True, "above"), ("D", False, "above"), ("E", True, "not_rej"), ("F", "if_rej", None)):
                if (ex == "above" and closed_above) or (ex == "not_rej" and not rejection): rec[f"{nm}_ret"], rec[f"{nm}_why"] = (e - C[j]) / e * 100, "hour exit"; continue
                s = min(e * 1.005, hh * (1 + TICK)) if (tight is True or (tight == "if_rej" and rejection)) else e * 1.005; res = None
                for k in range(j + 1, last + 1):
                    if H[k] >= s: res = ((e - s) / e * 100, "stop"); break
                    if L[k] <= tg: res = (1.0, "target"); break
                rec[f"{nm}_ret"], rec[f"{nm}_why"] = res or ((e - C[last]) / e * 100, "stall")
        else:
            for nm, tight, ex in (("A", False, None), ("B", True, None), ("C", True, "above"), ("D", False, "above"), ("E", True, "not_rej"), ("F", "if_rej", None)):
                rec[f"{nm}_ret"], rec[f"{nm}_why"] = go(tight, ex)
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    A = pd.read_csv(HERE / "v1_turn_entry.csv")
    F = A[(A.liq >= 15) & (A.pc >= 100) & (A.atr >= 2) & (A.gap > -0.25) & (A.gap <= 0.5) & (A.X == 0.001)]
    V = F[F.up & (((F.ov >= -0.5) & (F.ov < 0)) | ((F.ov >= 0) & (F.atr >= 3))) & ~F.in_path]
    with Pool(6) as p: R = pd.DataFrame([r for rr in p.map(run, list(V.groupby("ticker")), chunksize=5) for r in rr])
    R.to_csv(HERE / "turn_entry_then_v1_stop.csv", index=False)
    print(f"trades {len(R)} of {len(V)}; hour closed as a v1 rejection {R.rejection.mean()*100:.0f}%, closed back above the line {R.closed_above.mean()*100:.0f}%; "
          f"median hour-high stop after tightening {((R.hour_high * 1.0005 / R.entry - 1) * 100).median():.2f}%")
    NM = {"A": "A 0.5% all day", "B": "B tighten to the hour high", "C": "C tighten + exit if closed above the line", "D": "D 0.5% + exit if closed above",
          "E": "E keep only a v1 rejection (hour-high stop), else exit", "F": "F (user) trail to the hour high only if it confirmed, else keep 0.5%"}
    top10 = R.groupby("date").A_ret.sum().nlargest(10).index

    def cell(x, v):
        w = x[f"{v}_why"]; r = x[f"{v}_ret"]
        return (f"{len(x)} | {(w=='target').mean()*100:.0f} / {(w=='stall').mean()*100:.0f} / {(w=='stop').mean()*100:.0f} / {(w=='hour exit').mean()*100:.0f}% | "
                f"{(r.mean()-COST)*1000:+.0f} | {((r-COST)/0.5).mean()*1000:+.0f}")
    print("\n| version | n | target / stall / stop / hour-close exit | net Rs @1L | Rs @1k (0.5% initial risk) | top-10 days removed | months 06 / 07 / 08 / 09 / 10 |\n|---|---|---|---|---|---|---|")
    for v, lab in NM.items():
        mo = " / ".join(f"{(g[f'{v}_ret'].mean()-COST)*1000:+.0f}" for _, g in R.groupby(R.date.str[:7]))
        print(f"| {lab} | {cell(R, v)} | {(R[~R.date.isin(top10)][f'{v}_ret'].mean()-COST)*1000:+.0f} | {mo} |")
    print("\n### By entry hour, net Rs @1L: A / B / C / D / E / F\n| hour | n | A | B | C | D | E | F |\n|---|---|---|---|---|---|---|---|")
    for hr, g in R.groupby("hour"): print(f"| {hr} | {len(g)} | " + " | ".join(f"{(g[f'{v}_ret'].mean()-COST)*1000:+.0f}" for v in NM) + " |")
    print("\n### Split by how the hour closed (known at the hour close), net Rs @1L: A / E / F\n| hour closed as | n | A | E | F |\n|---|---|---|---|---|")
    for lab, g in (("v1 rejection (red, under the line)", R[R.rejection]), ("not a rejection, under the line", R[~R.rejection & ~R.closed_above]), ("back above the line", R[R.closed_above])):
        print(f"| {lab} | {len(g)} | {(g.A_ret.mean()-COST)*1000:+.0f} | {(g.E_ret.mean()-COST)*1000:+.0f} | {(g.F_ret.mean()-COST)*1000:+.0f} |")
    k = A[(A.ticker == "KALYANKJIL") & (A.date == "2026-10-16") & (A.X == 0.001)]
    hc = pd.DataFrame(run(("KALYANKJIL", k)))
    print("\nHAND CHECK KALYANKJIL 2026-10-16 (raw event):"); print(hc.round(2).T.to_string() if len(hc) else "  none")
