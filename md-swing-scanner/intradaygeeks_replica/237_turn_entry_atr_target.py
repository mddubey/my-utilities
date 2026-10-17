"""A TARGET THAT FITS THE STOCK instead of a fixed 1% (user, 2026-10-17: calm stocks rarely get stopped but stall short of 1%). Spec fixed
before running:
  Population: 236's F (turn 0.1% below the touch high, NO ATR filter; liquid, >= Rs100, gap zone, uptrend, branch A / B, daily 8 not in
    the path). Stop fixed 0.5% (the user's). Targets: fixed 1% | k x daily ATR%, k = 0.25 / 0.35 / 0.50 (no floor) | else out at 15:15.
  Report by ATR band (< 2 / 2-3 / 3-4 / >= 4%): net Rs per Rs1 lakh, target / stall / stop, median target; all bands; top-10 days removed.
  PART 2 (user's point: in fast stocks a late entry costs more): 233's events at X 0.1% vs X 0.2% (one step later), 0.5% stop, 1% target,
    same day filters, net by ATR band and the difference."""
import sys, importlib.util, io, contextlib, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent; sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
from orb_common import read5_official
COST = 0.085; KS = (0.25, 0.35, 0.50)
BANDS = [0, 2, 3, 4, 99]; BL = ["< 2%", "2-3%", "3-4%", ">= 4%"]


def run(args):
    t, g = args; m = read5_official(t); md = m.index.normalize(); out = []
    for ix, r in g.iterrows():
        x = m[md == pd.Timestamp(r.date)]; hm = x.index.strftime("%H:%M").values
        H, L, C = x.High.values, x.Low.values, x.Close.values
        j = np.where(hm == r.t_entry)[0]; lasts = np.where(hm <= "15:10")[0]
        if not len(j) or not len(lasts): continue
        j, last = j[0], lasts[-1]; e = r.entry; s = e * 1.005; rec = dict(ix=ix)
        for nm, tp in [("1pct", 1.0)] + [(f"k{k}", k * r.atr) for k in KS]:
            tg = e * (1 - tp / 100); res = None
            for k in range(j + 1, last + 1):
                if H[k] >= s: res = (-0.5, "stop"); break
                if L[k] <= tg: res = (tp, "target"); break
            rec[f"{nm}_ret"], rec[f"{nm}_why"] = res or ((e - C[last]) / e * 100, "stall"); rec[f"{nm}_tp"] = tp
        out.append(rec)
    return out


if __name__ == "__main__":
    from multiprocessing import Pool
    spec = importlib.util.spec_from_file_location("m", HERE / "236_turn_entry_drop_atr.py"); mm = importlib.util.module_from_spec(spec)
    with contextlib.redirect_stdout(io.StringIO()): spec.loader.exec_module(mm)
    F = mm.F.copy()
    with Pool(6) as p: R = pd.DataFrame([r for rr in p.map(run, list(F.groupby("ticker")), chunksize=5) for r in rr]).set_index("ix")
    F = F.join(R); F["band"] = pd.cut(F.atr, BANDS, right=False, labels=BL)
    assert (F["1pct_ret"] - F.fixed_ret).abs().max() < 1e-6, "1% target must reproduce 236"
    NM = [("1pct", "fixed 1%")] + [(f"k{k}", f"{k} x ATR") for k in KS]

    def cell(x, v):
        w = x[f"{v}_why"]
        return f"{(x[f'{v}_ret'].mean()-COST)*1000:+.0f} ({(w=='target').mean()*100:.0f}/{(w=='stall').mean()*100:.0f}/{(w=='stop').mean()*100:.0f}; tgt {x[f'{v}_tp'].median():.2f}%)"
    print(f"trades {len(F)} (1% target reproduces 236 exactly)")
    print("\n### Net Rs @1L (target / stall / stop %; median target) by ATR band\n| ATR band | n | " + " | ".join(l for _, l in NM) + " |\n|---|---|" + "---|" * len(NM))
    for b in BL:
        x = F[F.band == b]; print(f"| {b} | {len(x)} | " + " | ".join(cell(x, v) for v, _ in NM) + " |")
    print(f"| ALL | {len(F)} | " + " | ".join(cell(F, v) for v, _ in NM) + " |")
    print("| ALL, top-10 days removed (per version) | | " + " | ".join(
        f"{(F[~F.date.isin(F.groupby('date')[f'{v}_ret'].sum().nlargest(10).index)][f'{v}_ret'].mean()-COST)*1000:+.0f}" for v, _ in NM) + " |")
    print("| ALL, by month 06/07/08/09/10 | | " + " | ".join("/".join(f"{(g[f'{v}_ret'].mean()-COST)*1000:+.0f}" for _, g in F.groupby(F.date.str[:7])) for v, _ in NM) + " |")
    best = F.assign(mix=np.where(F.atr < 3, F["k0.35_ret"], F["1pct_ret"]))
    print(f"| mixed: 0.35 x ATR under 3% ATR, 1% at 3%+ | | {(best.mix.mean()-COST)*1000:+.0f} |")

    # PART 2: cost of entering one step later, by ATR band
    A = pd.read_csv(HERE / "v1_turn_entry.csv")
    G = A[(A.liq >= 15) & (A.pc >= 100) & (A.gap > -0.25) & (A.gap <= 0.5) & A.up & ~A.in_path & A.ov.notna()]
    G = G[((G.ov >= -0.5) & (G.ov < 0)) | (G.ov >= 0)].copy(); G["band"] = pd.cut(G.atr, BANDS, right=False, labels=BL)
    print("\n### PART 2: cost of selling one step later (0.2% vs 0.1% below the touch high), 0.5% stop, 1% target\n| ATR band | n at 0.1% | net at 0.1% | n at 0.2% | net at 0.2% | cost of the later entry |\n|---|---|---|---|---|---|")
    for b in BL:
        a, c = G[(G.band == b) & (G.X == 0.001)], G[(G.band == b) & (G.X == 0.002)]
        na, nc = (a.fixed_ret.mean() - COST) * 1000, (c.fixed_ret.mean() - COST) * 1000
        print(f"| {b} | {len(a)} | {na:+.0f} | {len(c)} | {nc:+.0f} | {nc - na:+.0f} |")
