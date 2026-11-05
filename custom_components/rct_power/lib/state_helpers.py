from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, get_args

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import as_local
from rctclient.types import (
    BatteryModuleResistance,
    BatteryModuleStatistics,
    BatteryModuleStatus,
)

from .api import ApiResponseValue
from .const import (
    FREQUENCY_STATE_DECIMAL_DIGITS,
    NUMERIC_STATE_DECIMAL_DIGITS,
    BatteryStatusFlag,
)


def get_first_api_response_value_as_state(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> StateType:
    if len(values) <= 0:
        return None

    return get_api_response_value_as_state(entity=entity, value=values[0])


def get_api_response_value_as_state(
    entity: SensorEntity,
    value: ApiResponseValue | None,
) -> StateType:
    if isinstance(value, bytes):
        return value.hex()

    if isinstance(
        value,
        (
            tuple,
            BatteryModuleStatus,
            BatteryModuleStatistics,
            BatteryModuleResistance,
        ),
    ):
        return None

    if isinstance(value, (int, float)) and entity.native_unit_of_measurement == "%":
        return round(value * 100, NUMERIC_STATE_DECIMAL_DIGITS)

    if isinstance(value, (int, float)) and entity.native_unit_of_measurement == "Hz":
        return round(value, FREQUENCY_STATE_DECIMAL_DIGITS)

    if isinstance(value, (int, float)):
        return round(value, NUMERIC_STATE_DECIMAL_DIGITS)

    return value


def get_first_api_response_value_as_absolute_state(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> StateType:
    value = get_first_api_response_value_as_state(entity=entity, values=values)

    if isinstance(value, (int, float)):
        return abs(value)

    return value


def get_first_api_response_value_as_bool(
    entity: Any,
    values: list[ApiResponseValue | None],
) -> bool | None:
    match values:
        case [bool() as first_value, *_]:
            return first_value
        case _:
            return None


def sum_api_response_values_as_state(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> float:
    return sum(
        (
            float(state_value)
            for value in values
            if isinstance(
                state_value := get_api_response_value_as_state(entity, value),
                (int, float),
            )
        ),
        0.0,
    )


#
# Battery status
#
BatteryStatus = Literal[
    "normal", "charging", "discharging", "calibrating", "balancing", "other"
]
available_battery_status: list[BatteryStatus] = list(get_args(BatteryStatus))


def get_api_response_value_as_battery_status(
    entity: SensorEntity,
    value: ApiResponseValue | None,
) -> BatteryStatus | None:
    if not isinstance(value, int):
        return None

    match BatteryStatusFlag(value):
        case BatteryStatusFlag.calibrating:
            return "calibrating"
        case BatteryStatusFlag.charging:
            return "charging"
        case BatteryStatusFlag.discharging:
            return "discharging"
        case BatteryStatusFlag.balancing:
            return "balancing"
        case BatteryStatusFlag.normal:
            return "normal"
        case _:
            return "other"


def _get_first_battery_status_flag(
    values: list[ApiResponseValue | None],
) -> BatteryStatusFlag | None:
    match values:
        case [int() as first_value, *_]:
            return BatteryStatusFlag(first_value)
        case _:
            return None


def is_battery_balancing(
    entity: Any, values: list[ApiResponseValue | None]
) -> bool | None:
    """Whether the balancing bit of the battery status is set."""
    flags = _get_first_battery_status_flag(values)
    if flags is None:
        return None
    return BatteryStatusFlag.balancing in flags


def is_battery_calibrating(
    entity: Any, values: list[ApiResponseValue | None]
) -> bool | None:
    """Whether the battery status reports a calibration (charging and discharging)."""
    flags = _get_first_battery_status_flag(values)
    if flags is None:
        return None
    return BatteryStatusFlag.calibrating in flags


def get_first_api_response_value_as_battery_status(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> BatteryStatus | None:
    match values:
        case [firstValue, *_] if firstValue is not None:
            return get_api_response_value_as_battery_status(entity, firstValue)
        case _:
            return None


#
# Bitfield
#
def get_api_response_values_as_bitfield(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> str:
    return "".join(f"{value:b}" for value in values if isinstance(value, int))


#
# Timestamp
#
def get_first_api_response_value_as_timestamp(
    entity: SensorEntity,
    values: list[ApiResponseValue | None],
) -> datetime | None:
    if len(values) <= 0:
        return None

    return get_api_response_value_as_timestamp(entity=entity, value=values[0])


def get_api_response_value_as_timestamp(
    entity: SensorEntity,
    value: ApiResponseValue | None,
) -> datetime | None:
    if isinstance(value, int):
        return as_local(datetime.fromtimestamp(value))  # noqa: DTZ006

    return None
