# Intraday EMA-pullback / pin-bar setup: literature check + cue tests (2026-10-01)

Scratch research only. Our own numbers: scripts 15-20 in this folder, log in TELEGRAM_CALLS.md.

## What the literature says (sources gathered by two research passes, links as found)

Entry
- Educators wait for the signal bar to CLOSE, then buy-stop above its high (Al Brooks "High 2"), or a limit at ~50% of
  the pin. Nobody found endorsing entry while the pin is still forming. All practitioner/course material, no tests.
  https://trasignal.com/blog/learn/al-brooks-2nd-entry-setup/ , https://www.easytradeweb.com/en/pin-bar-candlestick-trading/

Stop
- Practice: beyond the wick + buffer, or ~1-2.5x ATR. Indian broker blogs say 1-2% intraday (no data behind it).
  https://volatilitybox.com/research/volatility-adjusted-stop-losses/ , https://www.bajajbroking.in/knowledge-center/how-to-calculate-stop-loss-in-intraday-trading
- Academic: under a random walk a stop-loss always lowers expected return; it only helps when returns have momentum
  (Kaminski & Lo). https://dspace.mit.edu/bitstream/handle/1721.1/114876/Lo_When%20Do%20Stop-Loss.pdf
- NSE intraday volatility and spreads are U-shaped, highest 09:15-09:45, quietest 11:00-12:00.
  https://mpra.ub.uni-muenchen.de/89689/1/MPRA_paper_89689.pdf

What to expect
- Duvinage, Mazza & Petitjean (Quant Finance 2013): 83 candlestick rules on 5-min DJIA stocks -- some predictive power
  before costs, none profitable after costs. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2125889
- Marshall, Young & Rose: candlesticks not profitable on DJIA 1992-2002. https://www.researchgate.net/publication/223853109
- Bulkowski hammer (daily, downtrend reversal only, not pullback-continuation): reverses 60%, performance rank 65/103.
  https://thepatternsite.com/Hammer.html
- Pin-bar win rates of 60-78% circulate online, but trace to vendor/forex/4H-daily tests or to nothing at all.
- SEBI FY2022-23 study: 71% of individual intraday traders in cash equity lost money; 80% of those with >500 trades/yr.
  Loss-makers paid costs equal to 57% of their losses.
  https://www.sebi.gov.in/reports-and-statistics/research/jul-2024/study-analysis-of-intraday-trading-by-individuals-in-equity-cash-segment_84946.html
- Costs (MIS, inferred from published rates): ~0.08% round trip on Rs 1 lakh, ~0.045% on Rs 5 lakh, plus slippage
  -> ~0.06-0.15% realistic. At a 0.3-0.5% stop that is 0.2-0.4R per trade. https://www.cashoverflow.in/zerodha-charges/

Cues, ranked by evidence
1. Market's own intraday direction: Gao, Han, Li & Zhou (JFE 2018), first half-hour predicts last half-hour (SPY);
   Baltussen et al. (JFE 2021) in 60+ futures. India: one paper says it transfers (unverified, 403).
   https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2552752 , https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3760365
2. Time of day: individual stocks REVERSE in the last 30 min (Baltussen, Da & Soebhag 2025).
   https://academicweb.nd.edu/~zda/EOD.pdf
3. Relative volume "stocks in play": Zarattini, Barbon & Aziz (SSRN 2024), opening-range breakout, US; no ablation;
   authors sell education. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4729284
4. Volatility regime: intraday momentum concentrated in high-vol periods; one ORB replication got 76% of P&L in 2022.
   https://github.com/giovannibrusco/zarattini-2023-orb-qqq
5. VWAP: weak, mostly practitioner (QQQ); a replication decayed to Sharpe ~0 in 2025-26.
   https://github.com/codecat-ops/zarattini-2024-momentum-spy
6. Sector / relative strength: real at daily/monthly horizons; nothing found intraday.
7. Gap: up-gaps mostly fill (unreviewed DJIA study). https://www.academia.edu/43583357
8. RSI: weakest; RSI(2) intraday dies after 1bp of friction. https://quantifiedstrategies.substack.com/p/best-timeframe-for-rsi-we-backtested

## Our tests of those cues (19/20 scripts; definitions adopted from the review BEFORE looking)
Two trade sets: 5m held-rejection (Jun-Sep 2026, n=10,475, baseline -0.012%) and 1H close (2024-26, n=38,444,
baseline -0.031%). Mean % per trade, gross.

