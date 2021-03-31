# Interface to InfluxDB multisma2 database
#
# InfluxDB Line Protocol Reference
# https://docs.influxdata.com/influxdb/v2.0/reference/syntax/line-protocol/

import logging
import os
from config import config_from_yaml

from influxdb_client import InfluxDBClient, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


logger = logging.getLogger("sbhistory")

LP_LOOKUP = {
    "ac_measurements/power": {"measurement": "ac_measurements", "tag": "_inverter", "field": "power"},
    "ac_measurements/voltage": {"measurement": "ac_measurements", "tag": "_inverter", "field": "voltage"},
    "ac_measurements/current": {"measurement": "ac_measurements", "tag": "_inverter", "field": "current"},
    "ac_measurements/efficiency": {"measurement": "ac_measurements", "tag": "_inverter", "field": "efficiency"},
    "dc_measurements/power": {"measurement": "dc_measurements", "tag": "_inverter", "field": "power"},
    "status/reason_for_derating": {"measurement": "status", "tag": "_inverter", "field": "derating"},
    "status/general_operating_status": {"measurement": "status", "tag": "_inverter", "field": "operating_status"},
    "status/grid_relay": {"measurement": "status", "tag": "_inverter", "field": "grid_relay"},
    "status/condition": {"measurement": "status", "tag": "_inverter", "field": "condition"},
    "production/total_wh": {"measurement": "production", "tag": "_inverter", "field": "total_wh"},
    "production/midnight": {"measurement": "production", "tag": "_inverter", "field": "total_wh"},
    "sun/position": {"measurement": "sun", "tag": None, "field": None},
    "sun/irradiance": {"measurement": "sun", "tag": "measured", "field": "irradiance"},
}


class InfluxDB:
    def __init__(self):
        self._client = None
        self._write_api = None
        self._query_api = None
        self._delete_api = None
        self._enabled = False

    def check_config(self, config):
        """Check that the needed YAML options exist."""
        required_keys = ["url", "token", "bucket", "org"]
        for key in required_keys:
            if key not in config.keys():
                logger.error(f"Missing required 'influxdb2' option in YAML file: '{key}'")
                return False
        return True

    def start(self, config):
        key = "enable"
        if key not in config.keys():
            logger.error(f"Missing required 'influxdb2' option in YAML file: '{key}'")
            return False

        if not isinstance(config.enable, bool):
            logger.error(f"The influxdb 'enable' option is not a boolean '{config.enable}'")
            return False

        if not config.enable:
            logger.error(f"The influxdb 'enable' option must be enabled to use 'sbhistory': '{config.enable}'")
            return False

        if self.check_config(config) is False:
            return False

        self._bucket = config.bucket
        self._client = InfluxDBClient(url=config.url, token=config.token, org=config.org)
        if not self._client:
            logger.error(
                f"Failed to get InfluxDBClient object from {config.url} (check your url, token, and/or organization)"
            )
            return False
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        if not self._write_api:
            logger.error(f"Failed to get client write_api() object from {config.url}")
            return False
        self._delete_api = self._client.delete_api()
        if not self._delete_api:
            logger.error(f"Failed to get client delete_api() object from {config.url}")
            return False
        self._query_api = self._client.query_api()
        if not self._query_api:
            logger.error(f"Failed to get client query_api() object from {config.url}")
            return False
        try:
            self._query_api.query(f'from(bucket: "{self._bucket}") |> range(start: -1m)')
            logger.info(f"Connected to the InfluxDB database at {config.url}, bucket '{self._bucket}'")
            return True
        except Exception:
            logger.error(f"Unable to access bucket '{self._bucket}' at {config.url}")
        return False

    def stop(self):
        if self._write_api:
            self._write_api.close()
            self._write_api = None
        if self._client:
            bucket = self._bucket
            self._client.close()
            self._client = None
            logger.info(f"Closed the InfluxDB bucket '{bucket}'")

    def write_points(self, points):
        if not self._write_api:
            return False
        try:
            self._write_api.write(bucket=self._bucket, record=points, write_precision=WritePrecision.S)
            result = True
        except Exception as e:
            logger.error(f"Database write_points() call failed in write_points(): {e}")
            result = False
        return result

    def query(self):
        try:
            self._query_api.query(f'from(bucket: "{self._bucket}") |> range(start: -1m)')
            return True
        except Exception:
            logger.error(f"Unable to query from '{self._bucket}'")
        return False

    def write_history(self, site, topic):
        result = False
        if not self._write_api:
            return result

        lookup = LP_LOOKUP.get(topic, None)
        if not lookup:
            logger.error(f"write_history(): unknown topic '{topic}'")
            return result

        measurement = lookup.get("measurement")
        tag = lookup.get("tag")
        field = lookup.get("field")
        lps = []
        for inverter in site:
            inverter_name = inverter.pop(0)
            name = inverter_name.get("inverter", "sunnyboy")
            for history in inverter:
                t = history["t"]
                v = history["v"]
                midnight = history.get("midnight", "no")
                if v is None:
                    # logger.info(f"write_history(): '{type(v)}' in '{name}/{t}/{measurement}/{field}'")
                    continue
                elif isinstance(v, int):
                    lp = f"{measurement},{tag}={name},_midnight={midnight} {field}={v}i {t}"
                    lps.append(lp)
                else:
                    logger.error(
                        f"write_history(): unanticipated type '{type(v)}' in measurement '{measurement}/{field}'"
                    )
                    continue

        try:
            self._write_api.write(bucket=self._bucket, record=lps, write_precision=WritePrecision.S)
            result = True
        except Exception as e:
            logger.error(f"Database write_points() call failed in write_history(): {e}")
        return result


if __name__ == "__main__":
    yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sbhistory.yaml")
    config = config_from_yaml(data=yaml_file, read_from_file=True)
    influxdb = InfluxDB()
    result = influxdb.start(config=config.multisma2.influxdb2)
    if not result:
        print("Something failed")
    influxdb.stop()
