import pandas as pd
exec(open('be.py').read().split("def streak")[0])   # loads B, day(), sim()
def streak(x):
    m=c=0
    for v in x: c=c+1 if v<0 else 0; m=max(m,c)
    return m
N=pd.read_csv('m1/_NIFTY.csv',index_col=0,parse_dates=True)
rs=[]
for _,r in B.iterrows():
    d=day(r.t,r.date); et=pd.Timestamp(f"{r.date} {r['at']}")
    s=(d.loc[:et].Close.iloc[-1]/d.iloc[0].Open-1)*100
    nd=N[N.index.strftime('%Y-%m-%d')==r.date]; nn=(nd.loc[:et].Close.iloc[-1]/nd.iloc[0].Open-1)*100
    rs.append(s-nn)
B['vs_nifty']=rs
key=B[['t','date','at','vs_nifty']]
print('vs_nifty at entry: median %.2f, weaker(<0) n=%d, stronger(>=0) n=%d'%(B.vs_nifty.median(),(B.vs_nifty<0).sum(),(B.vs_nifty>=0).sum()))
for lab,buf,k in (('TIGHT + BE after +2R',0.0005,2),('ROOM 0.35% + hold',0.0035,None)):
    x=sim(buf,k).merge(key,on=['t','date','at'])
    print('\n'+lab)
    print(f"{'group':>10} {'n':>3} {'win%':>5} {'full stops':>10} {'avgR':>6} {'Rs/trade':>8} {'total':>8} {'w/o top3':>8} {'streak':>6}")
    for g,y in (('ALL',x),('WEAKER',x[x.vs_nifty<0]),('STRONGER',x[x.vs_nifty>=0])):
        print(f"{g:>10} {len(y):3d} {(y.R>0).mean()*100:5.0f} {(y.how=='stop').sum():10d} {y.R.mean():+6.2f} {y.rs.mean():+8.0f} {y.rs.sum():+8.0f} {y.rs.sum()-y.rs.nlargest(3).sum():+8.0f} {streak(y.rs):6d}")
    x['day_grp']=x.vs_nifty<0
    print('  by day (weaker / stronger Rs):',{d:(round(g[g.vs_nifty<0].rs.sum()),round(g[g.vs_nifty>=0].rs.sum())) for d,g in x.groupby('date')})
