## sbhistory
Application to pull Sunny Boy inverter data from one or more inverters and send to a InfluxDB2 database.  Additional features allow modeling irradiance for a specific location or import irradiance CSV files from a Seaward irradiance meter for checking model accuracy.

#
## What's new
#### 1.1.0
- new `production` option, this will query the SMA inverter(s) and write daily, monthly, and yearly totals to InfluxDB2.

#
## Installation
Python 3.8 or better is required, you can then install the Python requirements for this application:
```
    git clone https://github.com/sillygoose/sbhistory
    cd sbhistory
    pip3 install -e .
```

#
## Use
Make sure your InfluxDB database has an infinite retention policy, or at least longer than the start date for the data.

Rename the `sample_secrets.yaml` file to `.sbhistory_secrets.yaml` and edit to match your site (if you don't wish to use secrets then edit `sbhistory.yaml` to remove the `!secret` references).  Any secrets files are tagged in `.gitignore` and will not be included in the repository but if you wish you can put `.sbhistory_secrets.yaml` in any parent directory as `sbhistory` will start in the current directory and look in each parent directory up to your home directory for it (or just the current directory if you are not running in a user profile).

Run the application in VS Code or from the command line:

```
    cd sbhistory
    python3 sbhistory.py
```

#
## InfluxDB Outputs
Outputs are one per inverter, and if there is more than one inverter in your site, a site-wide value named `site` is created from the sum of the inverter outputs.  In the current version the following outputs can be selected to be sent on to InfluxDB:
- production

    `production` is the inverter(s) production in kWh for a day, month, or year:

        _measurement    production
        _inverter       inverter name(s), site
        _field          today (kWh), month (kWh), year (kWh)

    Measurements are written at midnight on the given period and running totals are updated by **multisma2**.

- daily_history

    `daily_history` is the value of theinverter(s) total Wh meter recorded at midnight (local time) each day:

        _measurement    production
        _inverter       inverter name(s), site
        _field          midnight (Wh)

    This measurement makes finding the production for a day, month, year, or any period the difference between the two selected records.

- fine_history

    `fine history `is the inverter(s) total Wh meter recorded at 5 minute periods throughout the day:

        _measurement    production
        _inverter       inverter name(s), site
        _field          total_wh (Wh)

    Like `daily_history`, production for a period is just a subtraction. But if you want to see the power in watts for a period you have to do some math. See the Flux `irradiance` script for how this is accomplished.

    NOTE: There is only limited production history stored on an inverter.

- irradiance

    The `irradiance` output is the estimated solar radiation (W/m<sup>2</sup>) available at a specific time on a collector with a fixed azimuth and tilt.  This varies through the year and takes into account the location, moisture (cold winter air holds less moisture than warm air), dust, and other seasonal effects.

        _measurement    sun
        _field          irradiance
        _type           modeled (W/m²)

    You can use the irradiance to estimate the solar potential for your PV array by multiplying the irradiance by the area of the array (in m<sup>2</sup>) and the unitless efficiency, i.e., a 300W panel with an area of 2 m<sup>2</sup> has an efficiency of 0.15.

    Keep in mind it is just a best guess since other factors such as diffuse and reflected radiation for a site are harder to quantify.

- seaward

    The `seaward` output reads log files from the Seaward Solar Survey 200R Irradiance Meter, this became an essential tool to verify the irradiance model with the actual solar flux hitting the panels (turned out to be very accurate without any further adjustment):

        _measurement    sun
        _field          irradiance
        _type           measured (W/m²)

        _measurement    sun
        _field          temperature
        _type           working (°C), ambient (°C)

    When enabled this will process every .csv file in the `path` option and write the results to InfluxDB.

#
## Errors
If you happen to make errors and get locked out of your inverters (confirm by being unable to log into an inverter using the WebConnect browser interface), the Sunny Boy inverters can be reset by

- disconnect grid power from inverters (usually one or more breakers)
- disconnect DC power from the panels to the inverters (rotary switch on each inverter)
- wait 2 minutes
- restore DC power via each rotary switch
- restore grid power via breakers

#
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
