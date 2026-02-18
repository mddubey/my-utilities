import csv
import sys

LOT_SIZE = 65  # constant lot size
CSV_FILE = 'options.csv'  # always read this

# Risk thresholds for payoff evaluation
MAX_LOSS_LIMIT = 3500  # Max acceptable loss threshold
MAX_LOSS_TO_PROFIT_RATIO = 3.5  # Max acceptable loss-to-profit ratio (e.g., 3.5:1 means max loss can be 3.5x max profit)

# ANSI color codes for terminal output
COLOR_RED = '\033[91m'
COLOR_GREEN = '\033[92m'
COLOR_AMBER = '\033[93m'
COLOR_RESET = '\033[0m'

def colorize_label(label):
    """Add color to risk labels"""
    if label == 'RED':
        return f"{COLOR_RED}●{COLOR_RESET}"
    elif label == 'GREEN':
        return f"{COLOR_GREEN}●{COLOR_RESET}"
    elif label == 'AMBER':
        return f"{COLOR_AMBER}●{COLOR_RESET}"
    return label

def label_distance(distance, DTE):
    if distance <= 50:
        return 'RED'
    elif distance <= 100:
        return 'AMBER'
    else:
        return 'GREEN'

def nearest_strike(spot, step=50):
    return round(spot / step) * step

def generate_candidate_table(spot, DTE, type_name, max_distance=300, step=50):
    candidates = []
    nearest = nearest_strike(spot, step)
    seen_green = False  # Track if we've passed through GREEN zone

    if type_name == 'CE':
        current = nearest if nearest >= spot else nearest + step
        while current <= spot + max_distance:
            distance = current - spot
            label = label_distance(distance, DTE)
            candidates.append((current, label))

            # Track if we've seen GREEN
            if label == 'GREEN':
                seen_green = True

            # Only stop if we've passed GREEN zone and now encounter RED again
            if label == 'RED' and seen_green:
                break

            current += step
    else:  # PE
        current = nearest if nearest <= spot else nearest - step
        while current >= spot - max_distance:
            distance = spot - current
            label = label_distance(distance, DTE)
            candidates.append((current, label))

            # Track if we've seen GREEN
            if label == 'GREEN':
                seen_green = True

            # Only stop if we've passed GREEN zone and now encounter RED again
            if label == 'RED' and seen_green:
                break

            current -= step
    return candidates

def display_candidate_table(candidates, type_name, spot):
    print(f"\n--- {type_name} Candidate Strikes ---")
    print(f"No  Strike   Distance   Label")
    for idx, (strike, label) in enumerate(candidates, 1):
        distance = abs(strike - spot) if type_name == 'CE' else abs(spot - strike)
        print(f"{idx:<3}{strike:<8}{distance:<10}{label:<6}")

def select_strikes_by_index(candidates, indexes):
    return [candidates[i-1][0] for i in indexes]

def parse_index_input(input_str, num_candidates):
    """
    Parse index input supporting individual numbers, ranges, and 'end' keyword.

    Examples:
        "3,4,5" -> [3, 4, 5]
        "3-5" -> [3, 4, 5]
        "3-end" -> [3, 4, ..., num_candidates]
        "1,3-5,7" -> [1, 3, 4, 5, 7]

    Args:
        input_str: User input string
        num_candidates: Total number of candidates available

    Returns:
        List of indexes (capped at num_candidates)
    """
    indexes = []
    parts = input_str.split(',')

    for part in parts:
        part = part.strip()
        if '-' in part:
            # Handle range
            start, end = part.split('-')
            start = start.strip()
            end = end.strip()

            start_idx = int(start)
            end_idx = num_candidates if end == 'end' else int(end)

            # Cap end_idx to available candidates
            end_idx = min(end_idx, num_candidates)

            indexes.extend(range(start_idx, end_idx + 1))
        else:
            # Single number
            idx = int(part)
            # Only add if within bounds
            if idx <= num_candidates:
                indexes.append(idx)

    return indexes

def generate_hedges(short_strike, type_name, spread_width):
    """
    Generate hedge strikes: one at spread_width and one at the next 50-point strike.
    """
    if type_name == 'CE':
        return [short_strike + spread_width, short_strike + 50]
    else:  # PE
        return [short_strike - spread_width, short_strike - 50]

