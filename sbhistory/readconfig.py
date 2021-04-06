"""Custom YAML file loader with !secrets support."""

import logging
import os
import sys

from dateutil.parser import parse
from pathlib import Path

from collections import OrderedDict
from typing import Dict, List, TextIO, TypeVar, Union

import yaml
from config import config_from_yaml


CONFIG_YAML = "sbhistory.yaml"
SECRET_YAML = "secrets.yaml"

JSON_TYPE = Union[List, Dict, str]  # pylint: disable=invalid-name
DICT_T = TypeVar("DICT_T", bound=Dict)  # pylint: disable=invalid-name

_LOGGER = logging.getLogger("sbhistory")
__SECRET_CACHE: Dict[str, JSON_TYPE] = {}


class ConfigError(Exception):
    """General YAML configurtion file exception."""


class FullLineLoader(yaml.FullLoader):
    """Loader class that keeps track of line numbers."""

    def compose_node(self, parent: yaml.nodes.Node, index: int) -> yaml.nodes.Node:
        """Annotate a node with the first line it was seen."""
        last_line: int = self.line
        node: yaml.nodes.Node = super().compose_node(parent, index)
        node.__line__ = last_line + 1  # type: ignore
        return node


def load_yaml(fname: str) -> JSON_TYPE:
    """Load a YAML file."""
    try:
        with open(fname, encoding="utf-8") as conf_file:
            return parse_yaml(conf_file)
    except UnicodeDecodeError as exc:
        _LOGGER.error("Unable to read file %s: %s", fname, exc)
        raise ConfigError(exc) from exc


def parse_yaml(content: Union[str, TextIO]) -> JSON_TYPE:
    """Load a YAML file."""
    try:
        # If configuration file is empty YAML returns None
        # We convert that to an empty dict
        return yaml.load(content, Loader=FullLineLoader) or OrderedDict()
    except yaml.YAMLError as exc:
        _LOGGER.error(str(exc))
        raise ConfigError(exc) from exc


def _load_secret_yaml(secret_path: str) -> JSON_TYPE:
    """Load the secrets yaml from path."""
    secret_path = os.path.join(secret_path, SECRET_YAML)
    if secret_path in __SECRET_CACHE:
        return __SECRET_CACHE[secret_path]

    _LOGGER.debug("Loading %s", secret_path)
    try:
        secrets = load_yaml(secret_path)
        if not isinstance(secrets, dict):
            raise ConfigError("Secrets is not a dictionary")
        if "logger" in secrets:
            logger = str(secrets["logger"]).lower()
            if logger == "debug":
                _LOGGER.setLevel(logging.DEBUG)
            else:
                _LOGGER.error(
                    "secrets.yaml: 'logger: debug' expected, but 'logger: %s' found",
                    logger,
                )
            del secrets["logger"]
    except FileNotFoundError:
        secrets = {}
    __SECRET_CACHE[secret_path] = secrets
    return secrets


def secret_yaml(loader: FullLineLoader, node: yaml.nodes.Node) -> JSON_TYPE:
    """Load secrets and embed it into the configuration YAML."""
    if os.path.basename(loader.name) == SECRET_YAML:
        _LOGGER.error("secrets.yaml: attempt to load secret from within secrets file")
        raise ConfigError("secrets.yaml: attempt to load secret from within secrets file")

    secret_path = os.path.dirname(loader.name)
    home_path = str(Path.home())
    do_walk = os.path.commonpath([secret_path, home_path]) == home_path

    while True:
        secrets = _load_secret_yaml(secret_path)
        if node.value in secrets:
            _LOGGER.debug(
                "Secret %s retrieved from secrets.yaml in folder %s",
                node.value,
                secret_path,
            )
            return secrets[node.value]

        if not do_walk or (secret_path == home_path):
            break
        secret_path = os.path.dirname(secret_path)

    raise ConfigError(f"Secret '{node.value}' not defined")


def check_daily_history(config):
    options = {}
    sbhistory_key = config.sbhistory
    if not sbhistory_key or "daily_history" not in sbhistory_key.keys():
        _LOGGER.warning("Expected option 'daily_history' in the 'sbhistory' settings")
        return None

    daily_history_key = sbhistory_key.daily_history
    if not daily_history_key or "enable" not in daily_history_key.keys():
        _LOGGER.error("Missing required 'enable' option in 'daily_history' settings")
        return None

    if isinstance(daily_history_key.enable, bool):
        if not daily_history_key.get("enable"):
            _LOGGER.info("'daily_history' option is disabled in the 'sbhistory' settings")
    else:
        _LOGGER.error("'enable' option in 'daily_history' settings must be a boolean")
        return None

    if "start" not in daily_history_key.keys():
        _LOGGER.error("Missing required 'start' option in 'daily_history' settings")
        return None

    try:
        parse(daily_history_key.start)
    except ValueError:
        _LOGGER.error("Incorrect date format in 'daily_history' settings, should be YYYY-MM-DD")
        return None

    options["enable"] = daily_history_key.enable
    options["start"] = daily_history_key.start
    return options


