import pandas as pd, yfinance as yf, warnings; warnings.filterwarnings('ignore')
C='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/intraday_5m/'
T=[("2026-10-13","RBLBANK","09:30",395.25,397.10,390.15,"09:38","taken"),
   ("2026-10-13","RBLBANK","10:00",395.50,397.10,None,None,"missed"),
   ("2026-10-14","JSWSTEEL","09:25",1182.0,1185.10,None,None,"missed"),
   ("2026-10-14","JSWSTEEL","09:35",1175.0,1185.10,1177.10,"11:55","taken"),
   ("2026-10-15","CEATLTD","09:30",3280.0,3303.40,None,None,"not taken"),
   ("2026-10-16","ORIENTELEC","09:35",210.0,215.20,207.20,"09:46","taken"),
   ("2026-10-16","WIPRO","09:50",181.10,182.10,182.10,"10:00","taken"),
   ("2026-10-16","PERSISTENT","10:05",5625.0,5652.0,5670.50,"11:24","taken"),
   ("2026-10-19","URBANCO","09:30",148.60,149.10,None,None,"missed"),
   ("2026-10-19","ORIENTELEC","09:35",204.60,205.60,202.82,"09:45","taken")]
live={}
for d,tk,et,e,s,x,xt,tag in T:
    if d=="2026-10-19":
        if tk not in live:
            b=yf.download(tk+'.NS',period='1d',interval='5m',progress=False,auto_adjust=False);b.columns=b.columns.get_level_values(0)
            b.index=b.index.tz_convert('Asia/Kolkata').tz_localize(None); live[tk]=b
        b=live[tk]
    else:
        b=pd.read_csv(C+tk+'.csv',index_col=0,parse_dates=True); b.index=pd.to_datetime(b.index,utc=True).tz_convert('Asia/Kolkata').tz_localize(None)
        b=b[b.index.strftime('%Y-%m-%d')==d]; b.columns=[c.capitalize() for c in b.columns]
    b=b[b.index.strftime('%H:%M')<='14:10']
    l915=b.Low.iloc[0]; c915=b.Close.iloc[0]
    after=b[b.index.strftime('%H:%M')>et]
    R=s-e
    hit=after[after.High>=s]
    st=hit.index[0] if len(hit) else None
    pre=after[after.index<st] if st is not None else after
    lo=pre.Low.min(); lot=pre.Low.idxmin()
    end='stop '+st.strftime('%H:%M') if st is not None else 'close %.2f'%after.Close.iloc[-1]
    held=(-1.0 if st is not None else (e-after.Close.iloc[-1])/R)
    got=(e-x)/R if x else None
    print(f"{d} {tk:10s} {tag:9s} e{e} s{s} R%={R/e*100:.2f} | best before stop {lo:.2f} ({(e-lo)/e*100:+.2f}%, {(e-lo)/R:.1f}R) at {lot:%H:%M} | 0915C {c915:.2f} 0915L {l915:.2f} reached={'Y' if lo<=l915 else 'N'} | then {end} | hold-to-stop/15:15 R={held:+.1f} | taken R={'' if got is None else f'{got:+.1f}'} | lastbar {b.index[-1]:%H:%M}")
