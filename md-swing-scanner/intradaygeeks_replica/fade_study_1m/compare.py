import pandas as pd
BUF=0.0035
def run(t,d,entry,from_t,peak,c915,l915):
    m=pd.read_csv(f'm1/{t}.csv',index_col=0,parse_dates=True); x=m[m.index.strftime('%Y-%m-%d')==d]
    a=x[(x.index>=pd.Timestamp(f'{d} {from_t}'))&(x.index.strftime('%H:%M')<='14:14')]
    stop=round(peak*(1+BUF),2); R=stop-entry
    hit=a[a.High>=stop]; st=hit.index[0] if len(hit) else None; pre=a[a.index<st] if st is not None else a
    def first(l):
        if l>=entry: return 'below'
        y=pre[pre.Low<=l]; return y.index[0].strftime('%H:%M') if len(y) else 'no'
    ex=stop if st is not None else a.Close.iloc[-1]
    return dict(stop=stop,risk=round(R/entry*100,2),T1=first(c915),T2=first(l915),exit=round(ex,2),exit_at=(st.strftime('%H:%M')+' stop') if st is not None else '14:15',
                pct=round((entry-ex)/entry*100,2),R=round((entry-ex)/R,1),best=round((1-pre.Low.min()/entry)*100,2))
T=[ # name, date, peak faded, 09:15 close, 09:15 low, (system entry, time), (your entry, from), actual
 ('RBLBANK','2026-10-13',396.95,390.35,388.25,(396.00,'09:27'),(395.25,'09:31'),'395.25 -> 390.15 (09:38) +1.29%'),
 ('JSWSTEEL','2026-10-14',1182.10,1173.00,1165.30,(1175.80,'09:30'),(1175.00,'09:38'),'1175 -> 1177.10 (11:55, trailed) -0.18%'),
 ('CEATLTD (seen)','2026-10-15',3297.80,3225.00,3186.70,(3264.20,'09:28'),(3280.00,'09:31'),'not taken'),
 ('ORIENTELEC','2026-10-16',214.81,204.50,204.00,(None,None),(210.00,'09:38'),'210 -> 207.20 (09:46) +1.33%'),
 ('URBANCO (missed)','2026-10-19',148.88,148.03,147.16,(147.23,'09:32'),(148.60,'09:31'),'no fill'),
 ('ORIENTELEC','2026-10-19',205.05,202.58,197.55,(None,None),(204.60,'09:38'),'204.60 -> 202.82 (09:45) +0.87%'),
]
for nm,d,pk,c,l,sy,yo,act in T:
    t=nm.split()[0]
    print(f'== {d} {nm} | faded high {pk} | T1 {c} T2 {l} | ACTUAL: {act}')
    if sy[0]: print('  SYSTEM  entry',sy[0],run(t,d,sy[0],sy[1],pk,c,l))
    print('  YOURS+ROOM entry',yo[0],run(t,d,yo[0],yo[1],pk,c,l))
