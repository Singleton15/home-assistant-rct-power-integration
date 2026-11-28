from __future__ import annotations

import math
from asyncio.tasks import gather
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from functools import cached_property
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import UNDEFINED, StateType, UndefinedType
from rctclient.registry import ObjectInfo

from ..const import CONF_ENTITY_PREFIX, ICON, EntityUpdatePriority
from ..coordinator import RctPowerDataUpdateCoordinator
from .api import (
    ApiResponse,
    ApiResponseValue,
    ValidApiResponse,
    get_valid_response_value_or,
)
from .device_class_helpers import guess_device_class_from_unit
from .multi_coordinator_entity import MultiCoordinatorEntity
from .registry import REGISTRY
from .state_helpers import (
    get_api_response_values_as_bitfield,
    get_first_api_response_value_as_state,
)


class RctPowerEntity(MultiCoordinatorEntity):
    entity_description: RctPowerEntityDescription
    object_infos: list[ObjectInfo]

    def __init__(
        self,
        coordinators: list[RctPowerDataUpdateCoordinator],
        config_entry: ConfigEntry,
        entity_description: RctPowerEntityDescription,
    ):
        super().__init__(coordinators)
        self.config_entry = config_entry
        self.entity_description = (  # pyright: ignore [reportIncompatibleVariableOverride]
            entity_description
        )
        self.object_infos = resolve_object_infos(self.entity_description)

    def get_api_response_by_id(
        self, object_id: int, default: ApiResponse | None = None
    ) -> ApiResponse | None:
        for coordinator in self.coordinators:
            latest_response = coordinator.get_latest_response(object_id)

            if latest_response is not None:
                return latest_response

        return default

    async def async_update(self) -> None:
        """Refresh the polling coordinators that provide this entity's data."""
        if not self.enabled:
            return

        object_ids = {object_info.object_id for object_info in self.object_infos}
        await gather(
            *(
                coordinator.async_request_refresh()
                for coordinator in self.coordinators
                if object_ids.intersection(coordinator.object_ids)
            )
        )

    def get_api_response_by_name(
        self, object_name: str, default: ApiResponse | None = None
    ) -> ApiResponse | None:
        return self.get_api_response_by_id(
            REGISTRY.get_by_name(object_name).object_id, default
        )

    def get_valid_api_response_value_by_id[R: ApiResponseValue](
        self, object_id: int, default: R | None = None
    ) -> ApiResponseValue | R | None:
        return get_valid_response_value_or(
            self.get_api_response_by_id(object_id, None), default
        )

    def get_valid_api_response_value_by_name[R: ApiResponseValue](
        self, object_name: str, default: R | None = None
    ) -> ApiResponseValue | R | None:
        return get_valid_response_value_or(
            self.get_api_response_by_name(object_name, None), default
        )

    async def async_write_value(self, value: float) -> int | float:
        """Write the entity's object and return the value read back."""
        object_id = self.object_infos[0].object_id
        response = await self.coordinators[0].client.async_write_value(object_id, value)

        if not isinstance(response, ValidApiResponse) or not isinstance(
            response.value, int | float
        ):
            raise HomeAssistantError(
                f"The inverter did not confirm the new value for {self.name}"
            )

        # update every coordinator that holds this object so all entities agree
        for coordinator in self.coordinators:
            if object_id in coordinator.object_ids:
                coordinator.record_valid_response(response)
                coordinator.async_set_updated_data(
                    {**coordinator.data, object_id: response}
                )

        return response.value

    @cached_property
    def unique_id(self) -> str | None:
        """Return a unique ID to use for this entity."""
        # this allows for keeping the entity identity stable for existing
        # sensors when the algorithm below changes
        if uid := self.entity_description.unique_id:
            return f"{self.config_entry.entry_id}-{uid}"

        object_ids = [str(object_info.object_id) for object_info in self.object_infos]
        return "-".join([self.config_entry.entry_id, *object_ids])

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the name of the entity."""
        entity_name = (
            self.entity_description.name
            if self.entity_description.name != UNDEFINED
            else slugify_entity_name(self.object_infos[0].name)
        )

        return f"{self.config_entry.data[CONF_ENTITY_PREFIX]} {entity_name}"

    @property
    def available(self) -> bool:
        return all(
            any(
                coordinator.last_update_success
                and coordinator.has_valid_value(object_info.object_id)
                for coordinator in self.coordinators
                if object_info.object_id in coordinator.object_ids
            )
            for object_info in self.object_infos
        )

    @cached_property
    def unit_of_measurement(self) -> str | None:
        if unit_of_measurement := super().unit_of_measurement:
            return unit_of_measurement

        return self.object_infos[0].unit

    @cached_property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return {}

    @property
    def device_info(self) -> DeviceInfo | None:
        return self.entity_description.get_device_info(self)


class RctPowerSensorEntity(SensorEntity, RctPowerEntity):
    entity_description: RctPowerSensorEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    def get_valid_api_responses(self) -> list[ApiResponseValue | None]:
        return [
            self.get_valid_api_response_value_by_id(object_info.object_id, None)
            for object_info in self.object_infos
        ]

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        if device_class := super().device_class:
            return device_class

        if self.native_unit_of_measurement:
            return guess_device_class_from_unit(self.native_unit_of_measurement)

        return None

    @property
    def native_value(self) -> StateType | date | datetime | Decimal:
        value = self.entity_description.get_native_value(
            self, self.get_valid_api_responses()
        )
        # some inverters report inf or nan for counters they don't have,
        # which Home Assistant rejects for numeric sensors
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        if native_unit_of_measurement := super().native_unit_of_measurement:
            return native_unit_of_measurement

        return self.object_infos[0].unit


class RctPowerBitfieldSensorEntity(RctPowerSensorEntity):
    @cached_property
    def native_unit_of_measurement(self) -> str | None:
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the device class of the sensor."""
        if device_class := super().device_class:
            return device_class

        if self.options:
            return SensorDeviceClass.ENUM

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            **(super().extra_state_attributes or {}),
            "bitfield": get_api_response_values_as_bitfield(
                self, self.get_valid_api_responses()
            ),
        }


