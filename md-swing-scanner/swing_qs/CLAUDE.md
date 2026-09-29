# swing_qs — RQ-QS research line (2026-09-26 onward)

This is a SEPARATE research line from the existing "BC" strategy documented in the
parent directory's `FINDINGS.md`/`CLAUDE.md`. Nothing here modifies, renames, or
supersedes BC — BC's existing recipe, history, and documentation stay exactly as they
are. This folder exists because the weekend's research kept optimizing filters before
ever defining what the strategy was supposed to catch (see `PRODUCT_DEFINITION.md`) —
rather than retrofit that definition onto BC's own established identity, it gets its own
name, its own files, and its own findings log.

**Read `PRODUCT_DEFINITION.md` before anything else in this folder.** It defines the
holding horizon (3-5 sessions, not fixed), the FAST/SLOW/FAKE trajectory labels (tied to
Meaningful Win, 0.25R), the two distinct failure modes, and the explicit Stage 0
guardrails (no feature promotion, no threshold optimization yet).

**Shared infrastructure, reused not duplicated**: `../population_builder.py` (the
canonical T-1-gated population builder), `../primed_engine.py` (real exit mechanics),
`../signals.py`'s `base_filters_pass` (BC v2's recipe, used here only as one candidate
recipe among several this line may eventually test, not as this line's own definition).
All of the parent `CLAUDE.md`'s guardrails (Rule #18 gate timing, Exit Engine Integrity,
Gate Integrity, Rule #19 robustness-before-finding) apply here too — this folder adds
requirements on top, it doesn't relax anything.

**This folder's own findings log is `swing_qs/FINDINGS.md`** — do not write this line's
research into the parent `FINDINGS.md`, and do not write BC's own research here.

## Two standing checks, learned the hard way in this folder's first session (2026-09-26)

1. **Circularity check**: any feature measured in the same units as a FAST/SLOW/FAKE
   label (price move vs. entry, in R) must be checked for how much of its raw separation
   rate is just restating the label — compute what fraction of the "positive" bucket was
   *already* at the label's threshold from the feature alone, and re-check on the
   decontaminated remainder before trusting the number.
2. **Pre-entry vs. post-entry check, sharper and easier to miss**: a feature is only a
   real ENTRY filter candidate if every value is knowable at the instant the trigger
   fires, using ONLY history up to that point — never "did X happen afterward" or "how
   long did X take," even if X itself is framed as a percentage or price level. A
   feature whose bucket membership depends on what the price does AFTER entry is a
   post-entry / early-warning signal at best, never an entry decision, no matter how
   clean its numbers look. (Caught here: "clear the 40-day high within N days" and even
   "the gap size, bucketed by whether/how it got touched" both secretly used the future
   to decide which bucket a trade belonged to — only a feature computed directly from
   history AT entry, with no forward search at all, passes this check.)

## Standing Stage 0 rule (do not violate)

No feature promotion, no threshold optimization, until Stage 0's three deliverables
(trajectory labels, trigger-timing dataset, base-descriptor dataset) exist and have been
reviewed. This is not a filter-hunting folder yet.

## External Reading Guardrail (adopted 2026-09-27)

Quick Swing research must begin from published breakout philosophy, not from backtests
— fixes a pattern repeated several times this weekend (inventing a hypothesis from the
dataset first, then discovering the literature had already framed the underlying
mechanism differently, e.g. F1/return-to-breakout vs. Darvas box failure). Every new QS
hypothesis should explicitly state which literature concept it is testing or
challenging before looking at historical results.

**Authoritative references, exact URLs (read before implementing new entry/exit ideas)**:
1. Qullamaggie (Kristjan Kullamägi) — Swing Trading School (breakout philosophy, stop
   placement, 3-5 day feedback expectation, scaling runners):
   https://breakoutshappen.com/stock-news/how-to-build-a-stock-watchlist-of-2-5-daily-breakout-candidates
