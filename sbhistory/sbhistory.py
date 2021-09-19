"""Code to interface with the SMA inverters and return the results."""
# Robust initialization and shutdown code courtesy of
# https://github.com/wbenny/python-graceful-shutdown.git

import logging
import sys
import os

import asyncio
import aiohttp
from delayedints import DelayedKeyboardInterrupt

from pvsite import Site
import version
import logfiles
from readconfig import read_config

from exceptions import FailedInitialization


_LOGGER = logging.getLogger("sbhistory")


class Multisma2:
    class NormalCompletion(Exception):
        pass

    class FailedInitialization(Exception):
        pass

    def __init__(self, config):
        self._config = config
        self._loop = asyncio.new_event_loop()
        self._session = None
        self._site = None

    def run(self):
        try:
            try:
                with DelayedKeyboardInterrupt():
                    self._start()
            except KeyboardInterrupt:
                _LOGGER.critical("Received KeyboardInterrupt during startup")
                raise

            self._wait()
            raise Multisma2.NormalCompletion

        except (KeyboardInterrupt, Multisma2.NormalCompletion, Multisma2.FailedInitialization):
            # The _stop() is also shielded from termination.
            try:
                with DelayedKeyboardInterrupt():
                    self._stop()
            except KeyboardInterrupt:
                _LOGGER.critical("Received KeyboardInterrupt during shutdown")

    async def _astart(self):
        self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        self._site = Site(self._session, self._config)
        result = await self._site.start()
        if not result:
            raise Multisma2.FailedInitialization

    async def _astop(self):
        _LOGGER.info("Closing sbhistory application")
        if self._site:
            await self._site.stop()
        if self._session:
            await self._session.close()

    async def _await(self):
        await self._site.run()

    def _start(self):
        self._loop.run_until_complete(self._astart())

    def _wait(self):
        self._loop.run_until_complete(self._await())

    def _stop(self):
        self._loop.run_until_complete(self._astop())


def main():
    """Set up and start sbhistory."""

    try:
        config = read_config(checking=False)
    except FailedInitialization as e:
        print(f"{e}")
        return

    logfiles.start(config)
    _LOGGER.info(f"multisma2 inverter collection utility {version.get_version()}, PID is {os.getpid()}")

    try:
        multisma2 = Multisma2(read_config(checking=True))
        multisma2.run()
    except FailedInitialization as e:
        _LOGGER.error(f"{e}")
    except Exception as e:
        _LOGGER.error(f"Unexpected exception: {e}")


if __name__ == "__main__":
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 9:
        main()
    else:
        print("python 3.9 or better required")
