"""Reads the BME280 sensor and Open-Meteo wind data once, logs both to local
CSVs, and pushes them to InfluxDB (queuing on disk if the database is
unreachable).

Intended to be run on a schedule (e.g. cron) on the Pi Zero W.
"""

import csv
import os
from collections.abc import Iterable
from datetime import datetime

import barometer
import openmeteo
import requests
from config import INFLUX_URL, LOGGER_DEVICE

SENSOR_DATA_CSV = "data/sensor_data.csv"
API_DATA_CSV = "data/api_data.csv"

QUEUE_FILE = "influx_queue.txt"


def write_csv(filepath: str, headers: list[str], row_data: Iterable) -> None:
    """Appends a line to a specific CSV file.

    Args:
        filepath: Path to the CSV file to append to.
        headers: Column headers to write if the file doesn't already exist.
        row_data: The row values to append.
    """

    file_exists = os.path.isfile(filepath)

    with open(filepath, "a", newline="") as f:
        writer = csv.writer(f)
        # Write the headers first if it's a brand new file
        if not file_exists:
            writer.writerow(headers)
        # Write your data list as a clean row
        writer.writerow(row_data)


def queue_data(measurement: str, timestamp_str: str, fields_dict: dict) -> None:
    """Formats data into Line Protocol and saves it to the outbox queue.

    Args:
        measurement: InfluxDB measurement name (e.g. "bme280").
        timestamp_str: Reading timestamp as "%Y-%m-%d %H:%M:%S".
        fields_dict: Field name -> value pairs to write.
    """
    dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    timestamp_ns = int(dt.timestamp() * 1_000_000_000)

    fields_str = ",".join(f"{k}={v}" for k, v in fields_dict.items())
    line_protocol = (
        f"{measurement},device={LOGGER_DEVICE} {fields_str} {timestamp_ns}\n"
    )

    with open(QUEUE_FILE, "a") as f:
        f.write(line_protocol)


def flush_queue_to_db() -> None:
    """Sends all backed-up lines in the queue to InfluxDB at once."""
    if not os.path.isfile(QUEUE_FILE) or os.stat(QUEUE_FILE).st_size == 0:
        return

    with open(QUEUE_FILE, "r") as f:
        lines = f.readlines()

    payload = "".join(lines)
    try:
        response = requests.post(INFLUX_URL, data=payload, timeout=5)
        if response.status_code == 204:
            open(QUEUE_FILE, "w").close()  # Clear queue file on success
            print(f"Successfully synced {len(lines)} data lines to server DB.")
        else:
            print(
                f"InfluxDB returned HTTP {response.status_code}. "
                "Data remaining in local queue."
            )
    except requests.exceptions.RequestException:
        print("Server offline. Data safely preserved in local queue.")


if __name__ == "__main__":
    # Get data as lists
    bme_data = (
        barometer.read_data()
    )  # e.g., ["2026-09-04 01:00:00", 47.5, 1013.5, 17.0]
    api_data = openmeteo.fetch_wind()  # e.g., ["2026-09-04 01:00:00", 8.93, 247.93]

    # Log directly to CSVs
    bme_headers = [
        "Timestamp",
        "Humidity (%)",
        "Pressure (hPa)",
        "Temperature (C)",
    ]

    if bme_data is not None:
        write_csv(SENSOR_DATA_CSV, bme_headers, bme_data)

        # Use Python unpacking to extract values from the lists cleanly
        timestamp, humidity, pressure, temperature = bme_data

        # Map them to dictionaries for InfluxDB
        bme_fields = {
            "humidity": humidity,
            "pressure": pressure,
            "temperature": temperature,
        }

        # Add to queue to be pushed
        queue_data("bme280", timestamp, fields_dict=bme_fields)
    else:
        print("BME280 unavailable; skipping sensor data.")

    api_headers = ["Timestamp", "Wind Speed (kmh)", "Wind Direction (deg)"]
    if api_data is not None:
        write_csv(API_DATA_CSV, api_headers, api_data)
        timestamp, wind_speed, wind_direction = api_data
        api_fields = {"wind_speed": wind_speed, "wind_direction": wind_direction}
        queue_data("open_meteo", timestamp, fields_dict=api_fields)
    else:
        print("Open-Meteo unavailable; skipping wind data.")

    # Push everything to the database
    flush_queue_to_db()
