"""Post-spike stocks: do the days after a news / results spike fade? (ORIENTELEC 2026-10-15 type; spec agreed in chat 2026-10-21;
RESULTS ONLY, nothing goes to STRATEGY.md.)

Spike day D: close >= +X% vs the previous close AND volume >= Y x the median volume of the 20 days before D.
  Variants fixed before running: +5% / 5x, +8% / 10x (main), +12% / 20x.
Filters on each day AFTER (known the evening before it, like the 09:21 list prep -- so the spike's own volume counts, which lets
  a stock that was thin before its results in, e.g. ORIENTELEC): prior close >= Rs100, 20-day traded value >= Rs10 cr, 14-day ATR >= 2%.
  (First run filtered on D itself and dropped ORIENTELEC 2026-10-15 -- fixed 2026-10-22.)
Days after (D+1, D+2, D+3, each shown alone): red day (close < open), close off the day's high %, open -> close %, gap %.
Baseline: every other stock-day passing the same filters that is not within 3 days after any +5%/5x spike.
Years shown separately (2023-10..2026-10, daily data).
Part 2 (5-min cache, 2026-06-10 on, D+1 / D+2 with prior-day median 5-min turnover >= Rs15 lakh): the morning high 09:20-09:40 --
  did price later trade back to the 09:15 close (when that close is below the morning high) by 14:15, and the fade from the
  morning high to the 14:15 low. Baseline = other liquid stock-days, and an in-play proxy (09:20-09:30 turnover >= 3x its 5-day median; Yahoo's 09:15 bar carries no volume).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd, numpy as np
from multiprocessing import Pool
from data.paths import DAILY_DIR, INTRADAY_5M_DIR

VAR = {'5%/5x': (0.05, 5), '8%/10x': (0.08, 10), '12%/20x': (0.12, 20)}
START = pd.Timestamp('2023-10-01')


def daily_one(t):
    try:
        d = pd.read_csv(DAILY_DIR / f'{t}.csv', index_col=0, parse_dates=True)[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
    except Exception:
        return None
    if len(d) < 60: return None
    pc = d.Close.shift()
    d['chg'] = d.Close / pc - 1
    d['vmult'] = d.Volume / d.Volume.shift().rolling(20).median()
    d['tv20'] = (d.Close * d.Volume).shift().rolling(20).mean()
    tr = pd.concat([d.High - d.Low, (d.High - pc).abs(), (d.Low - pc).abs()], axis=1).max(axis=1)
    d['atr'] = (tr.rolling(14).mean() / d.Close).shift()
    d['ok'] = (pc >= 100) & (d.tv20 >= 1e8) & (d.atr >= 0.02) & (d.chg.abs() < 0.4)
    d['red'] = d.Close < d.Open
    d['off_high'] = (d.High - d.Close) / d.High * 100
    d['oc'] = (d.Close / d.Open - 1) * 100
    d['gap'] = (d.Open / pc - 1) * 100
    d['t'] = t
    for k, (x, y) in VAR.items():
        d[f'spk_{k}'] = (pc >= 100) & (d.chg >= x) & (d.chg < 0.4) & (d.vmult >= y)
    return d[d.index >= START - pd.Timedelta(days=40)]


def stats(g):
    return pd.Series(dict(n=len(g), red=f'{g.red.mean() * 100:.0f}%', off_high=round(g.off_high.median(), 2),
                          oc=round(g.oc.median(), 2), oc_mean=round(g.oc.mean(), 2), gap=round(g.gap.median(), 2)))


def fivemin_one(args):
    t, dates = args
    try:
        m = pd.read_csv(INTRADAY_5M_DIR / f'{t}.csv', index_col=0, parse_dates=True)
    except Exception:
        return []
    m.index = m.index.tz_convert('Asia/Kolkata').tz_localize(None)
    m['to'] = m.Close * m.Volume; m['day'] = m.index.normalize()
    days = sorted(m.day.unique()); out = []
    med = m.groupby('day').to.median()
    first = m[(m.index.strftime('%H:%M') >= '09:20') & (m.index.strftime('%H:%M') <= '09:30')].groupby('day').to.sum()   # Yahoo's 09:15 bar has no volume
    for i, dy in enumerate(days):
        if i < 5: continue
        if med.get(days[i - 1], 0) < 15e5: continue
        b = m[m.day == dy]; hm = b.index.strftime('%H:%M')
        if len(b) < 60 or hm[0] != '09:15': continue
        c915 = b.Close.iat[0]
        mor = b[(hm >= '09:20') & (hm <= '09:40')]
        if not len(mor): continue
        mh = mor.High.max(); mt = mor.High.idxmax()
        rest = b[(b.index > mt) & (hm <= '14:14')]
        if not len(rest): continue
        f5 = first.reindex(days[i - 5:i]).median()
        out.append(dict(t=t, date=pd.Timestamp(dy), inplay=bool(first.get(dy, 0) >= 3 * f5) if f5 and f5 > 0 else False,
                        tag=dates.get(pd.Timestamp(dy), 'base'),
                        back_to_c915=bool((rest.Low <= c915).any()) if c915 < mh else np.nan,
                        fade_pct=(1 - rest.Low.min() / mh) * 100))
    return out


if __name__ == '__main__':
    tick = sorted(p.stem for p in DAILY_DIR.glob('*.csv') if not p.stem.startswith('_'))
    with Pool(6) as pool:
        parts = [r for r in pool.imap_unordered(daily_one, tick, chunksize=25) if r is not None]
    after_rows, base_rows, spikes = [], [], []
    for d in parts:
        excl = pd.Series(False, index=d.index)
        for k in (1, 2, 3): excl |= d['spk_5%/5x'].shift(k, fill_value=False)
        base = d[d.ok & ~excl & ~d['spk_5%/5x'] & (d.index >= START)]
        base_rows.append(base[['t', 'red', 'off_high', 'oc', 'gap']].assign(year=base.index.year))
        for v in VAR:
            for k in (1, 2, 3):
                aft = d[d[f'spk_{v}'].shift(k, fill_value=False) & d.ok & (d.index >= START)]
                after_rows.append(aft[['t', 'red', 'off_high', 'oc', 'gap']].assign(year=aft.index.year, var=v, k=f'D+{k}', date=aft.index))
        sp = d[d['spk_8%/10x'] & d.ok.shift(-1, fill_value=False) & (d.index >= START)]
        spikes.append(sp[['t', 'chg', 'vmult']].assign(date=sp.index))
    A = pd.concat(after_rows); B = pd.concat(base_rows); SP = pd.concat(spikes)
    pd.set_option('display.width', 220)
    print('spike days (8%/10x):', len(SP), '| baseline stock-days:', len(B))
    print('\nHAND CHECK ORIENTELEC:'); print(SP[SP.t == 'ORIENTELEC'].tail(3).round(3).to_string())
    print('\nBASELINE'); print(stats(B).to_frame().T.to_string(index=False))
    print('\nDAYS AFTER A SPIKE (all years)'); print(A.groupby(['var', 'k']).apply(stats).to_string())
    print('\nBY YEAR -- 8%/10x vs baseline (red-day rate / median open->close)')
    by = A[A['var'] == '8%/10x'].groupby(['k', 'year']).apply(stats)[['n', 'red', 'oc']].unstack('k')
    by_b = B.groupby('year').apply(stats)[['n', 'red', 'oc']]; by_b.columns = pd.MultiIndex.from_product([by_b.columns, ['base']])
    print(pd.concat([by, by_b], axis=1).to_string())

    # part 2: 5-min, D+1 / D+2 of 8%/10x spikes since 2026-06-10
    tags = {}
    for _, r in A[(A['var'] == '8%/10x') & A.k.isin(['D+1', 'D+2']) & (A.date >= '2026-06-11')].iterrows():
        tags.setdefault(r.t, {})[pd.Timestamp(r.date)] = r.k
    have5 = {p.stem for p in INTRADAY_5M_DIR.glob('*.csv')}
    jobs = [(t, tags.get(t, {})) for t in tick if t in have5]
    with Pool(6) as pool:
        F = pd.DataFrame([r for rs in pool.imap_unordered(fivemin_one, jobs, chunksize=20) for r in rs])
    def s2(g):
        return pd.Series(dict(n=len(g), back_to_0915_close=f"{g.back_to_c915.mean() * 100:.0f}%", fade_from_morning_high_med=round(g.fade_pct.median(), 2)))
    print('\nPART 2 (5-min, 2026-06-10 on): morning high 09:20-09:40 -> back to the 09:15 close by 14:15')
    out = pd.concat([F[F.tag != 'base'].groupby('tag').apply(s2), s2(F[(F.tag == 'base') & F.inplay]).rename('base in-play proxy').to_frame().T,
                     s2(F[F.tag == 'base']).rename('base all liquid').to_frame().T])
    print(out.to_string())
    A.to_csv(Path(__file__).resolve().parent / 'spike_after_days.csv', index=False)
