#!/usr/bin/env python

"""sbhistory setup."""
from pathlib import Path
from setuptools import setup

VERSION = "0.7.5"
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
    setup_requires=[
        "flake8",
    ],
    install_requires=[
        "aiohttp",
        "asyncio",
        "async_timeout",
        "csv",
        "jmespath",
        "influxdb-client",
        "paho-mqtt",
        "astral",
        "pysolar",
        "python-dateutil",
        "python-configuration",
        "pyyaml",
    ],
    zip_safe=True,
)
