from __future__ import annotations

import re
from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import DeviceInfo
from rctclient.registry import REGISTRY

from ..const import BATTERY_MODULE_COUNT, EntityUpdatePriority
from .battery_module_helpers import (
    get_cell_resistance_attributes,
    get_cell_status_attributes,
    get_cell_voltage_spread,
    get_first_api_response_value_as_cell_voltage,
    get_max_cell_resistance,
    get_max_cell_temperature,
    get_max_cell_voltage,
    get_mean_cell_resistance,
    get_mean_cell_voltage,
    get_min_cell_temperature,
    get_min_cell_voltage,
    get_tower_cell_resistance_attributes,
    get_tower_cell_status_attributes,
    get_tower_cell_voltage_attributes,
    get_tower_cell_voltage_spread,
    get_tower_connection_attributes,
    get_tower_flagged_cell_count,
    get_tower_max_cell_resistance,
    get_tower_max_cell_resistance_deviation,
    get_tower_weakest_cell_deviation,
    is_tower_connected,
)
from .device_info_helpers import (
    get_battery_device_info,
    get_battery_tower_2_device_info,
    get_inverter_device_info,
)
from .entity import (
    RctPowerBatteryModuleSensorEntityDescription,
    RctPowerBinarySensorEntityDescription,
    RctPowerBitfieldSensorEntityDescription,
    RctPowerEntity,
    RctPowerSensorEntityDescription,
)
from .state_helpers import (
    available_battery_status,
    get_first_api_response_value_as_absolute_state,
    get_first_api_response_value_as_battery_status,
    get_first_api_response_value_as_bool,
    get_first_api_response_value_as_timestamp,
    is_battery_balancing,
    is_battery_calibrating,
    sum_api_response_values_as_state,
)


def get_matching_names(expression: str) -> list[str]:
    compiled_expression = re.compile(expression)
    return [
        object_info.name
        for object_info in REGISTRY.all()
        if compiled_expression.match(object_info.name) is not None
    ]


battery_sensor_entity_descriptions: list[RctPowerSensorEntityDescription] = [
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.bms_sn",
        name="Battery Management System Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.bms_software_version",
        name="Battery Management System Software Version",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[0]",
        name="Battery Module 1 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[1]",
        name="Battery Module 2 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[2]",
        name="Battery Module 3 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[3]",
        name="Battery Module 4 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[4]",
        name="Battery Module 5 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.module_sn[5]",
        name="Battery Module 6 Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.charged_amp_hours",
        name="Battery Charge Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.discharged_amp_hours",
        name="Battery Discharge Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.current",
        name="Battery Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.voltage",
        name="Battery Voltage",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.maximum_charge_voltage",
        name="Battery Maximum Charging Voltage",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.minimum_discharge_voltage",
        name="Battery Minimum Discharging Voltage",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.maximum_discharge_current",
        name="Battery Maximum Discharging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.temperature",
        name="Battery Temperature",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.stored_energy",
        name="Battery Stored Energy",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.used_energy",
        name="Battery Used Energy",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.ah_capacity",
        name="Battery Charge Capacity",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.soc",
        name="Battery State of Charge",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.BATTERY,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_min_island",
        name="Battery Minimum State of Charge (Island)",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_min",
        name="Battery Minimum State of Charge",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_max",
        name="Battery Maximum State of Charge",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.soc_target",
        name="Battery State of Charge Target",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.soc_target_low",
        name="Battery State of Charge Low Target",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.soc_target_high",
        name="Battery State of Charge High Target",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.soh",
        name="Battery State of Health",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.cycles",
        name="Battery Cycles",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.bat_next_calib_date",
        name="Next Battery Calibration Date",
        update_priority=EntityUpdatePriority.INFREQUENT,
        device_class=SensorDeviceClass.TIMESTAMP,
        get_native_value=get_first_api_response_value_as_timestamp,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.bat_calib_reqularity",
        name="Battery Calibration Interval",
        update_priority=EntityUpdatePriority.STATIC,
        native_unit_of_measurement=UnitOfTime.DAYS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.calib_charge_power",
        name="Battery Calibration Charge Power",
        update_priority=EntityUpdatePriority.STATIC,
        native_unit_of_measurement=UnitOfPower.WATT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.maximum_charge_current",
        name="Battery Maximum Charging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="acc_conv.i_charge_max",
        name="Battery Converter Maximum Charging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="acc_conv.i_discharge_max",
        name="Battery Converter Maximum Discharging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_strategy",
        name="Battery State of Charge Strategy",
        update_priority=EntityUpdatePriority.INFREQUENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.soc_target_set",
        name="Battery State of Charge Constant Target",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="power_mng.battery_power_extern",
        name="Battery External Power",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.efficiency",
        name="Battery Efficiency",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
]


