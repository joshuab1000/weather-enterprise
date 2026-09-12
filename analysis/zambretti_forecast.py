"""Combines the latest pressure trend and wind direction into a Zambretti
forecast code/text, and writes the result to InfluxDB.
"""

import pandas as pd
import pressure_trends
import wind
import zambretti
from config import (
    ANALYSIS_DEVICE,
    DATABASE_HOST,
    DATABASE_NAME,
    DATABASE_PORT,
    TIMEZONE,
)
from influxdb import InfluxDBClient


def degrees_to_wind_index(degrees: float | None) -> int | None:
    """Convert a compass bearing in degrees to a 0-15 index (0=N, 4=E, 8=S, 12=W).

    Args:
        degrees: Wind direction in degrees (0-360), or None.

    Returns:
        A 0-15 compass index, or None if degrees was None.
    """
    if degrees is None:
        return None
    # Normalize degrees to 0-360 range
    degrees = float(degrees) % 360
    # Calculate index (22.5 degrees per step, offset by 11.25 for centering)
    return int((degrees + 11.25) / 22.5) % 16


def generate_forecast_report(
    current_pressure: float,
    current_timestamp: pd.Timestamp,
    pressure_trend: float,
    wind_index: int,
    wind_timestamp: pd.Timestamp,
    forecast_text: str,
) -> None:
    """Print a human-readable summary of the current forecast inputs and result.

    Args:
        current_pressure: Latest sea-level pressure, in hPa.
        current_timestamp: When current_pressure was measured.
        pressure_trend: Pressure change over the trend interval, in hPa.
        wind_index: Current wind direction as a 0-15 compass index.
        wind_timestamp: When the wind direction was measured.
        forecast_text: The Zambretti forecast description to display.
    """
    print(f"Current Pressure: {current_pressure:.2f}    (measured {current_timestamp})")
    print(f"3 Hour Pressure Trend: {pressure_trend:.2f}")
    print(
        f"Wind Direction: {wind.get_wind_direction_text(wind_index)}    (measured {wind_timestamp})"
    )
    print("\n--- Forecast: ---")
    print(forecast_text)


def save_forecast_to_db(
    timestamp: pd.Timestamp,
    current_pressure: float,
    pressure_trend: float,
    wind_dir_degrees: float | None,
    month: int,
    code: str,
    text: str,
) -> bool:
    """Write the computed Zambretti forecast to InfluxDB as a zambretti_forecast point.

    Args:
        timestamp: When the forecast inputs were measured.
        current_pressure: Latest sea-level pressure, in hPa.
        pressure_trend: Pressure change over the trend interval, in hPa.
        wind_dir_degrees: Current wind direction in degrees, or None.
        month: Month of the forecast (1-12), used by the Zambretti algorithm.
        code: The single-letter Zambretti forecast code.
        text: The human-readable forecast description.

    Returns:
        True on success, False if the write to InfluxDB failed.
    """
    try:
        client = InfluxDBClient(
            host=DATABASE_HOST, port=DATABASE_PORT, database=DATABASE_NAME
        )
        json_body = [
            {
                "measurement": "zambretti_forecast",
                "tags": {"device": ANALYSIS_DEVICE},
                "time": timestamp.tz_localize(TIMEZONE).isoformat(),
                "fields": {
                    "current_pressure": float(current_pressure),
                    "pressure_trend": float(pressure_trend),
                    "wind_direction": float(wind_dir_degrees)
                    if wind_dir_degrees is not None
                    else 0.0,
                    "month": int(month),
                    "forecast_code": str(code),
                    "forecast_text": str(text),
                },
            }
        ]
        client.write_points(json_body)
        print("Successfully uploaded Zambretti forecast to InfluxDB!")
        return True
    except Exception as e:
        print(f"Failed to write Zambretti forecast to InfluxDB: {e}")
        return False


def run_forecast() -> bool:
    """Entry point: compute and store today's Zambretti forecast from the latest InfluxDB data.

    Returns:
        True on success, False if required pressure or wind data was missing.
    """
    PRESSURE_TREND_INTERVAL = 6  # 3 hours

    pressure_data = pressure_trends.read_in_pressure_from_db()
    if pressure_data is None or pressure_data.empty:
        print(
            "Warning: No pressure data found in database. Skipping Zambretti forecast."
        )
        return False

    current_pressure_timestamp, current_pressure = pressure_trends.get_current_pressure(
        pressure_data
    )
    pressure_trend = pressure_trends.get_difference(
        pressure_data, PRESSURE_TREND_INTERVAL
    )
    if current_pressure is None or pressure_trend is None:
        print(
            "Warning: No current pressure or pressure trend data. Skipping Zambretti forecast."
        )
        return False

    wind_data = wind.read_in_wind_data_from_db()
    if wind_data is None:
        print("Warning: No wind data found in database. Skipping Zambretti forecast.")
        return False

    current_wind_timestamp, current_wind_dir_degrees = wind.get_current_wind_direction(
        wind_data
    )
    current_wind_dir_index = degrees_to_wind_index(current_wind_dir_degrees)

    if current_wind_dir_index is None:
        print("Warning: Wind direction index is missing. Skipping Zambretti forecast.")
        return False

    code = zambretti.ZambrettiCode(
        pressure=current_pressure,
        month=current_pressure_timestamp.month,
        wind=current_wind_dir_index,
        trend=pressure_trend,
    )
    forecast_text = zambretti.ZambrettiText(code)

    success = save_forecast_to_db(
        timestamp=current_pressure_timestamp,
        current_pressure=current_pressure,
        pressure_trend=pressure_trend,
        wind_dir_degrees=current_wind_dir_degrees,
        month=current_pressure_timestamp.month,
        code=code,
        text=forecast_text,
    )

    return success


if __name__ == "__main__":
    run_forecast()
    # generate_forecast_report(current_pressure, current_pressure_timestamp, pressure_trend, current_wind_dir_index, current_wind_timestamp, forecast_text)