2. Qullamaggie — Risk Management / Stops (stop placement around breakout lows / ADR):
   https://breakoutshappen.com/stock-news/qullamaggie-breakout-strategy-4-step-tutorial-for-swing-trading
3. TraderLion interview with Kristjan Kullamägi ("feedback", fast movers, why weak
   breakouts are suspicious early):
   https://lilys.ai/en/notes/notebooklm-20251211/mark-minervini-volatility-contraction-strategy
4. Reddit discussion summarizing Kullamägi execution (community/secondary, not authority):
   https://www.reddit.com/r/qullamaggie/comments/1cmak2c
5. Mark Minervini Trend Template (entry philosophy, VCP context — Product A/BC reference,
   not Quick Swing):
   https://www.openswingtrading.com/blog/mark-minervini-rules-tested-on-1-000-breakouts-2015-2025
6. Minervini selling rules (distribution days, moving averages, partial exits — Product
   A/BC reference only):
   https://tradingmomentum.substack.com/p/the-4-breakout-entry-architectures
7. Darvas Box strategy overview (box breakout/failure concept — inspiration for F1):
   https://s3.amazonaws.com/trading-products/darvas/Darvas-Bonus-Article.pdf
8. Darvas trailing stop / box failure explanation (trailing the structural floor upward):
   https://insight.definedgesecurities.com/newsletters/year-2020/07/19-07-2020-Weekly-Newsletter.pdf
9. TraderLion — Failed Breakouts (early failure vs. healthy retest, professional view):
   https://investynadvisors.com/how-to-find-the-best-stock-setups-before-they-break-out
10. Breakout pullback/reclaim discussion (why reclaiming a breakout level matters):
    https://tradesmrt.com/en/strategies/vcp-volatility-contraction-pattern/

**Reading order**: (1) Kullamägi Swing Trading School — defines the QS product
philosophy; (2) TraderLion interview — defines "feedback" within 3-5 sessions; (3)
Darvas Box — explains structural breakout failure; (4) Minervini selling rules —
reference for Product A/BC, not Quick Swing.

## Risk Unit Integrity has graduated to the parent project (2026-09-27)

The Stop Definition catch (every R-based number here silently inheriting BC v2's
20-day structural-low stop) turned out to be a general measurement-integrity rule, not
a swing_qs-specific one — it applies to any future R-based research anywhere in this
project (BC, Cell C, OX, anything). Per critic's explicit verdict, it now lives as
**Rule #20 in the parent `../CLAUDE.md`**, alongside the parent's new "Research
Preflight" five-question block. Read it there — it is not duplicated here.

## Three more standing rules, critic-specified, adopted 2026-09-27 — kept local to this
folder (product-specific, not general measurement rules)

4. **Decision-Time Feature Integrity Rule**: a feature is admissible for prediction or
   filtering only if its value could have been calculated using information available at
   the exact decision timestamp. A future event cannot become a pre-entry feature merely
   because it is eventually observable. (Per critic, this is essentially a specialization
   of the parent's Rule #18 — kept here mainly as a sharper, swing_qs-flavored restatement:
   it's why S1, the breakout day's own Low, was rejected as a practical stop despite being
   Kullamägi's literal documented convention — the day is still in progress at the moment
   of entry.)
5. **Alternative-Definition Integrity Rule**: when comparing strategy definitions, each
   definition must be implemented as an independent alternative entry process on the same
   underlying opportunity universe. A future event occurring after one strategy's entry
   must not be used as a proxy for another strategy definition. (Relevant here because
   we're comparing 10D/20D/40D as alternative entry-defined products, not a general
   project-wide concern.)
6. **Label Threshold Is Not Strategy Truth Rule**: FAST/SLOW/FAKE labels are research
   classifications, not presumed economic categories. Starting thresholds (0.25R by
   day_idx<=5, etc.) must remain explicitly provisional until validated against the
   product objective — don't treat a label boundary as settled just because it's been
   used in several tables already. (FAST/SLOW/FAKE are swing_qs product abstractions,
   not a general project concept.)
