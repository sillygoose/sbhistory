"""Code to interface with the SMA inverters and return the results."""

import asyncio
import logging
import dateutil
import datetime
import clearsky
# from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from astral.sun import sun
from astral import LocationInfo

from config import config_from_yaml
cfg = config_from_yaml(data='sbhistory.yaml', read_from_file=True)

logger = logging.getLogger('sbhistory')


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


class Site:
    """Class to describe a PV site with one or more inverters."""
    def __init__(self, session):
        """Create a new Site object."""
        self._influx = InfluxDB(cfg.influxdb2.enable)
        self._inverters = []
        for inverter in cfg.inverters:
            inv = inverter.get('inverter', None)
            self._inverters.append(Inverter(inv['name'], inv['url'], inv['user'], inv['password'], session))

    async def start(self):
        """Initialize the Site object."""
        if not self._influx.start(url=cfg.influxdb2.url, bucket=cfg.influxdb2.bucket, org=cfg.influxdb2.org, token=cfg.influxdb2.token):
            return False
        results = await asyncio.gather(*(inverter.initialize() for inverter in self._inverters))
        return False not in results

    async def stop(self):
        """Shutdown the Site object."""
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))
        self._influx.stop()

    # daily totals, day increments
    async def populate_daily_history(self):
        now = datetime.datetime.now()
        start = datetime.datetime(year=cfg.sbhistory.start_year, month=cfg.sbhistory.start_month, day=cfg.sbhistory.start_day)
        stop = datetime.datetime(year=now.year, month=now.month, day=now.day)
        print(f"Populating daily total production values from {start.date()} to {stop.date()}")

        inverters = await asyncio.gather(*(inverter.read_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
        for inverter in inverters:
            t = inverter[1]['t']
            dt = datetime.datetime.fromtimestamp(t)
            date = datetime.date(year=cfg.sbhistory.start_year, month=cfg.sbhistory.start_month, day=cfg.sbhistory.start_day)
            end_date = datetime.date(year=dt.year, month=dt.month, day=dt.day)
            delta = datetime.timedelta(days=1)
            while date < end_date:
                print("*", end='')
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

        site_total = []
        for t, v in total.items():
            if count[t] == len(inverters):
                site_total.append({'t': t, 'v': v})
        site_total.insert(0, {'inverter': 'site'})
        inverters.append(site_total)
        self._influx.write_history(inverters, 'production/today')
        print()

    # daily production, 5 minute increments, seems only available for the current year
    async def populate_fine_history(self):
        delta = datetime.timedelta(days=1)
        date = datetime.date(year=cfg.sbhistory.start_year, month=cfg.sbhistory.start_month, day=cfg.sbhistory.start_day)
        end_date = datetime.date.today() + delta
        print(f"Populating daily production values from {date} to {end_date}")

        while date < end_date:
            print(".", end='')
            start = datetime.datetime.combine(date, datetime.time(0, 0)) - datetime.timedelta(minutes=5)
            stop = start + delta

            total = {}
            count = {}
            inverters = await asyncio.gather(*(inverter.read_fine_history(int(start.timestamp()), int(stop.timestamp())) for inverter in self._inverters))
            for inverter in inverters:
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

            site_total = []
            for t, v in total.items():
                if count[t] == len(inverters):
                    site_total.append({'t': t, 'v': v})
            site_total.insert(0, {'inverter': 'site'})
            inverters.append(site_total)
            self._influx.write_history(inverters, 'production/total')
            date += delta
        print()

    async def populate_irradiance(self):
        site = clearsky.site_location(cfg.site.latitude, cfg.site.longitude, tz=cfg.site.tz)
        siteinfo = LocationInfo(cfg.site.name, cfg.site.region, cfg.site.tz, cfg.site.latitude, cfg.site.longitude)
        tzinfo = dateutil.tz.gettz(cfg.site.tz)

        delta = datetime.timedelta(days=1)
        date = datetime.date(year=cfg.sbhistory.start_year, month=cfg.sbhistory.start_month, day=cfg.sbhistory.start_day)
        end_date = datetime.date.today() + delta
        print(f"Populating irradiance values from {date} to {end_date}")

        lp_points = []
        while date < end_date:
            print(".", end='')
            astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
            dawn = astral['dawn']
            dusk = astral['dusk'] + datetime.timedelta(minutes=10)
            start = datetime.datetime(dawn.year, dawn.month, dawn.day, dawn.hour, int(int(dawn.minute / 10) * 10))
            stop = datetime.datetime(dusk.year, dusk.month, dusk.day, dusk.hour, int(int(dusk.minute / 10) * 10))

            # Get irradiance data for today and convert to InfluxDB line protocol
            irradiance = clearsky.get_irradiance(site=site, start=start.strftime("%Y-%m-%d %H:%M:00"), end=stop.strftime("%Y-%m-%d %H:%M:00"), tilt=cfg['solar_properties.tilt'], azimuth=cfg['solar_properties.azimuth'], freq='10min')
            for point in irradiance:
                t = point['t']
                v = point['v'] * cfg.solar_properties.area * cfg.solar_properties.efficiency
                lp = f'production,inverter=site irradiance={round(v, 1)} {t}'
                lp_points.append(lp)
            date += delta

        self._influx.write_points(lp_points)
        print()

    async def run(self):
        if cfg.sbhistory.daily_history:
            await self.populate_daily_history()
        if cfg.sbhistory.fine_history:
            await self.populate_fine_history()
        if cfg.sbhistory.irradiance_history:
            await self.populate_irradiance()