def risk_label(value, limit, higher_is_worse=True):
    """
    Assign risk label based on value and limit.

    Args:
        value: The value to evaluate
        limit: The threshold limit
        higher_is_worse: If True, higher values are worse (e.g., max loss)
                        If False, lower values are worse (e.g., max profit)

    Returns:
        'GREEN', 'AMBER', or 'RED'
    """
    if higher_is_worse:
        # For max loss: lower is better
        if value <= limit * 0.7:  # Under 70% of limit
            return 'GREEN'
        elif value <= limit:  # 70-100% of limit
            return 'AMBER'
        else:  # Over limit
            return 'RED'
    else:
        # For max profit: higher is better
        if value >= limit * 1.5:  # Over 150% of minimum
            return 'GREEN'
        elif value >= limit:  # 100-150% of minimum
            return 'AMBER'
        else:  # Below minimum
            return 'RED'

def ratio_risk_label(max_loss, max_profit, max_ratio):
    """
    Assign risk label based on loss-to-profit ratio for credit spreads.

    Args:
        max_loss: Maximum loss amount
        max_profit: Maximum profit amount
        max_ratio: Maximum acceptable loss-to-profit ratio (e.g., 3.5 means loss can be 3.5x profit)

    Returns:
        'GREEN', 'AMBER', or 'RED'
    """
    if max_profit == 0:
        return 'RED'  # Avoid division by zero

    ratio = max_loss / max_profit

    # GREEN: ratio is under 70% of max acceptable (e.g., under 2.45 for max_ratio=3.5)
    # AMBER: ratio is 70-100% of max acceptable (e.g., 2.45-3.5 for max_ratio=3.5)
    # RED: ratio exceeds max acceptable (e.g., over 3.5 for max_ratio=3.5)

    if ratio <= max_ratio * 0.7:
        return 'GREEN'
    elif ratio <= max_ratio:
        return 'AMBER'
    else:
        return 'RED'

def overall_risk_label(loss_label, profit_label):
    """
    Compute overall trade risk by combining loss and profit labels.
    If any is RED, overall is RED. If any is AMBER, overall is AMBER. Otherwise GREEN.

    Args:
        loss_label: Risk label for max loss
        profit_label: Risk label for max profit

    Returns:
        'GREEN', 'AMBER', or 'RED'
    """
    if loss_label == 'RED' or profit_label == 'RED':
        return 'RED'
    elif loss_label == 'AMBER' or profit_label == 'AMBER':
        return 'AMBER'
    else:
        return 'GREEN'

def compute_payoff(short_price, hedge_price, spread_width):
    credit = short_price - hedge_price
    max_loss = spread_width - credit
    max_profit = credit
    return credit, max_loss, max_profit

def calculate_target_exit_price(short_price, hedge_price, target_pct=70):
    """
    Calculate the spread price (buy-back price) to achieve target percentage of max profit.

    For credit spreads:
    - Entry: SELL spread at (short_price - hedge_price) = credit received
    - Max profit: credit received (when spread goes to 0)
    - Exit: BUY BACK spread at lower price to lock in profit

    Logic:
    - Initial credit = short_price - hedge_price
    - Target profit = credit * (target_pct / 100)
    - Remaining spread value = credit - target_profit
    - Exit spread price = credit * (1 - target_pct / 100)

    This means if you initially sold the spread for ₹21.35:
    - For 50% profit: buy back when spread is worth ₹10.68 (50% decay)
    - For 70% profit: buy back when spread is worth ₹6.41 (70% decay)

    Args:
        short_price: Premium received for short option
        hedge_price: Premium paid for hedge option
        target_pct: Target profit percentage (default 70%)

    Returns:
        Tuple of (target_spread_price, target_profit_amount)
    """
    # Calculate initial credit received (max profit potential)
    credit = short_price - hedge_price

    # Calculate target profit in rupees
    target_profit = credit * (target_pct / 100)

    # Calculate remaining spread value (what spread should be worth to exit)
    # To capture X% profit, the spread must decay by X%
    target_spread_price = credit * (1 - target_pct / 100)

    return target_spread_price, target_profit

