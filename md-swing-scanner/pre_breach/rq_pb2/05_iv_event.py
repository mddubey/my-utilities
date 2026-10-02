import sys, numpy as np, pandas as pd
sys.path.insert(0,'/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
S=str(__import__('pathlib').Path(__file__).resolve().parent)
iv=pd.concat([pd.read_csv(f'{S}/iv_{k}.csv',parse_dates=['date']) for k in range(8)])
iv=iv[(iv.iv>0.05)&(iv.iv<2.0)].sort_values(['ticker','date'])
iv['mkt']=iv.groupby('date').iv.transform('median'); iv['ex']=iv.iv-iv.mkt
iv['k']=iv.groupby('ticker').cumcount()
print('IV rows',len(iv),'tickers',iv.ticker.nunique(),iv.date.min().date(),iv.date.max().date())
print('IV median by year:',iv.groupby(iv.date.dt.year).iv.median().round(3).to_dict())
X=pd.read_pickle(f'{S}/pivot_feats.pkl')
p=pd.read_csv(''+str(__import__('pathlib').Path(__file__).resolve().parent.parent/'panel.csv')+'',parse_dates=['date'])
ev=p[p.touched & p.fo][['ticker','date','gap_through']].merge(X[['ticker','date','cls']],on=['ticker','date'],how='left')
ix=iv.set_index(['ticker','date'])
spot=iv.set_index(['ticker','k'])
ev=ev.merge(iv[['ticker','date','k']],on=['ticker','date'])
lags=[-10,-5,-3,-2,-1,0,1,2,3,5]
for L in lags:
    m=spot[['ex','spot']].rename(columns={'ex':f'ex{L}','spot':f's{L}'})
    ev=ev.merge(m,left_on=['ticker',ev.k+L],right_index=True,how='left') if False else ev
# simpler: lookup via dict
d={(t,k):(e,s) for t,k,e,s in zip(iv.ticker,iv.k,iv.ex,iv.spot)}
for L in lags:
    ev[f'ex{L}']=[d.get((t,k+L),(np.nan,np.nan))[0] for t,k in zip(ev.ticker,ev.k)]
    ev[f's{L}']=[d.get((t,k+L),(np.nan,np.nan))[1] for t,k in zip(ev.ticker,ev.k)]
ev=ev.dropna(subset=['ex-10','ex-1'])
print('\nevents',len(ev))
for L in lags: ev[f'd{L}']=(ev[f'ex{L}']-ev['ex-10'])*100   # vol points vs day -10
cols=[f'd{L}' for L in lags]
print('\nEXCESS-IV change vs day -10, vol points (all touched F&O events)')
print(ev[cols].agg(['mean','median']).round(2))
print('\nby eventual class (evaluation only)')
print(ev.groupby('cls')[cols].mean().round(2))
# return-matched control for the approach leg (-10 -> -1)
iv['ret10']=iv.groupby('ticker').spot.pct_change(9)       # k-10 -> k-1 equivalently 9 steps
iv['dex9']=iv.groupby('ticker').ex.diff(9)*100
ev['ret_app']=ev['s-1']/ev['s-10']-1; ev['dex_app']=ev['d-1']
ctrl=iv.dropna(subset=['ret10','dex9'])
edges=np.quantile(ctrl.ret10,np.linspace(0,1,11)); edges[0]-=1; edges[-1]+=1
ctrl['b']=pd.cut(ctrl.ret10,edges); ev['b']=pd.cut(ev.ret_app,edges)
cm=ctrl.groupby('b').dex9.mean()
ev['ctrl']=ev.b.map(cm).astype(float); ev['abn']=ev.dex_app-ev.ctrl
print('\napproach leg (-10 -> -1): raw excess-IV change, return-matched control, abnormal')
print(ev[['dex_app','ctrl','abn']].agg(['mean','median']).round(2))
print('by return decile:'); print(ev.groupby('b').agg(n=('abn','size'),raw=('dex_app','mean'),ctrl=('ctrl','mean'),abn=('abn','mean')).round(2))
ev['yr']=ev.date.dt.year; print('\nabnormal approach change by year'); print(ev.groupby('yr').abn.agg(['size','mean','median']).round(2))
# post-touch leg (0 -> +3) control
iv['ret3f']=iv.groupby('ticker').spot.shift(-3)/iv.spot-1; iv['dex3f']=(iv.groupby('ticker').ex.shift(-3)-iv.ex)*100
c2=iv.dropna(subset=['ret3f','dex3f']); e2=np.quantile(c2.ret3f,np.linspace(0,1,11)); e2[0]-=1; e2[-1]+=1
c2['b']=pd.cut(c2.ret3f,e2); ev['ret_post']=ev['s3']/ev['s0']-1; ev['dex_post']=(ev['ex3']-ev['ex0'])*100
ev['b2']=pd.cut(ev.ret_post,e2); ev['abn_post']=ev.dex_post-ev.b2.map(c2.groupby('b').dex3f.mean()).astype(float)
print('\npost-touch leg (0 -> +3): raw, abnormal'); print(ev[['dex_post','abn_post']].agg(['mean','median']).round(2))
print(ev.groupby('yr').abn_post.agg(['size','mean','median']).round(2))
ev.to_pickle(f'{S}/iv_events.pkl')
