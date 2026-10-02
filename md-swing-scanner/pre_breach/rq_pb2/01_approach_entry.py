"""Exploratory: enter BEFORE the breach, during the approach, on strength+volume.
Decision at a 5-min bar close, fill at next bar open (no same-bar lookahead)."""
import pandas as pd, numpy as np, sys
from pathlib import Path
from backtest import load
SP=Path(str(__import__('pathlib').Path(__file__).resolve().parent))
p=pd.read_csv(''+str(__import__('pathlib').Path(__file__).resolve().parent.parent/'panel.csv')+'',parse_dates=['date'])
p=p[(p.date>='2026-06-10')&(~p.gap_through)]
ZONE=float(sys.argv[1]) if len(sys.argv)>1 else 1.0   # % below trigger that defines "approaching"
rows=[]
for tk,g in p.groupby('ticker'):
    f=Path('intraday_cache')/f'{tk}.csv'
    if not f.exists(): continue
    b=pd.read_csv(f); b['dt']=pd.to_datetime(b.Datetime,utc=True).dt.tz_convert('Asia/Kolkata')
    b['day']=b.dt.dt.normalize().dt.tz_localize(None); b['hm']=b.dt.dt.strftime('%H:%M')
    b=b[(b.hm>='09:15')&(b.hm<='15:25')]
    b['cumv']=b.groupby('day').Volume.cumsum()
    piv=b.pivot_table(index='day',columns='hm',values='cumv')
    typ=piv.rolling(20,min_periods=10).median().shift(1)   # strictly prior sessions
    try: d=load(tk)
    except Exception: continue
    for r in g.itertuples():
        day=b[b.day==r.date].reset_index(drop=True)
        if len(day)<60 or r.date not in typ.index: continue
        tp=(day.High+day.Low+day.Close)/3
        vw=(tp*day.Volume).cumsum()/day.Volume.cumsum().replace(0,np.nan)
        trig=r.trigger; o=day.Open.iloc[0]
        touched_so_far=False; ev=None
        if day.High.iloc[:2].max()>=trig: continue
        for i in range(2,len(day)-1):           # decide from 09:25 close onward
            if day.High.iloc[i]>=trig: touched_so_far=True; break
            if day.hm.iloc[i]>'14:30': break
            dist=(trig/day.Close.iloc[i]-1)*100
            if dist<=ZONE:
                tv=typ.loc[r.date].get(day.hm.iloc[i],np.nan)
                ev=dict(i=i,hm=day.hm.iloc[i],dist=dist,
                        rvol=day.cumv.iloc[i]/tv if tv and tv>0 else np.nan,
                        above_vwap=day.Close.iloc[i]>vw.iloc[i],
                        from_open=(day.Close.iloc[i]/o-1)*100)
                break
        if ev is None: continue
        i=ev['i']; e=day.Open.iloc[i+1]
        rest=day.iloc[i+1:]
        hit=(rest.High>=trig).any()
        di=d.index.get_loc(r.date) if r.date in d.index else None
        def fc(k):
            return (d.Close.iloc[di+k]/e-1)*100 if di is not None and di+k<len(d) else np.nan
        rows.append(dict(ticker=tk,date=r.date,**{k:v for k,v in ev.items() if k!='i'},entry=e,trigger=trig,
            hit=hit, to_trig=(trig/e-1)*100,
            mfe_eod=(rest.High.max()/e-1)*100, mae_eod=(rest.Low.min()/e-1)*100,
            eod=(rest.Close.iloc[-1]/e-1)*100, T1=fc(1), T3=fc(3), T5=fc(5),
            atr_pct=r.atr_pct))
out=pd.DataFrame(rows); out.to_csv(SP/f'approach_z{ZONE}.csv',index=False)
print(f"ZONE={ZONE}%  events={len(out)}  sessions={out.date.nunique()}")
