"""Number platform for RCT Power, used for settings written to the inverter."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import PERCENTAGE, EntityCategory, Platform, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import Entity

from . import RctConfigEntry
from .const import (
    CONF_ALLOW_BATTERY_WRITES,
    CONF_ALLOW_WRITES,
    DOMAIN,
    EntityUpdatePriority,
)
from .lib.device_info_helpers import (
    get_battery_device_info,
    get_inverter_device_info,
)
from .lib.entity import RctPowerEntity, RctPowerEntityDescription
from .models import RctConfEntryOptions


@dataclass(frozen=True, kw_only=True)
class RctPowerNumberEntityDescription(
    RctPowerEntityDescription, NumberEntityDescription
):
    # the inverter value multiplied by this is shown in Home Assistant
    scale: float = 1
    # the config entry option that enables writing
    write_option: str = CONF_ALLOW_WRITES


number_entity_descriptions: list[RctPowerNumberEntityDescription] = [
    # the inverter takes a fraction of the solar plant peak power
    RctPowerNumberEntityDescription(
        get_device_info=get_inverter_device_info,
        key="buf_v_control.power_reduction",
        unique_id="external_power_reduction",
        name="External Power Reduction",
        icon="mdi:solar-power-variant",
        update_priority=EntityUpdatePriority.INFREQUENT,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        scale=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    # only used while the SOC strategy is "Constant"
    RctPowerNumberEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_target_set",
        unique_id="soc_target_set",
        name="Battery State of Charge Constant Target",
        icon="mdi:battery-arrow-up",
        write_option=CONF_ALLOW_BATTERY_WRITES,
        update_priority=EntityUpdatePriority.FREQUENT,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=5,
        native_max_value=100,
        native_step=0.1,
        scale=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    RctPowerNumberEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_min",
        unique_id="soc_min",
        name="Battery Minimum State of Charge",
        icon="mdi:battery-arrow-down",
        write_option=CONF_ALLOW_BATTERY_WRITES,
        update_priority=EntityUpdatePriority.FREQUENT,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=5,
        native_max_value=100,
        native_step=0.1,
        scale=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    RctPowerNumberEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_max",
        unique_id="soc_max",
        name="Battery Maximum State of Charge",
        icon="mdi:battery-arrow-up",
        write_option=CONF_ALLOW_BATTERY_WRITES,
        update_priority=EntityUpdatePriority.FREQUENT,
        native_unit_of_measurement=PERCENTAGE,
        native_min_value=5,
        native_max_value=100,
        native_step=0.1,
        scale=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
    # only used while the SOC strategy is "External"
    RctPowerNumberEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.battery_power_extern",
        unique_id="battery_power_extern",
        name="Battery External Power",
        icon="mdi:battery-sync",
        write_option=CONF_ALLOW_BATTERY_WRITES,
        update_priority=EntityUpdatePriority.INFREQUENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-10000,
        native_max_value=10000,
        native_step=100,
        mode=NumberMode.BOX,
        entity_category=EntityCategory.CONFIG,
    ),
]


class RctPowerNumberEntity(NumberEntity, RctPowerEntity):
    entity_description: RctPowerNumberEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    @property
    def native_value(self) -> float | None:
        value = self.get_valid_api_response_value_by_id(
            self.object_infos[0].object_id, None
        )
        if isinstance(value, int | float) and math.isfinite(value):
            return round(value * self.entity_description.scale, 2)
        return None

    async def async_set_native_value(self, value: float) -> None:
        tolerance = min(0.5, (self.entity_description.native_step or 1) / 2)

        # the inverter stores the setting permanently, so avoid needless writes
        if self.native_value is not None and math.isclose(
            self.native_value, value, abs_tol=tolerance
        ):
            return

        scale = self.entity_description.scale
        written = await self.async_write_value(value / scale)

        if not math.isclose(written * scale, value, abs_tol=tolerance):
            raise HomeAssistantError(
                f"The inverter kept {written * scale} instead of {value}"
            )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RctConfigEntry,
    async_add_entities: Callable[[list[Entity]], None],
) -> None:
    """Setup number platform for the settings writing is allowed for."""
    options = cast(RctConfEntryOptions, entry.options)

    # the feed-in limit in W was accepted by the inverter but had no effect
    entity_registry = er.async_get(hass)
    if entity_id := entity_registry.async_get_entity_id(
        Platform.NUMBER, DOMAIN, f"{entry.entry_id}-grid_feed_power_limit"
    ):
        entity_registry.async_remove(entity_id)

    data = entry.runtime_data

    async_add_entities(
        [
            RctPowerNumberEntity(
                coordinators=list(data.update_coordinators.values()),
                config_entry=entry,
                entity_description=entity_description,
            )
            for entity_description in number_entity_descriptions
            if options.get(entity_description.write_option, False)
        ]
    )