def calculate_target_spot(short_strike, hedge_strike, option_type, short_price, hedge_price, target_pct=70):
    """
    Calculate spot price at which the spread achieves target percentage of max profit.

    For vertical credit spreads:
    - Max profit = credit received (when both options expire worthless)
    - Target profit = credit * (target_pct / 100)
    - Current spread value at target = credit - target_profit
    - This means the spread must decay to: credit * (1 - target_pct/100)

    For CE spreads:
    - Both expire worthless when spot < short_strike
    - When spot is between strikes, short is ITM, hedge is OTM
    - Spread value = spot - short_strike (intrinsic only at expiry)
    - Target: spot - short_strike = credit * (1 - target_pct/100)
    - Spot = short_strike + credit * (1 - target_pct/100)

    For PE spreads:
    - Both expire worthless when spot > short_strike
    - When spot is between strikes, short is ITM, hedge is OTM
    - Spread value = short_strike - spot (intrinsic only at expiry)
    - Target: short_strike - spot = credit * (1 - target_pct/100)
    - Spot = short_strike - credit * (1 - target_pct/100)

    Args:
        short_strike: Strike price of the short option
        hedge_strike: Strike price of the hedge (long) option
        option_type: 'CE' for calls or 'PE' for puts
        short_price: Premium received for short option
        hedge_price: Premium paid for hedge option
        target_pct: Target profit percentage (default 70%)

    Returns:
        Target spot price (float)
    """
    # Calculate credit received (max profit)
    credit = short_price - hedge_price

    # Calculate target remaining spread value
    # If we want 70% profit, spread should be worth 30% of original credit
    remaining_value = credit * (1 - target_pct / 100)

    if option_type == 'CE':
        # For CE: spot needs to be below short strike for max profit
        # Target spot = short_strike + remaining_value
        # (This is where intrinsic value of spread equals remaining_value)
        target_spot = short_strike + remaining_value
    else:  # PE
        # For PE: spot needs to be above short strike for max profit
        # Target spot = short_strike - remaining_value
        # (This is where intrinsic value of spread equals remaining_value)
        target_spot = short_strike - remaining_value

    return target_spot