def get_battery_tower_sensor_entity_descriptions(
    object_prefix: str,
    name_prefix: str,
    get_device_info: Callable[[RctPowerEntity], DeviceInfo | None],
) -> list[RctPowerSensorEntityDescription]:
    """Sensors reported by the BMS of a battery tower."""
    return [
        RctPowerSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.max_cell_voltage",
            name=f"{name_prefix} Max Cell Voltage",
            update_priority=EntityUpdatePriority.FREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=3,
            get_native_value=get_first_api_response_value_as_cell_voltage,
        ),
        RctPowerSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.min_cell_voltage",
            name=f"{name_prefix} Min Cell Voltage",
            update_priority=EntityUpdatePriority.FREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=3,
            get_native_value=get_first_api_response_value_as_cell_voltage,
        ),
        RctPowerSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.max_cell_temperature",
            name=f"{name_prefix} Max Cell Temperature",
            update_priority=EntityUpdatePriority.FREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
        RctPowerSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.min_cell_temperature",
            name=f"{name_prefix} Min Cell Temperature",
            update_priority=EntityUpdatePriority.FREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        ),
    ]


def get_battery_module_sensor_entity_descriptions(
    object_prefix: str,
    name_prefix: str,
    get_device_info: Callable[[RctPowerEntity], DeviceInfo | None],
) -> list[RctPowerSensorEntityDescription]:
    """Sensors for each module of a battery tower."""
    descriptions: list[RctPowerSensorEntityDescription] = []

    for module_index in range(BATTERY_MODULE_COUNT):
        module_name = f"{name_prefix} Module {module_index + 1}"
        cells_object_name = f"{object_prefix}.cells[{module_index}]"
        cells_object_id = REGISTRY.get_by_name(cells_object_name).object_id
        resist_object_name = f"{object_prefix}.cells_resist[{module_index}]"
        resist_object_id = REGISTRY.get_by_name(resist_object_name).object_id

        descriptions += [
            RctPowerSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{object_prefix}.stack_cycles[{module_index}]",
                name=f"{module_name} Cycles",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.TOTAL_INCREASING,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.max_cell_voltage",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-max_cell_voltage",
                name=f"{module_name} Max Cell Voltage",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                suggested_display_precision=3,
                get_native_value=get_max_cell_voltage,
                get_extra_state_attributes=get_cell_status_attributes,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.min_cell_voltage",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-min_cell_voltage",
                name=f"{module_name} Min Cell Voltage",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                suggested_display_precision=3,
                get_native_value=get_min_cell_voltage,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.mean_cell_voltage",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-mean_cell_voltage",
                name=f"{module_name} Mean Cell Voltage",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.VOLT,
                suggested_display_precision=3,
                get_native_value=get_mean_cell_voltage,
                entity_registry_enabled_default=False,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.cell_voltage_spread",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-cell_voltage_spread",
                name=f"{module_name} Cell Voltage Spread",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.VOLTAGE,
                native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
                get_native_value=get_cell_voltage_spread,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.max_cell_temperature",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-max_cell_temperature",
                name=f"{module_name} Max Cell Temperature",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                get_native_value=get_max_cell_temperature,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{cells_object_name}.min_cell_temperature",
                object_names=[cells_object_name],
                unique_id=f"{cells_object_id}-min_cell_temperature",
                name=f"{module_name} Min Cell Temperature",
                update_priority=EntityUpdatePriority.INFREQUENT,
                state_class=SensorStateClass.MEASUREMENT,
                device_class=SensorDeviceClass.TEMPERATURE,
                native_unit_of_measurement=UnitOfTemperature.CELSIUS,
                get_native_value=get_min_cell_temperature,
                entity_registry_enabled_default=False,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{resist_object_name}.max_cell_resistance",
                object_names=[resist_object_name],
                unique_id=f"{resist_object_id}-max_cell_resistance",
                name=f"{module_name} Max Cell Resistance",
                update_priority=EntityUpdatePriority.STATIC,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="mΩ",
                entity_category=EntityCategory.DIAGNOSTIC,
                get_native_value=get_max_cell_resistance,
                get_extra_state_attributes=get_cell_resistance_attributes,
            ),
            RctPowerBatteryModuleSensorEntityDescription(
                get_device_info=get_device_info,
                key=f"{resist_object_name}.mean_cell_resistance",
                object_names=[resist_object_name],
                unique_id=f"{resist_object_id}-mean_cell_resistance",
                name=f"{module_name} Mean Cell Resistance",
                update_priority=EntityUpdatePriority.STATIC,
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="mΩ",
                entity_category=EntityCategory.DIAGNOSTIC,
                get_native_value=get_mean_cell_resistance,
            ),
        ]

    return descriptions


