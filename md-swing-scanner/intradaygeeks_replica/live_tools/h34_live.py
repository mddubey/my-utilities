import sys, pandas as pd, yfinance as yf, warnings; warnings.filterwarnings("ignore")
R = "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/"
p = pd.read_csv(R + "intradaygeeks_replica/prep/orb_prep_20261029.csv"); p = p[(p.liq5_L >= 15) & (p.pc >= 100)].set_index("t")
info = {}
for t in p.index:
    try:
        d = pd.read_csv(R + f"data/daily/{t}.csv").tail(1).iloc[0]; P = (d.High + d.Low + d.Close) / 3
        h = pd.read_csv(R + f"data/intraday_60m/{t}.csv", index_col=0); c = [x for x in h.columns if x.lower() == "close"][0]
        info[t] = dict(h=h[c], lv={"yday high": d.High, "yday close": d.Close, "R1": 2*P - d.Low, "R2": P + d.High - d.Low, "PP": P, "daily 8": p.loc[t, "e8y"]})
    except Exception: pass
x = yf.download([t + ".NS" for t in info], period="1d", interval="5m", group_by="ticker", progress=False, threads=True)
rows = []
for t, I in info.items():
    try: b = x[t + ".NS"].dropna()
    except Exception: continue
    if b.empty: continue
    hi, now = b.High.max(), b.Close.iloc[-1]
    e34 = pd.concat([I["h"], pd.Series([now])]).ewm(span=34, adjust=False).mean().iloc[-1]
    e8 = pd.concat([I["h"], pd.Series([now])]).ewm(span=8, adjust=False).mean().iloc[-1]
    if not (e34 * 0.998 <= hi <= e34 * 1.006 and now < e34): continue
    off = (hi - now) / hi * 100
    near = [f"{k} {v:.2f}" for k, v in I["lv"].items() if abs(v / e34 - 1) <= 0.003]
    rows.append(dict(ticker=t, now=round(now, 2), day_high=round(hi, 2), hh=b.High.idxmax().tz_convert("Asia/Kolkata").strftime("%H:%M"),
                     h34=round(e34, 2), pierce_pct=round((hi / e34 - 1) * 100, 2), now_vs_h34=round((now / e34 - 1) * 100, 2), off_high=round(off, 2),
                     h8=round(e8, 2), day_chg=round((now / I["lv"]["yday close"] - 1) * 100, 2), under_d8="Y" if now < I["lv"]["daily 8"] else "",
                     atr=round(p.loc[t, "atrp"], 2), liq5_L=round(p.loc[t, "liq5_L"]), level_at_h34=" | ".join(near)))
r = pd.DataFrame(rows)
r = r[r.off_high >= 0.15].sort_values(["level_at_h34", "liq5_L"], ascending=[False, False])
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 70); print(len(r)); print(r.to_string(index=False))
