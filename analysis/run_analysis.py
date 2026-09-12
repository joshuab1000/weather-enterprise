"""Entry point for the Pi 2 cron job: runs the pressure-trend and Zambretti
forecast scripts back to back.
"""

import pressure_trends
import zambretti_forecast

print("Running pressure trends...")
pressure_trends.run_pressure_trends()

print("Running Zambretti forecast...")
zambretti_forecast.run_forecast()
