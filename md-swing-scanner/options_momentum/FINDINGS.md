# options_momentum/FINDINGS.md

Closed/banked conclusions for this track only (separate from the shared project-root
FINDINGS.md, same discipline as `pre_breach/` and `short_discovery/`).

## RQ-OMD-01 — Stock-level fast-move behaviour map (2026-10-04) — CLOSED, mixed

**Hypothesis tested:** does an unusually large stock-relative 1H move get followed by a fast
same-direction continuation, usefully for a long directional option? Full population (2,192
tickers, no F&O/liquidity restriction), `data/intraday_60m/`, 2023-10-23 -> 2026-10-01,
8.83M qualifying bar-events. Full preflight/report: `RQ-OMD-01_PREFLIGHT.md` /
`RQ-OMD-01_REPORT.md`.

**CLOSED-NEGATIVE on the literal hypothesis.** No fast-continuation edge after a large move,
in either direction, at any horizon (1H through next session). If anything the reverse:
continuation rate is *lower* after an unusual move than after a normal-sized one, in both
directions (dn: 36.9% vs 45.4% combined A+D; up: 32.8% vs 40.0%). Don't re-litigate "does a
big move keep moving" under a new name later — this is the answer, checked against 3
pre-declared z-windows, 3 individual years, and an independent gap-bar slice, all agreeing.

**BANKED as a market-behaviour finding, NOT yet as an edge:** unusually large moves see weaker
same-direction continuation, monotonically with move size, **in both directions**
(next-session continuation: up_normal 44.4% > up_elevated 43.3% > up_unusual 42.1%; dn_normal
55.2% > dn_elevated 51.3% > dn_unusual 47.7%), robust across all 3 z-windows, all 3 years, and
independently corroborated by gap-bar behaviour (gap-ups fade more than gap-downs continue, at
every horizon). The down-side swing (55.2%->47.7%, 7.5pp) is larger than the up-side swing
(44.4%->42.1%, 2.3pp) — an asymmetry in magnitude, not in whether the pattern holds.

