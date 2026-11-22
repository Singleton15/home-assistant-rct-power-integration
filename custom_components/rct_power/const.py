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
CONF_CONFIG_ENTRY_ID: Final = "config_entry_id"
CONF_HOSTNAME: Final = "hostname"
CONF_RESTART_SERIAL_NUMBER: Final = "restart_serial_number"

# writing settings to the inverter, off by default
CONF_ALLOW_WRITES: Final = "allow_writes"
CONF_GOD_MODE: Final = "god_mode"
CONF_GOD_MODE_PASSWORD: Final = "god_mode_password"
CONF_SERVICE_PASSWORD: Final = "service_password"
CONF_WRITE_ACCESS: Final = "write_access"


class WriteAccess(StrEnum):
    NONE = "none"
    SERVICE = "service"
    FACTORY = "factory"


DEFAULT_ENTITY_PREFIX: Final = "RCT Power Storage"
DEFAULT_PORT: Final = 8899
RESTART_WAIT_SECONDS: Final = 30
SERVICE_RESTART_COMMUNICATION: Final = "restart_communication"


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
