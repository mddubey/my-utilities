# Literature synthesis: pre-breach and opening-session features

Compiled 2026-09-30 IST with a web literature search. Every claim is tagged with an evidence
tier:

- **STUDY**: a peer-reviewed paper, or an SSRN/academic working paper with stated data and method.
- **PRAC-DATA**: a practitioner backtest with stated rules, not peer-reviewed.
- **PRAC-CLAIM**: a practitioner claim with no published data.
- **FOLKLORE**: repeated widely, no data behind it.

Almost nothing below comes from Indian equities. Every intraday result is US or index data,
so assume it does **not** transfer to NSE until our own data shows it does.

## 1. Opening Range Breakout (ORB)

**Zarattini, Barbon & Aziz (2024), "A Profitable Day Trading Strategy For The U.S. Equity
Market," SSRN 4729284. Full PDF read. Tier: PRAC-DATA.** It is an SSRN working paper, and one
co-author sells trading education.

- **Data and filters:** more than 7,000 US stocks, 2016-2023, free of survivorship bias.
  Stocks must trade above $5, average at least 1M shares/day, and have a 14-day ATR above $0.50.
- **Rules:** trade in the direction of the first 5-minute candle. Stop at 10% of ATR. Exit at
  the close.
- **Costs:** only a commission of $0.0035/share. **No slippage is modelled.**

| Variant | Total return | Sharpe | Hit rate | Max drawdown |
|---|---|---|---|---|
| 5m ORB, all stocks | 29% | 0.48 | 41.4% | 13% |
| 5m ORB + relative volume ≥ 1x, top 20 stocks | 1,637% | 2.81 | 48.4% | 12% |
| 15m ORB + relative volume | 272% | 1.43 | 44.7% | 11% |
| 30m ORB + relative volume | 21% | 0.21 | 42.4% | 35% |

- Almost all of the edge comes from the relative-volume ("stocks in play") filter.
- The edge decays sharply as the opening window lengthens.
- There is no out-of-sample period.

**Independent replication of the 5m ORB on index CFDs, 2015-2026, about 2,900 sessions each
(mql5 blog). Tier: PRAC-DATA.**

- Gross returns match the paper: NQ +0.131R, SPX +0.119R, DAX +0.116R.
- **After spread and slippage** they fall to NQ +0.002R, SPX −0.081R, DAX −0.038R.
- Conclusion: the direction of the first 5-minute candle carries about 0.10R of information,
  roughly the size of the round-trip costs.

**Other sources**

- **Holmberg, Lönnbark & Lundström (2013)**, Finance Research Letters 10(1):27-33.
  Tier: STUDY. The abstract reports ORB returns significantly above zero. I did not open the
  full text. The market studied is probably crude oil futures (not verified).
- **Crabel (1990).** A book of 1980s futures tables. Tier: PRAC-DATA. I have not seen the
  tables.
- **India:** SSRN 5198458 (NSE ORB) appears to cover Tata Motors only, over one year, and is
  not significant (p ≈ 0.45-0.50, per the search snippet). No credible Indian ORB study found.

## 2. Gap-and-go vs gap-fade, and overnight vs intraday returns

**Berkman, Koch, Tuttle & Zhang (2012), JFQA 47(4):715-741, "Paying Attention: Overnight
Returns and the Hidden Cost of Buying at the Open." Tier: STUDY. Abstract read; full text
blocked.**

- Overnight returns are positive, then reverse intraday, because the opening price is inflated
  relative to later prices.
- The effect concentrates in stocks with recent attention: a high absolute return or heavy net
  retail buying the day before.
- It is stronger in hard-to-value or costly-to-arbitrage stocks, and when retail sentiment is
  high.
- The implicit cost of buying at the open "frequently exceed[s] the effective half spread."
- **This is directly on point.** A stock pushing up to its 10-day high is, by construction, an
  attention stock.

