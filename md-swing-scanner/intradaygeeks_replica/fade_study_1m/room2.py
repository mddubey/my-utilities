"""Room study, split by level, with the user's real target (2026-10-21, spec agreed in chat; RESULTS ONLY).
Setups = room.py (shapes A / B on the 09:21 lists 2026-10-12..10-21, 1-min bars).
Groups: A stacked (crossed level has another of the six within 0.3%) > A R1/R2 > A yday high/close > A daily 8 > A 09:15 high alone; B (no level).
Target = the 09:15 close if it is below the entry, else the 09:15 low if below the entry; neither below = no target (counted, dropped).
'Reached' = target traded before 14:15 (stop ignored). Room = how far a 1-min HIGH went above the spike before the target (reached)
or until 14:15 (not reached). Trades: stop = spike + buffer, exit AT THE TARGET, else out 14:15; net per Rs1k risk after ~Rs85/lakh."""
import os
import pandas as pd
from room import setups

BUF = [0.002, 0.0035, 0.005, 0.0075]


def group(s):
    if s['shape'] == 'B': return 'B (no level)'
    if s['stacked']: return 'A stacked'
    return {'R1': 'A R1/R2', 'R2': 'A R1/R2', 'yday high': 'A yday high/close', 'yday close': 'A yday high/close',
            'daily 8': 'A daily 8', '09:15 high': 'A 09:15 high alone'}[s['level']]


rows = []
for s in setups():
    day, ei, e, sp = s['day'], s['ei'], s['entry'], s['spike']
    tgt = s['c'] if s['c'] < e else (s['l'] if s['l'] < e else None)
    g = group(s)
    if tgt is None:
        rows.append(dict(group=g, date=s['date'], t=s['t'], target=None)); continue
    a = day.iloc[ei + 1:]; a = a[a.index.strftime('%H:%M') <= '14:14']
    hit = a[a.Low <= tgt]; ht = hit.index[0] if len(hit) else None
    pre = a[a.index < ht] if ht is not None else a
    room = (pre.High.max() / sp - 1) * 100 if len(pre) else -99
    r = dict(group=g, date=s['date'], t=s['t'], level=s['level'], entry=round(e, 2), spike=round(sp, 2), target=round(tgt, 2),
             tgt_pct=round((1 - tgt / e) * 100, 2), reached=ht is not None, room_pct=round(room, 3))
    for b in BUF:
        stop = sp * (1 + b); R = stop - e; res = None
        for _, bar in a.iterrows():
            if bar.High >= stop: res = -1.0; break          # stop checked first inside a bar (conservative)
            if bar.Low <= tgt: res = (e - tgt) / R; break
        if res is None: res = (e - a.Close.iloc[-1]) / R
        r[f'R_{b*100:g}'] = round(res, 2); r[f'net_{b*100:g}'] = round(1000 * res - 85 * (1000 / R) * e / 1e5)
    rows.append(r)

x = pd.DataFrame(rows); x.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'room2_setups.csv'), index=False)
pd.set_option('display.width', 250)
print('setups', len(x), '| no target below entry (dropped):', int(x.target.isna().sum()))
y = x[x.target.notna()].copy(); y['reached'] = y.reached.astype(bool)
order = ['A stacked', 'A R1/R2', 'A yday high/close', 'A daily 8', 'A 09:15 high alone', 'B (no level)']
out = []
for g in order + ['ALL']:
    z = y if g == 'ALL' else y[y.group == g]
    if not len(z): continue
    rch = z[z.reached]
    d = dict(group=g, n=len(z), tgt_median_pct=z.tgt_pct.median(), reached=f"{z.reached.mean()*100:.0f}%",
             reached_never_above_spike=f"{(rch.room_pct <= 0).mean()*100:.0f}%" if len(rch) else '-',
             room90_reached=round(rch.room_pct.quantile(.9), 2) if len(rch) else None,
             room_median_not_reached=round(z[~z.reached].room_pct.median(), 2) if (~z.reached).any() else None)
    for b in BUF:
        k = f'{b*100:g}'; d[f'win@{k}%'] = f"{(z[f'R_{k}'] > 0).mean()*100:.0f}%"; d[f'net@{k}%'] = round(z[f'net_{k}'].mean())
    out.append(d)
print(pd.DataFrame(out).to_string(index=False))
