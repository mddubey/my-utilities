"""Replay one live day's 09:21 ORB list on 1-minute bars, every type (2026-10-21). Usage: python3 replay_day.py YYYY-MM-DD scan.csv
1) fetch that day's 1-min bars for the list (MERGED into m1/, never overwriting the older days -- Yahoo keeps ~30 days only);
2) the day table (09:15 candle, hit 09:15 close / low, day high / low);
3) morning fade shapes A / B exactly as shapes.py, held to 14:15 or the stop, plus package (a) (stop to entry after +2R);
4) ORB sell-stop / buy-stop for every row not SKIPped: trigger from 09:30, tight and wide stops, out 14:15 and 15:15.
Descriptive replay of already-agreed definitions -- results only."""
import sys, re, os, warnings
import pandas as pd, yfinance as yf
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, '..', '..', 'data', 'daily') + '/'
date, scan = sys.argv[1], sys.argv[2]
sc = pd.read_csv(scan)
rx = re.compile(r'([\d.]+)->([\d.]+) \(L ([\d.]+) H ([\d.]+)\)')

# 1) fetch + merge
nxt = (pd.Timestamp(date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
d = yf.download([t + '.NS' for t in sc.ticker], start=date, end=nxt, interval='1m', group_by='ticker', progress=False, auto_adjust=False, threads=True)
miss = []
for t in sc.ticker:
    try:
        x = d[t + '.NS'].dropna(how='all')
        if not len(x): miss.append(t); continue
        x.index = x.index.tz_convert('Asia/Kolkata').tz_localize(None)
        fn = os.path.join(HERE, 'm1', f'{t}.csv')
        if os.path.exists(fn):
            old = pd.read_csv(fn, index_col=0, parse_dates=True)
            x = pd.concat([old[old.index.strftime('%Y-%m-%d') != date], x]).sort_index()
        x.to_csv(fn)
    except KeyError: miss.append(t)
print('1-min missing:', miss or 'none')


def day1m(t):
    m = pd.read_csv(os.path.join(HERE, 'm1', f'{t}.csv'), index_col=0, parse_dates=True)
    return m[m.index.strftime('%Y-%m-%d') == date]


def outcome(day, ei, entry, stop, c915, l915, side=-1, cut='14:14'):
    """side -1 = short. Returns hold-to-cut R, package-a R (BE after +2R), stop time, t1/t2 times, best R."""
    a = day.iloc[ei + 1:]; a = a[a.index.strftime('%H:%M') <= '15:14']
    R = abs(stop - entry)
    adverse = (a.High >= stop) if side < 0 else (a.Low <= stop)
    st = a.index[adverse.values.argmax()] if adverse.any() else None
    pre = a[a.index < st] if st is not None else a
    fav = (entry - pre.Low.min()) if side < 0 else (pre.High.max() - entry)
    def first(lv):
        if side > 0 or lv >= entry: return 'below' if side < 0 else '-'
        x = pre[pre.Low <= lv]; return x.index[0].strftime('%H:%M') if len(x) else 'no'
    ac = a[a.index.strftime('%H:%M') <= cut]
    hold = -1.0 if (st is not None and st.strftime('%H:%M') <= cut) else (entry - ac.Close.iloc[-1]) / R * (1 if side < 0 else -1)
    # package (a): stop -> entry once +2R reached (checked bar by bar, stop first)
    cur, be, pa = stop, False, None
    for ts, b in ac.iterrows():
        if (side < 0 and b.High >= cur) or (side > 0 and b.Low <= cur): pa = 0.0 if be else -1.0; break
        if not be and ((side < 0 and b.Low <= entry - 2 * R) or (side > 0 and b.High >= entry + 2 * R)): cur, be = entry, True
    if pa is None: pa = (entry - ac.Close.iloc[-1]) / R * (1 if side < 0 else -1)
    return dict(stop_hit=st.strftime('%H:%M') if st is not None else 'no', t1=first(c915), t2=first(l915),
                best_R=round(fav / R, 1), hold1415_R=round(hold, 2), pkgA_R=round(pa, 2), risk_pct=round(R / entry * 100, 2))


rows, A, B, ORB = [], [], [], []
for _, r in sc.iterrows():
    t = r.ticker; o, c, l, h = map(float, rx.search(r.c915).groups())
    day = day1m(t) if os.path.exists(os.path.join(HERE, 'm1', f'{t}.csv')) else pd.DataFrame()
    if len(day) < 200: continue
    tm = day.index.strftime('%H:%M'); idx = {x: i for i, x in enumerate(tm)}
    a = day[tm >= '09:20']
    rows.append(dict(rank=r['rank'], t=t, c915='red' if c < o else 'green', o=o, h=h, l=l, c=c,
                     above_915H=a[a.High > h].index[0].strftime('%H:%M') if (a.High > h).any() else 'N',
                     hit_915C=a[a.Low <= c].index[0].strftime('%H:%M') if (a.Low <= c).any() else 'N',
                     hit_915L=a[a.Low < l].index[0].strftime('%H:%M') if (a.Low < l).any() else 'N',
                     dayH=f"{a.High.max():.2f} {a.High.idxmax():%H:%M}", dayL=f"{a.Low.min():.2f} {a.Low.idxmin():%H:%M}",
                     close=round(day.Close.iloc[-1], 2)))
    dd = pd.read_csv(D + t + '.csv', parse_dates=['Date']); dd = dd[dd.Date < date]
    y = dd.iloc[-1]; pp = (y.High + y.Low + y.Close) / 3
    lv = {'09:15 high': h, 'yday high': y.High, 'yday close': y.Close, 'R1': 2 * pp - y.Low, 'R2': pp + (y.High - y.Low),
          'daily 8': dd.Close.ewm(span=8, adjust=False).mean().iloc[-1]}
    w = day[(tm >= '09:20') & (tm <= '09:45')]
    # B (as shapes.py)
    if c < o and len(w):
        pk = w.High.max(); pt = w.High.idxmax()
        if pk < h:
            before = day[(day.index <= pt) & (tm >= '09:20')]; L0 = min(l, before.Low.min())
            if pk / L0 - 1 >= 0.003:
                aft = day[(day.index > pt) & (day.index.strftime('%H:%M') <= '10:00')]
                e = aft[aft.Close <= pk * 0.998]; nh = aft[aft.High > pk]
                if len(e) and (not len(nh) or nh.index[0] > e.index[0]):
                    et = e.index[0]; entry = e.Close.iloc[0]; stop = pk * 1.0005
                    B.append(dict(t=t, rank=r['rank'], peak=f'{pk:.2f} {pt:%H:%M}', bounce_pct=round((pk / L0 - 1) * 100, 2), entry=round(entry, 2),
                                  at=et.strftime('%H:%M'), stop=round(stop, 2), **outcome(day, idx[et.strftime('%H:%M')], entry, stop, c, l)))
    # A (as shapes.py) -- 2026-10-23 (user): the list is only seen at 09:21, so a poke counts only if it starts from 09:21 with price
    # still under the level at 09:21 (a 09:15 / 09:20 poke cannot be traded); EVERY level is its own event (a later stack poke counts too)
    w21 = day[(tm >= '09:21') & (tm <= '09:45')]
    p0 = day.iloc[idx.get('09:21', 6)].Open
    for name, L in lv.items():
        if L <= p0: continue
        cr = w21[w21.High > L]
        if not len(cr): continue
        ct = cr.index[0]; win = day[(day.index >= ct) & (day.index <= ct + pd.Timedelta('10min'))]
        back = win[win.Close < L]
        if not len(back): continue
        et = back.index[0]; sp = day[(day.index >= ct) & (day.index <= et)].High.max(); entry = day.loc[et].Close; stop = sp * 1.0005
        A.append(dict(t=t, rank=r['rank'], first915='red' if c < o else 'green', level=f'{name} {L:.2f}', crossed=ct.strftime('%H:%M'), spike=round(sp, 2),
                      entry=round(entry, 2), at=et.strftime('%H:%M'), stop=round(stop, 2), **outcome(day, idx[et.strftime('%H:%M')], entry, stop, c, l)))
    # ORB stop orders (rows not skipped), live from 09:30
    if not str(r.status).startswith('SKIP'):
        short = str(r.side).upper().startswith('SHORT'); trig = float(r.trigger)
        aa = day[tm >= '09:30']
        hit = aa[aa.Low <= trig] if short else aa[aa.High >= trig]
        if len(hit):
            et = hit.index[0]; ei = idx[et.strftime('%H:%M')]
            for kind, stp in (('tight', float(r.stop_tight)), ('wide', float(r.stop_wide))):
                o14 = outcome(day, ei, trig, stp, c, l, side=-1 if short else 1, cut='14:14')
                o15 = outcome(day, ei, trig, stp, c, l, side=-1 if short else 1, cut='15:14')
                ORB.append(dict(t=t, rank=r['rank'], side='short' if short else 'long(info)', stop_kind=kind, trigger=trig, at=et.strftime('%H:%M'),
                                stop=stp, risk_pct=o14['risk_pct'], stop_hit=o14['stop_hit'], best_R=o14['best_R'], R_1415=o14['hold1415_R'], R_1515=o15['hold1415_R']))
        else:
            ORB.append(dict(t=t, rank=r['rank'], side='short' if short else 'long(info)', stop_kind='-', trigger=trig, at='never'))

pd.set_option('display.width', 300); pd.set_option('display.max_rows', 300)
for nm, X in (('DAY', rows), ('SHAPE B', B), ('SHAPE A', A), ('ORB STOP ORDERS', ORB)):
    x = pd.DataFrame(X); print(f'\n{nm} ({len(x)})'); print(x.to_string(index=False) if len(x) else '  none')
