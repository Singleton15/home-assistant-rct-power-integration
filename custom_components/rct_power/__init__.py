"""
Custom integration to integrate RCT Power with Home Assistant.

For more details about this integration, please refer to
https://github.com/weltenwort/home-assistant-rct-power-integration
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util.hass_dict import HassEntryKey

from .const import (
    CONF_HOSTNAME,
    DOMAIN,
    PLATFORMS,
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
) -> list[int]:
    """Collect object IDs needed by enabled entities for an update priority."""
    return list(
        {
            object_info.object_id
            for entity_description in all_entity_descriptions
            if entity_description.update_priority == update_priority
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

    very_frequent_update_coordinator = RctPowerDataUpdateCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        name_suffix="very_frequent",
        object_ids=object_ids_for_update_priority(
            EntityUpdatePriority.VERY_FREQUENT,
            entry.entry_id,
            entity_enabled_by_unique_id,
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