class RctPowerBatteryModuleSensorEntity(RctPowerSensorEntity):
    """Sensor derived from the cell data of a single battery module.

    The per-cell values are exposed as attributes, which are excluded from the
    recorder to keep the database small.
    """

    entity_description: RctPowerBatteryModuleSensorEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    _unrecorded_attributes = frozenset(
        {
            "cell_count",
            "cell_voltages",
            "cell_temperatures",
            "cell_status",
            "cell_resistances",
            "max_voltage_cell",
            "min_voltage_cell",
            "max_temperature_cell",
            "max_resistance_cell",
            "median_cell_voltage",
            "median_cell_resistance",
            "module_cell_voltages",
            "module_cell_resistances",
            "flagged_cells",
            "flagged_cell_voltages",
        }
    )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        get_extra_state_attributes = self.entity_description.get_extra_state_attributes

        if get_extra_state_attributes is None:
            return None

        return get_extra_state_attributes(self, self.get_valid_api_responses())


class RctPowerBinarySensorEntity(BinarySensorEntity, RctPowerEntity):
    entity_description: RctPowerBinarySensorEntityDescription  # pyright: ignore [reportIncompatibleVariableOverride]

    @cached_property
    def unit_of_measurement(self) -> str | None:
        # the voltage objects the state is derived from don't make it a voltage
        return None

    def get_valid_api_responses(self) -> list[ApiResponseValue | None]:
        return [
            self.get_valid_api_response_value_by_id(object_info.object_id, None)
            for object_info in self.object_infos
        ]

    @property
    def is_on(self) -> bool | None:
        return self.entity_description.get_is_on(self, self.get_valid_api_responses())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        get_extra_state_attributes = self.entity_description.get_extra_state_attributes

        if get_extra_state_attributes is None:
            return None

        return get_extra_state_attributes(self, self.get_valid_api_responses())


