import datetime as dt

import pandas as pd

from bhavcopy import fetch

NUM_EXPIRIES = 20
LOTTERY_LOW_MIN = 2.0
LOTTERY_LOW_MAX = 5.0
MULTIPLES = [5, 10, 20, 50, 80]


def most_recent_tuesday(day):
    offset = (day.weekday() - 1) % 7
    return day - dt.timedelta(days=offset)


def nifty_chain(df, expiry):
    return df[
        (df["TckrSymb"] == "NIFTY")
        & (df["FinInstrmTp"] == "IDO")
        & (df["XpryDt"] == expiry.isoformat())
    ]


def find_expiry_dates(n):
    tuesday = most_recent_tuesday(dt.date.today() - dt.timedelta(days=1))
    found = []
    while len(found) < n:
        for candidate in (tuesday, tuesday - dt.timedelta(days=1), tuesday + dt.timedelta(days=1)):
            df = fetch(candidate)
            if df is not None and not nifty_chain(df, candidate).empty:
                found.append(candidate)
                break
        tuesday -= dt.timedelta(days=7)
    return sorted(found)


def is_monthly(day):
    return (day + dt.timedelta(days=7)).month != day.month


def screen_day(day):
    chain = nifty_chain(fetch(day), day)
    hits = []
    for _, row in chain.iterrows():
        low, high = row["LwPric"], row["HghPric"]
        if not (LOTTERY_LOW_MIN <= low <= LOTTERY_LOW_MAX):
            continue
        crossed = [m for m in MULTIPLES if high >= m]
        if crossed:
            hits.append(dict(
                date=day, monthly=is_monthly(day), strike=row["StrkPric"], type=row["OptnTp"],
                low=low, high=high, close=row["ClsPric"],
                multiple=round(high / low, 1), crossed=max(crossed),
            ))
    return hits


def main():
    expiries = find_expiry_dates(NUM_EXPIRIES)
    print(f"{len(expiries)} expiries found: {expiries[0]} .. {expiries[-1]}\n")

    all_hits = []
    for day in expiries:
        hits = screen_day(day)
        all_hits.extend(hits)
        tag = "MONTHLY" if is_monthly(day) else "weekly "
        print(f"{day}  {tag}  {len(hits)} candidate(s)")

    out = pd.DataFrame(all_hits).sort_values(["date", "multiple"], ascending=[True, False])
    out.to_csv("magic_days.csv", index=False)
    print(f"\n{len(out)} candidate rows written to magic_days.csv")


if __name__ == "__main__":
    main()
