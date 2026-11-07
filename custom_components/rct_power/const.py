from __future__ import annotations

import logging
from enum import Enum, IntEnum, StrEnum
from typing import Final

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "rct_power"
ICON: Final = "mdi:solar-power"
PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

NAME: Final = "RCT Power"
INVERTER_MODEL: Final = "RCT Power Storage"
BATTERY_MODEL: Final = "RCT Power Battery"
BATTERY_MODULE_COUNT: Final = 6


class EntityUpdatePriority(Enum):
    VERY_FREQUENT = 0
    FREQUENT = 1
    INFREQUENT = 2
    STATIC = 3


# Configuration, options, defaults
CONF_ENTITY_PREFIX: Final = "entity_prefix"
CONF_HOSTNAME: Final = "hostname"

# writing settings to the inverter, off by default
CONF_ALLOW_WRITES: Final = "allow_writes"
CONF_ALLOW_BATTERY_WRITES: Final = "allow_battery_writes"

DEFAULT_ENTITY_PREFIX: Final = "RCT Power Storage"
DEFAULT_PORT: Final = 8899


class ConfScanInterval(StrEnum):
    VERY_FREQUENT = "very_frequent_scan_interval"
    FREQUENT = "frequent_scan_interval"
    INFREQUENT = "infrequent_scan_interval"
    STATIC = "static_scan_interval"


class ScanIntervalDefault(IntEnum):
    VERY_FREQUENT = 30
    FREQUENT = 30
    INFREQUENT = 60 * 3
    STATIC = 60 * 60