@dataclass(frozen=True, kw_only=True)
class RctPowerEntityDescription(EntityDescription):
    icon: str | None = ICON
    object_names: list[str] | None = None
    requires_god_mode: bool = False
    # to allow for stable entity identities even if the object ids change
    unique_id: str | None = None
    update_priority: EntityUpdatePriority = EntityUpdatePriority.FREQUENT
    get_device_info: Callable[[RctPowerEntity], DeviceInfo | None] = lambda e: None


@dataclass(frozen=True, kw_only=True)
class RctPowerSensorEntityDescription(
    RctPowerEntityDescription, SensorEntityDescription
):
    get_native_value: Callable[
        [RctPowerSensorEntity, list[ApiResponseValue | None]],
        StateType | date | datetime | Decimal,
    ] = get_first_api_response_value_as_state


@dataclass(frozen=True, kw_only=True)
class RctPowerBitfieldSensorEntityDescription(
    RctPowerEntityDescription, SensorEntityDescription
):
    get_native_value: Callable[
        [RctPowerSensorEntity, list[ApiResponseValue | None]],
        StateType | date | datetime | Decimal,
    ] = get_api_response_values_as_bitfield


@dataclass(frozen=True, kw_only=True)
class RctPowerBatteryModuleSensorEntityDescription(RctPowerSensorEntityDescription):
    get_extra_state_attributes: (
        Callable[
            [RctPowerSensorEntity, list[ApiResponseValue | None]],
            dict[str, Any],
        ]
        | None
    ) = None


@dataclass(frozen=True, kw_only=True)
class RctPowerBinarySensorEntityDescription(
    RctPowerEntityDescription, BinarySensorEntityDescription
):
    get_is_on: Callable[
        [RctPowerBinarySensorEntity, list[ApiResponseValue | None]], bool | None
    ]
    get_extra_state_attributes: (
        Callable[
            [RctPowerBinarySensorEntity, list[ApiResponseValue | None]],
            dict[str, Any],
        ]
        | None
    ) = None


def slugify_entity_name(name: str) -> str:
    return name.replace(".", "_").replace("[", "_").replace("]", "_").replace("?", "_")


def resolve_object_infos(
    entity_description: RctPowerEntityDescription,
) -> list[ObjectInfo]:
    object_names = entity_description.object_names or [entity_description.key]
    return [REGISTRY.get_by_name(object_name) for object_name in object_names]


