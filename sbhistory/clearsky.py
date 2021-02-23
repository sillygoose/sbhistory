"""Module to estimate the clearsky irradiance for a specific site."""

import logging
import datetime
from dateutil import tz
import math

import os
from config import config_from_yaml

from pprint import pprint

from pysolar.solar import get_altitude, get_azimuth
from pysolar.radiation import get_radiation_direct

from astral.sun import sun
from astral import LocationInfo


logger = logging.getLogger('sbhistory')


def current_global_irradiance(site_properties, solar_properties, timestamp):
    """Calculate the clear-sky POA (plane of array) irradiance for a specific time (seconds timestamp)."""
    dt = datetime.datetime.fromtimestamp(timestamp=timestamp, tz=tz.gettz(site_properties.tz))
    n = dt.timetuple().tm_yday

    sigma = math.radians(solar_properties.tilt)
    rho = solar_properties.get('rho', 0.0)

    C = 0.095 + 0.04 * math.sin(math.radians((n - 100) / 365))
    sin_sigma = math.sin(sigma)
    cos_sigma = math.cos(sigma)

    altitude = get_altitude(latitude_deg=site_properties.latitude, longitude_deg=site_properties.longitude, when=dt)
    beta = math.radians(altitude)
    sin_beta = math.sin(beta)
    cos_beta = math.cos(beta)

    azimuth = get_azimuth(latitude_deg=site_properties.latitude, longitude_deg=site_properties.longitude, when=dt)
    phi_s = math.radians(180 - azimuth)
    phi_c = math.radians(180 - solar_properties.azimuth)
    phi = phi_s - phi_c
    cos_phi = math.cos(phi)

    cos_theta = cos_beta * cos_phi * sin_sigma + sin_beta * cos_sigma
    ib = get_radiation_direct(when=dt, altitude_deg=altitude)
    ibc = ib * cos_theta
    idc = C * ib * (1 + cos_sigma) / 2
    irc = rho * ib * (sin_beta + C) * ((1 - cos_sigma) / 2)
    igc = ibc + idc + irc
    return igc


def global_irradiance(site_properties, solar_properties, dawn, dusk):
    """Calculate the clear-sky POA (plane of array) irradiance for a day."""
    MINUTES = 5
    irradiance = []
    tzinfo = tz.gettz(site_properties.tz)
    dusk += datetime.timedelta(minutes=MINUTES)
    dt = datetime.datetime(year=dawn.year, month=dawn.month, day=dawn.day, hour=dawn.hour, minute=int(int(dawn.minute / 10) * 10), tzinfo=tzinfo)
    stop = datetime.datetime(year=dusk.year, month=dusk.month, day=dusk.day, hour=dusk.hour, minute=int(int(dusk.minute / 10) * 10), tzinfo=tzinfo)
    while dt < stop:
        timestamp = int(dt.timestamp())
        igc = current_global_irradiance(site_properties, solar_properties, timestamp)
        irradiance.append({'t': timestamp, 'v': igc})
        dt += datetime.timedelta(minutes=MINUTES)
    return irradiance


if __name__ == "__main__":
    yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sbhistory.yaml')
    config = config_from_yaml(data=yaml_file, read_from_file=True)
    site_properties = config.multisma2.site
    solar_properties = config.multisma2.solar_properties

    timestamp = 1614010000
    igc = current_global_irradiance(site_properties, solar_properties, timestamp)
    print(f"{datetime.datetime.fromtimestamp(timestamp)}   {igc:.0f}")

    tzinfo = tz.gettz(site_properties.tz)
    siteinfo = LocationInfo(name=site_properties.name, region=site_properties.region, timezone=site_properties.tz, latitude=site_properties.latitude, longitude=site_properties.longitude)
    astral = sun(date=datetime.datetime.now(), observer=siteinfo.observer, tzinfo=tzinfo)
    dawn = astral['dawn']
    dusk = astral['dusk']
    igc_results = global_irradiance(site_properties, solar_properties, dawn, dusk)
    pprint(f"{igc_results}")