| cue | 5m: kept / removed | 1H: kept / removed | verdict |
|---|---|---|---|
| Nifty since-open with trade | -0.006 / -0.017 | -0.014 / -0.047 | same direction both, small |
| entry 10:15-11:30 vs later | +0.002 / worse later | +0.004 / -0.05 to -0.08 later | same direction both; later hours worst |
| gap > +0.5% in trade direction | -0.039 (worst) | -0.078 (worst) | consistent: avoid with-gaps |
| above VWAP (long) | -0.011 / -0.013 | -0.023 / -0.053 | 1H only |
| sector with trade | -0.019 / -0.008 | +0.012 / -0.031 | contradicts across sets |
| RVOL >= 2 | +0.008 (n=466) | -0.045 | nothing |
| RS vs Nifty | -0.019 / -0.008 | -0.028 / -0.034 | nothing |
| 1H RSI >= 50 (long) | -0.015 / -0.006 | -0.033 / -0.025 | nothing (as predicted) |
| ATR tercile | mid best, tiny | low/mid better than high | nothing |

Exploratory (chosen after seeing the table, so in-sample): Nifty-with + entry before 11:30 + no with-gap
  5m: n=1,130 +0.009% (months -0.07/-0.10/+0.05/+0.08); 1H: n=7,399 +0.019% (years +0.01/+0.06/-0.02).
  Shorts +0.045 / +0.069, longs -0.061 / -0.052. Still below the ~0.06-0.15% round-trip cost.

## Bottom line
The literature and our data agree: candlestick/pin rules at a moving average carry little or no edge intraday after
costs. Cues with real support (market direction, early session, avoid with-gaps) move expectancy by a few hundredths of
a percent, the right way, but not past costs. Shorts have been mildly better than longs in every variant; 2025-26 was a
weak market, so that may be the regime rather than the setup.

## Day-bias methods: literature check (2026-10-02)
No peer-reviewed or credible quantitative evidence that any early-session cue (09:15-10:15) predicts the rest of
Nifty's day. Practitioner-only (no tests found): Market Profile opening types (https://www.luxalgo.com/library/concept/open-types/),
CPR narrow = trend day (https://groww.in/blog/central-pivot-range), GIFT Nifty (predicts the GAP only), early breadth,
intraday PCR / max pain. India VIX moves with price, does not lead it (https://nsearchives.nseindia.com/research/content/res_WorkingPaper9.pdf).
Robust effects are elsewhere: (1) last-30-min momentum, prior close -> 15:00 predicts 15:00-15:30 (Gao et al. JFE 2018,
https://doi.org/10.1016/j.jfineco.2018.05.009; Baltussen et al. JFE 2021, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3760365),
mostly outside an MIS window; (2) overnight vs intraday: Zerodha's Nifty data 1999-2025, Rs 100 -> ~709 overnight-only vs
~62 intraday-only (https://inthemoneybyzerodha.substack.com/p/the-overnight-drift-why-markets-move) -- independently
matches our +123% / -42%. Gaps: IntradayLab 2016-26, Nifty gap-ups >= 1% (n=85) close below the open 55% of the time,
avg open->close -0.25% (https://intradaylab.com/blog/nifty-gap-up-history-analysis) -- conflicts with our gap-up > 0.5%
+0.19% from ~10:15; different threshold/window, to reconcile. Zarattini "Beat the Market" (SPY) works via convex
payoffs (43% hit), not direction forecasting (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4824172).

## "Mechanical core" (trend + VWAP + prior-bar break + prior-bar trail + skip ranges): literature (2026-10-02)
- VWAP as filter: Zarattini & Aziz QQQ (long/short by VWAP side) +671% 2018-23, but ~17% win rate, P&L from a few trend
  days (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4631351); replication matches trades/hit rate, sceptical.
- VWAP as EXIT: "Beat the Market" SPY: trailing stop max(band, VWAP) moved Sharpe 0.61 -> 1.24, skew -1.24 -> +1.29,
  hit 54% -> 43% (https://alexandria.unisg.ch/bitstreams/a99aba00-f967-49b3-aceb-f544dc386e0b/download);
  independent replication: Sharpe ~0 in 2025-26 out of sample (https://github.com/codecat-ops/zarattini-2024-momentum-spy).
- Index VWAP: no official definition; traders use NIFTY futures VWAP or constituent-weighted VWAP.
- "Steadily holding VWAP", prior-bar break entry, prior-bar trail, choppy/range skip filters, early breadth -> day bias:
  no quantified tests found (practitioner wording or Brooks's own claimed probabilities only). ADX filter sweeps: cut
  60-80% of trades without consistent gain (search summary). Stopping rules add value only with momentum (Kaminski & Lo).
- Verdict: sensible as entry conditioning, not an edge by itself; effects small and decaying. Matches our data:
  VWAP breadth doesn't call Nifty (44a); stock "steadily below VWAP" +0.104 vs +0.057 on our shorts (44b, exploratory).