def get_battery_tower_cell_health_sensor_entity_descriptions(
    object_prefix: str,
    name_prefix: str,
    get_device_info: Callable[[RctPowerEntity], DeviceInfo | None],
) -> list[RctPowerSensorEntityDescription]:
    """Sensors summarizing the cells of all modules of a battery tower.

    Meant for long-term tracking: each is a single number with long-term
    statistics, the affected cell position and all cell values are in the
    (unrecorded) attributes.
    """
    cells_object_names = [
        f"{object_prefix}.cells[{module_index}]"
        for module_index in range(BATTERY_MODULE_COUNT)
    ]
    resist_object_names = [
        f"{object_prefix}.cells_resist[{module_index}]"
        for module_index in range(BATTERY_MODULE_COUNT)
    ]

    return [
        RctPowerBatteryModuleSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.cells.cell_voltage_spread",
            object_names=cells_object_names,
            unique_id=f"{object_prefix}-tower_cell_voltage_spread",
            name=f"{name_prefix} Cell Voltage Spread",
            update_priority=EntityUpdatePriority.INFREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            get_native_value=get_tower_cell_voltage_spread,
            get_extra_state_attributes=get_tower_cell_voltage_attributes,
        ),
        RctPowerBatteryModuleSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.cells.weakest_cell_deviation",
            object_names=cells_object_names,
            unique_id=f"{object_prefix}-tower_weakest_cell_deviation",
            name=f"{name_prefix} Weakest Cell Deviation",
            update_priority=EntityUpdatePriority.INFREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            device_class=SensorDeviceClass.VOLTAGE,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_display_precision=0,
            get_native_value=get_tower_weakest_cell_deviation,
            get_extra_state_attributes=get_tower_cell_voltage_attributes,
        ),
        RctPowerBatteryModuleSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.cells_resist.max_cell_resistance",
            object_names=resist_object_names,
            unique_id=f"{object_prefix}-tower_max_cell_resistance",
            name=f"{name_prefix} Max Cell Resistance",
            update_priority=EntityUpdatePriority.STATIC,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="mΩ",
            get_native_value=get_tower_max_cell_resistance,
            get_extra_state_attributes=get_tower_cell_resistance_attributes,
        ),
        RctPowerBatteryModuleSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.cells_resist.max_cell_resistance_deviation",
            object_names=resist_object_names,
            unique_id=f"{object_prefix}-tower_max_cell_resistance_deviation",
            name=f"{name_prefix} Max Cell Resistance Deviation",
            update_priority=EntityUpdatePriority.STATIC,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            get_native_value=get_tower_max_cell_resistance_deviation,
            get_extra_state_attributes=get_tower_cell_resistance_attributes,
        ),
        RctPowerBatteryModuleSensorEntityDescription(
            get_device_info=get_device_info,
            key=f"{object_prefix}.cells.flagged_cells",
            object_names=cells_object_names,
            unique_id=f"{object_prefix}-tower_flagged_cells",
            name=f"{name_prefix} Flagged Cells",
            icon="mdi:scale-balance",
            update_priority=EntityUpdatePriority.INFREQUENT,
            state_class=SensorStateClass.MEASUREMENT,
            get_native_value=get_tower_flagged_cell_count,
            get_extra_state_attributes=get_tower_cell_status_attributes,
        ),
    ]


