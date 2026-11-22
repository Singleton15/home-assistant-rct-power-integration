"""Test writing the external power reduction."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.number import (
    ATTR_VALUE,
    SERVICE_SET_VALUE,
)
from homeassistant.components.number import (
    DOMAIN as NUMBER_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power.const import (
    CONF_ALLOW_WRITES,
    CONF_ENTITY_PREFIX,
    CONF_GOD_MODE,
    CONF_HOSTNAME,
    DEFAULT_PORT,
    DOMAIN,
)
from custom_components.rct_power.lib.api import RctPowerData, ValidApiResponse
from custom_components.rct_power.lib.registry import REGISTRY

REDUCTION_ID = REGISTRY.get_by_name("buf_v_control.power_reduction").object_id
ENTITY_ID = "number.master_external_power_reduction"
PHASE_OFFSET_OBJECT_IDS = [
    REGISTRY.get_by_name(f"phase_power_offset[{phase}]").object_id for phase in range(3)
]
MAINTENANCE_CHARGE_POWER_ID = REGISTRY.get_by_name(
    "power_mng.soc_charge_power"
).object_id
CALIBRATION_CHARGE_POWER_ID = REGISTRY.get_by_name(
    "power_mng.calib_charge_power"
).object_id
MAX_BATTERY_TO_GRID_POWER_ID = REGISTRY.get_by_name("p_rec_lim[1]").object_id
GRID_POWER_OFFSET_ID = REGISTRY.get_by_name("grid_power_offset").object_id
BATTERY_CONVERTER_CURRENT_IDS = {
    "acc_conv.i_charge_max": 0xB0FA4D23,
    "acc_conv.i_discharge_max": 0xC642B9D6,
}


def response(value: float, object_id: int = REDUCTION_ID) -> ValidApiResponse:
    return ValidApiResponse(
        object_id=object_id, time=datetime.now(tz=UTC), value=value, raw=None
    )


async def fake_get_data(object_ids: list[int]) -> RctPowerData:
    data: RctPowerData = {}
    for object_id in object_ids:
        name = REGISTRY.get_by_id(object_id).name
        if name == "inverter_sn":
            data[object_id] = ValidApiResponse(
                object_id=object_id, time=datetime.now(tz=UTC), value="INV1", raw=None
            )
        elif name == "android_description":
            data[object_id] = ValidApiResponse(
                object_id=object_id, time=datetime.now(tz=UTC), value="Master", raw=None
            )
        elif object_id == REDUCTION_ID:
            data[object_id] = response(1.0)
        elif object_id in PHASE_OFFSET_OBJECT_IDS:
            data[object_id] = response(10.0, object_id)
        elif object_id == MAINTENANCE_CHARGE_POWER_ID:
            data[object_id] = response(1000.0, object_id)
        elif object_id == CALIBRATION_CHARGE_POWER_ID:
            data[object_id] = response(3000.0, object_id)
        elif object_id == MAX_BATTERY_TO_GRID_POWER_ID:
            data[object_id] = response(3000.0, object_id)
        elif object_id == GRID_POWER_OFFSET_ID:
            data[object_id] = response(10.0, object_id)
        elif object_id in BATTERY_CONVERTER_CURRENT_IDS.values():
            data[object_id] = response(25.0, object_id)
    return data


def create_entry(hass: HomeAssistant, options: dict) -> MockConfigEntry:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "localhost",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: "Master",
        },
        options=options,
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=fake_get_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def set_value(
    hass: HomeAssistant,
    value: float,
    entity_id: str = ENTITY_ID,
) -> None:
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )


async def test_no_number_without_allow_writes(hass: HomeAssistant) -> None:
    await setup(hass, create_entry(hass, {}))
    assert hass.states.async_all(NUMBER_DOMAIN) == []


async def test_phase_offset_numbers_require_god_mode(hass: HomeAssistant) -> None:
    """Regular write permission does not expose the God mode offset controls."""
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))

    assert hass.states.get("number.master_grid_power_offset") is None
    assert hass.states.get("sensor.master_grid_power_offset") is None
    for phase in range(1, 4):
        assert (
            hass.states.get(
                f"number.master_power_sensor_phase_{phase}_offset_correction"
            )
            is None
        )
    assert hass.states.get("number.master_maintenance_charge_power") is None
    assert (
        hass.states.get("number.master_battery_converter_maximum_charging_current")
        is None
    )
    assert (
        hass.states.get("number.master_battery_converter_maximum_discharging_current")
        is None
    )


async def test_grid_power_offset_requires_factory_mode(hass: HomeAssistant) -> None:
    """Expose the grid offset read/write entities only in Factory mode."""
    assert GRID_POWER_OFFSET_ID == 0x5A55C519
    assert REGISTRY.get_by_id(0x2848A1EE).name == "grid_offset"
    await setup(hass, create_entry(hass, {CONF_GOD_MODE: True}))
    number_entity_id = "number.master_grid_power_offset"
    sensor_entity_id = "sensor.master_grid_power_offset"

    number_state = hass.states.get(number_entity_id)
    assert number_state is not None
    assert number_state.state == "10.0"
    assert number_state.attributes["unit_of_measurement"] == "W"
    assert number_state.attributes["min"] == -50
    assert number_state.attributes["max"] == 50
    assert number_state.attributes["step"] == 1

    sensor_state = hass.states.get(sensor_entity_id)
    assert sensor_state is not None
    assert sensor_state.state == "10.0"
    assert sensor_state.attributes["unit_of_measurement"] == "W"

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value, object_id)),
    ) as write:
        await set_value(hass, -50, number_entity_id)
        write.assert_awaited_once_with(GRID_POWER_OFFSET_ID, -50)

        await set_value(hass, 50, number_entity_id)
        assert write.await_count == 2
        write.assert_awaited_with(GRID_POWER_OFFSET_ID, 50)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, -51, number_entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 51, number_entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 0.5, number_entity_id)

    assert hass.states.get(number_entity_id).state == "50.0"  # type: ignore
    assert hass.states.get(sensor_entity_id).state == "50.0"  # type: ignore


async def test_write_maintenance_charge_power(hass: HomeAssistant) -> None:
    """Expose the maintenance charge power writer only in God mode."""
    await setup(hass, create_entry(hass, {CONF_GOD_MODE: True}))
    entity_id = "number.master_maintenance_charge_power"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "1000.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["min"] == 100
    assert state.attributes["max"] == 4000
    assert state.attributes["step"] == 100

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value, object_id)),
    ) as write:
        await set_value(hass, 1500, entity_id)
        write.assert_awaited_once_with(MAINTENANCE_CHARGE_POWER_ID, 1500)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, 4100, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 1550, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 0, entity_id)

    assert hass.states.get(entity_id).state == "1500.0"  # type: ignore


async def test_write_calibration_charge_power(hass: HomeAssistant) -> None:
    """Expose the calibration charge power writer with inverter write permission."""
    assert CALIBRATION_CHARGE_POWER_ID == 0xF393B7B0
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))
    entity_id = "number.master_battery_calibration_charge_power"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "3000.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 6000
    assert state.attributes["step"] == 1

    entity_entry = er.async_get(hass).async_get(entity_id)
    assert entity_entry is not None and entity_entry.device_id is not None
    device = dr.async_get(hass).async_get(entity_entry.device_id)
    assert device is not None
    assert (DOMAIN, "INV1") in device.identifiers

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value, object_id)),
    ) as write:
        await set_value(hass, 0, entity_id)
        write.assert_awaited_once_with(CALIBRATION_CHARGE_POWER_ID, 0)

        await set_value(hass, 6000, entity_id)
        assert write.await_count == 2
        write.assert_awaited_with(CALIBRATION_CHARGE_POWER_ID, 6000)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, 6001, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, -1, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 1.5, entity_id)

    assert hass.states.get(entity_id).state == "6000.0"  # type: ignore


@pytest.mark.parametrize(
    ("object_name", "number_entity_suffix"),
    [
        (
            "acc_conv.i_charge_max",
            "battery_converter_maximum_charging_current",
        ),
        (
            "acc_conv.i_discharge_max",
            "battery_converter_maximum_discharging_current",
        ),
    ],
)
async def test_write_battery_converter_current_limit(
    hass: HomeAssistant,
    object_name: str,
    number_entity_suffix: str,
) -> None:
    """Expose converter current limit writers only in God mode."""
    await setup(hass, create_entry(hass, {CONF_GOD_MODE: True}))
    entity_id = f"number.master_{number_entity_suffix}"
    object_id = BATTERY_CONVERTER_CURRENT_IDS[object_name]

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "25.0"
    assert state.attributes["unit_of_measurement"] == "A"
    assert state.attributes["min"] == 1
    assert state.attributes["max"] == 25
    assert state.attributes["step"] == 1

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda obj_id, value: response(value, obj_id)),
    ) as write:
        await set_value(hass, 20, entity_id)
        write.assert_awaited_once_with(object_id, 20)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, 26, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 0, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 20.5, entity_id)

    assert hass.states.get(entity_id).state == "20.0"  # type: ignore


@pytest.mark.parametrize(
    ("phase", "object_id"),
    [
        (1, PHASE_OFFSET_OBJECT_IDS[0]),
        (2, PHASE_OFFSET_OBJECT_IDS[1]),
        (3, PHASE_OFFSET_OBJECT_IDS[2]),
    ],
)
async def test_write_phase_power_offset(
    hass: HomeAssistant,
    phase: int,
    object_id: int,
) -> None:
    """Write a phase offset only with God mode and enforce its range and step."""
    await setup(hass, create_entry(hass, {CONF_GOD_MODE: True}))
    entity_id = f"number.master_power_sensor_phase_{phase}_offset_correction"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "10.0"
    assert state.attributes["min"] == 0
    assert state.attributes["max"] == 50
    assert state.attributes["step"] == 1

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda obj_id, value: response(value, obj_id)),
    ) as write:
        await set_value(hass, 20, entity_id)
        write.assert_awaited_once_with(object_id, 20)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, 51, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, -1, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 20.5, entity_id)

    assert hass.states.get(entity_id).state == "20.0"  # type: ignore


async def test_write_external_power_reduction(hass: HomeAssistant) -> None:
    """The inverter takes a fraction, Home Assistant shows percent."""
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "100.0"
    assert state.attributes["unit_of_measurement"] == "%"

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value)),
    ) as write:
        # an unchanged value is not written
        await set_value(hass, 100)
        write.assert_not_called()

        await set_value(hass, 60)
        write.assert_awaited_once_with(REDUCTION_ID, 0.6)

    assert hass.states.get(ENTITY_ID).state == "60.0"  # type: ignore
    # the read-only sensor follows the written value
    [sensor] = [
        s
        for s in hass.states.async_all("sensor")
        if s.entity_id.endswith("_external_power_reduction")
    ]
    assert sensor.state == "60.0"

    with pytest.raises(ServiceValidationError):
        await set_value(hass, 120)


async def test_write_max_battery_to_grid_power(hass: HomeAssistant) -> None:
    """Expose the battery-to-grid limit writer with inverter write permission."""
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))
    entity_id = "number.master_max_battery_to_grid_power"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "3000.0"
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["min"] == -6000
    assert state.attributes["max"] == 6000
    assert state.attributes["step"] == 1

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value, object_id)),
    ) as write:
        await set_value(hass, -6000, entity_id)
        write.assert_awaited_once_with(MAX_BATTERY_TO_GRID_POWER_ID, -6000)
        await set_value(hass, 6000, entity_id)
        assert write.await_count == 2
        write.assert_awaited_with(MAX_BATTERY_TO_GRID_POWER_ID, 6000)

        with pytest.raises(ServiceValidationError):
            await set_value(hass, -6001, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 6001, entity_id)
        with pytest.raises(ServiceValidationError):
            await set_value(hass, 1.5, entity_id)

    assert hass.states.get(entity_id).state == "6000.0"  # type: ignore


async def test_write_not_accepted(hass: HomeAssistant) -> None:
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))

    with (
        patch(
            "custom_components.rct_power.RctPowerApiClient.async_write_value",
            new=AsyncMock(return_value=response(1.0)),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await set_value(hass, 40)

    assert hass.states.get(ENTITY_ID).state == "100.0"  # type: ignore


async def test_removes_old_grid_feed_power_limit(hass: HomeAssistant) -> None:
    config_entry = create_entry(hass, {CONF_ALLOW_WRITES: True})
    entity_registry = er.async_get(hass)
    old = entity_registry.async_get_or_create(
        NUMBER_DOMAIN,
        DOMAIN,
        "test-grid_feed_power_limit",
        config_entry=config_entry,
    )

    await setup(hass, config_entry)

    assert entity_registry.async_get(old.entity_id) is None
    assert hass.states.get(ENTITY_ID) is not None
