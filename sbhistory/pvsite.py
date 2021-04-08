"""Code to interface with the SMA inverters and return state or history."""

import os
import asyncio
import logging
import dateutil
import datetime

import clearsky
import csv

# from pprint import pprint

from inverter import Inverter
from influx import InfluxDB

from astral.sun import sun
from astral import LocationInfo


_LOGGER = logging.getLogger("sbhistory")


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
            inv = inverter.get("inverter", None)
            self._inverters.append(Inverter(inv["name"], inv["url"], inv["user"], inv["password"], session))

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
        results = await asyncio.gather(*(inverter.initialize() for inverter in self._inverters))
        return False not in results

    async def stop_inverters(self):
        await asyncio.gather(*(inverter.close() for inverter in self._inverters))

    # daily totals, day increments
    async def populate_daily_history(self, config):
        if not config.sbhistory.daily_history.enable:
            return
        try:
            start = datetime.datetime.fromisoformat(config.sbhistory.daily_history.start)
        except Exception as e:
            print(e)
            return

        now = datetime.datetime.now()
        td = datetime.timedelta(hours=1)
        od = datetime.timedelta(days=1)

        start = start - td
        stop = datetime.datetime(year=now.year, month=now.month, day=now.day)
        stop += od
        _LOGGER.info(f"Populating daily history values from {start.date()} to {stop.date()}")

        await self.start_inverters()
        inverters = await asyncio.gather(
            *(
                inverter.read_history(start=int(start.timestamp()), stop=int(stop.timestamp()))
                for inverter in self._inverters
            )
        )
        await self.stop_inverters()

        for inverter in inverters:
            t = inverter[1]["t"]
            dt = datetime.datetime.fromtimestamp(t)
            date = start.date()
            end_date = datetime.date(year=dt.year, month=dt.month, day=dt.day)
            delta = datetime.timedelta(days=1)

            # add missing dates as 0 Wh values
            while date < end_date:
                print(".", end="", flush=True)
                newtime = datetime.datetime.combine(date, datetime.time(0, 0))
                t = int(newtime.timestamp())
                inverter.append({"t": t, "v": 0})
                date += delta

            # Sort the entries by date
            try:
                inv0 = inverter
                inv_name = inv0.pop(0)
                inv0.sort(key=lambda item: item.get("t"))
                inv0.insert(0, inv_name)
            except Exception as e:
                print(e)

            # normalize times to midnight
            midnight = datetime.time()
            for i in range(1, len(inverter)):
                t = inverter[i]["t"]
                v = inverter[i]["v"]
                dt = datetime.datetime.fromtimestamp(t)
                if dt.hour > 12:
                    new_day = dt.date() + datetime.timedelta(days=1)
                    new_dt = datetime.datetime.combine(new_day, midnight)
                    inverter[i]["t"] = int(new_dt.timestamp())
                else:
                    new_day = dt.date()
                    new_dt = datetime.datetime.combine(new_day, midnight)
                    inverter[i]["t"] = int(new_dt.timestamp())

                inverter[i]["midnight"] = "yes"

        # Calculate the total
        total = {}
        count = {}
        for inverter in inverters:
            last_non_null = None
            for i in range(1, len(inverter)):
                print(".", end="", flush=True)
                t = inverter[i]["t"]
                v = inverter[i]["v"]
                if v is None:
                    if not last_non_null:
                        continue
                    v = last_non_null
                    inverter[i]["v"] = last_non_null

                total[t] = v + total.get(t, 0)
                count[t] = count.get(t, 0) + 1
                last_non_null = v

        # Site output if multiple inverters
        if len(inverters) > 1:
            site_total = []
            for t, v in total.items():
                if count[t] == len(inverters):
                    site_total.append({"t": t, "v": v, "midnight": "yes"})
                    # print(f"\nmidnight detected on {t} with meter {v}")
            site_total.insert(0, {"inverter": "site"})
            inverters.append(site_total)

        self._influx.write_history(inverters, "production/midnight")
        print()

    # fine production, 5 minute increments
    async def populate_fine_history(self, config):
        if not config.sbhistory.fine_history.enable:
            return
        recent = config.sbhistory.fine_history.start.lower() == "recent"
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

        await self.start_inverters()
        while date < end_date:
            if recent:
                now = datetime.datetime.now()
                start = datetime.datetime.combine(date, now.time()) - datetime.timedelta(minutes=120)
            else:
                start = datetime.datetime.combine(date, datetime.time(0, 0)) - datetime.timedelta(minutes=5)
            stop = start + delta

            total = {}
            count = {}
            # await self.start_inverters()
            inverters = await asyncio.gather(
                *(
                    inverter.read_fine_history(start=int(start.timestamp()), stop=int(stop.timestamp()))
                    for inverter in self._inverters
                )
            )
            # await self.stop_inverters()

            for inverter in inverters:
                print(".", end="", flush=True)
                last_non_null = None
                for i in range(1, len(inverter)):
                    t = inverter[i]["t"]
                    v = inverter[i]["v"]

                    # Check for midnight timestamp
                    dt = datetime.datetime.fromtimestamp(t)
                    if dt.hour == 0 and dt.minute == 0:
                        inverter[i]["midnight"] = "no"

                    # Handle any missing data points
                    if v is None:
                        if not last_non_null:
                            continue
                        v = last_non_null
                        inverter[i]["v"] = last_non_null
                    total[t] = v + total.get(t, 0)
                    count[t] = count.get(t, 0) + 1
                    last_non_null = v

            # Site output if multiple inverters
            if len(inverters) > 1:
                site_total = []
                for t, v in total.items():
                    if count[t] == len(inverters):
                        # Check for midnight timestamp
                        dt = datetime.datetime.fromtimestamp(t)
                        midnight = "yes" if dt.hour == 0 and dt.minute == 0 else "no"
                        if midnight == "yes":
                            # print(f"\nmidnight detected on {t} with meter {v}")
                            midnight = "yes"
                        site_total.append({"t": t, "v": v, "midnight": midnight})
                site_total.insert(0, {"inverter": "site"})
                inverters.append(site_total)

            self._influx.write_history(inverters, "production/total_wh")
            date += delta

        await self.stop_inverters()
        print()

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
                print(".", end="", flush=True)
                astral = sun(date=date, observer=siteinfo.observer, tzinfo=tzinfo)
                dawn = astral["dawn"]
                dusk = astral["dusk"]
                irradiance = clearsky.global_irradiance(site_properties, solar_properties, dawn, dusk)
                for point in irradiance:
                    t = point["t"]
                    v = point["v"]
                    # sample: sun,_type=modeled irradiance=800 1556813561098
                    lp = f"sun,_type=modeled irradiance={round(v, 1)} {t}"
                    lp_points.append(lp)
                date += delta

            self._influx.write_points(lp_points)
            print()
        except Exception as e:
            _LOGGER.error(f"An exception occurred in populate_irradiance(): {e}")

    async def populate_csv_file(self, config):
        if not config.sbhistory.csv_file.enable:
            return
        try:
            site_properties = config.multisma2.site
            tzinfo = dateutil.tz.gettz(site_properties.tz)
            directory = config.sbhistory.csv_file.path
        except Exception as e:
            print(e)
            return
        try:
            for entry in os.scandir(directory):
                if not entry.is_file():
                    continue
                if not entry.path.endswith(".csv"):
                    continue

                csv_indices = {}
                lp_points = []
                with open(entry.path, newline="") as csvfile:
                    _LOGGER.info(f"Processing file {entry.name}")
                    reader = csv.reader(csvfile, delimiter=",", quotechar="|")
                    for row in reader:
                        if reader.line_num == 1:
                            to_find = ["Date", "Time", "Tpv", "Ta", "Irr", "Irr Unit", "Temp Unit"]
                            for heading in to_find:
                                index = row.index(heading)
                                csv_indices[heading] = index
                        else:
                            irradiance = row[csv_indices["Irr"]]
                            if irradiance.startswith("<"):
                                irradiance = "0"
                            irradiance = float(irradiance)

                            date = row[csv_indices["Date"]]
                            date_dmy = date.split(".")
                            d = datetime.date(
                                year=int("20" + date_dmy[2]), month=int(date_dmy[1]), day=int(date_dmy[0])
                            )

                            time = row[csv_indices["Time"]]
                            time_hms = time.split(":")
                            t = datetime.time(hour=int(time_hms[0]), minute=int(time_hms[1]))
                            dt = datetime.datetime.combine(date=d, time=t, tzinfo=tzinfo)
                            ts = int(dt.timestamp())

                            tpv = row[csv_indices["Tpv"]]
                            if tpv == "ERR":
                                tpv = None
                            ta = row[csv_indices["Ta"]]
                            if ta == "ERR":
                                ta = None

                            # sample: sun,_type=measured irradiance=800 1556813561098
                            lp_points.append(f"sun,_type=measured irradiance={irradiance} {ts}")
                            if tpv:
                                # sample: sun,_type=working temperature=10 1556813561098
                                lp_points.append(f"sun,_type=working temperature={float(ta)} {ts}")
                            if ta:
                                # sample: sun,_type=ambient temperature=8 1556813561098
                                lp_points.append(f"sun,_type=ambient temperature={float(tpv)} {ts}")
                            print(".", end="", flush=True)

                    self._influx.write_points(lp_points)
                    print()

        except Exception as e:
            print()
            _LOGGER.error(f"An error occurred in {entry.name}, line {reader.line_num}: {e}")
        print()

    async def run(self):
        config = self._config
        await self.populate_irradiance(config)
        await self.populate_csv_file(config)
        await self.populate_daily_history(config)
        await self.populate_fine_history(config)