battery_tower_2_sensor_entity_descriptions: list[RctPowerSensorEntityDescription] = [
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].bms_sn",
        name="Battery Tower 2 Battery Management System Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].bms_software_version",
        name="Battery Tower 2 Battery Management System Software Version",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].soc",
        name="Battery Tower 2 State of Charge",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.BATTERY,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].voltage",
        name="Battery Tower 2 Voltage",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].current",
        name="Battery Tower 2 Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].temperature",
        name="Battery Tower 2 Temperature",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].ah_capacity",
        name="Battery Tower 2 Charge Capacity",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].soh",
        name="Battery Tower 2 State of Health",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].maximum_charge_current",
        name="Battery Tower 2 Maximum Charging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_battery_tower_2_device_info,
        key="battery_placeholder[0].maximum_discharge_current",
        name="Battery Tower 2 Maximum Discharging Current",
        update_priority=EntityUpdatePriority.FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        RctPowerSensorEntityDescription(
            get_device_info=get_battery_tower_2_device_info,
            key=f"battery_placeholder[0].module_sn[{module_index}]",
            name=f"Battery Tower 2 Module {module_index + 1} Serial Number",
            update_priority=EntityUpdatePriority.STATIC,
        )
        for module_index in range(BATTERY_MODULE_COUNT)
    ),
    *get_battery_tower_sensor_entity_descriptions(
        "battery_placeholder[0]", "Battery Tower 2", get_battery_tower_2_device_info
    ),
]

battery_cell_sensor_entity_descriptions: list[RctPowerSensorEntityDescription] = [
    *get_battery_tower_sensor_entity_descriptions(
        "battery", "Battery", get_battery_device_info
    ),
    *get_battery_module_sensor_entity_descriptions(
        "battery", "Battery", get_battery_device_info
    ),
    *get_battery_module_sensor_entity_descriptions(
        "battery_placeholder[0]", "Battery Tower 2", get_battery_tower_2_device_info
    ),
    *get_battery_tower_cell_health_sensor_entity_descriptions(
        "battery", "Battery", get_battery_device_info
    ),
    *get_battery_tower_cell_health_sensor_entity_descriptions(
        "battery_placeholder[0]", "Battery Tower 2", get_battery_tower_2_device_info
    ),
]

