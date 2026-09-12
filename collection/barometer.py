"""Reads temperature, humidity, and pressure from a BME280 sensor over I2C.

Adapted from the official Raspberry Pi BME280 tutorial:
https://projects.raspberrypi.org/en/projects/build-your-own-weather-station/2
"""

from datetime import datetime

import bme280
import smbus2
from config import BME280_I2C_ADDRESS, BME280_I2C_PORT

bus = smbus2.SMBus(BME280_I2C_PORT)

bme280.load_calibration_params(bus, BME280_I2C_ADDRESS)


def read_data() -> tuple[str, float, float, float] | None:
    """Take one reading from the BME280 sensor.

    Returns:
        A (timestamp, humidity, pressure, temperature) tuple, or None if the
        sensor read fails.
    """
    try:
        # Get sensor readings
        bme280_data = bme280.sample(bus, BME280_I2C_ADDRESS)
        humidity = bme280_data.humidity
        pressure = bme280_data.pressure
        temperature = bme280_data.temperature
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return (timestamp, humidity, pressure, temperature)
    except Exception as e:
        print(f"Error reading sensor: {e}")
        return None


if __name__ == "__main__":
    read_data()
