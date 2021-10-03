""""""

import logging
import datetime

from inverter import Inverter

_LOGGER = logging.getLogger('sbhistory')


def write(influxdb, points, period):
    lp_points = []
    for t, inverter in points.items():
        for key, value in inverter.items():
            lp = f"production,_inverter={key} {period}={value} {t}"
            lp_points.append(lp)
    return influxdb.write_points(lp_points)


def process(inverter_results):
    results = {}
    site_wh = 0
    for inverter in inverter_results:
        name = inverter[0].get('inverter')
        if len(inverter) >= 3:
            start = inverter[1].get('v')
            end = inverter[-1].get('v')
            if start is None or end is None:
                continue
            wh = end - start
            site_wh += wh
            results[name] = wh / 1000
        else:
            _LOGGER.debug(f"Inverter '{name}' missing data ")
            return None
    results['site'] = site_wh / 1000
    return results
