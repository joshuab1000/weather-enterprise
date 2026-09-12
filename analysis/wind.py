"""Reads wind speed/direction from InfluxDB and converts it to compass points
for use by the Zambretti forecast.
"""

import pandas as pd
from config import DATABASE_HOST, DATABASE_NAME, DATABASE_PORT, TIMEZONE
from influxdb import InfluxDBClient


def parse_wind_data(df: pd.DataFrame) -> pd.DataFrame:
    """Convert a raw query result into a tz-naive wind series indexed by timestamp.

    Args:
        df: Raw query result with "Timestamp", wind speed, and direction columns.

    Returns:
        A DataFrame indexed by tz-naive timestamp with wind speed/direction.
    """
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    df["Timestamp"] = df["Timestamp"].dt.tz_convert(TIMEZONE)
    df["Timestamp"] = df["Timestamp"].dt.tz_localize(None)

    df = df.set_index("Timestamp")
    df = df.sort_index()
    fields = ["Wind Speed (kmh)", "Wind Direction (deg)"]
    wind_data = df[fields]
    return wind_data


# def read_in_wind_data(csv_path):
#     df = pd.read_csv(csv_path)
#     wind_data = parse_wind_data(df)
#     return wind_data


def read_in_wind_data_from_db() -> pd.DataFrame | None:
    """Query the last 48 hours of Open-Meteo wind readings from InfluxDB.

    Returns:
        A DataFrame of wind speed/direction indexed by timestamp, or None if
        no data is found.
    """
    client = InfluxDBClient(
        host=DATABASE_HOST, port=DATABASE_PORT, database=DATABASE_NAME
    )

    # Pull wind speed and direction from the last 48 hours
    query = "SELECT time, wind_speed, wind_direction FROM open_meteo WHERE time > now() - 48h"
    result = client.query(query)
    points = list(result.get_points())
    df = pd.DataFrame(points)
    if df.empty:
        # raise ValueError("No data returned from InfluxDB. Check database name or measurement schema.")
        print(
            "No data returned from InfluxDB. Check database name or measurement schema."
        )
        return None

    df = df.rename(
        columns={
            "time": "Timestamp",
            "wind_speed": "Wind Speed (kmh)",  # <-- Map to CSV style
            "wind_direction": "Wind Direction (deg)",  # <-- Map to CSV style
        }
    )

    # Pass the fresh DataFrame to your existing parsing logic
    wind_data = parse_wind_data(df)
    return wind_data


def get_current_wind_direction(wind_data: pd.DataFrame) -> tuple[pd.Timestamp, float]:
    """Return the (timestamp, wind_direction_deg) of the most recent reading.

    Args:
        wind_data: Wind series indexed by timestamp.

    Returns:
        The (timestamp, wind_direction_deg) of the most recent reading.
    """
    latest = wind_data.iloc[-1]
    timestamp = latest.name
    wind_direction = latest["Wind Direction (deg)"]
    return timestamp, wind_direction


def get_wind_direction_text(wind_val: int | str | None) -> str:
    """Convert a 0-15 compass index (or the text "calm") into its text label.

    Args:
        wind_val: A 0-15 compass index, or the literal string "calm".

    Returns:
        The compass label (e.g. "NNE"), or "calm".
    """
    if wind_val is None or wind_val == "calm":
        return "calm"

    compass_points = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    return compass_points[int(wind_val) % 16]


if __name__ == "__main__":
    wind_data = read_in_wind_data_from_db()
    if wind_data is None:
        print("No wind data found in database.")
    else:
        timestamp, wind_direction = get_current_wind_direction(wind_data)
        print(f"Current wind direction: {wind_direction}     (measured {timestamp})")
