"""Why does the short stack fail in 2026? (user, 2026-10-09). Spec fixed before running. Hypothesis: 2026's 'Nifty 8>34' days are
relief bounces inside a bigger fall. Population: the short stack (plain liquid touch, 09:15/10:15 candle, red, Nifty daily 8>34,
stock daily 8>34, ATR >= 2.56; scripts 115 v3 + 119). Split by two pre-declared LONG-term market filters, both known before the day:
  L1 Nifty close (yday) > its 200-day SMA;  L2 Nifty weekly 8-EMA > weekly 34-EMA, from the last COMPLETED week.
By year, and 2026 by month. Counts and net (Rs per Rs1 lakh after Rs85). Results only."""
import warnings
warnings.filterwarnings("ignore")
exec(open(__import__("pathlib").Path(__file__).resolve().parent / "119_stack_robustness_thresholds.py").read().split("def cell")[0])
wk = nc.resample("W-FRI").last(); wf = (wk.ewm(span=8, adjust=False).mean() > wk.ewm(span=34, adjust=False).mean())
# last completed week as of each day: the weekly flag of the PREVIOUS Friday
lt = pd.DataFrame({"l1": (nc > nc.rolling(200).mean()).shift(1)}, index=nc.index)
lt["l2"] = [bool(wf[wf.index < dd - pd.Timedelta(days=dd.weekday())].iloc[-1]) if (wf.index < dd - pd.Timedelta(days=dd.weekday())).any() else None for dd in nc.index]
S = S.join(lt, on="d")
K = S[(S.n834 == True) & (S.e8 > S.e34) & (S.atrp >= 2.56)].copy()
D = P[P.liq_prev >= 15].date.nunique()


def row(lab, g):
    if len(g) == 0: return f"| {lab} | 0 | | | | |"
    o = g.out; y = " / ".join(f"{g[g.yr == k].ret.mean()*1000 - 85:+.0f} (n{(g.yr == k).sum()})" if (g.yr == k).any() else "-" for k in ("2024", "2025", "2026"))
    return f"| {lab} | {len(g):,} | {g.date.nunique()} | {(o == 'target').mean()*100:.0f} / {(o == 'stall').mean()*100:.0f} / {(o == 'stop').mean()*100:.0f} | {g.ret.mean()*1000 - 85:+.0f} | {y} |"


print(f"stack n {len(K)} (check: 19,207)\n\n| group | setups | days | target / stall / stop % | Rs net | 2024 / 2025 / 2026 (n) |\n|---|---|---|---|---|---|")
print(row("STACK (all)", K))
for c, nm in (("l1", "Nifty > 200-day SMA"), ("l2", "Nifty weekly 8 > 34")):
    print(row(f"{nm}: YES", K[K[c] == True])); print(row(f"{nm}: NO", K[K[c] == False]))
print(row("both YES", K[(K.l1 == True) & (K.l2 == True)]))
print("\n## 2026 by month (stack)\n| month | setups | days | t/s/s % | Rs net | Nifty>200d share | weekly-up share |\n|---|---|---|---|---|---|---|")
for m, g in K[K.yr == "2026"].groupby(K.date.str[:7]):
    o = g.out
    print(f"| {m} | {len(g)} | {g.date.nunique()} | {(o=='target').mean()*100:.0f} / {(o=='stall').mean()*100:.0f} / {(o=='stop').mean()*100:.0f} | {g.ret.mean()*1000-85:+.0f} | {(g.l1==True).mean():.0%} | {(g.l2==True).mean():.0%} |")
