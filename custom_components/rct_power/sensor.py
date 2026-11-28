"""Sensor platform for RCT Power."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from enum import StrEnum
from typing import ClassVar

import aiohttp
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from . import RctConfigEntry
from .const import (
    CONF_ENTITY_PREFIX,
    CONF_GOD_MODE,
    CONF_HOSTNAME,
    DOMAIN,
)
from .coordinator import RctPowerDataUpdateCoordinator
from .lib.device_info_helpers import get_inverter_device_info
from .lib.entities import (
    battery_cell_sensor_entity_descriptions,
    battery_sensor_entity_descriptions,
    battery_tower_2_sensor_entity_descriptions,
    bitfield_sensor_entity_descriptions,
    inverter_sensor_entity_descriptions,
)
from .lib.entity import (
    RctPowerBatteryModuleSensorEntity,
    RctPowerBatteryModuleSensorEntityDescription,
    RctPowerBitfieldSensorEntity,
    RctPowerSensorEntity,
)

COMMUNICATION_PROBE_TIMEOUT_SECONDS = 5


class CommunicationState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    STALE = "stale"


class RctPowerCommunicationStatusSensor(SensorEntity):
    """Report whether inverter communication is online, offline, or stale."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:lan-connect"
    _attr_should_poll = False
    _attr_options: ClassVar[list[str]] = [state.value for state in CommunicationState]

    def __init__(
        self,
        entry: RctConfigEntry,
        coordinators: list[RctPowerDataUpdateCoordinator],
    ) -> None:
        self._entry = entry
        self._coordinators = coordinators
        self._monitored_coordinators = [
            coordinator
            for coordinator in coordinators
            if coordinator.update_priority in {"very_frequent", "frequent"}
            and coordinator.object_ids
        ]
        self._state: CommunicationState | None = (
            CommunicationState.ONLINE
            if any(
                coordinator.last_update_had_valid_response
                for coordinator in coordinators
            )
            else None
        )
        self._response_generation = sum(
            coordinator.last_update_had_valid_response for coordinator in coordinators
        )
        self._probe_task: asyncio.Task[None] | None = None

    @property
    def unique_id(self) -> str:
        return f"{self._entry.entry_id}-communication_status"

    @property
    def name(self) -> str:
        return f"{self._entry.data[CONF_ENTITY_PREFIX]} Communication Status"

    @property
    def native_value(self) -> str | None:
        return self._state.value if self._state else None

    @property
    def available(self) -> bool:
        return self._state is not None

    @property
    def device_info(self) -> DeviceInfo:
        serial_number = str(self._entry.unique_id or self._entry.entry_id)
        return DeviceInfo(identifiers={(DOMAIN, serial_number)})

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        for coordinator in self._coordinators:
            self.async_on_remove(
                coordinator.async_add_listener(
                    lambda coordinator=coordinator: self._handle_coordinator_update(
                        coordinator
                    )
                )
            )
        if any(
            not coordinator.last_update_success
            for coordinator in self._monitored_coordinators
        ):
            self._schedule_outage_detection()

    def _handle_coordinator_update(
        self, coordinator: RctPowerDataUpdateCoordinator
    ) -> None:
        if coordinator.last_update_had_valid_response:
            self._response_generation += 1
            self._state = CommunicationState.ONLINE
            self.async_write_ha_state()
            return

        if coordinator in self._monitored_coordinators:
            self._schedule_outage_detection()

    def _schedule_outage_detection(self) -> None:
        if (
            self._monitored_coordinators
            and self._state in {None, CommunicationState.ONLINE}
            and all(
                not coordinator.has_available_values
                for coordinator in self._monitored_coordinators
            )
            and self._probe_task is None
        ):
            self._probe_task = self.hass.async_create_task(
                self._async_detect_offline_or_stale()
            )

    async def _async_detect_offline_or_stale(self) -> None:
        response_generation = self._response_generation
        try:
            reachable = await self._async_http_probe()
        finally:
            self._probe_task = None

        if (
            response_generation == self._response_generation
            and self._state in {None, CommunicationState.ONLINE}
            and all(
                not coordinator.has_available_values
                for coordinator in self._monitored_coordinators
            )
        ):
            self._state = (
                CommunicationState.STALE if reachable else CommunicationState.OFFLINE
            )
            self.async_write_ha_state()

    async def _async_http_probe(self) -> bool:
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"http://{self._entry.data[CONF_HOSTNAME]}/",
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(
                    total=COMMUNICATION_PROBE_TIMEOUT_SECONDS
                ),
            ):
                return True
        except aiohttp.ClientError, TimeoutError:
            return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RctConfigEntry,
    async_add_entities: Callable[[list[Entity]], None],
) -> None:
    """Setup sensor platform."""
    data = entry.runtime_data

    battery_sensor_entities = [
        RctPowerSensorEntity(
            coordinators=list(data.update_coordinators.values()),
            config_entry=entry,
            entity_description=entity_description,
        )
        for entity_description in battery_sensor_entity_descriptions
        if entry.options.get(CONF_GOD_MODE, False)
        or not entity_description.requires_god_mode
    ]

    battery_cell_sensor_entities = [
        (
            RctPowerBatteryModuleSensorEntity
            if isinstance(
                entity_description, RctPowerBatteryModuleSensorEntityDescription
            )
            else RctPowerSensorEntity
        )(
            coordinators=list(data.update_coordinators.values()),
            config_entry=entry,
            entity_description=entity_description,
        )
        for entity_description in [
            *battery_tower_2_sensor_entity_descriptions,
            *battery_cell_sensor_entity_descriptions,
        ]
    ]

    inverter_sensor_entities = [
        RctPowerSensorEntity(
            coordinators=list(data.update_coordinators.values()),
            config_entry=entry,
            entity_description=entity_description,
        )
        for entity_description in inverter_sensor_entity_descriptions
        if entry.options.get(CONF_GOD_MODE, False)
        or not entity_description.requires_god_mode
    ]

    bitfield_sensor_entities = [
        RctPowerBitfieldSensorEntity(
            coordinators=list(data.update_coordinators.values()),
            config_entry=entry,
            entity_description=entity_description,
        )
        for entity_description in bitfield_sensor_entity_descriptions
    ]

    communication_status_sensor = RctPowerCommunicationStatusSensor(
        entry, list(data.update_coordinators.values())
    )

    # the battery devices refer to the inverter device by its registry id
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **get_inverter_device_info(inverter_sensor_entities[0]),
    )

    async_add_entities(
        [
            *battery_sensor_entities,
            *battery_cell_sensor_entities,
            *inverter_sensor_entities,
            *bitfield_sensor_entities,
            communication_status_sensor,
        ]
    )
