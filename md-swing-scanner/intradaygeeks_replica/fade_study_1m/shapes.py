import pandas as pd, re, numpy as np
S='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/orb_scans/'
D='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/daily/'
F={'2026-10-12':'orb_scan_20261012_0921.csv','2026-10-13':'orb_scan_20261013_0922.csv','2026-10-14':'orb_scan_20261014_0921.csv',
   '2026-10-15':'orb_scan_20261015_0921.csv','2026-10-16':'orb_scan_20261016_0921.csv','2026-10-19':'orb_scan_20261019_0921.csv'}
rx=re.compile(r'([\d.]+)->([\d.]+) \(L ([\d.]+) H ([\d.]+)\)')
def outcome(day,ei,entry,stop,c915,l915):
    a=day.iloc[ei+1:]; a=a[a.index.strftime('%H:%M')<='15:14']
    R=stop-entry; hit=a[a.High>=stop]; st=hit.index[0] if len(hit) else None
    pre=a[a.index<st] if st is not None else a
    def first(lv):
        if lv>=entry: return 'below'
        x=pre[pre.Low<=lv]; return x.index[0].strftime('%H:%M') if len(x) else 'no'
    lo=pre.Low.min() if len(pre) else entry
    a14=a[a.index.strftime('%H:%M')<='14:14']
    h14=-1.0 if (st is not None and st.strftime('%H:%M')<='14:14') else (entry-a14.Close.iloc[-1])/R
    return dict(stop_hit=st.strftime('%H:%M') if st is not None else 'no',t1=first(c915),t2=first(l915),
        best_pct=round((1-lo/entry)*100,2),best_R=round((entry-lo)/R,1),hold1415_R=round(h14,1),risk_pct=round(R/entry*100,2))
B=[];A=[]
for date,f in F.items():
    sc=pd.read_csv(S+f)
    for _,r in sc.iterrows():
        t=r.ticker; o,c,l,h=map(float,rx.search(r.c915).groups())
        m=pd.read_csv(f'm1/{t}.csv',index_col=0,parse_dates=True); day=m[m.index.strftime('%Y-%m-%d')==date]
        if len(day)<200: continue
        dd=pd.read_csv(D+t+'.csv',parse_dates=['Date']); dd=dd[dd.Date<date]
        y=dd.iloc[-1]; pp=(y.High+y.Low+y.Close)/3
        lv={'09:15 high':h,'yday high':y.High,'yday close':y.Close,'R1':2*pp-y.Low,'R2':pp+(y.High-y.Low),'daily 8':dd.Close.ewm(span=8,adjust=False).mean().iloc[-1]}
        tm=day.index.strftime('%H:%M'); idx={x:i for i,x in enumerate(tm)}
        w=day[(tm>='09:20')&(tm<='09:45')]
        # ---------- B
        if c<o and len(w):
            pk=w.High.max(); pt=w.High.idxmax()
            if pk<h:
                before=day[(day.index<=pt)&(tm>='09:20')]; L0=min(l,before.Low.min())
                if pk/L0-1>=0.003:
                    aft=day[(day.index>pt)&(day.index.strftime('%H:%M')<='10:00')]
                    e=aft[aft.Close<=pk*0.998]
                    nh=aft[aft.High>pk]
                    if len(e) and (not len(nh) or nh.index[0]>e.index[0]):
                        et=e.index[0]; entry=e.Close.iloc[0]; stop=pk*1.0005
                        B.append(dict(date=date,t=t,rank=r['rank'],peak=f'{pk:.2f} {pt:%H:%M}',bounce_pct=round((pk/L0-1)*100,2),entry=round(entry,2),at=et.strftime('%H:%M'),stop=round(stop,2),c915=c,l915=l,**outcome(day,idx[et.strftime('%H:%M')],entry,stop,c,l)))
        # ---------- A
        p0=day.iloc[idx.get('09:20',5)].Open
        best=None
        for name,L in lv.items():
            if L<=p0: continue
            cr=w[w.High>L]
            if not len(cr): continue
            ct=cr.index[0]; win=day[(day.index>=ct)&(day.index<=ct+pd.Timedelta('10min'))]
            back=win[win.Close<L]
            if not len(back): continue
            et=back.index[0]
            if best is None or et<best[2]: best=(name,L,et,ct)
        if best:
            name,L,et,ct=best; sp=day[(day.index>=ct)&(day.index<=et)].High.max(); entry=day.loc[et].Close; stop=sp*1.0005
            A.append(dict(date=date,t=t,rank=r['rank'],first915='red' if c<o else 'green',level=f'{name} {L:.2f}',crossed=ct.strftime('%H:%M'),spike=round(sp,2),entry=round(entry,2),at=et.strftime('%H:%M'),stop=round(stop,2),c915=c,l915=l,**outcome(day,idx[et.strftime('%H:%M')],entry,stop,c,l)))
pd.set_option('display.width',300); pd.set_option('display.max_rows',300)
for nm,X in (('B',B),('A',A)):
    x=pd.DataFrame(X); x.to_csv(f'shape_{nm}.csv',index=False); print(nm,len(x)); print(x.to_string()); print()
