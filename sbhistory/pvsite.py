"""Code to interface with the SMA inverters and return state or history."""

import asyncio
import logging
import dateutil
import datetime
from dateutil.relativedelta import relativedelta
from dateutil.parser import isoparse

from astral.sun import sun
from astral import LocationInfo

import clearsky
import production
import dailyhistory
import seaward

from inverter import Inverter
from influx import InfluxDB


_LOGGER = logging.getLogger('sbhistory')


def diff_month(d1, d2):
    return (d1.year - d2.year) * 12 + d1.month - d2.month


class Site:
    """Class to describe a PV site with one or more inverters."""

    def __init__(self, session, config):
        """Create a new Site object."""
        self._config = config
        self._influx = InfluxDB()
        self._inverters = []
        for inverter in config.multisma2.inverters:
            inv = inverter.get('inverter', None)
            self._inverters.append(Inverter(inv['name'], inv['url'], inv['username'], inv['password'], session))

    async def start(self):
        """Initialize the Site object."""
        config = self._config
        if not self._influx.start(config=config.multisma2.influxdb2):
            return False
        return True

    async def stop(self):
        """Shutdown the Site object."""
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))
        self._influx.stop()

    async def start_inverters(self):
        inverters = await asyncio.gather(*(inverter.initialize() for inverter in self._inverters))
        success = True
        for inverter in inverters:
            error = inverter.get('error', None)
            if error is None or len(error) > 0:
                _LOGGER.error(
                    f"Connection to inverter '{inverter.get('name')}' failed: {inverter.get('error', 'None')}")
                success = False
        if not success:
            return False
        return True

    async def stop_inverters(self):
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))

    async def production_worker(self, start, stop, period):
        if period == 'year':
            current = start.replace(month=1, day=1)
            stop = stop.replace(month=1, day=1) + relativedelta(years=1)
        elif period == 'month':
            current = start.replace(day=1)
            stop = stop.replace(day=1) + relativedelta(months=1)
        elif period == 'today':
            current = start
            stop = stop + relativedelta(days=1)
        else:
            _LOGGER.error(f"Unsupported period type: '{period}'")
            return

        _LOGGER.info(f"Populating '{period}' production values from {current.date()} to {stop.date()}")
        combined = {}
        while current < stop:
            if period == 'year':
                next = current + relativedelta(years=1)
            elif period == 'month':
                next = current + relativedelta(months=1)
            else:
                next = current + datetime.timedelta(days=1, hours=2)

            start_ts = int(current.timestamp())
            stop_ts = int(next.timestamp())
            if await self.start_inverters():
                inverters = await asyncio.gather(*(inverter.read_history(start=start_ts, stop=stop_ts) for inverter in self._inverters))
                await self.stop_inverters()
            else:
                return

            results = production.process(inverters)
            if results is None:
                _LOGGER.debug(f"{current}: failed to retrieve inverter data")
            else:
                combined[start_ts] = results

            current = current + datetime.timedelta(days=1) if period == 'today' else next
            print('.', end='', flush=True)
        print()
        production.write(influxdb=self._influx, points=combined, period=period)

    async def populate_production(self, config):
        if not config.sbhistory.production.enable:
            return
        try:
            start = dateutil.parser.parse(config.sbhistory.production.start)
            if config.sbhistory.production.get('stop', None):
                stop = dateutil.parser.parse(config.sbhistory.production.stop)
            else:
                stop = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        except Exception as e:
            _LOGGER.error(f"Unexpected exception: {e}")
            return

        periods = ['today', 'month', 'year']
        for period in periods:
            await self.production_worker(start, stop, period)

    async def populate_daily_history(self, config):
        if not config.sbhistory.daily_history.enable:
            return
        try:
            start = dateutil.parser.parse(config.sbhistory.daily_history.start)
            if config.sbhistory.daily_history.get('stop', None):
                stop = dateutil.parser.parse(config.sbhistory.daily_history.stop)
            else:
                stop = datetime.datetime.combine(datetime.date.today(), datetime.datetime.min.time())
        except Exception as e:
            print(e)
            return

        start = start - datetime.timedelta(hours=1)
        stop += datetime.timedelta(days=1)
        _LOGGER.info(f"Populating daily history values from {start.date()} to {stop.date()}")

        if await self.start_inverters():
            inverters = await asyncio.gather(
                *(
                    inverter.read_history(start=int(start.timestamp()), stop=int(stop.timestamp()))
                    for inverter in self._inverters
                )
            )
            await self.stop_inverters()
        else:
            return

        inverters = dailyhistory.process(inverters, start=start)
        self._influx.write_history(inverters, 'production/midnight')

    async def populate_fine_history(self, config):
        if not config.sbhistory.fine_history.enable:
            return
        recent = config.sbhistory.fine_history.start.lower() == 'recent'
        try:
            if not recent:
                date = datetime.date.fromisoformat(config.sbhistory.fine_history.start)
            else:
                date = datetime.date.today()
        except Exception as e:
            print(e)
            return

        delta = datetime.timedelta(days=1)
        end_date = datetime.date.today() + delta
        if recent:
            _LOGGER.info("Populating some recent total_wh values")
        else:
            _LOGGER.info(f"Populating fine history values from {date} to {end_date}")

        if await self.start_inverters():
            while date < end_date:
                if recent:
                    now = datetime.datetime.now()
                    start = datetime.datetime.combine(date, now.time()) - datetime.timedelta(minutes=120)
                else:
                    start = datetime.datetime.combine(date, datetime.time(0, 0)) - datetime.timedelta(minutes=5)
                stop = start + delta

                total = {}
                count = {}
                # if await self.start_inverters():
                inverters = await asyncio.gather(
                    *(
                        inverter.read_fine_history(start=int(start.timestamp()), stop=int(stop.timestamp()))
                        for inverter in self._inverters
                    )
                )
                if None in inverters:
                    _LOGGER.debug(f"At least one inverter failed to respond")
                    continue
                # await self.stop_inverters()

                for inverter in inverters:
                    print('.', end='', flush=True)
                    last_non_null = None
                    for i in range(1, len(inverter)):
                        t = inverter[i]['t']
                        v = inverter[i]['v']

                        # Handle any missing data points
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
        await self.stop_inverters()

    async def populate_irradiance(self, config):
        if not config.sbhistory.irradiance.enable:
            return
        try:
            date = datetime.datetime.fromisoformat(config.sbhistory.irradiance.start)
            site_properties = config.multisma2.site
            solar_properties = config.multisma2.solar_properties

            tzinfo = dateutil.tz.gettz(site_properties.tz)
            siteinfo = LocationInfo(
                name=site_properties.name,
                region=site_properties.region,
                timezone=site_properties.tz,
                latitude=site_properties.latitude,
                longitude=site_properties.longitude,
            )
        except Exception as e:
            print(e)
            return

        try:
            delta = datetime.timedelta(days=1)
            end_date = datetime.datetime.today() + delta
            _LOGGER.info(f"Populating irradiance values from {date.date()} to {end_date.date()}")

            lp_points = []
            while date < end_date:
                print('.', end='', flush=True)
                astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
                dawn = astral['dawn']
                dusk = astral['dusk']
                irradiance = clearsky.global_irradiance(site_properties, solar_properties, dawn, dusk)
                for point in irradiance:
                    t = point['t']
                    v = point['v']
                    # sample: sun,_type=modeled irradiance=800 1556813561098
                    lp = f"sun,_type=modeled irradiance={round(v, 1)} {t}"
                    lp_points.append(lp)
                date += delta

            print()
            self._influx.write_points(lp_points)
        except Exception as e:
            _LOGGER.error(f"An exception occurred in populate_irradiance(): {e}")

    async def populate_seaward(self, config):
        if not config.sbhistory.seaward.enable:
            return
        try:
            site_properties = config.multisma2.site
            tzinfo = dateutil.tz.gettz(site_properties.tz)
            directory = config.sbhistory.seaward.path
        except Exception as e:
            _LOGGER.error(f"An exception occurred in populate_seaward(): {e}")
            return
        seaward.process(directory, tzinfo, self._influx)

    async def populate_patches(self, config):
        try:
            patches = config.sbhistory.patches
        except Exception as e:
            #_LOGGER.info(f"Nothing to do, no patches found")
            return

        for patch_record in config.sbhistory.patches:
            patch = patch_record.get('patch', None)
            time_str = patch.get('time')
            measurement = patch.get('measurement')
            inverter = patch.get('inverter')
            field = patch.get('field')
            value = patch.get('value')

            date = isoparse(time_str)
            ts = int(date.timestamp())

            db_value = None
            db_type = ''
            try:
                db_value = int(value)
                db_type = 'i'
            except Exception as e:
                try:
                    db_value = float(value)
                except Exception as e:
                    _LOGGER.error(f"Unexpected patch value type, expected 'int' or 'float'")
            if db_value is None:
                return
            try:
                _LOGGER.info(f"Patching database value")
                lp_points = []
                # sample: production,_inverter=site today=800.0 1556813561098
                lp = f"{measurement},_inverter={inverter} {field}={db_value}{db_type} {ts}"
                lp_points.append(lp)
                self._influx.write_points(lp_points)
            except Exception as e:
                _LOGGER.error(f"An exception occurred in populate_patches(): {e}")

        return

    async def run(self):
        config = self._config
        await self.populate_production(config)
        await self.populate_irradiance(config)
        await self.populate_seaward(config)
        await self.populate_daily_history(config)
        await self.populate_fine_history(config)
        await self.populate_patches(config)
