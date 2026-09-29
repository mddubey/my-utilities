import csv
import math
import sys

# ── Configurable constants ─────────────────────────────────────────────────────
LOT_SIZE         = 65
CSV_FILE         = 'options.csv'
SPREAD_WIDTH     = 50      # fixed spread width in index points
DELTA_MIN        = 0.22    # lower bound for short-strike |delta|
DELTA_MAX        = 0.28    # upper bound for short-strike |delta|
MIN_CREDIT_RATIO = 0.25    # credit must be ≥ 25% of spread width
MAX_LOSS_RATIO   = 3.5     # max loss must be ≤ 3.5 × credit
RISK_FREE_RATE   = 0.065   # annual risk-free rate (RBI repo ~6.5%)

# CSV column indices (0-based).
# Default layout: NSE option chain CSV with one empty column before STRIKE.
# Verify against your file's second header row if delta values look wrong.
COL_STRIKE = 11
COL_CE_LTP = 5
COL_CE_IV  = 4
COL_PE_LTP = 17
COL_PE_IV  = 18


# ── Black-Scholes helpers ──────────────────────────────────────────────────────
def _ncdf(x):
    """Cumulative standard normal distribution."""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def bs_delta(S, K, T, r, sigma, option_type):
    """
    Black-Scholes delta.
    Returns None for degenerate inputs (expired, zero IV, etc.).
    CE delta ∈ (0, 1); PE delta ∈ (-1, 0).
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return None
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return _ncdf(d1) if option_type == 'CE' else _ncdf(d1) - 1.0


# ── CSV loader ─────────────────────────────────────────────────────────────────
def _parse_float(s):
    s = s.replace(',', '').strip()
    return float(s) if s and s != '-' else 0.0


def load_option_chain(spot, T):
    """
    Read options.csv and return a list of dicts:
      {strike, ce_ltp, pe_ltp, ce_delta, pe_delta}
    Delta is computed from IV (percentage column) via Black-Scholes.
    """
    min_cols = max(COL_STRIKE, COL_CE_LTP, COL_CE_IV, COL_PE_LTP, COL_PE_IV) + 1
    rows = []
    with open(CSV_FILE, newline='') as f:
        reader = csv.reader(f)
        next(reader)   # row 1: "CALLS,,PUTS" title
        next(reader)   # row 2: column headers
        for raw in reader:
            if len(raw) < min_cols:
                continue
            try:
                strike  = int(_parse_float(raw[COL_STRIKE]))
                ce_ltp  = _parse_float(raw[COL_CE_LTP])
                pe_ltp  = _parse_float(raw[COL_PE_LTP])
                ce_iv   = _parse_float(raw[COL_CE_IV])  / 100.0  # % → decimal
                pe_iv   = _parse_float(raw[COL_PE_IV])  / 100.0

                rows.append(dict(
                    strike   = strike,
                    ce_ltp   = ce_ltp,
                    pe_ltp   = pe_ltp,
                    ce_delta = bs_delta(spot, strike, T, RISK_FREE_RATE, ce_iv, 'CE'),
                    pe_delta = bs_delta(spot, strike, T, RISK_FREE_RATE, pe_iv, 'PE'),
                ))
            except (ValueError, IndexError):
                continue
    return rows


# ── Spread builder ─────────────────────────────────────────────────────────────
def build_spread(side, short_k, hedge_k, short_ltp, hedge_ltp, delta):
    """
    Construct a 50-point vertical credit spread and apply risk filters.
    Returns a dict on success, None if the spread fails any filter.
    """
    credit   = short_ltp - hedge_ltp
    max_loss = SPREAD_WIDTH - credit

    ok_credit = credit >= SPREAD_WIDTH * MIN_CREDIT_RATIO
    ok_ratio  = credit > 0 and max_loss <= MAX_LOSS_RATIO * credit
    passes    = ok_credit and ok_ratio

    # Breakeven at expiry
    breakeven = short_k + credit if side == 'CE' else short_k - credit

    # Profit-target buyback prices:
    #   50% target → buy back spread at 50% of credit received
    #   70% target → buy back spread at 30% of credit received
    tgt_50 = credit * 0.50
    tgt_70 = credit * 0.30

    return dict(
        side         = side,
        short_strike = short_k,
        hedge_strike = hedge_k,
        delta        = delta,
        credit       = credit,
        max_loss     = max_loss,
        breakeven    = breakeven,
        tgt_50       = tgt_50,
        tgt_70       = tgt_70,
        passes       = passes,
    )


# ── Output ─────────────────────────────────────────────────────────────────────
RED   = '\033[91m'
RESET = '\033[0m'

def print_table(spreads):
    COL = dict(side=5, short=7, hedge=7, delta=7,
               credit=8, maxloss=8, beven=9,
               t50=8, t70=8,
               risk_lot=10, profit_lot=11, p50_lot=10, p70_lot=10,
               flag=4)
    hdr = (
        f"{'Side':<{COL['side']}} "
        f"{'Short':>{COL['short']}} "
        f"{'Hedge':>{COL['hedge']}} "
        f"{'Delta':>{COL['delta']}} "
        f"{'Credit':>{COL['credit']}} "
        f"{'MaxLoss':>{COL['maxloss']}} "
        f"{'BEven':>{COL['beven']}} "
        f"{'50%Tgt':>{COL['t50']}} "
        f"{'70%Tgt':>{COL['t70']}} "
        f"{'RiskPerLot':>{COL['risk_lot']}} "
        f"{'ProfitPerLot':>{COL['profit_lot']}} "
        f"{'Prof@50%':>{COL['p50_lot']}} "
        f"{'Prof@70%':>{COL['p70_lot']}} "
        f"{'':>{COL['flag']}}"
    )
    sep = "─" * len(hdr)
    print(sep)
    print(hdr)
    print(sep)
    for s in spreads:
        risk_lot   = s['max_loss']        * LOT_SIZE
        profit_lot = s['credit']           * LOT_SIZE
        p50_lot    = s['credit'] * 0.50    * LOT_SIZE   # profit kept at 50% exit
        p70_lot    = s['credit'] * 0.70    * LOT_SIZE   # profit kept at 70% exit
        row = (
            f"{s['side']:<{COL['side']}} "
            f"{s['short_strike']:>{COL['short']}} "
            f"{s['hedge_strike']:>{COL['hedge']}} "
            f"{s['delta']:>{COL['delta']}.3f} "
            f"{s['credit']:>{COL['credit']}.2f} "
            f"{s['max_loss']:>{COL['maxloss']}.2f} "
            f"{s['breakeven']:>{COL['beven']}.2f} "
            f"{s['tgt_50']:>{COL['t50']}.2f} "
            f"{s['tgt_70']:>{COL['t70']}.2f} "
            f"₹{risk_lot:>{COL['risk_lot']-1},.0f} "
            f"₹{profit_lot:>{COL['profit_lot']-1},.0f} "
            f"₹{p50_lot:>{COL['p50_lot']-1},.0f} "
            f"₹{p70_lot:>{COL['p70_lot']-1},.0f} "
            f"{'':>{COL['flag']}}"
        )
        if s['passes']:
            print(row)
        else:
            print(f"{RED}{row}  ●{RESET}")
    print(sep)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) >= 3:
        spot = float(sys.argv[1])
        DTE  = int(sys.argv[2])
        print(f"Spot={spot:.0f}  DTE={DTE}")
    else:
        spot = float(input("Enter current Nifty spot: "))
        DTE  = int(input("Enter days to expiry (1-7): "))

    T = DTE / 365.0
    print(
        f"Delta range : [{DELTA_MIN}, {DELTA_MAX}]\n"
        f"Spread width: {SPREAD_WIDTH} pts\n"
        f"Filters     : Credit ≥ {MIN_CREDIT_RATIO*100:.0f}% of width  |  "
        f"Max Loss ≤ {MAX_LOSS_RATIO}× Credit\n"
    )

    chain  = load_option_chain(spot, T)
    lookup = {r['strike']: r for r in chain}

    spreads = []

    for row in chain:
        # ─ CE side: delta in [DELTA_MIN, DELTA_MAX] ─
        d = row['ce_delta']
        if d is not None and DELTA_MIN <= d <= DELTA_MAX:
            hedge_k = row['strike'] + SPREAD_WIDTH
            if hedge_k in lookup:
                s = build_spread(
                    'CE', row['strike'], hedge_k,
                    row['ce_ltp'], lookup[hedge_k]['ce_ltp'], d,
                )
                if s:
                    spreads.append(s)

        # ─ PE side: |delta| in [DELTA_MIN, DELTA_MAX] ─
        d = row['pe_delta']
        if d is not None and DELTA_MIN <= abs(d) <= DELTA_MAX:
            hedge_k = row['strike'] - SPREAD_WIDTH
            if hedge_k in lookup:
                s = build_spread(
                    'PE', row['strike'], hedge_k,
                    row['pe_ltp'], lookup[hedge_k]['pe_ltp'], d,
                )
                if s:
                    spreads.append(s)

    if not spreads:
        print("No qualifying delta strikes this week.")
        return

    # Sort: CE first, then PE; within each side by |delta| descending (closer to ATM first)
    spreads.sort(key=lambda x: (x['side'], -abs(x['delta'])))

    print_table(spreads)
    passed = sum(1 for s in spreads if s['passes'])
    print(f"\n{len(spreads)} spread(s) in delta range — {passed} pass risk filters, {len(spreads)-passed} flagged red.")
    print("50%Tgt / 70%Tgt = buyback spread price to lock in 50% / 70% of credit.")
    if len(spreads) - passed:
        print(f"Red = Credit < {MIN_CREDIT_RATIO*100:.0f}% of {SPREAD_WIDTH}pts  OR  MaxLoss > {MAX_LOSS_RATIO}× Credit")


if __name__ == '__main__':
    main()
