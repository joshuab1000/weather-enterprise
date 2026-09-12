"""Shared configuration for the Pi 2 analysis scripts.

Reads deployment-specific values (database host, station altitude) from the
.env file at the repo root.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DATABASE_HOST = os.getenv("DATABASE_HOST_IP", "127.0.0.1")
DATABASE_PORT = os.getenv("DATABASE_PORT", "8086")
DATABASE_NAME = os.getenv("DATABASE_NAME", "weather")

ANALYSIS_DEVICE = os.getenv("ANALYSIS_DEVICE", "pi_2")
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

SENSOR_ELEVATION_M = float(os.getenv("ALTITUDE_M", "0.0"))
