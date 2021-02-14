#!/usr/bin/env python

"""sbhist library setup."""
from pathlib import Path
from setuptools import setup

VERSION = "0.5.4"
URL = "https://github.com/sillygoose/sbhist"

setup(
    name="sbhist",
    version=VERSION,
    description="Download SMA Sunny Boy WebConnect history to InfluxDB",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url=URL,
    download_url="{}/tarball/{}".format(URL, VERSION),
    author="Rick Naro",
    author_email="sillygoose@me.com",
    license="MIT",
    packages=["sbhist"],
    # packages=find_packages(include=['sbhist', '.*'])
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
        "pvlib",
        "tables",
    ],
    zip_safe=True,
)