inverter_sensor_entity_descriptions: list[RctPowerSensorEntityDescription] = [
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="adc.u_acc",
        name="Inverter Battery Voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="android_description",
        name="Inverter Device Name",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="buf_v_control.power_reduction_max_solar",
        name="Generator Maximum Power",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="buf_v_control.power_reduction_max_solar_grid",
        name="Grid Maximum Feed Power",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="buf_v_control.power_reduction",
        name="External Power Reduction",
        update_priority=EntityUpdatePriority.INFREQUENT,
        native_unit_of_measurement="%",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="db.core_temp",
        name="Core Temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="db.temp1",
        name="Heat Sink Temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="db.temp2",
        name="Heat Sink (battery actuator) Temperature",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].enabled",
        name="Generator A Connected",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].mpp.fixed_voltage",
        name="Generator A MPP Fixed Voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].mpp.mpp_step",
        name="Generator A MPP Search Step",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].p_dc",
        name="Generator A Power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].rescan_correction",
        name="Generator A MPP Rescan Correction",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[0].u_sg_lp",
        name="Generator A Voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].enabled",
        name="Generator B Connected",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].mpp.fixed_voltage",
        name="Generator B MPP Fixed Voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].mpp.mpp_step",
        name="Generator B MPP Search Step",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].p_dc",
        name="Generator B Power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].rescan_correction",
        name="Generator B MPP Rescan Correction",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct[1].u_sg_lp",
        name="Generator B Voltage",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.dc_conv_struct.p_dc",
        object_names=[
            "dc_conv.dc_conv_struct[0].p_dc",
            "dc_conv.dc_conv_struct[1].p_dc",
        ],
        name="All Generators Power",
        state_class=SensorStateClass.MEASUREMENT,
        get_native_value=sum_api_response_values_as_state,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="dc_conv.start_voltage",
        name="Inverter DC Start Voltage",
        update_priority=EntityUpdatePriority.STATIC,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="iso_struct.Riso",
        name="Insulation Resistance",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="iso_struct.r_min",
        name="Minimum Insulation Resistance",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="iso_struct.Rn",
        name="Insulation Resistance Negative Input",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="iso_struct.Rp",
        name="Insulation Resistance Positive Input",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="inverter_sn",
        name="Inverter Serial Number",
        update_priority=EntityUpdatePriority.STATIC,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="svnversion",
        name="Inverter Software Version",
        update_priority=EntityUpdatePriority.INFREQUENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="flash_rtc.time_stamp_update",
        name="Date of Last Update",
        update_priority=EntityUpdatePriority.INFREQUENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_sum",
        name="Inverter AC Power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac[0]",
        name="Inverter Power P1",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="W",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac[1]",
        name="Inverter Power P2",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="W",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac[2]",
        name="Inverter Power P3",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="W",
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_load_sum_lp",
        name="Consumer Power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_load[0]",
        name="Consumer Power P1",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_load[1]",
        name="Consumer Power P2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_load[2]",
        name="Consumer Power P3",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_acc_lp",
        name="Battery Power",
        update_priority=EntityUpdatePriority.VERY_FREQUENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_grid_sum_lp",
        name="Grid Power",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_sc[0]",
        name="Grid Power P1",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_sc[1]",
        name="Grid Power P2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="g_sync.p_ac_sc[2]",
        name="Grid Power P3",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="grid_pll[0].f",
        name="Grid Frequency",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.f_grid[0]",
        name="Grid Frequency P1",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.f_grid[1]",
        name="Grid Frequency P2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.f_grid[2]",
        name="Grid Frequency P3",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.u_l_grid[0]",
        name="Grid Voltage P1",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.u_l_grid[1]",
        name="Grid Voltage P2",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="rb485.u_l_grid[2]",
        name="Grid Voltage P3",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_load_day",
        name="Consumer Energy Consumption Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_load_month",
        name="Consumer Energy Consumption Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_load_year",
        name="Consumer Energy Consumption Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_load_total",
        name="Consumer Energy Consumption Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ac_day",
        name="Inverter Energy Production Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ac_month",
        name="Inverter Energy Production Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ac_year",
        name="Inverter Energy Production Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ac_total",
        name="Inverter Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_feed_day",
        name="Grid Energy Production Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_feed_month",
        name="Grid Energy Production Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_feed_year",
        name="Grid Energy Production Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_feed_total",
        name="Grid Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_feed_absolute_total",
        unique_id="energy.e_grid_feed_absolute_total",  # to avoid collision
        object_names=["energy.e_grid_feed_total"],
        name="Grid Energy Production Absolute Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        get_native_value=get_first_api_response_value_as_absolute_state,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_load_day",
        name="Grid Energy Consumption Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_load_month",
        name="Grid Energy Consumption Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_load_year",
        name="Grid Energy Consumption Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_grid_load_total",
        name="Grid Energy Consumption Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ext_day",
        name="External Energy Production Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ext_month",
        name="External Energy Production Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ext_year",
        name="External Energy Production Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_ext_total",
        name="External Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_day[0]",
        name="Generator A Energy Production Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_month[0]",
        name="Generator A Energy Production Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_year[0]",
        name="Generator A Energy Production Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_total[0]",
        name="Generator A Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_day[1]",
        name="Generator B Energy Production Day",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_month[1]",
        name="Generator B Energy Production Month",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_year[1]",
        name="Generator B Energy Production Year",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_total[1]",
        name="Generator B Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="energy.e_dc_total",
        object_names=["energy.e_dc_total[0]", "energy.e_dc_total[1]"],
        name="All Generators Energy Production Total",
        update_priority=EntityUpdatePriority.INFREQUENT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        get_native_value=sum_api_response_values_as_state,
    ),
    RctPowerSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="io_board.s0_external_power",
        name="External Generator S0 Power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="W",
    ),
]

