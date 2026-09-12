"""Computes barometric pressure trends (rate of change over several intervals)
from BME280 readings stored in InfluxDB, and writes the results back for
Grafana and the Zambretti forecast to use.

Runs on the Pi 2 alongside zambretti_forecast.py.
"""

import pandas as pd
from config import (
    ANALYSIS_DEVICE,
    DATABASE_HOST,
    DATABASE_NAME,
    DATABASE_PORT,
    SENSOR_ELEVATION_M,
    TIMEZONE,
)
from csv_backup import write_csv
from influxdb import InfluxDBClient

TREND_FIELD_KEYS = [
    "trend_30m",
    "trend_1h",
    "trend_2h",
    "trend_3h",
    "trend_6h",
    "trend_12h",
    "trend_24h",
]


def convert_to_sea_level_pressure(
    pressure_hpa: float | pd.Series, elevation_m: float = SENSOR_ELEVATION_M
) -> float | pd.Series:
    """Converts station pressure to sea-level equivalent pressure (hPa).
    Equation is the inverse of the one here: https://www.weather.gov/media/epz/wxcalc/stationPressure.pdf

    Args:
        pressure_hpa: Station-level pressure reading (or a Series of them), in hPa.
        elevation_m: Sensor elevation above sea level, in meters.

    Returns:
        The pressure adjusted to sea level, in hPa (same shape as pressure_hpa).
    """
    pressure_sea_level_hpa = (
        pressure_hpa * (288 / (288 - 0.0065 * elevation_m)) ** 5.2561
    )
    return pressure_sea_level_hpa