**Aboody et al. (2018), JFQA 53(2). Tier: STUDY, abstract only.** A stock's overnight return
works as a firm-level sentiment measure. It persists in the short term and reverses in the
long term.

**Lou, Polk & Skouras (2019), JFE 134(1):192-213, "A tug of war." Tier: STUDY. Full PDF read.**

- **US:** momentum profits accrue entirely overnight; the intraday component is negative.
  Overnight-winner decile: +3.47%/month overnight vs −3.02%/month intraday.
- **9 non-US countries, India not among them:** momentum is mainly intraday, 0.96%/month
  intraday vs 0.23% overnight. In large caps it flips back to overnight.
- **Implication:** which way this goes depends on the market. The US "buy the open, give it
  back" pattern cannot be assumed for NSE momentum stocks.

**Della Corte et al., "Overnight-Intraday Reversal Everywhere," SSRN 2730304. Tier: STUDY.**
Covers futures across asset classes, not single stocks.

**Plastun et al. (2020), US index gaps on daily data, 1928-2018. Tier: STUDY, index level
only.**

- On the day of the gap, price tends to continue in the gap's direction.
- Only about 20% of gaps fill within 5 days, which contradicts the "gaps get filled" myth.
- The effect has weakened since the 1990s.
- This partly contradicts Berkman. Index gaps are not the same thing as single-stock attention
  gaps.

**Nifty index, overnight vs intraday returns, 2011-2020 (LinkedIn analysis). Tier: PRAC-DATA,
index level.** Overnight returns were positive almost every year, intraday returns mostly
negative, and about 92% of the up-moves came overnight. This points the same way as Berkman.

**Single-stock NSE gap-fill or gap-go statistics** (e.g. "small gaps fill 70-80%") are
**FOLKLORE**. No credible source was found.

## 3. VWAP reclaim or rejection

- **Zarattini & Aziz (2023), "VWAP: The Holy Grail…," SSRN 4631351. Tier: PRAC-DATA.** Tested
  on QQQ only, 2018-2023, with no slippage. It is a trend filter on an index ETF, not a test of
  a reclaim/rejection signal.
- The academic VWAP literature is about VWAP as an execution benchmark, not as a predictor.
- **Verdict:** VWAP reclaim/rejection as a single-stock continuation signal is **FOLKLORE**.
  It is not proposed as a feature, and the 5-min cache would only give a 2-bar VWAP by 09:25
  anyway.

## 4. Qullamaggie (Kristjan Kullamägi)

His own rules, from qullamaggie.com and a Chat With Traders transcript. **Tier: PRAC-CLAIM.**

- **Setup:** a prior move of 30-100%+ within 1-3 months, then an orderly consolidation with
  higher lows and a tightening range that rides the rising 10/20-day moving averages.
- **Entry:** above the opening-range high. The timeframe depends on how the stock opens:
  1-min if it gaps over the pivot, 5-min if it breaks in the first 5 minutes, 60-min if it
  breaks by 10:00.
- **Stop:** the low of the day, no wider than ADR/ATR.
- **Exits:** sell 1/3 to 1/2 after 3-5 days, then trail the rest on a close below the
  10/20-day moving average.
- **ADR filter:** ADR above about 4-5% (from secondary summaries).

**Claimed win rate:** about 25% in 2019 and about 35% in 2020. Self-reported, with no trade
log.

**What he says separates winners:** setup quality and breakout volume. This is not quantified.

The "Top 100 winners" case study is survivorship-biased and worthless as evidence. The "risk
under half an ADR returned a 13.9R median" claim could not be traced to any source.

**Relevance here:** he enters at the opening-range high, so he is **also** a buy-at-the-touch
trader, not a buy-blind-at-the-open trader. Nothing in his method supports a blind pre-touch
entry.

## 5. Early-session relative volume (distinct from full-day volume)

**Zarattini, Barbon & Aziz (2024). Tier: PRAC-DATA.** This is the only quantified source found.

