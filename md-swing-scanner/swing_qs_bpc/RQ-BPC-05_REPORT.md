# RQ-BPC-05 — Volume-Confirmed A Population Audit — Report

2026-10-04 IST. Built exactly per the critic's pre-registration (`RQ-BPC-05_SPEC.md`):
A = existing v0.1 gate AND breakout-day volume >= 1.5x `vol_avg10_prior` (the production
field, reused unchanged). No threshold optimization — 1.5x was fixed before this script ran.
`find_a_positions` and `analyze_one` reused unchanged from the original 04A/04C scripts, so
methodology is identical to the superseded run except for the one A qualification.

## Population

- Full A population (nifty500, lookbacks 10/20/40): **46,811** events.
- Volume buckets (diagnostic, not a gate): <1x 22.8%, 1-1.5x 22.0%, 1.5-2x 15.9%, 2-3x
  17.1%, >=3x 22.1%. **Nearly half of all previously-tested A's (44.8%) genuinely lacked
  volume confirmation** — this alone explains a large share of the original poke-and-fade
  signature.
- Corrected population (>=1.5x): **25,802 / 46,811 (55.1%)**.
- `has_bigger_preceding_thrust` (a bigger volume day sat in the 10 days before A — the
  exact failure mode found by hand on CONCORDBIO/SONACOMS/SAPPHIRE): **57.0% of ALL A's,
  44.0% even within the corrected (>=1.5x) population.** Raising the threshold reduces this
  mis-identification but does not solve it — flagged as a real limitation, not swept under
  the rug.
- holds-above-A subset (corrected population): **5,494 / 25,802 (21.3%)** — vs the original
  **8,403 / 46,750 (18.0%)**. A modest, directionally-consistent improvement.

## The decisive comparison — corrected vs original (n=5,494 vs n=8,391)

| metric | original (uncorrected A) | corrected (A >= 1.5x volume) |
|---|---|---|
| duration P25/50/75/90 (days) | 1 / 2 / 4 / 9 | 1 / 2 / 4 / 9 — **identical** |
| range width % P25/50/75/90 | 2.91 / 4.33 / 6.68 / 10.17 | 3.14 / 4.62 / 7.12 / 10.95 — **slightly wider** |
| range width / ATR, median | 1.36x | 1.42x — **no tightening** |
| close-to-close range %, median | 0.48% | 0.60% — **no tightening** |
| pause volume / 10d avg, median | 1.29x (no dry-up) | **1.53x — more volume, not less** |
| resolved | 90.7% | 90.3% |
| **B close above consolidation high** | **45.6%** | **44.8% — no material change** |
| B close vs high, median | -0.13% | -0.15% |

**Every single metric that mattered in the original 04B verdict is statistically unchanged
after volume-confirming A — several (pause volume, range width) move slightly in the wrong
direction.** The duration x width matrix shows the exact same shape as before: mass in
1-day/2-4% cells, longer pauses (5-7d/8+d) still have essentially zero mass under 2% width
— still widening, not tightening, with duration. B-close-above-high is flat 43.6%-48.2%
across every duration bucket, same as the original's flat 41-53%.

**Subgroup checks (per the critic's "confirm the same event" instruction):**
- High-volume subgroup (>=3x) is *worse*, not better, than the 1.5-3x band: 43.6% vs 46.0%
  B-close-above-high. Bigger A volume does not mean a better outcome.
- Rows where A is genuinely the standout day (no bigger preceding thrust) do modestly
  better than rows where a bigger thrust preceded A: 45.9% vs 42.8%. Real, in the expected
  direction, but only ~3pp — not enough to change the overall picture.

## 20-pair replay, same stratified method as 04C (seed 42, early/mid/late/random)

Visually more mixed than the original grid — RITES, VTL, OLECTRA, WIPRO, VEDL, HBLENGINE,
CROMPTON look like genuine stair-step continuations with real volume behind A. But
HINDPETRO, WOCKPHARMA, SOLARINDS, MGL, SOBHA still show the same poke-and-fade shape as
before — pokes the consolidation high, fades hard. This sample's B-close-above-high (12/20,
60%) is higher than the full population's 44.8%, but at n=20 that's ordinary binomial
sampling variance around a ~45% true rate (not a contradiction) — **the full 4,959-row
resolved population is the number to trust, not this 20-pair draw.** Flagged explicitly so
this isn't quietly cherry-picked as "the replay showed improvement" when the properly-powered
number didn't. Plot: `plot_bpc05c_pairs.png`.

## Applying the critic's pre-declared decision rule

**Reopen fails.** The corrected-A population does not materially change the central BPC
evidence: no recognizable tightening of the pause, no volume dry-up (if anything the
opposite), and the decisive B-close-above-high rate is unchanged (45.6% -> 44.8%, within
noise). Per the critic's own framing, this is **a stronger negative than 04B/04C's original
result**, because it rules out "we tested the wrong population" as the explanation — this is
now the right population (volume-confirmed, literature-grade breakouts), and the hypothesized
BPC continuation structure still doesn't show up in aggregate.

## What this does NOT mean

- It does not mean "volume doesn't matter" — the literature (Bulkowski, CFA Institute, the
  O'Neil 1995-2021 study) is still right that breakout-day volume predicts *something* real
  (A's own trajectory, not tested head-to-head here, is a separate question from B's).
- It does not mean every individual chart in the 20-pair sample was wrong to flag — several
  genuinely look like clean continuations. The finding is about the *population*: a real,
  volume-confirmed breakout does not reliably produce a tight, volume-drying, cleanly-
  resolving second-breakout structure often enough to be a usable aggregate edge.
- `has_bigger_preceding_thrust`'s modest effect (45.9% vs 42.8%) is a real, small, correctly-
  directioned signal that wasn't chased further here (per the critic's "we don't need to
  invent a new complicated gate yet" instruction) — a legitimate smaller thread if anyone
  wants to pick it up later, not a reason to keep this branch open now.

## Recommendation

Close PARKING_LOT #9 and this reopened branch, citing this result specifically (not the
superseded 04B/04C numbers) as the operative evidence — this is the stronger, population-
correct negative the critic's decision rule anticipated. Send to the critic for their own
close call before marking it final, same discipline as every other closure in this project.
