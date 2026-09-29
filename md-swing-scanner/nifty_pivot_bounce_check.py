"""Ad hoc (2026-09-27, user question re: was RBLBANK-adjacent NIFTY 09-22 S1/S2-touch-then-
bounce-to-PP a real, repeatable pattern or a lucky one-off): full 5-year NIFTY daily history,
real floor-trader pivots (same formula as pivots.py, computed from the PRIOR day's H/L/C, no
lookahead). Checks whether a day whose Low touches S1/S2 tends to bounce back toward/through
PP, and by how much, vs. an ordinary day's own intraday range -- the core mechanism behind
the Sept 22 case, tested at scale rather than assumed from one example.
"""
import pandas as pd

df = pd.read_csv("data_cache/_NIFTY.csv")
df["Date"] = pd.to_datetime(df.Date)

h, l, c = df.High.shift(1), df.Low.shift(1), df.Close.shift(1)
df["pp"] = (h + l + c) / 3
df["r1"] = 2 * df.pp - l
df["s1"] = 2 * df.pp - h
df["r2"] = df.pp + (h - l)
df["s2"] = df.pp - (h - l)

df = df.dropna(subset=["pp"]).reset_index(drop=True)

touched_s1 = df.Low <= df.s1
touched_s2 = df.Low <= df.s2
touched_r1 = df.High >= df.r1
touched_r2 = df.High >= df.r2

df["intraday_range_pct"] = (df.High - df.Low) / df.Low * 100
df["bounce_to_pp"] = df.High >= df.pp          # for support touches: did it recover to/through PP?
df["pullback_to_pp"] = df.Low <= df.pp         # for resistance touches: did it pull back to/through PP?
df["low_to_high_pct"] = (df.High - df.Low) / df.Low * 100
df["low_to_close_pct"] = (df.Close - df.Low) / df.Low * 100
df["high_to_close_pct"] = (df.Close - df.High) / df.High * 100

print(f"Full history: {len(df)} trading days, {df.Date.min().date()} to {df.Date.max().date()}")
print()

for label, mask in [("Touched S1 (Low<=S1)", touched_s1), ("Touched S2 (Low<=S2)", touched_s2)]:
    sub = df[mask]
    print(f"=== {label}: n={len(sub)} ({len(sub)/len(df)*100:.1f}% of all days) ===")
    print(f"  % that bounced back to/through PP same day: {sub.bounce_to_pp.mean()*100:.1f}%")
    print(f"  median intraday range (Low->High): {sub.low_to_high_pct.median():.2f}%")
    print(f"  median recovery Low->Close: {sub.low_to_close_pct.median():.2f}%")
    print()

print(f"=== BASELINE, ALL days: n={len(df)} ===")
print(f"  median intraday range (Low->High): {df.low_to_high_pct.median():.2f}%")
print(f"  median recovery Low->Close: {df.low_to_close_pct.median():.2f}%")
print()

for label, mask in [("Touched R1 (High>=R1)", touched_r1), ("Touched R2 (High>=R2)", touched_r2)]:
    sub = df[mask]
    print(f"=== {label}: n={len(sub)} ({len(sub)/len(df)*100:.1f}% of all days) ===")
    print(f"  % that pulled back to/through PP same day: {sub.pullback_to_pp.mean()*100:.1f}%")
    print(f"  median intraday range (Low->High): {sub.low_to_high_pct.median():.2f}%")
    print(f"  median High->Close pullback: {sub.high_to_close_pct.median():.2f}%")
    print()

# concentration/sanity check
s = df[touched_s1].low_to_high_pct.sort_values(ascending=False)
top10_share = s.head(10).sum() / s.sum() * 100 if s.sum() else float("nan")
print(f"concentration check (S1-touch population, top10/total low_to_high_pct sum): {top10_share:.1f}%  n={len(s)}")
