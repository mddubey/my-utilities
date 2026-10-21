import pandas as pd, yfinance as yf, re, os, warnings; warnings.filterwarnings('ignore')
S='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/orb_scans/'
F={'2026-10-12':'orb_scan_20261012_0921.csv','2026-10-13':'orb_scan_20261013_0922.csv','2026-10-14':'orb_scan_20261014_0921.csv',
   '2026-10-15':'orb_scan_20261015_0921.csv','2026-10-16':'orb_scan_20261016_0921.csv','2026-10-19':'orb_scan_20261019_0921.csv'}
tk=sorted({t for f in F.values() for t in pd.read_csv(S+f).ticker})
print(len(tk),'tickers')
d=yf.download([t+'.NS' for t in tk],start='2026-10-12',end='2026-10-20',interval='1m',group_by='ticker',progress=False,auto_adjust=False,threads=True)
miss=[]
for t in tk:
    try:
        x=d[t+'.NS'].dropna(how='all')
        if len(x)==0: miss.append(t); continue
        x.index=x.index.tz_convert('Asia/Kolkata').tz_localize(None); x.to_csv(f'm1/{t}.csv')
    except KeyError: miss.append(t)
print('missing',miss)
