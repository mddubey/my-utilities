"""Standard candle definitions on the rejection candle (user, 2026-10-08: "don't go by my definition, read, then test";
1H 3-year set only -- the 30m set is ~4 months of a falling market). Results only. Spec fixed before running, definitions
from the literature (Nison doji / spinning top; bearish pin bar; Brooks bear signal bar; close location value):
  Population: double_rejection_cap1e9.csv set b (current rules, no trend filter; candles are red by rule), OHLC from h1_cache.
  Classes (first match wins): doji body < 5% of range | spinning top body 5-20% and BOTH wicks > body |
  bearish pin bar upper wick >= 2x body and lower wick <= 0.5x body | Brooks bear signal bar close in bottom third
  (CLV <= 0.33) and upper tail 1/3-1/2 of range | other. Separately: CLV terciles (seller pressure).
  Crossed with today's trend rule (EMA8 < EMA34) vs EMA8 above; n, target / stop %, Rs net, by year."""
import numpy as np, pandas as pd
from pathlib import Path
HERE = Path(__file__).resolve().parent
z = pd.read_csv(HERE / "double_rejection_cap1e9.csv"); z = z[z.set == "b"].copy()
O, L = {}, {}
for t, g in z.groupby("ticker"):
    h = pd.read_csv(HERE / "h1_cache" / f"{t}.csv", index_col=0); h.index = pd.to_datetime(h.index, utc=True).tz_convert("Asia/Kolkata").tz_localize(None)
    for ix, r in g.iterrows():
        t0 = pd.Timestamp(r.date) + pd.Timedelta(hours=int(r.alarm), minutes=15)
        if t0 in h.index: O[ix], L[ix] = h.at[t0, "Open"], h.at[t0, "Low"]
z["O"], z["L"] = pd.Series(O), pd.Series(L); z = z.dropna(subset=["O", "L"])
rg = (z.qh - z.L).replace(0, np.nan); body = (z.O - z.qc).abs(); up = z.qh - z[["O", "qc"]].max(axis=1); lo = z[["O", "qc"]].min(axis=1) - z.L
z["clv"] = (z.qc - z.L) / rg; b = body / rg
z["cls"] = np.select([b < 0.05, (b < 0.20) & (up > body) & (lo > body), (up >= 2 * body) & (lo <= 0.5 * body),
                      (z.clv <= 1 / 3) & (up / rg >= 1 / 3) & (up / rg <= 1 / 2)],
                     ["doji", "spinning top", "bearish pin bar", "Brooks bear signal bar"], "other")
z["clvt"] = pd.cut(z.clv, [-0.01, 1 / 3, 2 / 3, 1.01], labels=["close in bottom third (sellers)", "middle third", "top third (buyers)"])
z["tr"] = np.where(z.gap < 0, "today (EMA8 below)", "EMA8 above")
z.to_csv(HERE / "candle_types.csv", index=False)
for col, nm in (("cls", "candle class"), ("clvt", "close location")):
    print(f"\n## by {nm}\n| trend rule | {nm} | n | target % | stop % | Rs net | 2024 / 2025 / 2026 |\n|---|---|---|---|---|---|---|")
    for (a, c), g in z.groupby(["tr", col], observed=True):
        yy = (g.groupby(g.date.str[:4]).ret.mean() * 1000 - 85).round(0).astype(int).to_dict()
        print(f"| {a} | {c} | {len(g)} | {(g.out == 'target').mean()*100:.0f} | {(g.out == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {' / '.join(f'{v:+d}' for v in yy.values())} |")