bitfield_sensor_entity_descriptions: list[RctPowerBitfieldSensorEntityDescription] = [
    RctPowerBitfieldSensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="fault.flt",
        object_names=[
            "fault[0].flt",
            "fault[1].flt",
            "fault[2].flt",
            "fault[3].flt",
        ],
        name="Faults",
        update_priority=EntityUpdatePriority.FREQUENT,
        unique_id=f"{0x37F9D5CA}",  # for backwards-compatibility
    ),
    RctPowerBitfieldSensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.bat_status",
        name="Battery Status",
        update_priority=EntityUpdatePriority.FREQUENT,
        get_native_value=get_first_api_response_value_as_battery_status,
        options=available_battery_status,
    ),
]


def get_battery_tower_connection_entity_description(
    object_prefix: str,
    name_prefix: str,
    get_device_info: Callable[[RctPowerEntity], DeviceInfo | None],
) -> RctPowerBinarySensorEntityDescription:
    """Whether the tower is connected to the battery DC bus of the inverter."""
    return RctPowerBinarySensorEntityDescription(
        get_device_info=get_device_info,
        key=f"{object_prefix}.connected",
        object_names=[f"{object_prefix}.voltage", "adc.u_acc"],
        unique_id=f"{object_prefix}-tower_connected",
        name=f"{name_prefix} Connection",
        icon="mdi:battery-sync",
        update_priority=EntityUpdatePriority.FREQUENT,
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        get_is_on=is_tower_connected,
        get_extra_state_attributes=get_tower_connection_attributes,
    )


binary_sensor_entity_descriptions: list[RctPowerBinarySensorEntityDescription] = [
    RctPowerBinarySensorEntityDescription(
        get_device_info=get_inverter_device_info,
        key="power_mng.use_grid_power_enable",
        name="Allow External Power",
        update_priority=EntityUpdatePriority.FREQUENT,
        get_is_on=get_first_api_response_value_as_bool,
    ),
    get_battery_tower_connection_entity_description(
        "battery", "Battery", get_battery_device_info
    ),
    get_battery_tower_connection_entity_description(
        "battery_placeholder[0]", "Battery Tower 2", get_battery_tower_2_device_info
    ),
    RctPowerBinarySensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.bat_status.balancing",
        object_names=["battery.bat_status"],
        unique_id="battery-status-balancing",
        name="Battery Balancing",
        icon="mdi:scale-balance",
        update_priority=EntityUpdatePriority.FREQUENT,
        device_class=BinarySensorDeviceClass.RUNNING,
        get_is_on=is_battery_balancing,
    ),
    RctPowerBinarySensorEntityDescription(
        get_device_info=get_battery_device_info,
        key="battery.bat_status.calibrating",
        object_names=["battery.bat_status"],
        unique_id="battery-status-calibrating",
        name="Battery Calibration",
        icon="mdi:battery-sync-outline",
        update_priority=EntityUpdatePriority.FREQUENT,
        device_class=BinarySensorDeviceClass.RUNNING,
        get_is_on=is_battery_calibrating,
    ),
]

sensor_entity_descriptions = [
    *battery_sensor_entity_descriptions,
    *battery_tower_2_sensor_entity_descriptions,
    *battery_cell_sensor_entity_descriptions,
    *inverter_sensor_entity_descriptions,
    *bitfield_sensor_entity_descriptions,
]

all_entity_descriptions = [
    *sensor_entity_descriptions,
    *binary_sensor_entity_descriptions,
]