def parse_pressure_data(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a raw query result into a tz-naive, sea-level-adjusted pressure
    series indexed by timestamp.

    Args:
        df: Raw query result with "Timestamp" and "Pressure (hPa)" columns.

    Returns:
        A DataFrame indexed by tz-naive timestamp with sea-level pressure.
    """
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Timestamp"] = df["Timestamp"].dt.tz_convert(TIMEZONE)
    df["Timestamp"] = df["Timestamp"].dt.tz_localize(None)

    df = df.set_index("Timestamp")
    df = df.sort_index()

    # Convert raw readings to sea level
    df["Pressure (hPa)"] = convert_to_sea_level_pressure(df["Pressure (hPa)"])

    fields = ["Pressure (hPa)"]
    pressure_data = df[fields]
    return pressure_data


# def read_in_pressure_from_csv(csv_path):
#     df = pd.read_csv(csv_path)
#     pressure_data = parse_pressure_data(df)
#     return pressure_data


def read_in_pressure_from_db() -> pd.DataFrame:
    """Query the last 48 hours of BME280 pressure readings from InfluxDB.

    Returns:
        A DataFrame of sea-level pressure indexed by timestamp.

    Raises:
        ValueError: If InfluxDB returns no rows.
    """
    client = InfluxDBClient(
        host=DATABASE_HOST, port=DATABASE_PORT, database=DATABASE_NAME
    )

    # Pull all data from the last 48 hours
    query = (
        'SELECT time, pressure AS "Pressure (hPa)" FROM bme280 WHERE time > now() - 48h'
    )
    result = client.query(query)
    points = result.get_points()
    df = pd.DataFrame(points)
    if df.empty:
        raise ValueError(
            "No data returned from InfluxDB. Check database name or measurement schema."
        )
    df = df.rename(columns={"time": "Timestamp"})
    pressure_data = parse_pressure_data(df)
    return pressure_data


def get_current_pressure(pressure_data: pd.DataFrame) -> tuple[pd.Timestamp, float]:
    """Return the (timestamp, pressure) of the most recent reading.

    Args:
        pressure_data: Pressure series indexed by timestamp.

    Returns:
        The (timestamp, pressure) of the most recent reading.
    """
    latest = pressure_data.iloc[-1]
    timestamp = latest.name
    pressure = latest["Pressure (hPa)"]
    return timestamp, pressure


def get_data_for_period(pressure_data: pd.DataFrame, n: int) -> pd.DataFrame | None:
    """Return pressure data covering the last n 30-minute intervals.
    This makes sure we're actually getting the closest thing to
    30-minute intervals even if some entries are slightly off from that.

    Args:
        pressure_data: Pressure series indexed by timestamp.
        n: Number of 30-minute intervals to look back.

    Returns:
        The pressure data from the target time to now, or None if there isn't
        enough history, or the nearest readings are too far apart to
        interpolate across.
    """

    hours = n * 0.5

    latest_timestamp = pressure_data.index[-1]
    target_timestamp = latest_timestamp - pd.Timedelta(hours=hours)

    # Make sure we actually have data going back far enough
    if target_timestamp < pressure_data.index[0]:
        return None

    data = pressure_data.copy()

    # Find the readings immediately before and after the target time
    before = data.loc[data.index <= target_timestamp]
    after = data.loc[data.index >= target_timestamp]
    if before.empty or after.empty:
        return None

    before_timestamp = before.index[-1]
    after_timestamp = after.index[0]

    # Don't interpolate across a gap that's too big
    gap = after_timestamp - before_timestamp
    if gap > pd.Timedelta(hours=1):
        return None

    # Add the exact target time and sort by timestamp
    data.loc[target_timestamp] = float("nan")
    data = data.sort_index()

    # Interpolate pressure at the target time
    data["Pressure (hPa)"] = data["Pressure (hPa)"].interpolate(method="time")
    data = data.loc[target_timestamp:latest_timestamp]

    return data


def get_difference(pressure_data: pd.DataFrame, n: int = 6) -> float | None:
    """Return pressure difference over n 30-minute intervals.
    Default number of measurements is 6 (3 hours, "pressure tendency").

    Args:
        pressure_data: Pressure series indexed by timestamp.
        n: Number of 30-minute intervals to look back.

    Returns:
        The pressure change over the period, in hPa, or None if there isn't
        enough history to compute it.
    """
    data = get_data_for_period(pressure_data, n)

    if data is None:
        return None

    new_pressure = data["Pressure (hPa)"].iloc[-1]
    old_pressure = data["Pressure (hPa)"].iloc[0]

    difference = new_pressure - old_pressure

    return difference


def get_min_max(pressure_data: pd.DataFrame, n: int = 6) -> tuple[float, float] | None:
    """Default number of measurements is 6 (3 hours, "pressure tendency").

    Args:
        pressure_data: Pressure series indexed by timestamp.
        n: Number of 30-minute intervals to look back.

    Returns:
        A (min, max) tuple of pressure over the period, in hPa, or None if
        there isn't enough history to compute it.
    """
    data = get_data_for_period(pressure_data, n)

    if data is None:
        return None

    min_pressure = data["Pressure (hPa)"].min()
    max_pressure = data["Pressure (hPa)"].max()

    print("Min:", min_pressure, "Max:", max_pressure)
    return min_pressure, max_pressure


def describe_trend(pressure_difference: float | None, hours_elapsed: float) -> str:
    """Describe a pressure trend normalized per hour.

    Args:
        pressure_difference: Pressure change over the period, in hPa.
        hours_elapsed: Length of the period, in hours.

    Returns:
        A human-readable trend label, e.g. "Rising Slowly".
    """

    if pressure_difference is None:
        return "Insufficient data"

    rate_per_hour = pressure_difference / hours_elapsed

    trend = ""
    if rate_per_hour < -0.67:
        trend = "Falling Rapidly"
    elif rate_per_hour < -0.17:
        trend = "Falling Slowly"
    elif rate_per_hour < 0.17:
        trend = "Steady"
    elif rate_per_hour < 0.67:
        trend = "Rising Slowly"
    else:
        trend = "Rising Rapidly"
    # print("Pressure has been:", trend)

    return trend


def format_time_duration(total_minutes: int) -> str:
    """Format a minute count as a human-readable duration, e.g. "3 hours".

    Args:
        total_minutes: Duration in minutes.

    Returns:
        A human-readable duration string.
    """
    if total_minutes == 30:
        return "30 minutes"
    else:
        hours = total_minutes // 60
        # Handle singular "hour" vs plural "hours"
        unit = "hour" if hours == 1 else "hours"
        return f"{hours} {unit}"


def calculate_trends(
    pressure_data: pd.DataFrame, intervals: list[int] = [1, 2, 4, 6, 12, 24, 48]
) -> dict:
    """Calculate the pressure trends for each interval in intervals list.

    Args:
        pressure_data: Pressure series indexed by timestamp.
        intervals: 30-minute interval counts to compute trends for.

    Returns:
        A dict keyed by interval, each value holding total_minutes,
        time_duration, difference, and field_key.
    """
    results = {}
    for interval in intervals:
        total_minutes = interval * 30
        time_duration = format_time_duration(total_minutes)
        difference = get_difference(pressure_data, interval)

        # Determine the dictionary key for the database
        field_key = (
            f"trend_{total_minutes}m"
            if total_minutes < 60
            else f"trend_{total_minutes // 60}h"
        )

        results[interval] = {
            "total_minutes": total_minutes,
            "time_duration": time_duration,
            "difference": difference,
            "field_key": field_key,
        }
    return results


def generate_current_report(
    pressure_data: pd.DataFrame, intervals: list[int] = [1, 2, 4, 6, 12, 24, 48]
) -> None:
    """Print the current pressure and trend summary for each interval to stdout.

    Args:
        pressure_data: Pressure series indexed by timestamp.
        intervals: 30-minute interval counts to report on.
    """
    latest_timestamp, latest_pressure = get_current_pressure(pressure_data)
    print(f"Current pressure: {latest_pressure}     (measured {latest_timestamp})")

    trend_data = calculate_trends(pressure_data, intervals)

    for interval, data in trend_data.items():
        difference = data["difference"]
        time_duration = data["time_duration"]

        hours_elapsed = data["total_minutes"] / 60
        trend = describe_trend(difference, hours_elapsed)

        # If there is no difference for this interval, print a missing difference as --
        # Otherwise, print the normal row with timestamp and difference
        if difference is None:
            print(f"{time_duration:<12} {'--':>7}       {trend}")
        else:
            print(f"{time_duration:<12} {difference:>7.2f} hPa   {trend}")


def save_trends_to_db(
    pressure_data: pd.DataFrame, intervals: list[int] = [1, 2, 4, 6, 12, 24, 48]
) -> bool | None:
    """Write the latest computed pressure trends to InfluxDB as a pressure_trends point.

    Args:
        pressure_data: Pressure series indexed by timestamp.
        intervals: 30-minute interval counts to compute trends for.

    Returns:
        True on a successful write, False if the write failed, or None if
        there were no trends to write.
    """
    latest_timestamp, _ = get_current_pressure(pressure_data)

    trend_data = calculate_trends(pressure_data)

    trend_fields = {}
    for data in trend_data.values():
        if data["difference"] is not None:
            trend_fields[data["field_key"]] = float(data["difference"])

    if trend_fields:
        timestamp_with_offset = latest_timestamp.tz_localize(TIMEZONE).isoformat()

        write_csv(
            "pressure_trends.csv",
            ["Timestamp"] + TREND_FIELD_KEYS,
            [timestamp_with_offset] + [trend_fields.get(key, "") for key in TREND_FIELD_KEYS],
        )

        try:
            client = InfluxDBClient(
                host=DATABASE_HOST, port=DATABASE_PORT, database=DATABASE_NAME
            )
            json_body = [
                {
                    "measurement": "pressure_trends",
                    "tags": {"device": ANALYSIS_DEVICE},
                    "time": timestamp_with_offset,
                    "fields": trend_fields,
                }
            ]
            client.write_points(json_body)
            print("Successfully uploaded pressure trends to InfluxDB!")
            return True
        except Exception as e:
            print(f"Failed to write pressure trends to InfluxDB: {e}")
            return False
    return None


def run_pressure_trends() -> bool:
    """Entry point: compute and store pressure trends from the latest InfluxDB data.

    Returns:
        True on success, False if there was no data to process.
    """
    pressure_data = read_in_pressure_from_db()
    if pressure_data is None or pressure_data.empty:
        print("Warning: No pressure data found in database. Skipping trends.")
        return False
    else:
        save_trends_to_db(pressure_data)
        return True


if __name__ == "__main__":
    run_pressure_trends()
