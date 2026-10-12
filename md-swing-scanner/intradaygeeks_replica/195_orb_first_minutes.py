"""Why do quick ORB losers fail? (user, 2026-10-12: 'the ones failing in the first 2-3 minutes -- because of what?'). DESCRIPTIVE, Yahoo
1-min bars (176's cache, 2026-09-12..10-08), in-play trades, paper rules (stop 10% ATR from the trigger fill, 1-min mid rule).
Groups: QUICK LOSERS (stopped within 15 min) / OTHER LOSERS / WINNERS (positive at the close) / BIG WINNERS (>= +3R). For each: stop
size vs a normal 5-min candle of that stock (median 5-min range yesterday), the trigger minute's volume vs the 10 minutes before it,
and the best / worst move in the first 1, 3 and 5 minutes after entry (in R). Results only."""
import sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent))
from data.paths import INTRADAY_5M_DIR
exec(open(HERE / "182_orb_sip_slippage.py").read().split('\nif __name__ == "__main__":')[0])
X = pd.read_csv(HERE / "orb_sip_1m.csv"); X = X[X.traded1m == True]
rows = []
for _, r in X.iterrows():
    m = load_day(r.ticker, r.date); s = int(r.side)
    first = m[m.hm < "09:20"]; rest = m[(m.hm >= "09:20") & (m.hm < "15:15")]
    trig = first.Low.min() if s < 0 else first.High.max(); hit = rest[(rest.Low < trig) if s < 0 else (rest.High > trig)]
    if not len(hit): continue
    i = hit.index[0]; e = min(trig, m.loc[i].Open) if s < 0 else max(trig, m.loc[i].Open); risk = e * 0.1 * r.atr / 100
    after = m[m.index >= i]; prev10 = m[(m.index < i) & (m.index >= i - pd.Timedelta("10min"))]
    rec = dict(side=s, R=r.R10m1mid, out=r.o10m1mid, et=m.loc[i].hm, stop_pct=0.1 * r.atr,
               volx=m.loc[i].Volume / prev10.Volume.mean() if len(prev10) and prev10.Volume.mean() > 0 else np.nan)
    m5 = pd.read_csv(INTRADAY_5M_DIR / f"{r.ticker}.csv", index_col=0, parse_dates=True); m5.index = m5.index.tz_convert("Asia/Kolkata").tz_localize(None)
    yd = m5[m5.index.normalize() < pd.Timestamp(r.date)]; yd = yd[yd.index.normalize() == yd.index.normalize().max()]
    rec["candle5"] = ((yd.High - yd.Low) / yd.Close).median() * 100
    for n in (1, 3, 5):
        w = after.iloc[:n]
        rec[f"mfe{n}"] = (s * ((w.Low.min() if s < 0 else w.High.max()) - e)) / risk
        rec[f"mae{n}"] = (s * ((w.High.max() if s < 0 else w.Low.min()) - e)) / risk
    st = after[(after.High >= e + risk) if s < 0 else (after.Low <= e - risk)]
    rec["mins"] = (st.index[0] - i).total_seconds() / 60 if len(st) else np.nan
    rows.append(rec)
D = pd.DataFrame(rows)
D["grp"] = np.where((D.out == "stop") & (D.mins <= 15), "quick losers (stopped <= 15 min)", np.where(D.R < 0, "other losers", np.where(D.R >= 3, "big winners (>= +3R)", "smaller winners")))
print(f"1-min trades: {len(D)} ({(D.side < 0).sum()} shorts, {(D.side > 0).sum()} longs)")
print("| group | trades | stop size % | normal 5-min candle % (yday median) | stop / candle | break-minute volume vs prev 10 min | best move first 1 / 3 / 5 min (R) | worst move first 1 / 3 / 5 min (R) |\n|---|---|---|---|---|---|---|---|")
for gname in ("quick losers (stopped <= 15 min)", "other losers", "smaller winners", "big winners (>= +3R)"):
    g = D[D.grp == gname]
    print(f"| {gname} | {len(g)} | {g.stop_pct.median():.2f} | {g.candle5.median():.2f} | {(g.stop_pct / g.candle5).median():.2f} | {g.volx.median():.1f}x | "
          f"{g.mfe1.median():+.2f} / {g.mfe3.median():+.2f} / {g.mfe5.median():+.2f} | {g.mae1.median():+.2f} / {g.mae3.median():+.2f} / {g.mae5.median():+.2f} |")