def check_fine_history(config):
    options = {}
    sbhistory_key = config.sbhistory
    if not sbhistory_key or "fine_history" not in sbhistory_key.keys():
        _LOGGER.warning("Expected option 'fine_history' in the 'sbhistory' settings")
        return None

    fine_history_key = sbhistory_key.fine_history
    if not fine_history_key or "enable" not in fine_history_key.keys():
        _LOGGER.error("Missing required 'enable' option in 'fine_history' settings")
        return None

    if isinstance(fine_history_key.enable, bool):
        if not fine_history_key.get("enable"):
            _LOGGER.info("'fine_history' option is disabled in the 'sbhistory' settings")
    else:
        _LOGGER.error("'enable' option in 'fine_history' settings must be a boolean")
        return None

    if "start" not in fine_history_key.keys():
        _LOGGER.error("Missing required 'start' option in 'fine_history' settings")
        return None

    if fine_history_key.start == "recent":
        pass
    else:
        try:
            parse(fine_history_key.start)
        except ValueError:
            _LOGGER.error("Incorrect date format in 'fine_history' settings, should be YYYY-MM-DD")
            return None

    options["enable"] = fine_history_key.enable
    options["start"] = fine_history_key.start
    return options


def check_irradiance(config):
    options = {}
    sbhistory_key = config.sbhistory
    if not sbhistory_key or "irradiance" not in sbhistory_key.keys():
        _LOGGER.warning("Expected option 'irradiance' in the 'sbhistory' settings")
        return None

    irradiance_key = sbhistory_key.irradiance
    if not irradiance_key or "enable" not in irradiance_key.keys():
        _LOGGER.error("Missing required 'enable' option in 'irradiance' settings")
        return None

    if isinstance(irradiance_key.enable, bool):
        if not irradiance_key.enable:
            _LOGGER.info("'irradiance' option is disabled in the 'sbhistory' settings")
    else:
        _LOGGER.error("'enable' option in 'irradiance' settings must be a boolean")
        return None

    options["enable"] = irradiance_key.enable
    if "start" not in irradiance_key.keys():
        _LOGGER.error("Missing required 'start' option in 'irradiance' settings")
        return None

    try:
        parse(irradiance_key.start)
    except ValueError:
        _LOGGER.error("Incorrect date format in 'irradiance' settings, should be YYYY-MM-DD")
        return None

    multisma2_key = config.multisma2
    if not multisma2_key:
        _LOGGER.error("Missing required 'multisma2' section in YAML file settings")
        return None

    keys = ["site", "solar_properties"]
    for key in keys:
        if key not in multisma2_key.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'multisma2' settings")
            return None

    site_key = multisma2_key.site
    keys = ["name", "region", "tz", "latitude", "longitude"]
    for key in keys:
        if key not in site_key.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'multisma2.site' settings")
            return None
        options[key] = site_key.get(key)

    solar_properties_key = multisma2_key.solar_properties
    keys = ["tilt", "area"]
    for key in keys:
        if key not in solar_properties_key.keys():
            _LOGGER.error(f"Missing required '{key}' option in 'multisma2.solar_properties' settings")
            return None
        options[key] = solar_properties_key.get(key)

    return options


def check_csv_file(config):
    options = {}
    sbhistory_key = config.sbhistory
    if not sbhistory_key or "csv_file" not in sbhistory_key.keys():
        _LOGGER.warning("Expected option 'csv_file' in the 'sbhistory' settings")
        return None

    csv_file_key = sbhistory_key.csv_file
    if not csv_file_key or "enable" not in csv_file_key.keys():
        _LOGGER.error("Missing required 'enable' option in 'csv_file' settings")
        return None

    if isinstance(csv_file_key.enable, bool):
        if not csv_file_key.enable:
            _LOGGER.info("'csv_file' option is disabled in the 'sbhistory' settings")
    else:
        _LOGGER.error("'enable' option in 'irradiance' settings must be a boolean")
        return None

    options["enable"] = csv_file_key.enable
    if "path" not in csv_file_key.keys():
        _LOGGER.error("Missing required 'path' option in 'csv_file' settings")
        return None

    options["path"] = csv_file_key.path
    return options


def read_config():
    try:
        yaml.FullLoader.add_constructor("!secret", secret_yaml)
        yaml_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_YAML)
        config = config_from_yaml(data=yaml_file, read_from_file=True)

        irradiance_options = check_irradiance(config)
        daily_history_options = check_daily_history(config)
        fine_history_options = check_fine_history(config)
        csv_options = check_csv_file(config)
        if None in [irradiance_options, daily_history_options, fine_history_options, csv_options]:
            return None
        return config

    except Exception as e:
        print(e)
        return None


if __name__ == "__main__":
    # make sure we can run
    if sys.version_info[0] >= 3 and sys.version_info[1] >= 8:
        config = read_config()
    else:
        print("python 3.8 or better required")
