"""Full-hour trigger at the hour-close alarms (user, 2026-10-04): the setup is the 1H rejection; the 30-min check at
10:45 / 11:45 is an early look at the hour so far. At 11:15 / 12:15 the trigger candle becomes the FULL hour
(10:15-11:15 / 11:15-12:15): open = hour open, high = hour high (= stop), close = hour close. Same checklist, 2:1 rule,
exits. 10:45 / 11:45 unchanged. Set a (30m) only; set b already is the full-hour version. Output: full_hour_trigger.csv
(new rows); compare with stop_rate_filters.csv set a (old rows, script 67)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
s67 = open(HERE / "67_stop_rate_filters.py").read()
head, tail = s67.split('exec(compile(src, "63mod", "exec"))', 1)
head += '''src = src.replace("qi = np.where(k30 == q)[0]", "qi = np.where((k30 == q) | ((k30 == q - 1) & (q % 2 == 1)))[0]", 1)
assert "(k30 == q - 1)" in src
'''
exec(compile(head + 'exec(compile(src, "63mod", "exec"))\n', "68", "exec"))
if __name__ == "__main__":
    from multiprocessing import Pool
    t5 = sorted(p.stem for p in M5.glob("*.csv") if not p.stem.startswith("_"))
    with Pool(6) as p:
        A = pd.DataFrame(sum(p.map(gen_a, t5, chunksize=10), []))
    A.to_csv(HERE / "full_hour_trigger.csv", index=False); print(len(A))
