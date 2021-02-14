"""Code to interface with the SMA inverters and return the results."""

import logging
from pprint import pprint

import sma


logger = logging.getLogger('sbhistory')


class Inverter:
    """Class to encapsulate a single inverter."""

    def __init__(self, name, url, group, password, session):
        """Setup an Inverter class instance."""
        self._name = name
        self._url = url
        self._password = password
        self._group = group
        self._session = session
        self._sma = None

    async def initialize(self):
        """Setup inverter for data collection."""
        # SMA class object for access to inverters
        self._sma = sma.SMA(session=self._session, url=self._url, password=self._password, group=self._group)
        await self._sma.new_session()
        if self._sma.sma_sid is None:
            logger.info("%s - no session ID", self._name)
            return False
        return True

    async def close(self):
        """Log out of the inverter."""
        if self._sma:
            await self._sma.close_session()
            self._sma = None

    async def read_history(self, start, stop):
        """Read the baseline inverter production."""
        history = await self._sma.read_history(start, stop)
        history.insert(0, {'inverter': self._name})
        return history

    async def read_fine_history(self, start, stop):
        """Read the baseline inverter production."""
        history = await self._sma.read_fine_history(start, stop)
        history.insert(0, {'inverter': self._name})
        return history