"""Module handling the application and production log files/"""

import os
import sys
import logging
from datetime import datetime
from config import config_from_yaml

logger = logging.getLogger('sbhistory')

LOGGING_VAR = {}


#
# Public
#

def stop():
    """Closes open log files."""
    if "datalogging" in LOGGING_VAR:
        handle = LOGGING_VAR.pop("datalogging")
        logger.info("Closing production data log %s", LOGGING_VAR["filename"])
        handle.close()


def create_application_log(app_logger):
    """Create the application log."""
    yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sbhistory.yaml')
    cfg = config_from_yaml(data=yaml_file, read_from_file=True)

    now = datetime.now()
    filename = os.path.expanduser(
        cfg.log.file + "_" + now.strftime("%Y-%m-%d") + ".log"
    )

    # Create the directory if needed
    filename_parts = os.path.split(filename)
    if filename_parts[0] and not os.path.isdir(filename_parts[0]):
        os.mkdir(filename_parts[0])
    filename = os.path.abspath(filename)
    logging_level = logging.ERROR
    if cfg.log.level == 'Info':
        logging_level = logging.INFO
    elif cfg.log.level == 'Warn':
        logging_level = logging.WARN
    logging.basicConfig(
        filename=filename,
        filemode="w+",
        format=cfg.log.format,
        level=logging_level,
    )

    # Add some console output for anyone watching
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(cfg.log.format))
    app_logger.addHandler(console_handler)
    app_logger.setLevel(logging.INFO)

    # First entry
    app_logger.info("Created application log %s", filename)
