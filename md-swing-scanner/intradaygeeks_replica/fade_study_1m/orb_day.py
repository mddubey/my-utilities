import pandas as pd
C='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/intraday_5m/'
live=pd.read_csv('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/orb_scans/orb_scan_20261019_0921.csv')
tk=list(live.ticker)+['LTM','FEDERALBNK']
out=[]
for t in tk:
    b=pd.read_csv(C+t+'.csv',index_col=0,parse_dates=True); b.index=pd.to_datetime(b.index,utc=True).tz_convert('Asia/Kolkata').tz_localize(None)
    b=b[b.index.strftime('%Y-%m-%d')=='2026-10-19']; b.columns=[c.capitalize() for c in b.columns]
    f=b.iloc[0]; red=f.Close<f.Open
    p921=b.iloc[1].Close  # 09:20 bar close
    a=b.iloc[1:]
    hi=a.High.max(); lo=a.Low.min()
    out.append(dict(t=t,c915='red' if red else 'green',o=f.Open,h=f.High,l=f.Low,c=f.Close,p0921=p921,
      above915H='Y '+a[a.High>f.High].index[0].strftime('%H:%M') if (a.High>f.High).any() else 'N',
      hit915C='Y '+a[a.Low<=f.Close].index[0].strftime('%H:%M') if (a.Low<=f.Close).any() else 'N',
      hit915L='Y '+a[a.Low<f.Low].index[0].strftime('%H:%M') if (a.Low<f.Low).any() else 'N',
      dayH=f"{hi:.2f} {a.High.idxmax():%H:%M}",dayL=f"{lo:.2f} {a.Low.idxmin():%H:%M}",close=round(b.iloc[-1].Close,2),
      chg_from_0921=round((b.iloc[-1].Close/p921-1)*100,2)))
print(pd.DataFrame(out).round(2).to_string())