- Relative volume is defined as first-5-minute volume ÷ the 14-day average of first-5-minute
  volume, so it is matched for time of day.
- ORB profit per trade rises monotonically with it:

| First-5-min relative volume | Profit per trade |
|---|---|
| < 1x | −0.02R |
| > 1x | +0.08R |
| > 30x | +0.38R |

- The same filter over 15/30/60-minute windows is much weaker.
- **Caveat:** it measures follow-through of an intraday breakout in either direction, not
  whether a 10-day-high level holds.

**Other sources**

- **Gao et al. (2018):** market intraday momentum is stronger on days with high
  first-half-hour volume (R² 1.1% on low-volume days vs 3.1% on the highest). Index level.
- **O'Neil's "40-50% above average volume" breakout rule:** refers to full-day volume, and no
  study backs it. Tier: FOLKLORE. This project already found full-day breakout volume magnitude
  null (closed 2026-09-21).
- **Time-of-day-adjusted relative volume indicators** (TradingView, Trade-Ideas) have no
  published tests.

**Deviation we are forced into:** the 09:15 bar's volume is 0 in 97% of our 5-minute cache.
Our proxy is the 09:20-09:25 bar measured against its own prior-20-session median. That is the
*second* 5 minutes, known at 09:25. The literature's effect decays quickly with window length,
so this proxy may miss some of it.

## 6. Intraday momentum and same-day hold rates

- **Gao, Han, Li & Zhou (2018), JFE 129(2), "Market intraday momentum." Tier: STUDY.** On SPY,
  1993-2013, the first half-hour's return (measured from the prior close) predicts the last
  half-hour's return: slope 0.069, R² 1.6%. It is stronger on volatile, high-volume and news
  days. It predicts the close, not a 30-minute hold after a touch, and the authors explicitly
  did not study the cross-section of individual stocks.
- **Komarov (2017), SSRN 2905713. Tier: STUDY, working paper.** For single US stocks, intraday
  momentum is mostly *market* momentum, and the stock-specific part mean-reverts. That is
  consistent with this project's 2026-09-05 finding that first-15-minute stock returns vs the
  rest of the day correlate at −0.007, with a mild mean-reversion tilt.
- **Baltussen, Da & Soebhag (2023), "End-of-Day Reversal." Tier: STUDY.** Individual stocks
  reverse sharply in the last 30 minutes, mostly among intraday losers.
- **Published hold rates for same-day breakouts of multi-day highs, conditioned on opening
  behaviour:** **none found.** This project's own intraday data is the only source.

## 7. The cost of buying an option at the open

- **NSE market structure (NSE circulars):** since 2025-12-08, the pre-open call auction covers
  stock *futures* but **not options**. A stock option's first trade at 09:15 comes straight off
  the continuous order book with no auction. Inference: its spread at that moment is likely the
  widest of the day.
- **Da, Goyenko & Zhang (2025), "Intraday Option Return: A Tale of Two Momentum." Tier: STUDY,
  working paper. US equity options, 2010-2018.**
  - Delta-neutral straddle returns are most negative in the morning: −0.07% and −0.12% for the
    first two half-hours, vs about −0.04% by the close.
  - Effective spreads and price impact are highest in the first interval (the "morning jolt").
  - The direction plausibly applies to NSE; the size of the effect there is unknown.
- **Agarwalla & Pandey (2012), IIMA WP. Tier: STUDY.** Intraday volatility on Indian stocks
  follows a reverse-J shape, highest at the open.
- **SEBI FY22-24 study. Tier: STUDY, regulator data.** 93% of individual F&O traders lost
  money. Transaction costs were about 28% of those losses.
- **Theta size, from Black-Scholes, not a study:**
  - An ATM call at 35% implied volatility is worth about 3.7% of spot with 25 days to expiry,
    and about 2.3% with 10 days.
  - Daily theta is about premium ÷ (2 × days to expiry), which is roughly 2%/day at 25 days
    and 5%/day at 10 days.
  - At delta 0.5, a 1% move in the stock is worth about 14% of premium at 25 days to expiry.

