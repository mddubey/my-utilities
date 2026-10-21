"""How much room does a morning-fade stop need? (2026-10-21, spec agreed in chat; RESULTS ONLY)
Setups = shapes A / B exactly as shapes.py, on the saved 09:21 lists 2026-10-12..10-21, 1-minute bars (m1/).
'Worked' = price falls >= 0.75% below entry before 14:15 (fixed before running, independent of any stop).
1) adverse excursion ABOVE THE SPIKE HIGH before working (winners) / until 14:15 (non-winners), in % of the spike;
2) retest cue: dip >= 0.2% under entry, then back within 0.15% of the spike before the target -- lower high or poke above;
3) buffers beyond the spike 0.2 / 0.35 / 0.5 / 0.75 % and 10 / 20 % of daily ATR: package (a) (stop to entry after +2R,
   out 14:15), net per Rs1k risk after ~Rs85 per Rs1 lakh."""
import re, os
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.join(HERE, '..', 'orb_scans') + '/'
D = os.path.join(HERE, '..', '..', 'data', 'daily') + '/'
F = {'2026-10-12': 'orb_scan_20261012_0921.csv', '2026-10-13': 'orb_scan_20261013_0922.csv', '2026-10-14': 'orb_scan_20261014_0921.csv',
     '2026-10-15': 'orb_scan_20261015_0921.csv', '2026-10-16': 'orb_scan_20261016_0921.csv', '2026-10-19': 'orb_scan_20261019_0921.csv',
     '2026-10-21': 'orb_scan_20261021_0921.csv'}
rx = re.compile(r'([\d.]+)->([\d.]+) \(L ([\d.]+) H ([\d.]+)\)')
WORK, DIP, NEAR = 0.0075, 0.002, 0.0015


def setups():
    out = []
    for date, f in F.items():
        sc = pd.read_csv(S + f)
        for _, r in sc.iterrows():
            t = r.ticker; o, c, l, h = map(float, rx.search(r.c915).groups())
            fn = os.path.join(HERE, 'm1', f'{t}.csv')
            if not os.path.exists(fn): continue
            m = pd.read_csv(fn, index_col=0, parse_dates=True); day = m[m.index.strftime('%Y-%m-%d') == date]
            if len(day) < 200: continue
            dd = pd.read_csv(D + t + '.csv', parse_dates=['Date']); dd = dd[dd.Date < date]
            y = dd.iloc[-1]; pp = (y.High + y.Low + y.Close) / 3
            tr = pd.concat([dd.High - dd.Low, (dd.High - dd.Close.shift()).abs(), (dd.Low - dd.Close.shift()).abs()], axis=1).max(axis=1)
            atr_pct = tr.tail(14).mean() / y.Close
            lv = {'09:15 high': h, 'yday high': y.High, 'yday close': y.Close, 'R1': 2 * pp - y.Low, 'R2': pp + (y.High - y.Low),
                  'daily 8': dd.Close.ewm(span=8, adjust=False).mean().iloc[-1]}
            tm = day.index.strftime('%H:%M'); idx = {x: i for i, x in enumerate(tm)}
            w = day[(tm >= '09:20') & (tm <= '09:45')]
            if c < o and len(w):
                pk = w.High.max(); pt = w.High.idxmax()
                if pk < h:
                    before = day[(day.index <= pt) & (tm >= '09:20')]; L0 = min(l, before.Low.min())
                    if pk / L0 - 1 >= 0.003:
                        aft = day[(day.index > pt) & (day.index.strftime('%H:%M') <= '10:00')]
                        e = aft[aft.Close <= pk * 0.998]; nh = aft[aft.High > pk]
                        if len(e) and (not len(nh) or nh.index[0] > e.index[0]):
                            et = e.index[0]
                            out.append(dict(date=date, t=t, shape='B', c915='red', level='none', stacked=False, c=c, l=l, spike=pk, entry=e.Close.iloc[0], ei=idx[et.strftime('%H:%M')], at=et.strftime('%H:%M'), atr=atr_pct, day=day))
            p0 = day.iloc[idx.get('09:20', 5)].Open; best = None
            for name, L in lv.items():
                if L <= p0: continue
                cr = w[w.High > L]
                if not len(cr): continue
                ct = cr.index[0]; win = day[(day.index >= ct) & (day.index <= ct + pd.Timedelta('10min'))]
                back = win[win.Close < L]
                if not len(back): continue
                et = back.index[0]
                if best is None or et < best[2]: best = (name, L, et, ct)
            if best:
                name, L, et, ct = best; sp = day[(day.index >= ct) & (day.index <= et)].High.max()
                stk = any(abs(v / L - 1) <= 0.003 for k, v in lv.items() if k != name)
                out.append(dict(date=date, t=t, shape='A', c915='red' if c < o else 'green', level=name, stacked=stk, c=c, l=l, spike=sp, entry=day.loc[et].Close, ei=idx[et.strftime('%H:%M')],
                                at=et.strftime('%H:%M'), atr=atr_pct, day=day))
    return out


