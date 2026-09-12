"""Shared CSV backup helper, mirroring collection/log_data.py's pattern.

Used by the analysis scripts to keep a local record of what was computed and
sent to InfluxDB, with an explicit UTC offset on every timestamp so the
backup itself can never develop the naive-timestamp ambiguity that caused
the timezone bug in the first place.
"""

import csv
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def write_csv(filename: str, headers: list[str], row_data: list) -> None:
    """Appends a line to a CSV file under the repo's data/ directory.

    Args:
        filename: CSV filename (e.g. "zambretti_forecast.csv").
        headers: Column headers to write if the file doesn't already exist.
        row_data: The row values to append.
    """
    filepath = DATA_DIR / filename
    file_exists = filepath.is_file()

    with open(filepath, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row_data)
