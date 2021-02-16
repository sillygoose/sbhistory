"""Module handling the application and production log files."""

import os
import sys
import logging
from datetime import datetime


logger = logging.getLogger('sbhistory')

LOGGING_VAR = {}


#
# Public
#

def stop():
    """Closes open log files."""
    if "datalogging" in LOGGING_VAR:
        handle = LOGGING_VAR.pop("datalogging")
        logger.info("Closing production history log %s", LOGGING_VAR["filename"])
        handle.close()


def create_application_log(app_logger, config):
    """Create the application log."""
    now = datetime.now()
    filename = os.path.expanduser(
        config.sbhistory.log.file + "_" + now.strftime("%Y-%m-%d") + ".log"
    )

    # Create the directory if needed
    filename_parts = os.path.split(filename)
    if filename_parts[0] and not os.path.isdir(filename_parts[0]):
        os.mkdir(filename_parts[0])
    filename = os.path.abspath(filename)
    logging.basicConfig(
        filename=filename,
        filemode="w+",
        format=config.sbhistory.log.format,
        level=logging.INFO,
    )

    # Add some console output for anyone watching
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(config.sbhistory.log.format))
    app_logger.addHandler(console_handler)
    app_logger.setLevel(logging.INFO)

    # First entry
    app_logger.info("Created application log %s", filename)
