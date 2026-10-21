# Morning fade, 1-minute study (2026-10-20, Dussehra holiday)

RESULTS ONLY -- nothing here is adopted. Not in STRATEGY.md until discussed and agreed with the user.
One week (2026-10-12..10-19, all Nifty below its 200-day), mechanical entries, gross of slippage.

## Data
- `m1/` = Yahoo 1-minute bars for every stock on the saved 09:21 ORB in-play lists of 2026-10-12/13/14/15/16/19,
  plus `_NIFTY.csv`. NOT committed (22 MB) and NOT regeneratable after ~mid-Nov 2026 (Yahoo keeps ~30 days of 1-min).
- `fetch1m.py` rebuilt it (only works while Yahoo still has those dates).

## Shapes (the user's own split of the morning fade)
- A = failed breakout (reversal): a fade level (09:15 high, yday high/close, R1/R2, daily 8) crossed 09:20-09:45,
  a 1-min close back under within 10 min = entry, stop = spike high + 0.05%.
- B = pullback continuation: red 09:15 candle, bounce peak 09:20-09:45 under the 09:15 high and >= 0.3% off the low,
  entry = first 1-min close >= 0.2% below the peak (by 10:00), stop = peak + 0.05%.

## Scripts and results (held to 14:15 or the stop; Rs per Rs1k risk net of Rs85/lakh)
| Script | Question | Result |
|---|---|---|
| `shapes.py` -> `shape_A.csv`, `shape_B.csv` | find A / B cases | B 50: +1.50R avg, 52% win, fat tail. A 45: 22% win; green-09:15 A 11% win, -0.51R |
| (inline) | full-green bounce bars (user's skip rule) | B with full-green bars 35% win vs 71% without |
| (inline) | are B stops shakeouts? | 26 stopped: 14 had been +2R first, 6 real reversals (2-10% past), ~2-3 cheap blips; median 64 min to stop |
| `buffer.py` | stop buffer 0.05 / 0.2 / 0.35 / 0.5% | 0.35%: 62% win, +50.8k (w/o top-3 +28.1k ~ same as tight +29.3k), smaller bad days; 0.2% saved nothing |
| `be.py` | stop to entry after +1/2/3R | tight stop + BE after +2R: +69.4k vs hold +68.1k, full losses 24 -> 11. On the 0.35% stop BE hurts (-5..-10k) |
| `compare.py` | user's real trades vs system / own entry + 0.35% stop + hold | user's 4 taken: actual +3.3%, own entries + room + hold +9.2%; no room stop hit |
| `rs.py`, `rs2.py` | weak vs strong vs Nifty (since open / day change / bounce) | since-open split degenerate (45/50 weaker); day change and bounce: no usable signal -- dropped by the user |
| `fade_after.py`, `orb_day.py`, `orb_two.py`, `live20.py` | live-day helpers (2026-10-19): post-exit paths, ORB low-break, push-high fade | descriptive |

Open decision (user, for live trading): (a) tight stop + BE after +2R + out 14:15, or (b) 0.35% room + hold to 14:15.