def get_option_prices_from_csv(strikes):
    """Returns dictionary: {strike: {'CE': price, 'PE': price}}"""
    prices = {}
    with open(CSV_FILE, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Skip row 1: "CALLS,,PUTS" title row
        headers = next(reader)  # Read row 2: actual column headers

        for row in reader:
            # Skip rows with insufficient columns (incomplete data)
            if len(row) < 18:
                continue

            try:
                # Column 11 (index 11) = STRIKE, remove commas and convert to int
                strike = int(float(row[11].replace(',', '')))

                # Only process strikes we actually need
                if strike in strikes:
                    # Column 5 (index 5) = CE LTP (Call Option Last Traded Price)
                    ce_ltp = float(row[5].replace(',', '')) if row[5] and row[5] != '-' else 0.0

                    # Column 17 (index 17) = PE LTP (Put Option Last Traded Price)
                    pe_ltp = float(row[17].replace(',', '')) if row[17] and row[17] != '-' else 0.0

                    prices[strike] = {
                        'CE': ce_ltp,
                        'PE': pe_ltp
                    }
            except (ValueError, IndexError):
                # Skip rows that can't be parsed (malformed data)
                continue

    return prices

def main():
    # Check if command-line arguments are provided
    if len(sys.argv) >= 3:
        spot = float(sys.argv[1])
        DTE = int(sys.argv[2])
        print(f"Using command-line args: spot={spot}, DTE={DTE}")
    else:
        spot = float(input("Enter current Nifty spot: "))
        DTE = int(input("Enter days to expiry (1-5): "))
    spread_width = {1:50, 2:100, 3:100, 4:150, 5:200}[DTE]
    print(f"Suggested spread width based on DTE={DTE}: {spread_width}")

    CE_candidates = generate_candidate_table(spot, DTE, 'CE')
    PE_candidates = generate_candidate_table(spot, DTE, 'PE')

    display_candidate_table(CE_candidates, 'CE', spot)
    display_candidate_table(PE_candidates, 'PE', spot)

    ce_input = input("Select CE strikes to short [default: 3-6]: ").strip() or "3-6"
    pe_input = input("Select PE strikes to short [default: 3-6]: ").strip() or "3-6"

    short_CE_indexes = parse_index_input(ce_input, len(CE_candidates))
    short_PE_indexes = parse_index_input(pe_input, len(PE_candidates))

    short_CE_strikes = select_strikes_by_index(CE_candidates, short_CE_indexes)
    short_PE_strikes = select_strikes_by_index(PE_candidates, short_PE_indexes)

    # --- Collect all strikes we need (shorts + hedges) ---
    all_strikes = set(short_CE_strikes + short_PE_strikes)

    # Add hedge strikes for CE shorts
    for short_strike in short_CE_strikes:
        hedges = generate_hedges(short_strike, 'CE', spread_width)
        all_strikes.update(hedges)

    # Add hedge strikes for PE shorts
    for short_strike in short_PE_strikes:
        hedges = generate_hedges(short_strike, 'PE', spread_width)
        all_strikes.update(hedges)

    # --- Read prices from CSV ---
    option_prices = get_option_prices_from_csv(all_strikes)

    # --- Compute CE Payoffs ---
    # Collect all CE spreads first for sorting
    ce_spreads = []
    for short_strike in short_CE_strikes:
        hedges = generate_hedges(short_strike, 'CE', spread_width)
        for hedge_strike in hedges:
            short_price = option_prices[short_strike]['CE']
            # Skip if hedge strike not available in CSV
            if hedge_strike not in option_prices or option_prices[hedge_strike]['CE'] == 0.0:
                continue
            hedge_price = option_prices[hedge_strike]['CE']
            credit, max_loss, max_profit = compute_payoff(short_price, hedge_price, spread_width)

            # Calculate risk labels for scaled values (multiplied by lot size)
            credit_scaled = credit * LOT_SIZE
            max_loss_scaled = max_loss * LOT_SIZE
            max_profit_scaled = max_profit * LOT_SIZE

            loss_label = risk_label(max_loss_scaled, MAX_LOSS_LIMIT, higher_is_worse=True)
            ratio_label = ratio_risk_label(max_loss_scaled, max_profit_scaled, MAX_LOSS_TO_PROFIT_RATIO)
            overall_label = overall_risk_label(loss_label, ratio_label)

            # Calculate target exit prices for profit milestones
            exit_price_50, profit_50 = calculate_target_exit_price(short_price, hedge_price, 50)
            exit_price_70, profit_70 = calculate_target_exit_price(short_price, hedge_price, 70)

            ce_spreads.append({
                'short_strike': short_strike,
                'hedge_strike': hedge_strike,
                'spread_name': f"{short_strike}/{hedge_strike}",
                'short_price': short_price,
                'hedge_price': hedge_price,
                'credit_scaled': credit_scaled,
                'max_loss_scaled': max_loss_scaled,
                'max_profit_scaled': max_profit_scaled,
                'overall_label': overall_label,
                'exit_price_50': exit_price_50,
                'profit_50': profit_50,
                'exit_price_70': exit_price_70,
                'profit_70': profit_70
            })

    # Sort: GREEN first, then AMBER, then RED; within each tier by max profit descending
    risk_order = {'GREEN': 0, 'AMBER': 1, 'RED': 2}
    ce_spreads.sort(key=lambda x: (risk_order[x['overall_label']], -x['max_profit_scaled']))

    # Print sorted CE spreads
    print("\n" + "="*160)
    print("BEARISH/DOWNTREND SPREADS (Short Calls)")
    print("="*160)
    print(f"| {'Short':<18} | {'Hedge':<18} | {'Credit':>9} | {'Max Loss':>10} | {'Max Profit':>11} | {'Exit 50%':>10} | {'Profit@50%':>12} | {'Exit 70%':>10} | {'Profit@70%':>12} | {'Risk':^6} |")
    print("|" + "-"*20 + "|" + "-"*20 + "|" + "-"*11 + "|" + "-"*12 + "|" + "-"*13 + "|" + "-"*12 + "|" + "-"*14 + "|" + "-"*12 + "|" + "-"*14 + "|" + "-"*8 + "|")

    for spread in ce_spreads:
        overall_color = colorize_label(spread['overall_label'])
        short_label = f"{spread['short_strike']}CE @ ₹{spread['short_price']:.2f}"
        hedge_label = f"{spread['hedge_strike']}CE @ ₹{spread['hedge_price']:.2f}"
        print(f"| {short_label:<18} | {hedge_label:<18} | ₹{spread['credit_scaled']:>8.0f} | ₹{spread['max_loss_scaled']:>9.0f} | ₹{spread['max_profit_scaled']:>10.0f} | "
              f"₹{spread['exit_price_50']:>9.2f} | ₹{spread['profit_50']*LOT_SIZE:>11.0f} | ₹{spread['exit_price_70']:>9.2f} | ₹{spread['profit_70']*LOT_SIZE:>11.0f} | {overall_color:^6} |")

    print("="*160)

    # --- Compute PE Payoffs ---
    # Collect all PE spreads first for sorting
    pe_spreads = []
    for short_strike in short_PE_strikes:
        hedges = generate_hedges(short_strike, 'PE', spread_width)
        for hedge_strike in hedges:
            short_price = option_prices[short_strike]['PE']
            # Skip if hedge strike not available in CSV
            if hedge_strike not in option_prices or option_prices[hedge_strike]['PE'] == 0.0:
                continue
            hedge_price = option_prices[hedge_strike]['PE']
            credit, max_loss, max_profit = compute_payoff(short_price, hedge_price, spread_width)

            # Calculate risk labels for scaled values (multiplied by lot size)
            credit_scaled = credit * LOT_SIZE
            max_loss_scaled = max_loss * LOT_SIZE
            max_profit_scaled = max_profit * LOT_SIZE

            loss_label = risk_label(max_loss_scaled, MAX_LOSS_LIMIT, higher_is_worse=True)
            ratio_label = ratio_risk_label(max_loss_scaled, max_profit_scaled, MAX_LOSS_TO_PROFIT_RATIO)
            overall_label = overall_risk_label(loss_label, ratio_label)

            # Calculate target exit prices for profit milestones
            exit_price_50, profit_50 = calculate_target_exit_price(short_price, hedge_price, 50)
            exit_price_70, profit_70 = calculate_target_exit_price(short_price, hedge_price, 70)

            pe_spreads.append({
                'short_strike': short_strike,
                'hedge_strike': hedge_strike,
                'spread_name': f"{short_strike}/{hedge_strike}",
                'short_price': short_price,
                'hedge_price': hedge_price,
                'credit_scaled': credit_scaled,
                'max_loss_scaled': max_loss_scaled,
                'max_profit_scaled': max_profit_scaled,
                'overall_label': overall_label,
                'exit_price_50': exit_price_50,
                'profit_50': profit_50,
                'exit_price_70': exit_price_70,
                'profit_70': profit_70
            })

    # Sort: GREEN first, then AMBER, then RED; within each tier by max profit descending
    pe_spreads.sort(key=lambda x: (risk_order[x['overall_label']], -x['max_profit_scaled']))

    # Print sorted PE spreads
    print("\n" + "="*160)
    print("BULLISH/UPTREND SPREADS (Short Puts)")
    print("="*160)
    print(f"| {'Short':<18} | {'Hedge':<18} | {'Credit':>9} | {'Max Loss':>10} | {'Max Profit':>11} | {'Exit 50%':>10} | {'Profit@50%':>12} | {'Exit 70%':>10} | {'Profit@70%':>12} | {'Risk':^6} |")
    print("|" + "-"*20 + "|" + "-"*20 + "|" + "-"*11 + "|" + "-"*12 + "|" + "-"*13 + "|" + "-"*12 + "|" + "-"*14 + "|" + "-"*12 + "|" + "-"*14 + "|" + "-"*8 + "|")

    for spread in pe_spreads:
        overall_color = colorize_label(spread['overall_label'])
        short_label = f"{spread['short_strike']}PE @ ₹{spread['short_price']:.2f}"
        hedge_label = f"{spread['hedge_strike']}PE @ ₹{spread['hedge_price']:.2f}"
        print(f"| {short_label:<18} | {hedge_label:<18} | ₹{spread['credit_scaled']:>8.0f} | ₹{spread['max_loss_scaled']:>9.0f} | ₹{spread['max_profit_scaled']:>10.0f} | "
              f"₹{spread['exit_price_50']:>9.2f} | ₹{spread['profit_50']*LOT_SIZE:>11.0f} | ₹{spread['exit_price_70']:>9.2f} | ₹{spread['profit_70']*LOT_SIZE:>11.0f} | {overall_color:^6} |")

    print("="*160)

if __name__ == '__main__':
    main()
