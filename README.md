# The Weather Enterprise

This project grew out of a dream I've had for a backyard hobby weather station for a long time. I bought all the parts and followed [this awesome tutorial](https://projects.raspberrypi.org/en/projects/build-your-own-weather-station) from the Raspberry Pi Foundation, but once I got to the end, I realized I was way more excited about the meteorology and software side of the project than I was about figuring out how to weather-proof a Raspberry Pi, a breadboard, and a bunch of loose sensors on jumper wires. Years later, I had another stroke of motivation for tinkering with weather data, so that's what this is.

My original goal was to see if I could generate basic forecast with as little data and math as possible, which led me to [Zambretti](https://en.wikipedia.org/wiki/Zambretti_Forecaster) forecasts. This project currently combines pressure data from my own BME280 sensor and wind speed/direction data from the Open-Meteo [Weather Forecast API](https://open-meteo.com/en/docs) to generate basic short-term forecasts using a [Python implementation of a Zambretti forecaster](https://pywws.readthedocs.io/en/legacy/_modules/pywws/Forecast.html#ZambrettiCode).

Currently, I'm working on setting up a little Grafana dashboard to display all the stats and forecasts that are being logged. Once that's up and running, I think my next goal is to try to learn the very basics of machine learning and see if I can train some sort of model to be slightly more accurate for my backyard than the Zambretti script.

I have a lot of ideas that come after that, but I will refrain from listing them here because they ebb and flow so much that I'm not sure which ones I'll actually pursue and which I'll forget about.

## Hardware & Setup

This project is meant to run on three machines. Any three computers (or Docker containers) would probably work, but I'm currently using:

- **Pi Zero W**: runs `collection/` to read the BME280 sensor and pull wind
  data from Open-Meteo.
  OS: Raspbian GNU/Linux 13 (trixie), Python 3.13.5
- **Raspberry Pi 2**: runs `analysis/` to calculate basic pressure trends and Zambretti forecasts, as well as host a Grafana dashboard. It has to run an older version of Grafana since the Pi 2 is 32 bit.
  OS: Raspbian GNU/Linux 13 (trixie), Python 3.13.5, Grafana 9.4.7
- **Banana Pro**: Hosts an InfluxDB database that the Pis access. I haven't written any code for this one.
  OS: Armbian_community 26.11.0-trunk.33 trixie, InfluxDB: v1.6.7~rc0

You'll also need a BME280 sensor wired up to whichever machine runs
`collection/`. You could also replace the sensor with pressure data from Open-Meteo if you prefer.

## Running It

1. Copy `.env.example` to a new file called `.env` and fill in your own values (location,
   database IP, sensor wiring, etc.).
2. On each machine, `pip install -r` the matching `requirements.txt`
   (`collection/requirements.txt` on the Pi Zero W,
   `analysis/requirements.txt` on the Pi 2).
3. Run `collection/log_data.py` on the Pi Zero W and
   `analysis/run_analysis.py` on the Pi 2.

Each script runs once and exits. Schedule repeated runs however you like:
a cron job, a systemd timer, or just a `while true` loop with a
`sleep` in it. You can also run either file manually if you only want one reading.

I currently run each file in a cron job that goes every 30 minutes.

## Credits

This project leans on a few things I didn't write myself:

- **`analysis/zambretti.py`**: The Zambretti forecast algorithm itself,
  vendored from the [pywws.ZambrettiCore module](https://pythonhosted.org/pywws/fr/html/_modules/pywws/ZambrettiCore.html) (license header preserved in the
  file). It's under its own **GPLv2+** license. I modified this file slightly to pull in a local `get_wind_direction_text` function without needing to import the real `pywws.conversions` module for wind direction conversions, added a couple docstrings, and changed a bit of formatting to appease my linter.
- **`collection/barometer.py`**: Adapted from the BME280 section of the official Raspberry Pi Foundation's [Build Your Own Weather Station](https://projects.raspberrypi.org/en/projects/build-your-own-weather-station/2) tutorial.
- The sea-level pressure formula in **`analysis/pressure_trends.py`**:
  transcribed from the National Weather Service's [station pressure
  calculator](https://www.weather.gov/media/epz/wxcalc/stationPressure.pdf). I had to invert it, because after troubleshooting it for a little while, I realized that the equation is for converting barometric pressure at sea-level into station pressure and I needed to do the opposite.

## License

This project is licensed under the [GNU General Public License v2.0 or
later](LICENSE).
