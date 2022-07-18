# Interface to InfluxDB multisma2 database
#
# InfluxDB Line Protocol Reference
# https://docs.influxdata.com/influxdb/v2.0/reference/syntax/line-protocol/

import logging
import os
from config import config_from_yaml

from influxdb_client import InfluxDBClient, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

from exceptions import FailedInitialization


_LOGGER = logging.getLogger("sbhistory")

LP_LOOKUP = {
    'ac_measurements/power': {'measurement': 'ac_measurements', 'tags': ['_inverter'], 'field': 'power'},
    'ac_measurements/voltage': {'measurement': 'ac_measurements', 'tags': ['_inverter'], 'field': 'voltage'},
    'ac_measurements/current': {'measurement': 'ac_measurements', 'tags': ['_inverter'], 'field': 'current'},
    'ac_measurements/efficiency': {'measurement': 'ac_measurements', 'tags': ['_inverter'], 'field': 'efficiency'},
    'dc_measurements/power': {'measurement': 'dc_measurements', 'tags': ['_inverter', '_string'], 'field': 'power'},
    'dc_measurements/voltage': {'measurement': 'dc_measurements', 'tags': ['_inverter', '_string'], 'field': 'voltage'},
    'dc_measurements/current': {'measurement': 'dc_measurements', 'tags': ['_inverter', '_string'], 'field': 'current'},
    'status/reason_for_derating': {'measurement': 'status', 'tags': ['_inverter'], 'field': 'derating'},
    'status/general_operating_status': {'measurement': 'status', 'tags': ['_inverter'], 'field': 'operating_status'},
    'status/grid_relay': {'measurement': 'status', 'tags': ['_inverter'], 'field': 'grid_relay'},
    'status/condition': {'measurement': 'status', 'tags': ['_inverter'], 'field': 'condition'},
    'production/total_wh': {'measurement': 'production', 'tags': ['_inverter'], 'field': 'total_wh'},
    'production/midnight': {'measurement': 'production', 'tags': ['_inverter'], 'field': 'midnight'},
    'production/today': {'measurement': 'production', 'tags': ['_inverter'], 'field': 'today'},
    'production/month': {'measurement': 'production', 'tags': ['_inverter'], 'field': 'month'},
    'production/year': {'measurement': 'production', 'tags': ['_inverter'], 'field': 'year'},
    'sun/position': {'measurement': 'sun', 'tags': None, 'field': None},
    'sun/irradiance': {'measurement': 'sun', 'tags': ['_type'], 'field': 'irradiance'},
}


class InfluxDB:
    def __init__(self):
        self._client = None
        self._write_api = None
        self._query_api = None
        self._enabled = False

    def __del__(self):
        if self._client:
            self._client.close()

    def check_config(self, influxdb2):
        """Check that the needed YAML options exist."""
        errors = False
        required = {'enable': bool, 'url': str, 'token': str, 'bucket': str, 'org': str}
        options = dict(influxdb2)
        for key in required:
            if key not in options.keys():
                _LOGGER.error(f"Missing required 'influxdb2' option in YAML file: '{key}'")
                errors = True
            else:
                v = options.get(key, None)
                if not isinstance(v, required.get(key)):
                    _LOGGER.error(f"Expected type '{required.get(key).__name__}' for option 'influxdb2.{key}'")
                    errors = True
        if errors:
            raise FailedInitialization(Exception("Errors detected in 'influxdb2' YAML options"))
        return options

    def start(self, config):
        if not self.check_config(config):
            return False
        if not config.enable:
            _LOGGER.info(f"The InfluxDB database is disabled")
            return True
        try:
            self._bucket = config.bucket
            self._client = InfluxDBClient(url=config.url, token=config.token, org=config.org)
            if not self._client:
                raise Exception(
                    f"Failed to get InfluxDBClient from {config.url} (check url, token, and/or organization)")

            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            if not self._write_api:
                raise Exception(f"Failed to get client write_api() object from {config.url}")

            query_api = self._client.query_api()
            if not query_api:
                raise Exception(f"Failed to get client query_api() object from {config.url}")
            try:
                query_api.query(f'from(bucket: "{self._bucket}") |> range(start: -1m)')
                self._enabled = True
                _LOGGER.info(f"Connected to the InfluxDB database at {config.url}, bucket '{self._bucket}'")
            except Exception:
                raise Exception(f"Unable to access bucket '{self._bucket}' at {config.url}")

        except Exception as e:
            _LOGGER.error(f"{e}")
            self.stop()
            return False

        return True

    def stop(self):
        if self._enabled:
            if self._write_api:
                self._write_api.close()
                self._write_api = None
            if self._client:
                self._client.close()
                self._client = None

    def write_points(self, points):
        if not self._enabled:
            return True

        if not self._write_api:
            return False
        try:
            self._write_api.write(bucket=self._bucket, record=points, write_precision=WritePrecision.S)
            result = True
        except Exception as e:
            _LOGGER.error(f"Database write() call failed in write_points(): {e}")
            result = False
        return result

    def write_history(self, site, topic):
        if not self._enabled:
            return True

        if not self._write_api:
            return False

        lookup = LP_LOOKUP.get(topic, None)
        if not lookup:
            _LOGGER.error(f"write_history(): unknown topic '{topic}'")
            return False

        measurement = lookup.get('measurement')
        tags = lookup.get('tags', None)
        field = lookup.get('field', None)
        lps = []
        for inverter in site:
            inverter_name = inverter.pop(0)
            name = inverter_name.get('inverter', 'sunnyboy')
            for history in inverter:
                t = history['t']
                v = history['v']
                if v is None:
                    continue
                lp = f"{measurement}"
                if tags and len(tags):
                    lp += f",{tags[0]}={name}"
                if isinstance(v, int):
                    lp += f" {field}={v}i {t}"
                    lps.append(lp)
                else:
                    _LOGGER.error(
                        f"write_history(): unanticipated type '{type(v)}' in measurement '{measurement}/{field}'"
                    )
                    continue

        try:
            self._write_api.write(bucket=self._bucket, record=lps, write_precision=WritePrecision.S)
            return True
        except Exception as e:
            _LOGGER.error(f"Database write() call failed in write_history(): {e}")
            return False


if __name__ == "__main__":
    yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sbhistory.yaml")
    config = config_from_yaml(data=yaml_file, read_from_file=True)
    influxdb = InfluxDB()
    result = influxdb.start(config=config.multisma2.influxdb2)
    if not result:
        print("Something failed")
    influxdb.stop()
