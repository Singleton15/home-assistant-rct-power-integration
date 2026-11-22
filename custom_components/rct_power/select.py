"""Select platform for RCT Power, used for settings written to the inverter."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import Entity
from rctclient.registry import REGISTRY

from . import RctConfigEntry
from .const import CONF_ALLOW_BATTERY_WRITES, CONF_ALLOW_WRITES, EntityUpdatePriority
from .lib.device_info_helpers import get_inverter_device_info
from .lib.entity import RctPowerEntity, RctPowerEntityDescription
from .models import RctConfEntryOptions


@dataclass(frozen=True, kw_only=True)
class RctPowerSelectEntityDescription(
    RctPowerEntityDescription, SelectEntityDescription
):
    pass


# the app offers the first four, "SOC target = SOC" is undocumented but kept
# for testing, "Middle battery voltage" is left out
SOC_STRATEGIES = ["Constant", "External", "Internal", "Schedule", "SOC target = SOC"]


select_entity_descriptions: list[RctPowerSelectEntityDescription] = [
    RctPowerSelectEntityDescription(
        get_device_info=get_inverter_device_info,
        key="power_mng.soc_strategy",
        unique_id="soc_strategy",
        name="Battery State of Charge Strategy",
        icon="mdi:battery-charging-high",
        update_priority=EntityUpdatePriority.INFREQUENT,
        options=SOC_STRATEGIES,
        entity_category=EntityCategory.CONFIG,
    ),
    RctPowerSelectEntityDescription(
        get_device_info=get_inverter_device_info,
        key="modbus.mode",
        unique_id="modbus_mode_select",
        name="RS485 Modbus Mode",
        icon="mdi:swap-horizontal",
        update_priority=EntityUpdatePriority.INFREQUENT,
        options=list((REGISTRY.get_by_name("modbus.mode").enum_map or {}).values()),
        entity_category=EntityCategory.CONFIG,
    ),
]


class RctPowerSelectEntity(SelectEntity, RctPowerEntity):
    entity_description: RctPowerSelectEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    @property
    def enum_map(self) -> dict[int, str]:
        return self.object_infos[0].enum_map or {}

    @property
    def current_option(self) -> str | None:
        value = self.get_valid_api_response_value_by_id(
            self.object_infos[0].object_id, None
        )
        if isinstance(value, int) and (option := self.enum_map.get(value)) in (
            self.options
        ):
            return option
        return None

    async def async_select_option(self, option: str) -> None:
        # the inverter stores the setting permanently, so avoid needless writes
        if option == self.current_option:
            return

        [value] = [key for key, name in self.enum_map.items() if name == option]
        written = await self.async_write_value(value)

        if written != value:
            raise HomeAssistantError(
                f"The inverter kept {self.enum_map.get(int(written), written)}"
                f" instead of {option}"
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RctConfigEntry,
    async_add_entities: Callable[[list[Entity]], None],
) -> None:
    """Setup select platform, only if writing is allowed for this inverter."""
    options = cast(RctConfEntryOptions, entry.options)

    data = entry.runtime_data
    entity_descriptions: list[RctPowerSelectEntityDescription] = []

    if options.get(CONF_ALLOW_BATTERY_WRITES, False):
        entity_descriptions.append(select_entity_descriptions[0])

    if options.get(CONF_ALLOW_WRITES, False):
        entity_descriptions.append(select_entity_descriptions[1])

    async_add_entities(
        [
            RctPowerSelectEntity(
                coordinators=list(data.update_coordinators.values()),
                config_entry=entry,
                entity_description=entity_description,
            )
            for entity_description in entity_descriptions
        ]
    )
