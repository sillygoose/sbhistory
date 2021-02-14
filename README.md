# sbhistory
Application to pull Sunny Boy inverter history and send to a InfluxDB 2.x or 1.8.x database

## Installation
Python 3.7 or better is required, you can then install the Python requirements for this application:
```
git clone https://github.com/sillygoose/sbhistory
cd sbhistory
pip install -e .
```

## Use
Make sure your InfluxDB database has an infinite retention policy, or at least longer than the start date for data.

Copy the file `sample.yaml` to `sbhistory.yaml` and fill in the details for your local site and inverters.  Run the application from the command line using Python 3.7 or later:

`python3 sbhistory.py`

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
- Tricks for managing startup and shutdown
    - https://github.com/wbenny/python-graceful-shutdown


