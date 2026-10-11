"""EMAPB v2 -- full pipeline: Stage 0 (established uptrend) gating Stage A-D (advance -> pullback
-> base -> breakout), per EMAPB_STAGE0_SPEC_FINAL.md Revision 4 (2026-10-11).

Architecture:
  - Stage 0 runs continuously per ticker on the confirmed-swing event stream (K=2), tracking
    NO_TREND / ESTABLISHED / PENDING_WARNING via pivot_list (Structure 1, establishment + fresh-
    cycle bookkeeping only) and defended_low/reference_high/pending_warning (Structure 2,
    append-only event-stream tracking, confirmation-triggered per the per-bar order: close-check
    before today's new confirmations).
  - Fresh-cycle fix (the final blocking item): on invalidation, pivot_list is reset AND an
    `eligible_floor` (the invalidation's pivot-date boundary) is recorded. Any pivot whose pivot
    date <= eligible_floor is skipped entirely when rebuilding pivot_list -- not appended, not
    replaced-as-tail, not locked, not used for any establishment check. It may still exist in the
    full event stream for audit, but never touches pivot_list again.
  - Stage A's "advance" is anchored directly to Stage 0's own defended_low/reference_high: the
    moment Stage 0 ESTABLISHES, the L2->H2 pair is the first advance candidate. Any subsequent
    reference_high update while still searching for a base extends the same candidate's peak
    (Stage 0's own tracking IS the extension mechanism -- no separate logic needed). Stage A
    qualifies if (reference_high - defended_low) >= 2*ATR(20 at the defended_low's swing date) and
    the swing-low-to-swing-high separation >= 3 sessions.
  - Stage B (pullback): a narrower, LOCAL invalidation for this specific candidate leg (2/3
    retracement of the advance, or a close below the advance's own swing low) -- distinct from and
    independent of Stage 0's broader trend invalidation. Losing Stage B cancels only the current
    Stage A/B/C/D candidate; Stage 0's established uptrend can persist and spawn a new candidate
    later. Losing Stage 0 cancels everything in flight (per Section 4 of the spec) and forces a
    fresh Stage 0 search.
  - Stage C (base): unchanged 5-bar front-loaded-low-stabilization + 3*ATR width cap, from
    EMAPB_SPEC_v1.md.
  - Stage D (breakout): unchanged close-over-resistance, one breakout per base.

Track B (descriptive only, never gates Track A): breakout-day EOD close -> next-trading-day EOD
close return.

Usage: python3 swing_qs_emapb/35_emapb_v2_full_pipeline.py [--tickers T1,T2,...] [--limit N]
"""
import sys, os, argparse
sys.path.insert(0, '/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
os.chdir('/Users/mdubey/workspace/personal/my-utilities/md-swing-scanner')
import numpy as np
import pandas as pd
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
SWING_K = 2
ATR_WINDOW = 20
ADVANCE_MIN_ATR_MULT = 2.0
ADVANCE_MIN_SEPARATION_DAYS = 3
RETRACEMENT_DISQUALIFY = 2.0 / 3.0
BASE_WINDOW = 5
BASE_STABILIZE_TAIL = 2
BASE_MAX_RANGE_ATR_MULT = 3.0


def load_daily(path):
    d = pd.read_csv(path)
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if d.empty or len(d) < 80 or not required.issubset(d.columns):
        return None
    d["Date"] = pd.to_datetime(d.Date)
    d = d.sort_values("Date").drop_duplicates("Date").reset_index(drop=True)
    d["prev_close"] = d.Close.shift(1)
    d["tr"] = pd.concat([
        d.High - d.Low, (d.High - d.prev_close).abs(), (d.Low - d.prev_close).abs(),
    ], axis=1).max(axis=1)
    d["atr20"] = d.tr.rolling(ATR_WINDOW).mean()
    return d


def confirmed_swings(d):
    n = len(d)
    is_low = np.zeros(n, dtype=bool)
    is_high = np.zeros(n, dtype=bool)
    dual = np.zeros(n, dtype=bool)
    for i in range(SWING_K, n - SWING_K):
        wl = d.Low.iloc[i - SWING_K:i + SWING_K + 1].values
        wh = d.High.iloc[i - SWING_K:i + SWING_K + 1].values
        low_ok = d.Low.iloc[i] == wl.min() and (wl == d.Low.iloc[i]).sum() == 1
        high_ok = d.High.iloc[i] == wh.max() and (wh == d.High.iloc[i]).sum() == 1
        if low_ok and high_ok:
            dual[i] = True  # excluded from both structures per spec Section 1
        elif low_ok:
            is_low[i] = True
        elif high_ok:
            is_high[i] = True
    return is_low, is_high, dual


class Stage0:
    """Structure 1 (pivot_list, establishment + fresh-cycle) and Structure 2 (event-stream
    tracking) per EMAPB_STAGE0_SPEC_FINAL.md Revision 4."""
    def __init__(self):
        self.pivot_list = []  # list of (type, index, price); type in {'L','H'}
        self.state = "NO_TREND"
        self.defended_low = None
        self.defended_low_idx = None
        self.reference_high = None
        self.reference_high_idx = None
        self.pending_warning = None  # (confirm_index, snapshot_defended_low)
        self.eligible_floor = -1  # pivot-date boundary; pivots with index <= this are ineligible

    def feed_pivot(self, ptype, idx, price, log):
        """Called once per confirmed (non-dual) swing, at its confirmation point, in order."""
        if self.state == "NO_TREND":
            self._feed_establishment(ptype, idx, price, log)
        else:
            self._feed_tracking(ptype, idx, price, log)

    def _feed_establishment(self, ptype, idx, price, log):
        if idx <= self.eligible_floor:
            log.append(dict(event="pre_boundary_excluded", idx=idx, ptype=ptype, price=price))
            return  # never touches pivot_list -- the fresh-cycle fix
        pl = self.pivot_list
        if pl and pl[-1][0] == ptype:
            pl[-1] = (ptype, idx, price)  # replace tail
        else:
            if pl:
                locked = pl[-1]
                # check establishment: the 4 entries ending at the just-locked pivot
                if len(pl) >= 4 and locked[0] == 'H':
                    L1, H1, L2, H2 = pl[-4], pl[-3], pl[-2], pl[-1]
                    if (L1[0] == 'L' and H1[0] == 'H' and L2[0] == 'L' and H2[0] == 'H'
                            and L2[2] > L1[2] and H2[2] > H1[2]):
                        self.state = "ESTABLISHED"
                        self.defended_low, self.defended_low_idx = L2[2], L2[1]
                        self.reference_high, self.reference_high_idx = H2[2], H2[1]
                        log.append(dict(event="stage0_established", idx=idx, defended_low=L2[2],
                                         reference_high=H2[2]))
            pl.append((ptype, idx, price))

    def _feed_tracking(self, ptype, idx, price, log):
        if ptype == 'L':
            if self.pending_warning is None and price > self.defended_low:
                self.defended_low, self.defended_low_idx = price, idx
        else:  # High
            if price > self.reference_high:
                self.reference_high, self.reference_high_idx = price, idx
                if self.pending_warning is not None:
                    log.append(dict(event="warning_cleared", idx=idx))
                    self.pending_warning = None
            elif price < self.reference_high:
                if self.pending_warning is None:
                    self.pending_warning = (idx, self.defended_low)
                    log.append(dict(event="lower_high_warning", idx=idx, snapshot=self.defended_low))

    def check_close_invalidation(self, idx, close_price, log):
        """Step 1 of the per-bar order -- must run BEFORE feed_pivot for today's confirmations."""
        if self.state == "ESTABLISHED" and self.pending_warning is not None:
            _, snapshot = self.pending_warning
            if close_price < snapshot:
                log.append(dict(event="invalidated", idx=idx, snapshot=snapshot))
                self.state = "NO_TREND"
                self.pivot_list = []
                self.eligible_floor = idx
                self.defended_low = self.reference_high = self.pending_warning = None
                return True
        return False


def run_ticker(ticker, d):
    n = len(d)
    is_low, is_high, dual = confirmed_swings(d)
    s0 = Stage0()
    log = []
    episodes = []

    # Stage A-D candidate state
    cand_state = None  # None, "PULLBACK_SEARCHING_BASE", "CONFIRMED_BASE_WAITING_BREAKOUT"
    swing_low_price = swing_low_i = peak_price = peak_i = None
    search_start = box_high = box_low = box_start = box_end = None
    last_tried_pair = None  # (defended_low_idx, reference_high_idx) already attempted -- don't retry unchanged

    for i in range(SWING_K, n - SWING_K):
        confirmed_i = i  # the pivot at bar (i - SWING_K) is confirmed as of bar i
        pivot_bar = i - SWING_K

        # step 1: close-check BEFORE today's new confirmations
        was_established = (s0.state == "ESTABLISHED")
        invalidated = s0.check_close_invalidation(i, d.Close.iloc[i], log)
        if invalidated and cand_state is not None:
            episodes.append(dict(ticker=ticker, outcome="stage0_invalidated_cancelled_candidate",
                                  cand_state=cand_state, swing_low_date=d.Date.iloc[swing_low_i],
                                  peak_date=d.Date.iloc[peak_i], invalidation_date=d.Date.iloc[i]))
            cand_state = None

        # step 2: process today's confirmations
        if dual[pivot_bar]:
            log.append(dict(event="dual_pivot_excluded", idx=pivot_bar))
        else:
            if is_low[pivot_bar]:
                ref_high_before = s0.reference_high
                s0.feed_pivot('L', pivot_bar, d.Low.iloc[pivot_bar], log)
            if is_high[pivot_bar]:
                ref_high_before = s0.reference_high
                s0.feed_pivot('H', pivot_bar, d.High.iloc[pivot_bar], log)

        # Stage A candidate start/extension: only while ESTABLISHED
        if s0.state == "ESTABLISHED":
            current_pair = (s0.defended_low_idx, s0.reference_high_idx)
            if (cand_state is None and s0.defended_low_idx is not None and s0.reference_high_idx is not None
                    and s0.reference_high_idx > s0.defended_low_idx and current_pair != last_tried_pair):
                atr_sl = d.atr20.iloc[s0.defended_low_idx]
                rise = s0.reference_high - s0.defended_low
                sep_days = s0.reference_high_idx - s0.defended_low_idx
                last_tried_pair = current_pair  # mark attempted regardless of outcome below
                if pd.notna(atr_sl) and atr_sl > 0 and rise >= ADVANCE_MIN_ATR_MULT * atr_sl \
                        and sep_days >= ADVANCE_MIN_SEPARATION_DAYS:
                    swing_low_price, peak_price = s0.defended_low, s0.reference_high
                    swing_low_i, peak_i = s0.defended_low_idx, s0.reference_high_idx
                    search_start = max(i + 1, peak_i + 1)
                    cand_state = "PULLBACK_SEARCHING_BASE"
            elif cand_state == "PULLBACK_SEARCHING_BASE" and s0.reference_high > peak_price:
                peak_price = s0.reference_high
                search_start = i + 1

        # Stage B/C/D processing (only if a candidate is active)
        if cand_state in ("PULLBACK_SEARCHING_BASE", "CONFIRMED_BASE_WAITING_BREAKOUT") and i > search_start - 1:
            running_low = d.Low.iloc[max(0, peak_i):i + 1].min()
            retracement = (peak_price - running_low) / (peak_price - swing_low_price) if peak_price > swing_low_price else 0
            close_breach = d.Close.iloc[i] < swing_low_price
            if retracement >= RETRACEMENT_DISQUALIFY or close_breach:
                episodes.append(dict(ticker=ticker, outcome="advance_invalidated",
                                      peak_date=d.Date.iloc[peak_i], invalidation_date=d.Date.iloc[i],
                                      retracement=retracement))
                cand_state = None
                continue

            if cand_state == "PULLBACK_SEARCHING_BASE" and i >= search_start + BASE_WINDOW - 1:
                w0, w1 = search_start, search_start + BASE_WINDOW
                window = d.iloc[w0:w1]
                min_low = window.Low.min()
                min_low_pos = window.Low.values.argmin()
                tail = window.Low.iloc[-BASE_STABILIZE_TAIL:]
                stabilized = (min_low_pos <= 2) and (tail > min_low).all()
                atr_start = d.atr20.iloc[w0]
                rng = window.High.max() - window.Low.min()
                width_ok = pd.notna(atr_start) and atr_start > 0 and rng <= BASE_MAX_RANGE_ATR_MULT * atr_start
                if stabilized and width_ok:
                    box_high, box_low = window.High.max(), window.Low.min()
                    box_start, box_end = w0, w1 - 1
                    cand_state = "CONFIRMED_BASE_WAITING_BREAKOUT"
                else:
                    search_start += 1
            elif cand_state == "CONFIRMED_BASE_WAITING_BREAKOUT" and i >= box_end + 1:
                if d.Close.iloc[i] < box_low:
                    episodes.append(dict(ticker=ticker, outcome="base_invalidated",
                                          box_start_date=d.Date.iloc[box_start], box_end_date=d.Date.iloc[box_end],
                                          box_high=box_high, box_low=box_low, invalidation_date=d.Date.iloc[i]))
                    cand_state = "PULLBACK_SEARCHING_BASE"
                    search_start = i + 1
                elif d.Close.iloc[i] > box_high:
                    d0_close = d.Close.iloc[i]
                    d1_ret = ((d.Close.iloc[i + 1] / d0_close - 1) * 100) if i + 1 < n else np.nan
                    episodes.append(dict(ticker=ticker, outcome="breakout",
                                          swing_low_date=d.Date.iloc[swing_low_i], peak_date=d.Date.iloc[peak_i],
                                          box_start_date=d.Date.iloc[box_start], box_end_date=d.Date.iloc[box_end],
                                          box_high=box_high, box_low=box_low,
                                          breakout_date=d.Date.iloc[i], breakout_close=d0_close,
                                          track_b_d1_ret=d1_ret))
                    cand_state = None

    return episodes, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.tickers:
        files = [f"data/daily/{t}.csv" for t in args.tickers.split(",")]
    else:
        files = sorted(glob.glob("data/daily/*.csv"))
        if args.limit:
            files = files[:args.limit]

    all_rows = []
    for n, f in enumerate(files):
        ticker = os.path.basename(f).replace(".csv", "")
        d = load_daily(f)
        if d is None:
            continue
        rows, _log = run_ticker(ticker, d)
        all_rows.extend(rows)
        if (n + 1) % 200 == 0:
            print(f"  ...{n+1}/{len(files)} tickers")

    df = pd.DataFrame(all_rows)
    df.to_csv(f"{HERE}/rq_emapb_v2_episodes.csv", index=False)
    print(f"\nTotal episode records: {len(df):,}\n")
    if not df.empty:
        print(df.outcome.value_counts())
        bo = df[df.outcome == "breakout"]
        if len(bo):
            print(f"\n=== Breakouts: n={len(bo):,} ===")
            print(bo.track_b_d1_ret.describe(percentiles=[.1, .25, .5, .75, .9]).round(2))
            print(f"% positive: {(bo.track_b_d1_ret > 0).mean()*100:.1f}%")


if __name__ == "__main__":
    main()
