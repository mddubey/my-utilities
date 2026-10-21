"""Fixed 1% target (2026-10-21, asked in chat; RESULTS ONLY). Same 116 setups as room.py.
Target = entry - 1% (0.75% shown alongside), stop = spike + buffer, exit at the target, else out 14:15. Stop checked first
inside a bar. Net per Rs1k risk after ~Rs85 per Rs1 lakh. Groups as room2.py."""
import os
import pandas as pd
from room import setups
from room2 import group

BUF = [0.002, 0.0035, 0.005, 0.0075]
rows = []
for s in setups():
    day, ei, e, sp = s['day'], s['ei'], s['entry'], s['spike']
    a = day.iloc[ei + 1:]; a = a[a.index.strftime('%H:%M') <= '14:14']
    r = dict(group=group(s), date=s['date'], t=s['t'], shape=s['shape'])
    for tp in (0.0075, 0.01):
        tgt = e * (1 - tp)
        for b in BUF:
            stop = sp * (1 + b); R = stop - e; res = None
            for _, bar in a.iterrows():
                if bar.High >= stop: res = -1.0; break
                if bar.Low <= tgt: res = (e - tgt) / R; break
            if res is None: res = (e - a.Close.iloc[-1]) / R
            k = f'{tp*100:g}_{b*100:g}'
            r[f'R_{k}'] = res; r[f'net_{k}'] = 1000 * res - 85 * (1000 / R) * e / 1e5; r[f'hit_{k}'] = res > 0 and abs(res - (e - tgt) / R) < 1e-9
    rows.append(r)
x = pd.DataFrame(rows)
pd.set_option('display.width', 250)
for tp in ('0.75', '1'):
    out = []
    for g in ['ALL', 'B (no level)', 'A 09:15 high alone', 'A (all other levels)']:
        z = x if g == 'ALL' else (x[~x.group.isin(['B (no level)', 'A 09:15 high alone'])] if g.startswith('A (all') else x[x.group == g])
        d = dict(group=g, n=len(z))
        for b in BUF:
            k = f'{tp}_{b*100:g}'
            dly = z[f'net_{k}'].groupby(z.date).sum().sort_values()
            d[f'tgt_hit@{b*100:g}%'] = f"{z[f'hit_{k}'].mean()*100:.0f}%"
            d[f'stopped@{b*100:g}%'] = f"{(z[f'R_{k}'] == -1).mean()*100:.0f}%"
            d[f'net@{b*100:g}%'] = round(z[f'net_{k}'].mean())
            if g == 'ALL': d[f'woBestDay@{b*100:g}%'] = int(dly.iloc[:-1].sum())
        out.append(d)
    print(f'\nTARGET {tp}% fixed'); print(pd.DataFrame(out).to_string(index=False))