known_faults: list[str] = [
    "TRAP occurred",
    "RTC can't be configured",
    "RTC 1Hz signal timeout",
    "Hardware Stop by 3.3V fault",
    "Hardware Stop by PWM Logic",
    "Hardware Stop by Uzk overvoltage",
    "Uzk+ is over limit",
    "Uzk- is over limit",
    "Throttle Phase L1 overcurrent",
    "Throttle Phase L2 overcurrent",
    "Throttle Phase L3 overcurrent",
    "Buffer capacitor voltage",
    "Quartz fault",
    "Grid under_voltage phase 1",
    "Grid under_voltage phase 2",
    "Grid under_voltage phase 3",
    "Battery overcurrent",
    "Relays Test failed",
    "Board Over Temperature",
    "Core Over Temperature",
    "Sink 1 Over Temperature",
    "Sink 2 Over Temperature",
    "Error by I2C communication with Power Board",
    "Power Board Error",
    "PWM output ports defect",
    "Insulation is too small or not plausible",
    "I DC Component Max (1 A)",
    "I DC Component Max Slow (47 mA)",
    "One of the DSD channels possibly defect (too big current offset)",
    "Error by RS485 communication with Relays BoxIGBT L1 BH defect",
    "Phase to phase over voltage",
    "IGBT L1 BH defect",
    "IGBT L1 BL defect",
    "IGBT L2 BH defect",
    "IGBT L2 BL defect",
    "IGBT L3 BH defect",
    "IGBT L3 BL defect",
    "Long Term over voltage phase 1",
    "Long Term over voltage phase 2",
    "Long Term over voltage phase 3",
    "Over voltage phase 1, level 1",
    "Over voltage phase 1, level 2",
    "Over voltage phase 2, level 1",
    "Over voltage phase 2, level 2",
    "Over voltage phase 3, level 1",
    "Over voltage phase 3, level 2",
    "Over frequency, level 1",
    "Over frequency, level 2",
    "Under voltage phase 1, level 1",
    "Under voltage phase 1, level 2",
    "Under voltage phase 2, level 1",
    "Under voltage phase 2, level 2",
    "Under voltage phase 3, level 1",
    "Under voltage phase 3, level 2",
    "Under frequency, level 1",
    "Under frequency, level 2",
    "CPU Exception NMI",
    "CPU Exception HardFault",
    "CPU Exception MemManage",
    "CPU Exception BusFault",
    "CPU Exception UsageFault",
    "RTC Power on reset",
    "RTC Oscillation stops",
    "RTC Supply voltage drop",
    "Jump of RCD current DC + AC > 30mA was noticed",
    "Jump of RCD current DC > 60mA was noticed",
    "Jump of RCD current AC > 150mA was noticed",
    "RCD current > 300mA was noticed",
    "incorrect 5V was noticed",
    "incorrect -9V was noticed",
    "incorrect 9V was noticed",
    "incorrect 3V3 was noticed",
    "failure of RDC calibration was noticed",
    "failure of I2C was noticed",
    "afi frequency generator failure",
    "sink temperature too high",
    "Uzk is over limit",
    "Usg A is over limit",
    "Usg B is over limit",
    "Switching On Conditions Umin phase 1",
    "Switching On Conditions Umax phase 1",
    "Switching On Conditions Fmin phase 1",
    "Switching On Conditions Fmax phase 1",
    "Switching On Conditions Umin phase 2",
    "Switching On Conditions Umax phase 2",
    "Battery current sensor defect",
    "Battery booster damaged",
    "Switching On Conditions Umin phase 3",
    "Switching On Conditions Umax phase 3",
    "Voltage surge or average offset is too big on AC-terminals (phase failure detected)",
    "Inverter is disconnected from the household grid",
    "Difference of the measured +9V between DSP and PIC is too big",
    "1.5V error",
    "2.5V error",
    "1.5V measurement difference",
    "2.5V measurement difference",
    "The battery voltage is outside of the expected range",
    "Unable to start the main PIC software",
    "PIC bootloader detected unexpectedly",
    "Phase position error (not 120° as expected)",
    "Battery overvoltage",
    "Throttle current is unstable",
    "Difference between internal and external measured grid voltage is too big in phase",
    "Difference between internal and external measured grid voltage is too big in phase",
    "Difference between internal and external measured grid voltage is too big in phase",
    "External emergency turn off signal is active",
    "Battery is empty, not more energy for standby",
    "CAN communication timeout with battery",
    "Timing problem",
    "Battery IGBT's Heat Sink Over Temperature",
    "Battery heat sink temperature too high",
    "Internal Relays Box error",
    "Relays Box PE off error",
    "Relays Box PE on error",
    "Internal battery error",
    "Parameter changed",
    "3 attempts of island building are failed",
    "Phase to phase under voltage",
    "System reset detected",
    "Update detected",
    "FRT over-voltage",
    "FRT under-voltage",
    "IGBT L1 free wheeling diode defect",
    "IGBT L2 free wheeling diode defect",
    "IGBT L3 free wheeling diode defect",
    "1 phase mode is activated but not allowed for this device class (e.g. 10K)",
    "Island detected",
]
