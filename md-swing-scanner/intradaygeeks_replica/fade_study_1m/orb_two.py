import pandas as pd
C='/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/data/intraday_5m/'
L=pd.read_csv('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner/intradaygeeks_replica/orb_scans/orb_scan_20261019_0921.csv')
L=L[L.side=='SHORT']
A=[];F=[]
for _,r in L.iterrows():
    t=r.ticker
    b=pd.read_csv(C+t+'.csv',index_col=0,parse_dates=True); b.index=pd.to_datetime(b.index,utc=True).tz_convert('Asia/Kolkata').tz_localize(None)
    b=b[b.index.strftime('%Y-%m-%d')=='2026-10-19']; b.columns=[c.capitalize() for c in b.columns]
    b=b[b.index.strftime('%H:%M')<='15:10']
    h,l,c=r.h915,r.l915,r.cl915; a=b.iloc[1:]
    # ---- original ORB: break of the 09:15 low
    br=a[a.Low<l]
    if len(br):
        bt=br.index[0]; post=a[a.index>=bt]
        st=post[post.High>=r.stop_tight]
        A.append(dict(t=t,trig=l,status=r.status.split(':')[0],broke=bt.strftime('%H:%M'),before930='Y' if bt.strftime('%H:%M')<'09:30' else 'N',
           low_after=f"{post.Low.min():.2f} {post.Low.idxmin():%H:%M}",max_drop=round((1-post.Low.min()/l)*100,2),
           tight_stop=r.stop_tight,tight_hit=st.index[0].strftime('%H:%M') if len(st) else 'no',close1515=round(post.Close.iloc[-1],2),close_vs_trig=round((1-post.Close.iloc[-1]/l)*100,2)))
    else: A.append(dict(t=t,trig=l,status=r.status.split(':')[0],broke='never'))
    # ---- morning fade: push high 09:20-09:40, then targets
    w=a[a.index.strftime('%H:%M')<='09:40']; ph=w.High.max(); pt=w.High.idxmax(); aft=a[a.index>pt]
    def first(cond): 
        x=aft[cond(aft)]; return x.index[0].strftime('%H:%M') if len(x) else 'no'
    newhi=first(lambda d:d.High>ph)
    F.append(dict(t=t,o=r.o915,h=h,l=l,c=c,push_high=f"{ph:.2f} {pt:%H:%M}",push_vs_c915=round((ph/c-1)*100,2),
        hit_c915=first(lambda d:d.Low<=c),hit_l915=first(lambda d:d.Low<=l),above_push=newhi,
        low_after=f"{aft.Low.min():.2f} {aft.Low.idxmin():%H:%M}",fall_from_push=round((1-aft.Low.min()/ph)*100,2),close1515=round(aft.Close.iloc[-1],2)))
pd.set_option('display.width',250)
print(pd.DataFrame(A).to_string()); print(); print(pd.DataFrame(F).to_string())
