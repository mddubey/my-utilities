import sys, pandas as pd, yfinance as yf, warnings; warnings.filterwarnings("ignore")
R = "/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/"
p = pd.read_csv(R + "intradaygeeks_replica/prep/orb_prep_20261030.csv")
p = p[(p.liq5_L >= 15) & (p.data_ok == True)] if "data_ok" in p else p[p.liq5_L >= 15]
lv = {}
for t in p.t:
    try:
        d = pd.read_csv(R + f"data/daily/{t}.csv", index_col=0).tail(3); y = d.iloc[-1]
        P = (y.High + y.Low + y.Close) / 3
        L = {"yday high": y.High, "yday close": y.Close, "R1": 2*P - y.Low, "R2": P + y.High - y.Low,
             "daily 8": p.set_index("t").loc[t, "e8y"]}
        try:
            h = pd.read_csv(R + f"data/intraday_60m/{t}.csv", index_col=0)
            c = [x for x in h.columns if x.lower() == "close"][0]; L["1H34"] = h[c].ewm(span=34, adjust=False).mean().iloc[-1]
        except Exception: pass
        lv[t] = L
    except Exception: pass
tk = [t + ".NS" for t in lv]
x = yf.download(tk, period="1d", interval="5m", group_by="ticker", progress=False, threads=True)
rows = []
for t in lv:
    try: b = x[t + ".NS"].dropna()
    except Exception: continue
    if b.empty: continue
    hi, now, op = b.High.max(), b.Close.iloc[-1], b.Open.iloc[0]
    hit = [f"{k} {v:.2f}" for k, v in lv[t].items() if hi >= v * 0.997 and hi <= v * 1.006]
    off = (hi - now) / hi * 100
    rows.append(dict(ticker=t, open=round(op, 2), day_high=round(hi, 2), now=round(now, 2), off_high_pct=round(off, 2),
                     day_chg=round((now / lv[t]["yday close"] - 1) * 100, 2), hh_time=b.High.idxmax().tz_convert("Asia/Kolkata").strftime("%H:%M"),
                     poked=" | ".join(hit), liq5_L=round(p.set_index("t").loc[t, "liq5_L"], 1)))
r = pd.DataFrame(rows); r.to_csv(sys.argv[1] if len(sys.argv) > 1 else "/dev/null", index=False)
pd.set_option("display.width", 250); pd.set_option("display.max_colwidth", 80)
print("POKED A LEVEL AND TURNING (day high within -0.3%..+0.6% of a level, now >= 0.2% off the high):")
print(r[(r.poked != "") & (r.off_high_pct >= 0.2)].sort_values("off_high_pct", ascending=False).to_string(index=False))
print("\nAT THE DAY HIGH NOW (within 0.15%), with a level poked:")
print(r[(r.poked != "") & (r.off_high_pct < 0.2)].to_string(index=False))
print("\nAT THE DAY HIGH NOW, no level:", ", ".join(r[(r.poked == "") & (r.off_high_pct < 0.15)].ticker.tolist()))
# about to poke: at/near day high, nearest level 0-0.6% above now
ab = []
for _, q in r[(r.off_high_pct < 0.3)].iterrows():
    up = sorted([(v, k) for k, v in lv[q.ticker].items() if v > q.day_high * 1.006 or (v > q.now and q.poked == "")])
    up = [(v, k) for v, k in up if v > q.now and (v / q.now - 1) * 100 <= 0.6]
    if up: ab.append(dict(ticker=q.ticker, now=q.now, day_chg=q.day_chg, next_level=" | ".join(f"{k} {v:.2f}" for v, k in up), dist_pct=round((up[0][0]/q.now-1)*100, 2), liq5_L=q.liq5_L))
print("\nABOUT TO POKE (near day high, level within 0.6% above):")
print(pd.DataFrame(ab).sort_values("dist_pct").to_string(index=False) if ab else "none")
