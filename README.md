# sbhistory
Application to pull Sunny Boy inverter history and send to a InfluxDB 2.x or 1.8.x database

## Installation
Python 3.7 or better is required, you can then install the Python requirements for this application:
```
    git clone https://github.com/sillygoose/sbhistory
    cd sbhistory
    pip3 install -e .
```

## Use
Make sure your InfluxDB database has an infinite retention policy, or at least longer than the start date for data.

Copy the file `sample.yaml` to `sbhistory.yaml` and fill in the details for your local site and inverters.  Run the application from the command line using Python 3.7 or later:

```
    cd sbhistory
    python3 sbhistory.py
```

## Outputs
Outputs are one per inverter, and if there is more than one inverter in your site, a site-wide value named `site` is created from the sum of the inverter outputs.  In the current version the following outputs can be selected to be sent to InfluxDB:
- daily_history

    Daily history is the inverter(s) total Wh meter recorded at midnight (local time) each day:

        _measurement    `production`
        _inverter       `inverter name(s)`, 'site'
        _field          `midnight`

    This makes finding the production for a day, month, year, or any period the difference between the two selected records.

- fine_history

    Fine history is the inverter(s) total Wh meter recorded at 5 minute periods throughout the day:

        _measurement    `production`
        _inverter       `inverter name(s)`, `site`
        _field          `total_wh`

    Like the daily_history, production for a period is just a subtraction. But if you want to see the power in watts for a period you have to do some math. See the Flux `irradiance` script for how this is accomplished.

    NOTE: It seems that only the current year daily production data is stored on an inverter.

- irradiance_history

    The irradiance history output is the estimated solar radiation (W/m<sup>2</sup>) available at a specific time on a collector with a fixed azimuth and tilt.  This varies through the year and takes into account the location, moisture (cold winter air holds less moisture and is clearer than warm moist air), and other seasonal effects.

        _measurement    `sun`
        _field          `irradiance`

    You can use the irradiance to estimate the solar potential for your PV array by multiplying the irradiance by the area of the array (in m<sup>2</sup>) and the unitless efficiency, i.e., a 300W panel with an area of 2 m<sup>2</sup> has an efficiency of 0.15.

    Keep in mind it is just a best guess since other factors such as diffuse and reflected radiation for a site are harder to quantify.

## Errors
If you happen to make errors and get locked out of your inverters (confirm by being unable to log into an inverter using the WebConnect browser interface), the Sunny Boy inverters can be reset by

- disconnect grid power from inverters (usually one or more breakers)
- disconnect DC power from the panels to the inverters (rotary switch on each inverter)
- wait 2 minutes
- restore DC power via each rotary switch
- restore grid power via breakers

## Thanks
Thanks for the following packages used to build this software:
- PYSMA library for WebConnect
    - http://www.github.com/kellerza/pysma
- YAML configuration file support
    - https://python-configuration.readthedocs.io
- Astral solar calculator
    - https://astral.readthedocs.io
- Solar irradiance on a tilted collector
    - Chapter 7 of 'Renewable and Efficient Electric Power Systems' by Masters
- Tricks for managing startup and shutdown
    - https://github.com/wbenny/python-graceful-shutdown


