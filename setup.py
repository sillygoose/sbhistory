#!/usr/bin/env python

"""sbhistory setup."""
from pathlib import Path
from setuptools import setup

VERSION = "0.5.6"
URL = "https://github.com/sillygoose/sbhistory"

setup(
    name="sbhistory",
    version=VERSION,
    description="Download SMA Sunny Boy WebConnect history to InfluxDB",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url=URL,
    download_url="{}/tarball/{}".format(URL, VERSION),
    author="Rick Naro",
    author_email="sillygoose@me.com",
    license="MIT",
    packages=["sbhistory"],
    setup_requires=[
        "flake8",
    ],
    install_requires=[
        "aiohttp",
        "asyncio",
        "jmespath",
        "influxdb-client",
        "paho-mqtt",
        "astral",
        "python-dateutil",
        "python-configuration",
    ],
    zip_safe=True,
)
