import sys, numpy as np, pandas as pd
sys.path.insert(0,'/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
from backtest import load
from pivots import daily_pivots
S=str(__import__('pathlib').Path(__file__).resolve().parent)
X=pd.read_pickle(S+'/pivot_feats.pkl')[['ticker','date','trigger','cls','r5','r10','room_250']]
out=[]
for tk,g in X.groupby('ticker'):
    try: d=load(tk,daily_pivots)
    except Exception: continue
    C=d.Close; e13=C.ewm(span=13,adjust=False).mean()
    F=pd.DataFrame({'pp':d.pp,'s1':d.s1,'s2':d.s2,                      # row T = from T-1 HLC
        'ema8':d.ema8.shift(1),'ema13':e13.shift(1),'ema21':d.ema21.shift(1),'ema34':d.ema34.shift(1),
        'atr':d.atr14.shift(1),'low_T':d.Low}).reindex(g.date)
    gg=g.set_index('date').join(F).reset_index(); out.append(gg)
Y=pd.concat(out)
for lv in ['pp','s1','s2','ema8','ema13','ema21','ema34']:
    Y[f'd_{lv}']=(Y.trigger-Y[lv])/Y.atr
near=['pp','s1','ema8','ema13','ema21']
for w in (0.5,1.0,1.5):
    Y[f'conf_{w}']=sum(((Y[f'd_{l}']>=0)&(Y[f'd_{l}']<=w)).astype(int) for l in near)
Y['stack']=(Y.ema8>Y.ema13)&(Y.ema13>Y.ema21)&(Y.ema21>Y.ema34)
Y['SAME_low_above_s1']=Y.low_T>=Y.s1; Y['SAME_low_above_ema8']=Y.low_T>=Y.ema8
Y.to_pickle(S+'/support_feats.pkl')
def st(g): return pd.Series({'n':len(g),'BLAST%':(g.cls=='BLAST').mean()*100,'FAIL%':(g.cls=='FAIL').mean()*100,'r5_mean':g.r5.mean(),'r10_mean':g.r10.mean()})
pd.set_option('display.width',200)
print('BASELINE'); print(st(Y).round(2).to_frame().T)
for lv in ['pp','s1','s2','ema8','ema13','ema21','ema34']:
    c=f'd_{lv}'; b=pd.qcut(Y[c].rank(method='first'),3,labels=['T1 near','T2','T3 far'])
    t=Y.groupby(b).apply(st).round(2); t['range(ATR)']=Y.groupby(b)[c].agg(lambda s:f'{s.min():.2f}..{s.max():.2f}')
    print(f'\n{c}  (trigger minus level, ATR)'); print(t)
for w in (0.5,1.0,1.5):
    print(f'\nconfluence within {w} ATR below trigger'); print(Y.groupby(Y[f'conf_{w}'].clip(upper=4)).apply(st).round(2))
print('\nEMA stack 8>13>21>34'); print(Y.groupby('stack').apply(st).round(2))
print('\nSAME-DAY TELEMETRY (not promotable): touch-day low held above S1'); print(Y.groupby('SAME_low_above_s1').apply(st).round(2))
print('\nSAME-DAY TELEMETRY: touch-day low held above EMA8'); print(Y.groupby('SAME_low_above_ema8').apply(st).round(2))
