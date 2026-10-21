import pandas as pd
B=pd.read_csv('shape_B.csv'); cache={}
def day(t,d):
    if t not in cache: cache[t]=pd.read_csv(f'm1/{t}.csv',index_col=0,parse_dates=True)
    m=cache[t]; return m[m.index.strftime('%Y-%m-%d')==d]
def sim(buf,k):
    out=[]
    for _,r in B.iterrows():
        d=day(r.t,r.date); pk=float(r.peak.split()[0]); e=r.entry; s0=pk*(1+buf); R=s0-e
        a=d[(d.index>pd.Timestamp(f"{r.date} {r['at']}"))&(d.index.strftime('%H:%M')<='14:14')]
        stop=s0; be=False; res=None; how='14:15'
        for ts,b in a.iterrows():
            if b.High>=stop: res=(e-stop)/R; how='BE' if be else 'stop'; break
            if k and not be and b.Low<=e-k*R: be=True; stop=e   # effective from next minute
        if res is None: res=(e-a.Close.iloc[-1])/R
        pos=1000/(R/e); out.append(dict(t=r.t,date=r.date,at=r['at'],R=res,rs=res*1000-pos*85/1e5,how=how))
    return pd.DataFrame(out).sort_values(['date','at'])
def streak(x):
    m=c=0
    for v in x: c=c+1 if v<0 else 0; m=max(m,c)
    return m
print(f"{'stop':>6} {'rule':>14} {'full stops':>10} {'BE exits':>8} {'win%':>5} {'avgR':>6} {'Rs/trade':>8} {'total':>8} {'w/o top3':>8} {'streak':>6}")
for buf in (0.0005,0.0035):
    for k in (None,1,2,3):
        x=sim(buf,k)
        print(f"{buf*100:5.2f}% {('hold to 14:15' if not k else f'BE after +{k}R'):>14} {(x.how=='stop').sum():10d} {(x.how=='BE').sum():8d} {(x.R>0).mean()*100:5.0f} {x.R.mean():+6.2f} {x.rs.mean():+8.0f} {x.rs.sum():+8.0f} {x.rs.sum()-x.rs.nlargest(3).sum():+8.0f} {streak(x.rs):6d}")
