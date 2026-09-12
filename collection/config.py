"""Shared configuration for the Pi Zero W data-collection scripts.

Reads deployment-specific values (location, database host, sensor wiring)
from the .env file at the repo root.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

LATITUDE = float(os.getenv("LATITUDE", "0.0"))
LONGITUDE = float(os.getenv("LONGITUDE", "0.0"))
TIMEZONE = os.getenv("TIMEZONE", "America/New_York")

DATABASE_HOST_IP = os.getenv("DATABASE_HOST_IP", "127.0.0.1")
DATABASE_PORT = os.getenv("DATABASE_PORT", "8086")
DATABASE_NAME = os.getenv("DATABASE_NAME", "weather")
INFLUX_URL = f"http://{DATABASE_HOST_IP}:{DATABASE_PORT}/write?db={DATABASE_NAME}"

LOGGER_DEVICE = os.getenv("LOGGER_DEVICE", "pi_zero")

BME280_I2C_ADDRESS = int(os.getenv("BME280_I2C_ADDRESS", "0x77"), 16)
BME280_I2C_PORT = int(os.getenv("BME280_I2C_PORT", "1"))
