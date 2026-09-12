"""One-off utility to backfill historical CSV readings (collected before
InfluxDB was wired up) into the database in Line Protocol batches.

Run manually, e.g.: python backfill_database.py
"""

import csv
import os
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

# Configuration
DATABASE_HOST_IP = os.getenv("DATABASE_HOST_IP", "127.0.0.1")
DATABASE_PORT = os.getenv("DATABASE_PORT", "8086")
DATABASE_NAME = os.getenv("DATABASE_NAME", "weather")
INFLUX_URL = f"http://{DATABASE_HOST_IP}:{DATABASE_PORT}/write?db={DATABASE_NAME}"

LOGGER_DEVICE = os.getenv("LOGGER_DEVICE", "pi_zero")

SENSOR_DATA_CSV = "data/sensor_data.csv"
API_DATA_CSV = "data/api_data.csv"


def backfill_csv(
    filepath: str, measurement: str, field_mappings: dict[str, str]
) -> None:
    """Read a CSV file and send its rows to InfluxDB as Line Protocol, in one batch.

    Args:
        filepath: Path to the CSV file to backfill.
        measurement: InfluxDB measurement name to write to (e.g. "bme280").
        field_mappings: Maps CSV column headers to InfluxDB field names.
    """
    if not os.path.isfile(filepath):
        print(f"File {filepath} not found. Skipping...")
        return

    payload_lines = []

    with open(filepath, "r") as f:
        # csv.DictReader automatically maps the header row to keys in a dictionary
        reader = csv.DictReader(f)

        for row in reader:
            try:
                # Parse historical timestamp to nanoseconds
                # Assumes timestamp header is exactly "Timestamp"
                dt = datetime.strptime(row["Timestamp"], "%Y-%m-%d %H:%M:%S")
                timestamp_ns = int(dt.timestamp() * 1_000_000_000)

                # Extract fields using the mapping dictionary
                fields = []
                for csv_header, influx_field in field_mappings.items():
                    val = float(row[csv_header])
                    fields.append(f"{influx_field}={val}")
                fields_str = ",".join(fields)

                # Form Line Protocol string
                line = f"{measurement},device={LOGGER_DEVICE} {fields_str} {timestamp_ns}\n"
                payload_lines.append(line)

            except Exception as e:
                print(f"Skipping bad row in {filepath}: {row}. Error: {e}")

    # Send the historical logs in one or two highly efficient batches
    if payload_lines:
        payload = "".join(payload_lines)
        print(f"Sending {len(payload_lines)} rows from {filepath} to InfluxDB...")
        try:
            response = requests.post(INFLUX_URL, data=payload, timeout=10)
            if response.status_code == 204:
                print(f"Successfully backfilled {measurement}!")
            else:
                print(f"Failed. InfluxDB returned status: {response.status_code}")
                print(response.text)
        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
    else:
        print(f"No valid data found in {filepath}")


if __name__ == "__main__":
    # Define exact mappings: {"CSV Column Header": "InfluxDB Field Name"}

    bme_fields = {
        "Humidity (%)": "humidity",
        "Pressure (hPa)": "pressure",
        "Temperature (C)": "temperature",
    }

    meteo_fields = {
        "Wind Speed (kmh)": "wind_speed",
        "Wind Direction (deg)": "wind_direction",
    }

    print("Starting historical data backfill...")
    backfill_csv(SENSOR_DATA_CSV, "bme280", bme_fields)
    backfill_csv(API_DATA_CSV, "open_meteo", meteo_fields)
    print("Done!")
