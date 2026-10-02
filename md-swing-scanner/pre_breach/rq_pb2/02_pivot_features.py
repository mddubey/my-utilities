import sys, numpy as np, pandas as pd
sys.path.insert(0,'/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
from backtest import load
S=str(__import__('pathlib').Path(__file__).resolve().parent)
p=pd.read_csv(''+str(__import__('pathlib').Path(__file__).resolve().parent.parent/'panel.csv')+'',parse_dates=['date'])
t=p[p.touched & ~p.gap_through].copy()
rows=[]
for tk,g in t.groupby('ticker'):
    try: d=load(tk)
    except Exception: continue
    d=d.copy(); H,L,C,V,O=d.High,d.Low,d.Close,d.Volume,d.Open
    h10=H.rolling(10).max().shift(1)                 # = high10_prior on row T  (T-10..T-1)
    feats={}
    # everything below is computed on row T-1 information only -> shift so row T holds T-1-known values
    piv=h10  # pivot level for day T
    for tol in (0.5,1,2):
        # days in T-20..T-1 with High >= pivot*(1-tol)
        cnt=pd.concat([(H.shift(j)>=piv*(1-tol/100)) for j in range(1,21)],axis=1).sum(axis=1)
        feats[f'tests_{tol}']=cnt
    # pivot age: bars since argmax of H over T-10..T-1
    feats['pivot_age']=H.rolling(10).apply(lambda a: 9-np.argmax(a),raw=True).shift(1)+1
    atr=(pd.concat([H-L,(H-C.shift()).abs(),(L-C.shift()).abs()],axis=1).max(axis=1)).rolling(14).mean().shift(1)
    for lb in (60,120,250):
        older=H.shift(11).rolling(lb-10).max()          # highs T-(lb)..T-11
        feats[f'room_{lb}']=(older-piv*1.005)/atr
    for w in (3,5,10):
        feats[f'dryup_{w}']=V.shift(1).rolling(w).mean()/V.shift(1).rolling(50).mean()
    up=C>C.shift(); dnv=V.where(~up,0)
    pp=up & (V>dnv.shift(1).rolling(10).max())
    for w in (3,5,10):
        feats[f'pp_{w}']=pp.shift(1).rolling(w).max()
        feats[f'speed_{w}']=(C.shift(1)/C.shift(1+w)-1)/(atr/C.shift(1))
    F=pd.DataFrame(feats); F['c5']=C.shift(-5); F['c10']=C.shift(-10); F['atr_abs']=atr
    F=F.reindex(g.date)
    gg=g.set_index('date').join(F)
    rows.append(gg.reset_index())
X=pd.concat(rows)
X['r5']=(X.c5/X.trigger-1)/(X.atr_abs/X.trigger)
X['r10']=(X.c10/X.trigger-1)/(X.atr_abs/X.trigger)
X['cls']=np.where(X.r5>=1.5,'BLAST',np.where(X.r5<=-1.0,'FAIL','STALL'))
X.to_pickle(S+'/pivot_feats.pkl'); print(len(X), X.cls.value_counts(normalize=True).round(3).to_dict())