## What this implies for the spec

**Supported enough to test**

- Opening gap relative to the trigger, and the size of the gap, as a HOLD predictor: Berkman
  (STUDY, US).
- Prior-day attention (the absolute size of yesterday's return, and yesterday's volume ratio)
  as a HOLD predictor: Berkman (STUDY). **It overlaps the gap feature**, so the two are
  decomposed rather than stacked (checklist item 7).
- Early relative volume as a FIRE predictor: Zarattini et al. (PRAC-DATA, US, no slippage).

**Weak**

- Direction of the first 5-minute candle: PRAC-DATA, and the edge is about equal to costs.
- Market opening gap: STUDY, but at index level. Use it as a conditioning variable, not a
  primary one.

**Not supported: FOLKLORE, or no data found**

- VWAP reclaim/rejection.
- NSE gap-fill percentages.
- O'Neil breakout volume.
- Any published statistic on hold/reject after a touch.

**On a blind entry at 09:15.** Every study-backed item points *against* it:

- The opening price of an attention stock is inflated.
- Option spreads are widest at the open, and stock options get no auction.
- Straddle value bleeds fastest in the morning.

There is one mixed item. Lou, Polk & Skouras find that outside the US, momentum accrues
intraday, which would make buying at the open *less* costly for momentum stocks. The literature
does not settle the question; our own real option legs have to.

## URLs visited

- https://www.wealth-lab.com/api/discussion/download/pdf/8007-ssrn-4729284-1-pdf
- https://www.mql5.com/en/blogs/post/776235
- https://www.quantconnect.com/research/18444/opening-range-breakout-for-stocks-in-play/
- https://ideas.repec.org/a/eee/finlet/v10y2013i1p27-33.html
- https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/paying-attention-overnight-returns-and-the-hidden-cost-of-buying-at-the-open/F9AAD159B512C651F09D5D52011D88E0
- https://www.smallake.kr/wp-content/uploads/2015/01/SSRN-id2440866.pdf
- https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
- https://repository.up.ac.za/server/api/core/bitstreams/f829a6c1-5762-48b1-89eb-a1ef54125843/content
- https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/c953a0e6-e93e-4bf7-b839-45a90cedced4.pdf
- https://academicweb.nd.edu/~zda/IntraOption.pdf
- http://www.efmaefm.org/0EFMAMEETINGS/EFMA%20ANNUAL%20MEETINGS/2024-Lisbon/papers/EndofDayReversal_withnames.pdf
- https://www.cxoadvisory.com/momentum-investing/intraday-stock-price-momentum-and-reversal-trading/
- https://www.iima.ac.in/sites/default/files/rnpfiles/19191060542012-11-03.pdf
- https://aibi.org.in/Sebipr/Updated_SEBI_Study_Reveals_93_percentage_of_Individual_Traders_Incurred_Losses_in_Equity_F&O_between_FY22_and_FY24.pdf
- https://qullamaggie.com/my-3-timeless-setups-that-have-made-me-tens-of-millions/
- https://tradingresourcehub.substack.com/p/interview-qullamaggie-chat-with-traders-part1
- https://www.financialwisdomtv.com/post/qullamaggie-breakout-setup-case-study-what-the-top-100-winning-stocks-reveal
- https://www.linkedin.com/pulse/overnight-vs-intraday-returns-indian-equity-markets-praveen-kumar

Seen in search results only (blocked or not fetched): SSRN 4416622, 1625495, 2905713,
5198458, 4631351; Aboody et al. (JFQA); Gao et al. (JFE, ScienceDirect); Akbas et al. 2022
(JFE); Wiley fima.12284; the Monash NSE intraday liquidity paper; Tandfonline papers on the NSE
pre-open auction; NSE/broker pages on the December 2025 pre-open change.
