"""Switch platform for writable RCT Power settings."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity

from . import RctConfigEntry
from .const import CONF_ALLOW_WRITES, EntityUpdatePriority
from .lib.device_info_helpers import get_inverter_device_info
from .lib.entity import RctPowerEntity, RctPowerEntityDescription
from .models import RctConfEntryOptions


@dataclass(frozen=True, kw_only=True)
class RctPowerSwitchEntityDescription(
    RctPowerEntityDescription, SwitchEntityDescription
):
    pass


switch_entity_descriptions: list[RctPowerSwitchEntityDescription] = [
    RctPowerSwitchEntityDescription(
        get_device_info=get_inverter_device_info,
        key="power_mng.use_grid_power_enable",
        name="Allow External Power",
        icon="mdi:transmission-tower-import",
        update_priority=EntityUpdatePriority.FREQUENT,
        entity_category=EntityCategory.CONFIG,
    ),
]


class RctPowerSwitchEntity(SwitchEntity, RctPowerEntity):
    entity_description: RctPowerSwitchEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    @property
    def is_on(self) -> bool | None:
        value = self.get_valid_api_response_value_by_id(
            self.object_infos[0].object_id, None
        )
        return value if isinstance(value, bool) else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_set_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_set_state(False)

    async def _async_set_state(self, value: bool) -> None:
        if self.is_on is value:
            return

        written = await self.async_write_value(value)
        if not isinstance(written, bool) or written is not value:
            raise HomeAssistantError(
                f"The inverter kept {written} instead of {value} for {self.name}"
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RctConfigEntry,
    async_add_entities: Callable[[list[Entity]], None],
) -> None:
    """Set up writable switches when writing is enabled for this inverter."""
    options = cast(RctConfEntryOptions, entry.options)
    if not options.get(CONF_ALLOW_WRITES, False):
        return

    data = entry.runtime_data
    async_add_entities(
        [
            RctPowerSwitchEntity(
                coordinators=list(data.update_coordinators.values()),
                config_entry=entry,
                entity_description=entity_description,
            )
            for entity_description in switch_entity_descriptions
        ]
    )
