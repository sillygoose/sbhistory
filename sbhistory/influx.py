# Interface to InfluxDB multisma2 database
#
# InfluxDB Line Protocol Reference
# https://docs.influxdata.com/influxdb/v2.0/reference/syntax/line-protocol/

import logging

from influxdb_client import InfluxDBClient, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS


logger = logging.getLogger('sbhistory')

LP_LOOKUP = {
    'ac_measurements/power': {'measurement': 'ac_measurements', 'tag': '_inverter', 'field': 'power'},
    'ac_measurements/voltage': {'measurement': 'ac_measurements', 'tag': '_inverter', 'field': 'voltage'},
    'ac_measurements/current': {'measurement': 'ac_measurements', 'tag': '_inverter', 'field': 'current'},
    'ac_measurements/efficiency': {'measurement': 'ac_measurements', 'tag': '_inverter', 'field': 'efficiency'},
    'dc_measurements/power': {'measurement': 'dc_measurements', 'tag': '_inverter', 'field': 'power'},
    'status/reason_for_derating': {'measurement': 'status', 'tag': '_inverter', 'field': 'derating'},
    'status/general_operating_status': {'measurement': 'status', 'tag': '_inverter', 'field': 'operating_status'},
    'status/grid_relay': {'measurement': 'status', 'tag': '_inverter', 'field': 'grid_relay'},
    'status/condition': {'measurement': 'status', 'tag': '_inverter', 'field': 'condition'},
    'production/total_wh': {'measurement': 'production', 'tag': '_inverter', 'field': 'total_wh'},
    'sun/position': {'measurement': 'sun', 'tag': None, 'field': None},
}


class InfluxDB():
    def __init__(self, enabled):
        self._client = None
        self._write_api = None
        self._enabled = enabled

    def start(self, url, bucket, org, token):
        if not self._enabled:
            return True
        self._bucket = bucket
        self._client = InfluxDBClient(url=url, token=token, org=org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS) if self._client else None
        result = self._client if self._client else False
        logger.info(f"{'Opened' if result else 'Failed to open'} the InfluxDB database '{bucket}' at {url}")
        return result

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

    def write_history(self, site, topic):
        result = False
        if not self._write_api:
            return result

        lookup = LP_LOOKUP.get(topic, None)
        if not lookup:
            logger.error(f"write_history(): unknown topic '{topic}'")
            return result

        measurement = lookup.get('measurement')
        tag = lookup.get('tag')
        field = lookup.get('field')
        lps = []
        for inverter in site:
            inverter_name = inverter.pop(0)
            name = inverter_name.get('inverter', 'sunnyboy')
            for history in inverter:
                t = history['t']
                v = history['v']
                if v is None:
                    # logger.info(f"write_history(): '{type(v)}' in '{name}/{t}/{measurement}/{field}'")
                    continue
                elif isinstance(v, int):
                    lp = f'{measurement},{tag}={name} {field}={v}i {t}'
                    lps.append(lp)
                else:
                    logger.error(f"write_history(): unanticipated type '{type(v)}' in measurement '{measurement}/{field}'")
                    continue

        try:
            self._write_api.write(bucket=self._bucket, record=lps, write_precision=WritePrecision.S)
            result = True
        except Exception as e:
            logger.error(f"Database write_points() call failed in write_history(): {e}")
        return result
