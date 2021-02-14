"""Code to interface with the SMA inverters and return the results."""
# Robust initialization and shutdown code courtesy of 
# https://github.com/wbenny/python-graceful-shutdown.git

import logging
import sys

import asyncio
import aiohttp
from delayedints import DelayedKeyboardInterrupt

from pvsite import Site
import version
import logfiles


logger = logging.getLogger('sbhistory')


class Multisma2:
    class NormalCompletion(Exception):
        pass
    class FailedInitialization(Exception):
        pass

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._session = None
        self._site = None

    def run(self):
        try:
            # Shield _start() from termination.
            try:
                with DelayedKeyboardInterrupt():
                    self._start()
            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt during startup")
                raise

            # multisma2 is running, wait for completion.
            self._wait()
            raise Multisma2.NormalCompletion

        except (KeyboardInterrupt, Multisma2.NormalCompletion, Multisma2.FailedInitialization):
            # The _stop() is also shielded from termination.
            try:
                with DelayedKeyboardInterrupt():
                    self._stop()
            except KeyboardInterrupt:
                logger.info("Received KeyboardInterrupt during shutdown")

    async def _astart(self):
        logfiles.create_application_log(logger)
        logger.info(f"multisma2 inverter production history utility {version.get_version()}")

        self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        self._site = Site(self._session)
        result = await self._site.start()
        if not result: raise Multisma2.FailedInitialization

    async def _astop(self):
        await self._site.stop()
        await self._session.close()
        logfiles.stop()

    async def _await(self):
        await self._site.run()

    def _start(self):
        self._loop.run_until_complete(self._astart())

    def _wait(self):
        self._loop.run_until_complete(self._await())

    def _stop(self):
        self._loop.run_until_complete(self._astop())


def main():
    """Set up and start multisma2."""
    multisma2 = Multisma2()
    multisma2.run()


if __name__ == "__main__":
    # make sure we can run multisma2
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
        main()
    else:
        print("python 3.7 or better required")
