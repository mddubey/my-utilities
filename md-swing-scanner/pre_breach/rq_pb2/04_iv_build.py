"""ATM implied vol per ticker-day from the NSE F&O bhavcopy closes. Exploratory scratch."""
import sys, importlib.util
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
ROOT=Path('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner'); sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('ol',ROOT/'pre_breach/03_option_legs.py'); ol=importlib.util.module_from_spec(spec); spec.loader.exec_module(ol)
R=0.065
def bs(S,K,T,s,cp):
    d1=(np.log(S/K)+(R+s*s/2)*T)/(s*np.sqrt(T)); d2=d1-s*np.sqrt(T)
    return S*norm.cdf(d1)-K*np.exp(-R*T)*norm.cdf(d2) if cp=='CE' else K*np.exp(-R*T)*norm.cdf(-d2)-S*norm.cdf(-d1)
def iv(px,S,K,T,cp):
    lo,hi=0.01,3.0
    if not (bs(S,K,T,lo,cp)<px<bs(S,K,T,hi,cp)): return np.nan
    for _ in range(60):
        m=(lo+hi)/2
        if bs(S,K,T,m,cp)<px: lo=m
        else: hi=m
    return (lo+hi)/2
k,n=int(sys.argv[1]),int(sys.argv[2])
files=sorted((ROOT/'options_cache').glob('*.csv'))[k::n]
out=[]
for f in files:
    d=pd.to_datetime(f.stem)
    try:
        spot=ol.full_day(d)
        raw=pd.read_csv(f,usecols=['FinInstrmTp','TckrSymb','XpryDt','StrkPric','OptnTp','ClsPric','TtlTradgVol'])
    except Exception as e:
        print('skip',f.stem,e,flush=True); continue
    raw=raw[(raw.FinInstrmTp=='STO')&(raw.TtlTradgVol>0)&(raw.ClsPric>0)]
    raw['XpryDt']=pd.to_datetime(raw.XpryDt); raw['dte']=(raw.XpryDt-d).dt.days
    raw=raw[raw.dte>=7]
    for t,g in raw.groupby('TckrSymb'):
        if t not in spot.index or not spot[t]>0: continue
        S=float(spot[t]); g=g[g.XpryDt==g.XpryDt.min()]
        c=g[g.OptnTp=='CE'].set_index('StrkPric').ClsPric; p=g[g.OptnTp=='PE'].set_index('StrkPric').ClsPric
        ks=c.index.intersection(p.index)
        if len(ks)==0: continue
        K=min(ks,key=lambda x:abs(x-S))
        if abs(K/S-1)>0.05: continue
        T=g.dte.iloc[0]/365
        ivc,ivp=iv(c[K],S,K,T,'CE'),iv(p[K],S,K,T,'PE')
        out.append(dict(ticker=t,date=d,spot=S,K=K,dte=g.dte.iloc[0],iv_c=ivc,iv_p=ivp,iv=np.nanmean([ivc,ivp])))
    print(f.stem,flush=True)
pd.DataFrame(out).to_csv(Path(sys.argv[3])/f'iv_{k}.csv',index=False)
