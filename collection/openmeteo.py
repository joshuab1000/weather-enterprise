"""Fetches the latest wind speed and direction for the station's location
from the Open-Meteo forecast API.
"""

from datetime import datetime

import openmeteo_requests
import requests_cache
from config import LATITUDE, LONGITUDE, TIMEZONE
from retry_requests import retry


def fetch_wind() -> tuple[str, float, float] | None:
    """Fetch the most recent 15-minute wind speed/direction reading for LATITUDE/LONGITUDE.

    Returns:
        A (timestamp, wind_speed_kmh, wind_direction_deg) tuple, or None if
        the request or parsing fails.
    """
    try:
        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession(".cache", expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        # Builder configuration parameters
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": LATITUDE,
            "longitude": LONGITUDE,
            "minutely_15": ["wind_speed_10m", "wind_direction_10m"],
            "timezone": TIMEZONE,
        }

        responses = openmeteo.weather_api(url, params=params)
        response = responses[0]

        minutely_15 = response.Minutely15()

        wind_speed = minutely_15.Variables(0).ValuesAsNumpy()
        wind_direction = minutely_15.Variables(1).ValuesAsNumpy()

        # Get the most recent value
        latest_speed = round(float(wind_speed[-1]), 2)
        latest_direction = round(float(wind_direction[-1]), 2)

        # Convert everything into the dataframe
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return (timestamp, latest_speed, latest_direction)

    except Exception as e:
        print(f"Error fetching/parsing wind data: {e}")
        return None


if __name__ == "__main__":
    fetch_wind()
