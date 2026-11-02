import pandas as pd, glob, os
fs = sorted(glob.glob("data/nse_fo_bhav/2026*.csv")) + sorted(glob.glob("data/nse_fo_bhav/2025*.csv"))
fs = sorted(fs); days = [os.path.basename(f)[:8] for f in fs]
U = ["TckrSymb","FinInstrmTp","XpryDt","StrkPric","OptnTp","OpnIntrst","OpnPric","ClsPric","SttlmPric","UndrlygPric"]
def load(f):
    b = pd.read_csv(f, usecols=U); return b[(b.TckrSymb=="NIFTY") & (b.FinInstrmTp=="IDO")]
rows = []
for i in range(1, len(fs)):
    d = pd.Timestamp(days[i]).strftime("%Y-%m-%d"); b = load(fs[i])
    if d not in set(b.XpryDt): continue
    p = load(fs[i-1]); p = p[p.XpryDt==d]; spot = p.UndrlygPric.iloc[0]
    ce = p[(p.OptnTp=="CE") & (p.StrkPric>spot) & (p.StrkPric<=spot*1.015)]
    pe = p[(p.OptnTp=="PE") & (p.StrkPric<spot) & (p.StrkPric>=spot*0.985)]
    big = ce.OpnIntrst.max()
    near_c = ce[ce.OpnIntrst>=0.5*big].StrkPric.min()          # nearest call wall >= half the biggest
    bigp = pe.OpnIntrst.max(); near_f = pe[pe.OpnIntrst>=0.5*bigp].StrkPric.max()
    t = b[(b.XpryDt==d) & (b.OptnTp=="PE")].set_index("StrkPric")
    close = b.UndrlygPric.iloc[0]
    def leg(k):
        if k not in t.index: return "-"
        o, v = t.loc[k, "OpnPric"], max(0, k-close)
        return f"{o:.0f} -> {v:.0f}"
    rows.append(dict(day=d, prev=round(spot), close=round(close), chg=f"{(close/spot-1)*100:+.2f}%",
                     call_wall=int(near_c), PE_at_call_wall=leg(near_c), put_wall=int(near_f), PE_at_put_wall=leg(near_f)))
print(pd.DataFrame(rows).to_string(index=False))
r = pd.DataFrame(rows)
def parse(s):
    if s=="-": return None
    a,b = s.split(" -> "); return float(a), float(b)
for col in ["PE_at_call_wall","PE_at_put_wall"]:
    r[col+"_o"] = r[col].map(lambda s: parse(s)[0] if parse(s) else None); r[col+"_v"] = r[col].map(lambda s: parse(s)[1] if parse(s) else None)
r["c"] = r.chg.str.rstrip("%").astype(float)
for name, g in [("down >0.5%", r[r.c<=-0.5]), ("down 0.15-0.5%", r[(r.c>-0.5)&(r.c<=-0.15)]), ("flat +-0.15%", r[r.c.abs()<0.15]), ("up", r[r.c>=0.15])]:
    out = [name, len(g)]
    for col in ["PE_at_call_wall","PE_at_put_wall"]:
        o, v = g[col+"_o"], g[col+"_v"]
        out += [f"{(v>o).mean()*100:.0f}%", f"{(v.sum()/o.sum()):.2f}x", f"{(v==0).mean()*100:.0f}%"]
    print(out)