def path(s):
    day, ei, e, sp = s['day'], s['ei'], s['entry'], s['spike']
    a = day.iloc[ei + 1:]; a = a[a.index.strftime('%H:%M') <= '14:14']
    tgt = e * (1 - WORK); hitw = a[a.Low <= tgt]; wt = hitw.index[0] if len(hitw) else None
    pre = a[a.index < wt] if wt is not None else a
    mae = (pre.High.max() / sp - 1) * 100 if len(pre) else 0.0
    # retest cue
    dipped = pre[pre.Low <= e * (1 - DIP)]; retest = None
    if len(dipped):
        after = pre[pre.index > dipped.index[0]]; rt = after[after.High >= sp * (1 - NEAR)]
        if len(rt): retest = 'poke above' if rt.High.max() > sp else 'lower high'
    return dict(worked=wt is not None, mae_above_spike_pct=round(mae, 3), retest=retest or 'none',
                mins_to_work=int((wt - day.index[ei]).total_seconds() / 60) if wt is not None else None)


def pkg_a(s, stop):
    day, ei, e = s['day'], s['ei'], s['entry']; R = stop - e
    a = day.iloc[ei + 1:]; a = a[a.index.strftime('%H:%M') <= '14:14']
    cur, be = stop, False
    for _, b in a.iterrows():
        if b.High >= cur: return 0.0 if be else -1.0
        if not be and b.Low <= e - 2 * R: cur, be = e, True
    return (e - a.Close.iloc[-1]) / R


if __name__ == '__main__':
    S_ = setups(); rows = []
    for s in S_:
        p = path(s); r = {k: v for k, v in s.items() if k not in ('day', 'ei')}; r.update(p)
        for nm, stop in [('0.2%', s['spike'] * 1.002), ('0.35%', s['spike'] * 1.0035), ('0.5%', s['spike'] * 1.005), ('0.75%', s['spike'] * 1.0075),
                         ('10%ATR', s['spike'] * (1 + 0.10 * s['atr'])), ('20%ATR', s['spike'] * (1 + 0.20 * s['atr']))]:
            R = pkg_a(s, stop); cost = 85 * (1000 / (stop - s['entry'])) * s['entry'] / 1e5
            r[f'R_{nm}'] = round(R, 2); r[f'net_{nm}'] = round(1000 * R - cost)
        rows.append(r)
    x = pd.DataFrame(rows); x.to_csv(os.path.join(HERE, 'room_setups.csv'), index=False)
    pd.set_option('display.width', 250)
    print('setups', len(x), x.groupby(['shape', 'c915']).size().to_dict(), '| worked', int(x.worked.sum()))
    print('\n1) ADVERSE EXCURSION ABOVE THE SPIKE (%), before working / until 14:15')
    q = [.5, .75, .9, 1.0]
    for w_, g in x.groupby('worked'):
        print(('WORKED' if w_ else 'NEVER WORKED').ljust(13), 'n', len(g), ' quantiles', [round(g.mae_above_spike_pct.quantile(v), 2) for v in q],
              ' share <=0', f"{(g.mae_above_spike_pct <= 0).mean() * 100:.0f}%")
    print('   ATR% of setups: median', round(x.atr.median() * 100, 2))
    print('\n2) RETEST CUE among winners'); print(x[x.worked].retest.value_counts().to_string())
    print('   among non-winners'); print(x[~x.worked].retest.value_counts().to_string())
    print('   mins to work (winners) median', x[x.worked].mins_to_work.median())
    print('\n3) BUFFERS (package a, out 14:15), per Rs1k risk')
    res = []
    for nm in ['0.2%', '0.35%', '0.5%', '0.75%', '10%ATR', '20%ATR']:
        n = x[f'net_{nm}']; dly = n.groupby(x.date).sum().sort_values()
        res.append(dict(buffer=nm, win=f"{(x[f'R_{nm}'] > 0).mean() * 100:.0f}%", stopped=f"{(x[f'R_{nm}'] == -1).mean() * 100:.0f}%",
                        avgR=round(x[f'R_{nm}'].mean(), 2), net_per_trade=round(n.mean()), net_total=int(n.sum()), wo_top5_trades=int(n.sort_values().iloc[:-5].sum()),
                        wo_best_day=int(dly.iloc[:-1].sum())))
    print(pd.DataFrame(res).to_string(index=False))
    for sh, g in x.groupby('shape'):
        print(f'\n   shape {sh} (n {len(g)}): net per trade', {nm: round(g[f"net_{nm}"].mean()) for nm in ['0.2%', '0.35%', '0.5%', '0.75%', '10%ATR', '20%ATR']})
