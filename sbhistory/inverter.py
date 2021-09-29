"""Code to interface with the SMA inverters and return the results."""

import logging
import sma

from exceptions import SmaException


_LOGGER = logging.getLogger('sbhistory')


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
        try:
            self._sma = sma.SMA(session=self._session, url=self._url, password=self._password, group=self._group)
        except SmaException as e:
            _LOGGER.debug(f"Inverter error with '{self._url}': '{e.name}'")
            return False

        try:
            await self._sma.new_session()
            print(f"Connected to SMA inverter {self._name} at {self._url}")
            return True
        except SmaException as e:
            _LOGGER.debug(f"{self._name}, login failed: {e}")
            return False

    async def close(self):
        """Log out of the inverter."""
        if self._sma:
            await self._sma.close_session()
            self._sma = None

    async def read_history(self, start, stop):
        """Read the baseline inverter production."""
        try:
            history = await self._sma.read_history(start, stop)
            history.insert(0, {'inverter': self._name})
            return history
        except SmaException as e:
            _LOGGER.error(f"Inverter '{self._url}' read_history(): '{e.name}'")
            return None

    async def read_fine_history(self, start, stop):
        """Read the baseline inverter production."""
        try:
            history = await self._sma.read_fine_history(start, stop)
            history.insert(0, {'inverter': self._name})
            return history
        except SmaException as e:
            _LOGGER.error(f"Inverter '{self._url}' read_history(): '{e.name}'")
            return None
