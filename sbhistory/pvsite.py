"""Code to interface with the SMA inverters and return state or history."""

import asyncio
import logging
import dateutil
import datetime
import clearsky
import math
# from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from astral.sun import sun
from astral import LocationInfo


logger = logging.getLogger('sbhistory')


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


class Site:
    """Class to describe a PV site with one or more inverters."""
    def __init__(self, session, config):
        """Create a new Site object."""
        self._config = config
        self._influx = InfluxDB(config.multisma2.influxdb2.enable)
        self._inverters = []
        for inverter in config.multisma2.inverters:
            inv = inverter.get('inverter', None)
            self._inverters.append(Inverter(inv['name'], inv['url'], inv['user'], inv['password'], session))

    async def start(self):
        """Initialize the Site object."""
        config = self._config
        if not self._influx.start(url=config.multisma2.influxdb2.url, bucket=config.multisma2.influxdb2.bucket, org=config.multisma2.influxdb2.org, token=config.multisma2.influxdb2.token):
            return False
        results = await asyncio.gather(*(inverter.initialize() for inverter in self._inverters))
        return False not in results

    async def stop(self):
        """Shutdown the Site object."""
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))
        self._influx.stop()

    # daily totals, day increments
    async def populate_daily_history(self):
        cfg = self._config
        now = datetime.datetime.now()
        start = datetime.datetime(year=cfg.sbhistory.start.year, month=cfg.sbhistory.start.month, day=cfg.sbhistory.start.day)
        stop = datetime.datetime(year=now.year, month=now.month, day=now.day)
        print(f"Populating daily history values from {start.date()} to {stop.date()}")

        inverters = await asyncio.gather(*(inverter.read_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
        for inverter in inverters:
            t = inverter[1]['t']
            dt = datetime.datetime.fromtimestamp(t)
            date = datetime.date(year=cfg.sbhistory.start.year, month=cfg.sbhistory.start.month, day=cfg.sbhistory.start.day)
            end_date = datetime.date(year=dt.year, month=dt.month, day=dt.day)
            delta = datetime.timedelta(days=1)
            while date < end_date:
                print(".", end='', flush=True)
                newtime = datetime.datetime.combine(date, datetime.time(0, 0))
                t = int(newtime.timestamp())
                inverter.append({'t': t, 'v': 0})
                date += delta

            # Sort the entries by date
            try:
                inv0 = inverter
                inv_name = inv0.pop(0)
                inv0.sort(key=lambda item: item.get("t"))
                inv0.insert(0, inv_name)
            except Exception as e:
                print(e)

        total = {}
        count = {}
        for inverter in inverters:
            last_non_null = None
            for i in range(1, len(inverter)):
                print(".", end='', flush=True)
                t = inverter[i]['t']
                v = inverter[i]['v']
                if v is None:
                    if not last_non_null:
                        continue
                    v = last_non_null
                    inverter[i]['v'] = last_non_null
                total[t] = v + total.get(t, 0)
                count[t] = count.get(t, 0) + 1
                last_non_null = v

        # Site output if multiple inverters
        if len(inverters) > 1:
            site_total = []
            for t, v in total.items():
                if count[t] == len(inverters):
                    site_total.append({'t': t, 'v': v})
            site_total.insert(0, {'inverter': 'site'})
            inverters.append(site_total)

        self._influx.write_history(inverters, 'production/midnight')
        print()

    # fine production, 5 minute increments
    async def populate_fine_history(self):
        config = self._config
        delta = datetime.timedelta(days=1)
        date = datetime.date(year=config.sbhistory.start.year, month=config.sbhistory.start.month, day=config.sbhistory.start.day)
        end_date = datetime.date.today() + delta
        print(f"Populating fine history values from {date} to {end_date}")

        while date < end_date:
            start = datetime.datetime.combine(date, datetime.time(0, 0)) - datetime.timedelta(minutes=5)
            stop = start + delta

            total = {}
            count = {}
            inverters = await asyncio.gather(*(inverter.read_fine_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
            for inverter in inverters:
                print(".", end='', flush=True)
                last_non_null = None
                for i in range(1, len(inverter)):
                    t = inverter[i]['t']
                    v = inverter[i]['v']
                    if v is None:
                        if not last_non_null:
                            continue
                        v = last_non_null
                        inverter[i]['v'] = last_non_null
                    total[t] = v + total.get(t, 0)
                    count[t] = count.get(t, 0) + 1
                    last_non_null = v

            # Site output if multiple inverters
            if len(inverters) > 1:
                site_total = []
                for t, v in total.items():
                    if count[t] == len(inverters):
                        site_total.append({'t': t, 'v': v})
                site_total.insert(0, {'inverter': 'site'})
                inverters.append(site_total)

            self._influx.write_history(inverters, 'production/total_wh')
            date += delta
        print()

    async def populate_irradiance(self, config):
        try:
            start = config.sbhistory.start
            site_properties = config.multisma2.site
            solar_properties = config.multisma2.solar_properties

            tzinfo = dateutil.tz.gettz(site_properties.tz)
            siteinfo = LocationInfo(name=site_properties.name, region=site_properties.region, timezone=site_properties.tz, latitude=site_properties.latitude, longitude=site_properties.longitude)

            delta = datetime.timedelta(days=1)
            date = datetime.datetime(year=start.year, month=start.month, day=start.day)
            end_date = datetime.datetime.today() + delta
            print(f"Populating irradiance values from {date.date()} to {end_date.date()}")

            lp_points = []
            while date < end_date:
                print(".", end='', flush=True)
                astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
                dawn = astral['dawn']
                dusk = astral['dusk']
                irradiance = clearsky.global_irradiance(site_properties, solar_properties, dawn, dusk)
                for point in irradiance:
                    t = point['t']
                    v = point['v']
                    if not math.isnan(v):
                        lp = f'sun irradiance={round(v, 1)} {t}'
                        lp_points.append(lp)
                date += delta

            self._influx.write_points(lp_points)
            print()
        except Exception as e:
            logger.error(f"An exception occurred in populate_irradiance(): {e}")

    async def run(self):
        config = self._config
        if config.sbhistory.outputs.daily_history:
            await self.populate_daily_history()
        if config.sbhistory.outputs.fine_history:
            await self.populate_fine_history()
        if config.sbhistory.outputs.irradiance_history:
            await self.populate_irradiance(config)
