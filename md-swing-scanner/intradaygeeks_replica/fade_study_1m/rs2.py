import pandas as pd
exec(open('be.py').read().split("def streak")[0])
def streak(x):
    m=c=0
    for v in x: c=c+1 if v<0 else 0; m=max(m,c)
    return m
N=pd.read_csv('m1/_NIFTY.csv',index_col=0,parse_dates=True)
ND=pd.read_csv('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/daily/_NIFTY.csv')
DD='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/daily/'
m1=[];m2=[]
for _,r in B.iterrows():
    d=day(r.t,r.date); et=pd.Timestamp(f"{r.date} {r['at']}"); pt=pd.Timestamp(f"{r.date} {r.peak.split()[1]}"); pk=float(r.peak.split()[0])
    nd=N[N.index.strftime('%Y-%m-%d')==r.date]
    yc=pd.read_csv(DD+r.t+'.csv').query('Date<@r.date').Close.iloc[-1]; nyc=ND[ND.Date<r.date].Close.iloc[-1]
    m1.append((d.loc[:et].Close.iloc[-1]/yc-1)*100-(nd.loc[:et].Close.iloc[-1]/nyc-1)*100)
    t19=pd.Timestamp(f"{r.date} 09:19")
    s0=d.loc[:t19].Close.iloc[-1]; n0=nd.loc[:t19].Close.iloc[-1]
    nh=nd[(nd.index>=pd.Timestamp(f"{r.date} 09:20"))&(nd.index<=pt)].High.max()
    m2.append((pk/s0-1)*100-(nh/n0-1)*100)
B['day_vs']=m1; B['bounce_vs']=m2
key=B[['t','date','at','day_vs','bounce_vs']]
for col,lab in (('day_vs','#1 DAY change vs Nifty (yday close -> entry)'),('bounce_vs','#2 BOUNCE vs Nifty (09:19 -> bounce high)')):
    print(f'\n===== {lab}: median {B[col].median():+.2f}, weaker n={(B[col]<0).sum()}, stronger n={(B[col]>=0).sum()}')
    for pl,buf,k in (('TIGHT + BE after +2R',0.0005,2),('ROOM 0.35% + hold',0.0035,None)):
        x=sim(buf,k).merge(key,on=['t','date','at'])
        print(' '+pl)
        for g,y in (('ALL',x),('WEAKER',x[x[col]<0]),('STRONGER',x[x[col]>=0])):
            print(f"   {g:>8} n={len(y):2d} win={(y.R>0).mean()*100:3.0f}% fullstops={(y.how=='stop').sum():2d} avgR={y.R.mean():+5.2f} Rs/trade={y.rs.mean():+6.0f} total={y.rs.sum():+7.0f} w/o top3={y.rs.sum()-y.rs.nlargest(3).sum():+7.0f} streak={streak(y.rs)}")
        print('   days positive (weaker/stronger):',sum(g[g[col]<0].rs.sum()>0 for _,g in x.groupby('date')),'/',sum(g[g[col]>=0].rs.sum()>0 for _,g in x.groupby('date') if (g[col]>=0).any()),'of days with trades',x.groupby('date').size().shape[0],(x[x[col]>=0].date.nunique()))
B[['date','t','day_vs','bounce_vs','hold1415_R']].round(2).to_csv('rs_table.csv',index=False)
