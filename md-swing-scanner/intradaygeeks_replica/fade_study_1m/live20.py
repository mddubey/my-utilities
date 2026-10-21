import yfinance as yf, pandas as pd, warnings; warnings.filterwarnings('ignore')
t="IXIGO EUROPRATIK KROSS PNB DEEDEV GABRIEL SOLARA PAUSHAKLTD JINDALSAW TIPSMUSIC CROMPTON AURUM SHILPAMED URBANCO HBLENGINE HSCL KRN KARURVYSYA ORIENTHOT MBEL".split()
d=yf.download([x+'.NS' for x in t],period='1d',interval='5m',progress=False,auto_adjust=False,group_by='ticker',threads=True)
rows=[]
for x in t:
    b=d[x+'.NS'].dropna(); b.index=b.index.tz_convert('Asia/Kolkata')
    f=b.iloc[0]; l=b.iloc[-1]; now=l.Close
    rows.append(dict(tk=x,now=round(now,2),h915=round(f.High,2),l915=round(f.Low,2),dH=round(b.High.max(),2),dL=round(b.Low.min(),2),
      to915H=round((f.High/now-1)*100,2),to915L=round((now/f.Low-1)*100,2),todH=round((b.High.max()/now-1)*100,2),todL=round((now/b.Low.min()-1)*100,2),
      last=f"{l.name:%H:%M} {l.Open:.2f}->{l.Close:.2f} H{l.High:.2f} L{l.Low:.2f}"))
print(pd.DataFrame(rows).to_string())