**Correction, 2026-10-04 (Rule #22):** the dn_normal number above was originally reported as
49.9% (non-monotonic vs dn_elevated's 51.3%) due to a bug caught while building RQ-OMD-02 — a
`pre_reversal_mfe<=next_mfe` invariant check surfaced that exactly-flat bar-to-bar returns
(`r_T==0`, 5.1% of all rows, concentrated in illiquid/stale-price tickers) were being silently
emitted as meaningless "down move" events (`np.sign(0)==0` fell into the down branch
everywhere). Fixed in both panel builders; full before/after diff confirmed every
unusual/elevated bucket number is byte-identical (nothing already told to the critic changes)
— only dn_normal and the gap_down split moved, both upward, which is what restored the down
side's monotonicity rather than breaking the finding. Full detail: `RQ-OMD-01_REPORT.md`'s
correction note.

**Critic verdict (2026-10-04, full text in session log) — OMD-01 closed as specified below,
"buy puts after a spike" explicitly NOT banked:**
- The fade/reversal phenomenon itself is real and worth recording, and is more interesting
  for showing up at the 1H level than a daily-bar reversal result would be — but the broad
  "large moves reverse" finding is non-novel in the literature (intraday extreme-move
  reversal, Indian-market evidence included), so the value here is the measurement, not the
  discovery of reversal per se.
- **Rate isn't enough.** The A/B/C/D classification (reversal = retraces >=0.5x the initial
  move by 2H) tells us frequency, not economics — a 3% spike that gives back 1.5% is a very
  different trade than one that gives back 0.4% and stabilizes. Need depth-of-retracement and
  speed-of-retracement as continuous measures, not a single binary rate.
- **The overnight question is open, not settled.** Gap-bar corroboration does NOT establish
  the up-move fade is independent of overnight reversal — the literature has substantial
  evidence for overnight-to-intraday reversal specifically, and separately for intraday
  returns having their own reversal character. Correct next step: decompose the phenomenon
  into overnight-originated vs genuinely-intraday-originated moves before assigning it a
  mechanism, not declare it independent (my report overclaimed this).
- **Options add a real hurdle even if the stock-level effect holds**: IV/premium/skew may
  already price in the post-move reversal tendency, so stock reversal != long-put edge. Can't
  be settled without broad intraday options data, which we don't have.
- **F&O result is a diagnostic lead, not evidence of an edge.** 42% (F&O) vs 32-36% (non-F&O)
  combined continuation is a cross-sectional population difference (size/liquidity/spread/
  sector composition all differ between F&O and non-F&O names) — it does NOT yet show that
  *F&O unusual* moves continue more than *F&O normal* moves, which is the comparison that
  would actually matter. Preserve as a lead; do not start a separate F&O-continuation project
  on this alone.

**What OMD-01 actually established (critic's framing, adopted):**
1. Hypothesis (unusual move -> fast continuation) — REJECTED.
2. The larger the unusual 1H move, the less likely immediate same-direction continuation —
   ROBUST, banked.
3. Large move -> immediate reversal — real enough to investigate, NOT yet an options edge.
4. F&O stocks look less hostile to continuation than the broad universe — interesting
   diagnostic, NOT yet a strategy.

**Next step, per critic's explicit sequencing — do NOT jump to "test put buying after
spikes."** RQ-OMD-02 (Fast Reversal Quality) is the required intermediate step: decompose
overnight- vs intraday-originated moves, measure continuous retracement depth/speed (25/50/
75/100% of the initial move, pre-declared checkpoints, no threshold optimization), and only
then — if the reversal survives that decomposition — ask the options-economics question
(IV/premium effects). Architecture: stock phenomenon -> speed/magnitude -> robustness ->
option translation -> option economics, never skipping a step. See `RQ-OMD-02_SPEC.md`.

**Known scope limits, not blockers:** gap bars (09:15, overnight+first-hour) were not
z-bucketed against their own history in OMD-01 — reported as one unconditional up/down split
only (see preflight). RQ-OMD-02 removes this limitation since the overnight/intraday split is
now the central question. The 0.5x-of-own-move A/B/C/D threshold is a first-cut
classification for readability, not primary evidence — the continuous distributions (Table 1,
no threshold involved) are, and OMD-02 continues that discipline (continuous path first, no
magic retracement %).

## RQ-OMD-02 — Fast Reversal Quality (2026-10-04) — CLOSED, sharpens OMD-01 downward

**Critic-specified design** (overnight/intraday decomposition, continuous 25/50/75/100%
retracement checkpoints, F&O-unusual-vs-F&O-normal). Full report: `RQ-OMD-02_REPORT.md`.
Caught and fixed, en route, the flat-return bug described above plus a second edge case
(pre-reversal continuation isn't computable when the 25% checkpoint crosses in the very first
forward bar — now NaN, not a fabricated 0); a `pre_reversal_mfe<=next_mfe` invariant holds
with zero violations across 8.36M rows after both fixes.

**Headline: OMD-01's "weaker continuation" mostly means STALL, not a deep reversal — this
makes the put-after-spike idea look weaker, not stronger.** Unusual moves retrace their own
size *less often and slower* than normal moves (dn_unusual full-round-trip 53% vs dn_normal
88%; up_unusual 50% vs up_normal 89%). A big move mostly just stops where it is; it rarely
gives back most of itself within the next session. Robust across 3 calendar-matched window
pairs and 2024-2026.

**Overnight-vs-intraday decomposition (critic's Question B): overnight-originated unusual
moves are STICKIER (retrace less, slower) than intraday-originated ones** — e.g. overnight
up_unusual full-round-trip 18.7% vs intraday up_unusual's 50.2%. This argues *against* the
up-fade being a repackaged overnight-reversal effect, not for it — if anything overnight moves
are the more persistent ones. Not a full mechanism attribution (would need options/order-flow
data this project doesn't have), but the decomposition the critic asked for is done and points
the opposite direction from the worry.

**F&O-unusual vs F&O-normal (critic's Question C, the missing cut from OMD-01): the
unusual-stalls-more-than-normal pattern holds within F&O names too** — real, not purely
compositional. But the F&O-vs-non-F&O gap itself is modest by this metric (~2pp, vs the ~6-10pp
gap OMD-01's A/B/C/D view showed) — that earlier gap looks more sensitive to the 0.5x
classification threshold than to a deep structural F&O effect. Diagnostic caveat, not a reason
to start an F&O-specific project.

**Net effect on the three questions the critic posed:** A (rate vs economics) — answered
directionally, reversal is mostly stall, not deep give-back. B (overnight confound) —
addressed, argues against the overnight explanation. C (options economics) — untouched by
design, still the open hurdle before any product framing.

**Status: both RQs in this branch are CLOSED.** The combined picture (real, robust,
multi-year, cross-window, F&O-generalizing fade-to-stall pattern that is NOT a sharp,
economically obvious reversal trade) argues for checking back with the critic before investing
further research time in the put-after-spike angle specifically — see next-decision options in
`RQ-OMD-02_REPORT.md`. Do not default to resuming this branch next session without a new
trigger (critic verdict on OMD-02, or a new hypothesis).
