import pandas as pd, numpy as np
from pathlib import Path
HERE = Path(__file__).parent
r = pd.read_csv(HERE / "ema34_entry_1h_results.csv", parse_dates=["date"])
r = r[r.date >= "2024-01-01"]   # first full year of 1H coverage
def stats(x, lab):
    if len(x) < 30: return None
    w, lo = x[x.R > 0], x[x.R <= 0]
    srt = x.ret_pct.sort_values(ascending=False); tot = x.ret_pct.sum()
    yr = x.groupby(x.date.dt.year).ret_pct.mean()
    return dict(group=lab, n=len(x), stop_med=x.stop_pct.median(), win=(x.R > 0).mean()*100,
                win025=(x.R >= .25).mean()*100, mean=x.ret_pct.mean(), med=x.ret_pct.median(),
                meanR=x.R.mean(), payoff=w.R.mean()/abs(lo.R.mean()) if len(lo) else np.nan,
                top10=srt.head(10).sum()/tot*100 if tot > 0 else np.nan,
                y24=yr.get(2024), y25=yr.get(2025), y26=yr.get(2026))
def table(sub, title):
    rows = []
    for v in ("V0", "V0_leaky_target", "V1_1", "V1_2", "V1_3", "V2"):
        x = sub[sub.variant == v]
        rows += [stats(x, v)]
        if v == "V0": rows += [stats(x[x.heavy == True], "V0 heavy")]
    print(f"\n=== {title}"); print(pd.DataFrame([z for z in rows if z]).round(2).to_string(index=False))
ok = r[r.weekly.isin(["touch", "untested"])]
table(ok, "both sides, weekly touch+untested")
table(ok[ok.weekly == "touch"], "both sides, weekly TOUCH only")
for s in ("long", "short"):
    table(ok[(ok.weekly == "touch") & (ok.side == s)], f"{s}, weekly TOUCH")
# V2 split: days the daily candle went on to confirm vs fail
v0days = set(zip(r[r.variant == "V0"].ticker, r[r.variant == "V0"].date))
v2 = ok[ok.variant == "V2"].copy(); v2["confirmed"] = [(a, b) in v0days for a, b in zip(v2.ticker, v2.date)]
print("\n=== V2 split by whether the daily candle later confirmed (V0 needs this; V2 cannot know it)")
print(pd.DataFrame([stats(v2[v2.confirmed], "V2 on days that confirmed"),
                    stats(v2[~v2.confirmed], "V2 on days that failed")]).round(2).to_string(index=False))
print("\nV2 entry hour:", v2.entry_hour.value_counts(normalize=True).round(2).sort_index().to_dict())
print("V2 entry distance past EMA % (25/50/75):", v2.above_ema_pct.quantile([.25,.5,.75]).round(2).tolist())
