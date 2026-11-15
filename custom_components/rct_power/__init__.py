"""
Custom integration to integrate RCT Power with Home Assistant.

For more details about this integration, please refer to
https://github.com/Singleton15/home-assistant-rct-power-integration
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, cast

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.hass_dict import HassEntryKey

from .const import (
    CONF_CONFIG_ENTRY_ID,
    CONF_GOD_MODE,
    CONF_HOSTNAME,
    CONF_RESTART_SERIAL_NUMBER,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    RESTART_WAIT_SECONDS,
    SERVICE_RESTART_COMMUNICATION,
    ConfScanInterval,
    EntityUpdatePriority,
    ScanIntervalDefault,
)
from .coordinator import RctPowerDataUpdateCoordinator
from .lib.api import RctPowerApiClient
from .lib.entities import all_entity_descriptions
from .lib.entity import RctPowerEntityDescription, resolve_object_infos
from .models import RctConfEntryData, RctConfEntryOptions

RCT_DATA_KEY: HassEntryKey[RctData] = HassEntryKey(DOMAIN)

type RctConfigEntry = ConfigEntry[RctData]


@dataclass
class RctData:
    update_coordinators: dict[EntityUpdatePriority, RctPowerDataUpdateCoordinator]


def object_ids_for_update_priority(
    update_priority: EntityUpdatePriority,
    entry_id: str,
    entity_enabled_by_unique_id: dict[str, bool],
    god_mode_enabled: bool = False,
) -> list[int]:
    """Collect object IDs needed by enabled entities for an update priority."""
    return list(
        {
            object_info.object_id
            for entity_description in all_entity_descriptions
            if entity_description.update_priority == update_priority
            and (god_mode_enabled or not entity_description.requires_god_mode)
            and entity_enabled_by_unique_id.get(
                _entity_unique_id(entry_id, entity_description),
                entity_description.entity_registry_enabled_default is not False,
            )
            for object_info in resolve_object_infos(entity_description)
        }
    )


def _entity_unique_id(
    entry_id: str, entity_description: RctPowerEntityDescription
) -> str:
    if entity_description.unique_id:
        return f"{entry_id}-{entity_description.unique_id}"

    object_ids = [
        str(object_info.object_id)
        for object_info in resolve_object_infos(entity_description)
    ]
    return "-".join([entry_id, *object_ids])


async def _async_send_restart_request(
    hass: HomeAssistant, entry: RctConfigEntry, serial_number: str
) -> None:
    session = async_get_clientsession(hass)
    async with session.get(
        f"http://{entry.data[CONF_HOSTNAME]}/EN/restart.html",
        headers={"Authorization": aiohttp.encode_basic_auth("admin", serial_number)},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as response:
        response.raise_for_status()
        body = await response.read()
        if b"rebooting" not in body.lower():
            raise HomeAssistantError(
                "The inverter response did not confirm that it is rebooting"
            )
        LOGGER.info(
            "RCT Power inverter %s confirmed that it is rebooting",
            entry.unique_id or entry.entry_id,
        )


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register integration-wide services."""

    async def async_restart_communication(call: ServiceCall) -> None:
        entry_id = call.data[CONF_CONFIG_ENTRY_ID]
        entry = cast(
            RctConfigEntry | None, hass.config_entries.async_get_entry(entry_id)
        )
        if entry is None or entry.domain != DOMAIN:
            raise HomeAssistantError(f"Unknown RCT Power config entry: {entry_id}")
        options = cast(RctConfEntryOptions, entry.options)
        serial_number = options.get(CONF_RESTART_SERIAL_NUMBER) or entry.unique_id
        if not serial_number:
            raise HomeAssistantError(
                "Configure the inverter serial number in the RCT Power options "
                "before restarting communication"
            )

        restart_locks: dict[str, asyncio.Lock] = hass.data.setdefault(
            f"{DOMAIN}_restart_locks", {}
        )
        lock = restart_locks.setdefault(entry_id, asyncio.Lock())
        async with lock:
            if entry.state is not ConfigEntryState.LOADED:
                raise HomeAssistantError(
                    f"RCT Power config entry {entry_id} is not loaded"
                )
            if not await hass.config_entries.async_unload(entry_id):
                raise HomeAssistantError(
                    f"Failed to stop communication for RCT Power config entry {entry_id}"
                )

            try:
                await _async_send_restart_request(hass, entry, serial_number)
            except (aiohttp.ClientError, TimeoutError) as err:
                raise HomeAssistantError(
                    f"Failed to restart communication for RCT Power config entry {entry_id}"
                ) from err
            finally:
                await asyncio.sleep(RESTART_WAIT_SECONDS)
                if not await hass.config_entries.async_setup(entry_id):
                    raise HomeAssistantError(
                        f"Failed to resume communication for RCT Power config entry {entry_id}"
                    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESTART_COMMUNICATION,
        async_restart_communication,
        schema=vol.Schema({vol.Required(CONF_CONFIG_ENTRY_ID): cv.string}),
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RctConfigEntry) -> bool:
    """Set up this integration using UI."""
    data = cast(RctConfEntryData, entry.data)
    options = cast(RctConfEntryOptions, entry.options)

    client = RctPowerApiClient(
        hostname=data[CONF_HOSTNAME],
        port=data[CONF_PORT],
    )
    entity_registry = er.async_get(hass)
    entity_enabled_by_unique_id = {
        entity_entry.unique_id: entity_entry.disabled_by is None
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
    }
    god_mode_enabled = options.get(CONF_GOD_MODE, False)

    very_frequent_update_coordinator = RctPowerDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        name_suffix="very_frequent",
        object_ids=object_ids_for_update_priority(
            EntityUpdatePriority.VERY_FREQUENT,
            entry.entry_id,
            entity_enabled_by_unique_id,
            god_mode_enabled,
        ),
        update_interval=options.get(
            ConfScanInterval.VERY_FREQUENT, ScanIntervalDefault.VERY_FREQUENT
        ),
    )

    frequent_update_coordinator = RctPowerDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        name_suffix="frequent",
        object_ids=object_ids_for_update_priority(
            EntityUpdatePriority.FREQUENT,
            entry.entry_id,
            entity_enabled_by_unique_id,
            god_mode_enabled,
        ),
        update_interval=options.get(
            ConfScanInterval.FREQUENT, ScanIntervalDefault.FREQUENT
        ),
    )

    infrequent_update_coordinator = RctPowerDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        name_suffix="infrequent",
        object_ids=object_ids_for_update_priority(
            EntityUpdatePriority.INFREQUENT,
            entry.entry_id,
            entity_enabled_by_unique_id,
            god_mode_enabled,
        ),
        update_interval=options.get(
            ConfScanInterval.INFREQUENT, ScanIntervalDefault.INFREQUENT
        ),
    )

    static_update_coordinator = RctPowerDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        name_suffix="static",
        object_ids=object_ids_for_update_priority(
            EntityUpdatePriority.STATIC,
            entry.entry_id,
            entity_enabled_by_unique_id,
            god_mode_enabled,
        ),
        update_interval=options.get(
            ConfScanInterval.STATIC, ScanIntervalDefault.STATIC
        ),
    )

    await very_frequent_update_coordinator.async_config_entry_first_refresh()
    await frequent_update_coordinator.async_config_entry_first_refresh()
    await infrequent_update_coordinator.async_config_entry_first_refresh()
    await static_update_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = RctData(
        {
            EntityUpdatePriority.VERY_FREQUENT: very_frequent_update_coordinator,
            EntityUpdatePriority.FREQUENT: frequent_update_coordinator,
            EntityUpdatePriority.INFREQUENT: infrequent_update_coordinator,
            EntityUpdatePriority.STATIC: static_update_coordinator,
        }
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RctConfigEntry) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: RctConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: RctConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing a device only if none of its entities is available.

    Devices can be orphaned when a serial number changes or could not be read.
    """
    entity_registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_device(
        entity_registry, device_entry.id, include_disabled_entities=True
    ):
        state = hass.states.get(entity_entry.entity_id)
        if state is not None and state.state != "unavailable":
            return False
    return True
