import pandas as pd
B=pd.read_csv('shape_B.csv')
cache={}
def day(t,d):
    if t not in cache: cache[t]=pd.read_csv(f'm1/{t}.csv',index_col=0,parse_dates=True)
    m=cache[t]; return m[m.index.strftime('%Y-%m-%d')==d]
res={}
for buf in (0.0005,0.002,0.0035,0.005):
    out=[]
    for _,r in B.iterrows():
        d=day(r.t,r.date); pk=float(r.peak.split()[0]); stop=pk*(1+buf); e=r.entry
        a=d[(d.index>pd.Timestamp(f"{r.date} {r['at']}"))&(d.index.strftime('%H:%M')<='14:14')]
        hit=a[a.High>=stop]; R=stop-e
        if len(hit): res_r=-1.0; st=True
        else: res_r=(e-a.Close.iloc[-1])/R; st=False
        risk_pct=R/e; pos=1000/risk_pct; cost=pos*85/1e5
        out.append(dict(date=r.date,at=r['at'],t=r.t,stopped=st,R=res_r,rs=res_r*1000-cost,risk_pct=risk_pct*100))
    res[buf]=pd.DataFrame(out).sort_values(['date','at'])
base=res[0.0005]
def streak(x):
    m=c=0
    for v in x: c=c+1 if v<0 else 0; m=max(m,c)
    return m
print(f"{'buffer':>7} {'stopped':>8} {'saved':>6} {'saved->win':>10} {'win%':>5} {'avgR':>6} {'Rs/1k net':>9} {'total Rs':>9} {'worst streak':>12} {'risk med%':>9}")
for buf,x in res.items():
    saved=(base.stopped.values & ~x.stopped.values); sw=(saved & (x.R.values>0)).sum()
    print(f"{buf*100:6.2f}% {x.stopped.sum():8d} {saved.sum():6d} {sw:10d} {(x.R>0).mean()*100:5.0f} {x.R.mean():+6.2f} {x.rs.mean():+9.0f} {x.rs.sum():+9.0f} {streak(x.rs):12d} {x.risk_pct.median():9.2f}")
print()
for buf,x in res.items():
    y=x[x.t!='PAUSHAKLTD'] if False else x
    top=x.rs.nlargest(3).sum(); print(f"{buf*100:.2f}%: total without top-3 trades {x.rs.sum()-top:+.0f}; by day", x.groupby('date').rs.sum().round(0).to_dict())
print()
for buf in (0.0035,0.005):
    x=res[buf]; s=base.stopped.values & ~x.stopped.values
    print(f"{buf*100:.2f}% saved:", [(t,d,round(rr,1)) for t,d,rr in zip(x.t[s],x.date[s],x.R[s])])
