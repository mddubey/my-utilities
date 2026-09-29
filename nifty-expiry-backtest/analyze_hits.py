import pandas as pd

from bhavcopy import fetch


def day_open(day):
    df = fetch(day)
    fut = df[(df.TckrSymb == "NIFTY") & (df.FinInstrmTp == "IDF")]
    fut = fut[fut.XpryDt >= day.isoformat()].sort_values("XpryDt")
    return fut.iloc[0]["OpnPric"]


def otm_distance(row, open_px):
    if row["type"] == "CE":
        return row["strike"] - open_px
    return open_px - row["strike"]


def main():
    hits = pd.read_csv("magic_days.csv", parse_dates=["date"])
    total_expiries = 20
    hit_dates = hits["date"].nunique()

    opens = {d: day_open(d.date()) for d in hits["date"].unique()}
    hits["day_open"] = hits["date"].map(lambda d: opens[d])
    hits["otm_distance"] = hits.apply(lambda r: otm_distance(r, r["day_open"]), axis=1)

    print(f"{hit_dates}/{total_expiries} expiries had at least one zero-to-hero contract")
    print(f"{len(hits)} total candidate contracts across those expiries\n")

    cols = ["date", "monthly", "type", "strike", "day_open", "otm_distance", "low", "high", "multiple"]
    print(hits[cols].sort_values("date").to_string(index=False))

    print("\nOTM distance (points from day's opening level) stats:")
    print(hits["otm_distance"].describe())


if __name__ == "__main__":
    main()
