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
from config import config_from_yaml


logger = logging.getLogger("sbhistory")


def buildYAMLExceptionString(exception, file="sbhistory"):
    e = exception
    try:
        type = ""
        file = file
        line = 0
        column = 0
        info = ""

        if e.args[0]:
            type = e.args[0]
            type += " "

        if e.args[1]:
            file = os.path.basename(e.args[1].name)
            line = e.args[1].line
            column = e.args[1].column

        if e.args[2]:
            info = os.path.basename(e.args[2])

        if e.args[3]:
            file = os.path.basename(e.args[3].name)
            line = e.args[3].line
            column = e.args[3].column

        errmsg = f"YAML file error {type}in {file}:{line}, column {column}: {info}"

    except Exception:
        errmsg = "YAML file error and no idea how it is encoded."

    return errmsg


class Multisma2:
    class NormalCompletion(Exception):
        pass

    class FailedInitialization(Exception):
        pass

    def __init__(self):
        self._loop = asyncio.new_event_loop()
        self._session = None
        self._site = None
        try:
            yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sbhistory.yaml")
            self._config = config_from_yaml(data=yaml_file, read_from_file=True)
        except Exception as e:
            error_message = buildYAMLExceptionString(exception=e, file="sbhistory.yaml")
            print(error_message)
            raise Multisma2.FailedInitialization

    def run(self):
        try:
            try:
                with DelayedKeyboardInterrupt():
                    self._start()
            except KeyboardInterrupt:
                logger.critical("Received KeyboardInterrupt during startup")
                raise

            self._wait()
            raise Multisma2.NormalCompletion

        except (KeyboardInterrupt, Multisma2.NormalCompletion, Multisma2.FailedInitialization):
            # The _stop() is also shielded from termination.
            try:
                with DelayedKeyboardInterrupt():
                    self._stop()
            except KeyboardInterrupt:
                logger.critical("Received KeyboardInterrupt during shutdown")

    async def _astart(self):
        logfiles.create_application_log(logger, self._config)
        logger.info(f"multisma2 inverter production history utility {version.get_version()}")

        self._session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False))
        self._site = Site(self._session, self._config)
        result = await self._site.start()
        if not result:
            raise Multisma2.FailedInitialization

    async def _astop(self):
        if self._site:
            await self._site.stop()
        if self._session:
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
    try:
        multisma2 = Multisma2()
        multisma2.run()
    except Multisma2.FailedInitialization:
        pass
    except Exception as e:
        print(f"Unexpected exception: {e}")


if __name__ == "__main__":
    # make sure we can run multisma2
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 7:
        main()
    else:
        print("python 3.7 or better required")
