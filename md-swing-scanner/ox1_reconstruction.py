"""
OX1 -- Stock -> Option Intraday Reconstruction (Research Infrastructure)

Status: PROMOTED (RQ-OX1-A/B/C/D, 2026-09-21 through 2026-09-23) to
Research Infrastructure / Validated Reconstruction Layer.
NOT production. NOT an execution simulator. NOT a trading signal.
Full validation record: FINDINGS.md, search "RQ-OX1-A" through "RQ-OX1-D".

Canonical OX1 Principle (critic, RQ-OX1-D review, verbatim):
  OX1 is validated for comparative research across candidate exit timings,
  not for asserting executable historical option prices.

Architectural boundary (critic, RQ-OX1-D disposition):
  option_backtest.py remains the production/reference engine.
  This module is the research infrastructure provider, consumed by
  research RQ-*.py scripts only. Do not import this into
  option_backtest.py, daily_scan.py, or any live/production path.

Non-goals, explicit:
  - No numeric confidence interval or probability -- categorical flags
    only, until there is a validated basis for a number.
  - No execution-price estimate of any kind (see executable_price below).
  - No wiring into any live/production path.
  - No change to any existing trading rule, gate, or exit logic.
  - OX1 outputs must never be used as an optimization target (don't
    optimize a stop, hold duration, or threshold against a reconstructed
    premium -- that's exactly how reconstruction uncertainty creeps into
    an objective function as fake precision).

Honest limitation, verbatim from the critic's own RQ-OX1-D review:
  The confidence flags describe known degradation conditions, not
  estimated reconstruction error. Not proven: that the flags are
  exhaustive, that each flag independently explains error magnitude,
  or that multiple flags combine monotonically.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

BETA_ATM_CURRENT = 0.492  # frozen, RQ-OX1-A stratum median. Never refit here.
RECONSTRUCTION_METHOD = "OX1_beta_v1_ATM_current_0.492"

# Heuristic thresholds below are honest heuristics grounded in the
# validated n=9 pilot's general character (RQ-OX1-B/C), NOT fit or tuned
# to match its 2 known best-exit mismatches (ATHERENERG, SOLARINDS) --
# doing that would be exactly the threshold-hunting Research Integrity
# Rule #6 forbids. They are round, pre-registered-style numbers, not an
# optimized cutoff.
LARGE_MOVE_THRESHOLD_PCT = 3.0        # pilot's stock moves ranged ~0-5.7%
LATE_SESSION_CHECKPOINT_MIN = 120     # +120min and beyond; OX1 Continuous Trading Rule
PATH_REVERSAL_RETRACE_FRAC = 0.5      # retraced >=50% of its own intraday excursion
MONEYNESS_BAND_PCT = 2.0              # matches RQ-OX1-A's ATM band definition


@dataclass
class ContractMetadata:
    ticker: str
    strike: float
    expiry: str
    option_type: str  # "CE" or "PE"
    moneyness_at_entry_pct: float
    moneyness_bucket: str  # "ATM" / "ITM" / "OTM"


@dataclass
class Reconstruction:
    reconstructed_option_value: float
    reconstruction_method: str
    timestamp: str
    contract_metadata: ContractMetadata
    reconstruction_flags: List[str]
    reconstruction_confidence: str  # BASELINE / CAUTION / LOW_CONFIDENCE
    executable_price: Optional[float]
    execution_status: str


def _moneyness_bucket(spot: float, strike: float, band_pct: float = MONEYNESS_BAND_PCT) -> str:
    diff_pct = (spot - strike) / strike * 100
    if abs(diff_pct) <= band_pct:
        return "ATM"
    return "ITM" if diff_pct > 0 else "OTM"


def _path_reversal(stock_path: List[Tuple[str, float]]) -> bool:
    """stock_path: chronological (timestamp, price), entry first, current last.
    True if price has retraced >=PATH_REVERSAL_RETRACE_FRAC of its own
    largest intraday excursion from entry (the path-dependent
    deterioration/fade family from OX1-B/C, generalized per the critic's
    RQ-OX1-D review beyond a literal direction-sign flip)."""
    if len(stock_path) < 3:
        return False
    s0 = stock_path[0][1]
    moves = [p - s0 for _, p in stock_path]
    extremum = max(moves, key=abs)
    current = moves[-1]
    if extremum == 0:
        return False
    same_side = (extremum > 0) == (current > 0) or current == 0
    retrace = 1 - (current / extremum) if same_side else 1.0
    return retrace >= PATH_REVERSAL_RETRACE_FRAC


def reconstruct_option_value(
    ticker: str,
    strike: float,
    expiry: str,
    option_type: str,
    entry_timestamp: str,
    entry_spot: float,
    entry_option_price: float,
    current_timestamp: str,
    stock_path: List[Tuple[str, float]],
    moneyness: str = "atm",
    expiry_choice: str = "current",
    beta: float = BETA_ATM_CURRENT,
) -> Reconstruction:
    """
    stock_path: list of (timestamp:str ISO8601 IST, price:float),
    chronological, entry_timestamp first, current_timestamp last.

    Only ATM/current-month is validated (RQ-OX1-A/B/C, n=9 real intraday
    paths). Other moneyness/expiry combos are allowed but carry an
    UNVALIDATED_STRATUM flag and LOW_CONFIDENCE -- they were never tested
    at intraday checkpoints.
    """
    current_spot = stock_path[-1][1]
    delta_s = current_spot - entry_spot
    reconstructed_value = entry_option_price + beta * delta_s

    entry_moneyness_pct = (entry_spot - strike) / strike * 100
    entry_bucket = _moneyness_bucket(entry_spot, strike)
    current_bucket = _moneyness_bucket(current_spot, strike)

    flags = []

    stock_move_pct = (current_spot - entry_spot) / entry_spot * 100
    if abs(stock_move_pct) >= LARGE_MOVE_THRESHOLD_PCT:
        flags.append("LARGE_MOVE")

    # LATE_SESSION measures minutes elapsed since the CURRENT checkpoint's
    # own trading-session open (09:15 IST same calendar day), not minutes
    # since entry_timestamp. In the validated n=9 pilot these were always
    # identical (entry was always 09:15 same-day), so the distinction never
    # showed up -- but for a cross-day application (entry = prior day's
    # close, checkpoint = next day's 09:30/10:00/11:30) elapsed-since-entry
    # would always exceed any reasonable threshold and the flag would fire
    # on every row, which defeats its purpose. This generalizes correctly
    # to both the same-day and cross-day case.
    current_dt = datetime.fromisoformat(current_timestamp)
    session_open = current_dt.replace(hour=9, minute=15, second=0, microsecond=0)
    elapsed_in_session_min = (current_dt - session_open).total_seconds() / 60
    if elapsed_in_session_min >= LATE_SESSION_CHECKPOINT_MIN:
        flags.append("LATE_SESSION")

    if entry_bucket != current_bucket:
        flags.append("MONEYNESS_TRANSITION")

    if _path_reversal(stock_path):
        flags.append("PATH_DEPENDENCE")

    if moneyness != "atm" or expiry_choice != "current":
        flags.append("UNVALIDATED_STRATUM")

    if not flags:
        confidence = "BASELINE"
    elif "UNVALIDATED_STRATUM" in flags or len(flags) >= 2:
        confidence = "LOW_CONFIDENCE"
    else:
        confidence = "CAUTION"

    return Reconstruction(
        reconstructed_option_value=round(reconstructed_value, 2),
        reconstruction_method=RECONSTRUCTION_METHOD,
        timestamp=current_timestamp,
        contract_metadata=ContractMetadata(
            ticker=ticker,
            strike=strike,
            expiry=expiry,
            option_type=option_type,
            moneyness_at_entry_pct=round(entry_moneyness_pct, 2),
            moneyness_bucket=entry_bucket,
        ),
        reconstruction_flags=flags,
        reconstruction_confidence=confidence,
        executable_price=None,
        execution_status="NOT_MODELED",
    )
