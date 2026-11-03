"""Replay one live day's 09:21 ORB list on 1-minute bars (2026-10-21; shapes A/B removed 2026-11-02). Usage: python3 replay_day.py YYYY-MM-DD scan.csv
1) fetch that day's 1-min bars for the list (MERGED into m1/, never overwriting the older days -- Yahoo keeps ~30 days only);
2) the day table (09:15 candle, hit 09:15 close / low, day high / low);
3) FLAGGED LEVELS -- held or broke: the nearest 4 levels above the 09:21 price -- the scan's FADE LEVELS (09:15 high,
   yday high / close, daily R1 / R2, daily 8) plus weekly / monthly PP R1 R2; STACK = another level within 0.3%. First tag 09:21-10:30, then whichever comes
   first by 14:14: HELD = a 1% fall below the level before any high 0.5% over it (the user's buffer stop); BROKE = 0.5% over it
   first; STALL = neither. Also the overshoot before the fall, the deepest fall to 14:14 and Nifty's move from its 09:15 open
   at the tag (squeeze context). Descriptive -- which levels held, not a strategy;
4) ORB sell-stop / buy-stop for every row not SKIPped: trigger from 09:30, tight and wide stops, out 14:15 and 15:15.
Shapes A / B (mechanical first-touch fades) removed 2026-11-02: the user does not trade them (and B had lookahead)."""
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
nf = yf.download('^NSEI', start=date, end=nxt, interval='1m', progress=False, auto_adjust=False)
nf.columns = nf.columns.get_level_values(0); nf.index = nf.index.tz_convert('Asia/Kolkata').tz_localize(None)
n_open = nf.Open.iloc[0] if len(nf) else None


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


def level_fate(day, L, p0):
    """First tag 09:21-10:30, then HELD (1% fall first) / BROKE (0.5% over first) / STALL by 14:14."""
    tm = day.index.strftime('%H:%M')
    w = day[(tm >= '09:21') & (tm <= '10:30') & (day.High >= L)]
    if not len(w): return dict(tagged='no')
    tt = w.index[0]; a = day[(day.index >= tt) & (tm <= '14:14')]
    br = a[a.High >= L * 1.005]; fl = a[a.Low <= L * 0.99]
    bt = br.index[0] if len(br) else None; ft = fl.index[0] if len(fl) else None
    if ft is not None and (bt is None or ft < bt): fate, at = 'HELD', ft
    elif bt is not None: fate, at = 'BROKE', bt
    else: fate, at = 'STALL', None
    pre = a[a.index <= at] if at is not None else a
    nif = day_nifty_chg(tt)
    return dict(tagged=tt.strftime('%H:%M'), fate=fate, at=at.strftime('%H:%M') if at is not None else '',
                over_pct=round((pre.High.max() / L - 1) * 100, 2), max_fall_pct=round((1 - a.Low.min() / L) * 100, 2),
                nifty_at_tag=f'{nif:+.2f}%' if nif is not None else '')


def day_nifty_chg(ts):
    if n_open is None: return None
    x = nf[nf.index <= ts]
    return (x.Close.iloc[-1] / n_open - 1) * 100 if len(x) else None


rows, LV, ORB = [], [], []
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
    # weekly / monthly pivots too (the user's 1H / 1D chart levels -- MUTHOOTFIN 11-02 was a W-R1 stack, not on the scan)
    dt = pd.Timestamp(date); di = dd.set_index('Date')
    wk = di[di.index < dt - pd.Timedelta(days=dt.weekday())]; wk = wk[wk.index >= wk.index[-1] - pd.Timedelta(days=wk.index[-1].weekday())]
    mo = di[di.index < dt.replace(day=1)]; mo = mo[mo.index >= mo.index[-1].replace(day=1)]
    for tf, (hh, ll, cc) in (('W', (wk.High.max(), wk.Low.min(), wk.Close.iloc[-1])), ('M', (mo.High.max(), mo.Low.min(), mo.Close.iloc[-1]))):
        p_ = (hh + ll + cc) / 3; lv.update({f'{tf}-PP': p_, f'{tf}-R1': 2 * p_ - ll, f'{tf}-R2': p_ + (hh - ll)})
    # flagged levels (the scan's FADE LEVELS + W/M pivots: nearest 4 above the 09:21 price) -- held or broke
    p0 = day.iloc[idx.get('09:21', 6)].Open
    above = sorted((L, name) for name, L in lv.items() if L > p0)[:4]
    for L, name in above:
        near = [n for v, n in above if n != name and abs(v / L - 1) <= 0.003]
        LV.append(dict(t=t, rank=r['rank'], c915='red' if c < o else 'green', level=f'{name} {L:.2f}', dist_pct=round((L / p0 - 1) * 100, 2),
                       stack='+'.join(near), **level_fate(day, L, p0)))
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
for nm, X in (('DAY', rows), ('FLAGGED LEVELS -- held or broke (tag 09:21-10:30; HELD = -1% before +0.5%)', LV), ('ORB STOP ORDERS', ORB)):
    x = pd.DataFrame(X); print(f'\n{nm} ({len(x)})'); print(x.to_string(index=False) if len(x) else '  none')
x = pd.DataFrame(LV)
if len(x) and 'fate' in x:
    tg = x[x.tagged != 'no']; tg = tg.assign(kind=(tg['stack'] != '').map({True: 'stacked', False: 'single'}))
    print('\nSUMMARY (tagged levels):'); print(tg.groupby('kind').fate.value_counts().unstack(fill_value=0).to_string())
