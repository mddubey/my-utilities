import pandas as pd, glob, os
n = pd.read_csv("data/index_intraday/_NIFTY_5m_60d.csv", index_col=0, parse_dates=True)
n.index = n.index.tz_convert("Asia/Kolkata"); n.columns = [c.lower() for c in n.columns]
days = sorted(set(n.index.date.astype(str)))
files = {os.path.basename(f)[:8]: f for f in glob.glob("data/nse_fo_bhav/*.csv")}
rows = []
for i, d in enumerate(days[1:], 1):
    p = days[i-1].replace("-", "")
    if p not in files: continue
    b = pd.read_csv(files[p], usecols=["TckrSymb","FinInstrmTp","XpryDt","StrkPric","OptnTp","OpnIntrst","UndrlygPric"])
    b = b[(b.TckrSymb=="NIFTY") & (b.FinInstrmTp=="IDO")]
    exp = b.XpryDt.min(); b = b[b.XpryDt==exp]
    spot = n[n.index.date.astype(str)==days[i-1]].close.iloc[-1]
    ce = b[(b.OptnTp=="CE") & (b.StrkPric>spot) & (b.StrkPric<=spot*1.015)]
    pe = b[(b.OptnTp=="PE") & (b.StrkPric<spot) & (b.StrkPric>=spot*0.985)]
    ceil = ce.loc[ce.OpnIntrst.idxmax()]; flr = pe.loc[pe.OpnIntrst.idxmax()]
    t = n[n.index.date.astype(str)==d]
    def res(lvl, up):
        hit = t[t.high>=lvl] if up else t[t.low<=lvl]
        if hit.empty: return "no touch"
        t0 = hit.index[0].strftime("%H:%M"); c = t.close.iloc[-1]
        held = c < lvl if up else c > lvl
        return f"{t0} {'HELD' if held else 'BROKE'}"
    rows.append(dict(day=d, expiry="EXP" if exp==d else "", prev=round(spot), ceiling=int(ceil.StrkPric), c_oi_L=round(ceil.OpnIntrst/1e5),
                     floor=int(flr.StrkPric), f_oi_L=round(flr.OpnIntrst/1e5), hi=round(t.high.max()), lo=round(t.low.min()), close=round(t.close.iloc[-1]),
                     ceiling_res=res(ceil.StrkPric, True), floor_res=res(flr.StrkPric, False)))
print(pd.DataFrame(rows).tail(25).to_string(index=False))
