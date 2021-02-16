"""Code to interface with the SMA inverters and return the results."""

import os
import asyncio
import logging
import dateutil
import datetime
# import clearsky
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
                print(".", end='')
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
                print(".", end='')
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
                print(".", end='')
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

#    async def populate_irradiance(self):
#        site = clearsky.site_location(cfg.sbhistory.site.latitude, cfg.sbhistory.site.longitude, tz=cfg.sbhistory.site.tz)
#        siteinfo = LocationInfo(cfg.sbhistory.site.name, cfg.sbhistory.site.region, cfg.sbhistory.site.tz, cfg.sbhistory.site.latitude, cfg.sbhistory.site.longitude)
#        tzinfo = dateutil.tz.gettz(cfg.sbhistory.site.tz)
#
#        delta = datetime.timedelta(days=1)
#        date = datetime.date(year=cfg.sbhistory.start.year, month=cfg.sbhistory.start.month, day=cfg.sbhistory.start.day)
#        end_date = datetime.date.today() + delta
#        print(f"Populating irradiance values from {date} to {end_date}")
#
#        lp_points = []
#        while date < end_date:
#            print(".", end='')
#            astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
#            dawn = astral['dawn']
#            dusk = astral['dusk'] + datetime.timedelta(minutes=10)
#            start = datetime.datetime(dawn.year, dawn.month, dawn.day, dawn.hour, int(int(dawn.minute / 10) * 10))
#            stop = datetime.datetime(dusk.year, dusk.month, dusk.day, dusk.hour, int(int(dusk.minute / 10) * 10))
#
#            # Get irradiance data for today and convert to InfluxDB line protocol
#            irradiance = clearsky.get_irradiance(site=site, start=start.strftime("%Y-%m-%d %H:%M:00"), end=stop.strftime("%Y-%m-%d %H:%M:00"), tilt=cfg['solar_properties.tilt'], azimuth=cfg['solar_properties.azimuth'], freq='10min')
#            for point in irradiance:
#                t = point['t']
#                v = point['v'] * cfg.sbhistory.solar_properties.area * cfg.sbhistory.solar_properties.efficiency
#                lp = f'production,inverter=site irradiance={round(v, 1)} {t}'
#                lp_points.append(lp)
#            date += delta
#
#        self._influx.write_points(lp_points)
#        print()

    async def run(self):
        config = self._config
        if config.sbhistory.outputs.daily_history:
            await self.populate_daily_history()
        if config.sbhistory.outputs.fine_history:
            await self.populate_fine_history()
#        if config.sbhistory.outputs.irradiance_history:
#            await self.populate_irradiance()
