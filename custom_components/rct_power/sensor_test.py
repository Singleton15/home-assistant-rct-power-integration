"""Test the battery tower and module sensors."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry
from rctclient.registry import REGISTRY
from rctclient.utils import decode_value

from custom_components.rct_power import async_remove_config_entry_device
from custom_components.rct_power.const import (
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    DEFAULT_PORT,
    DOMAIN,
    EntityUpdatePriority,
)
from custom_components.rct_power.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.rct_power.lib.api import (
    ApiResponseValue,
    RctPowerData,
    ValidApiResponse,
    get_response_data_type,
)
from custom_components.rct_power.lib.battery_module_helpers_test import (
    encode_module_resistance,
    encode_module_status,
)

RAW_VALUES: dict[str, ApiResponseValue | bytes] = {
    "inverter_sn": "INV1",
    "android_description": "Master",
    "prim_sm.island_flag": 2,
    "power_mng.use_grid_power_enable": True,
    "battery.bms_sn": "BMS1",
    # an inverter without an external generator reports inf here
    "energy.e_ext_total": float("inf"),
    "battery_placeholder[0].bms_sn": "BMS2",
    "battery_placeholder[0].max_cell_voltage": 3.312,
    "battery_placeholder[0].soc": 0.42,
    "battery_placeholder[0].voltage": 463.9,
    # tower 2 is disconnected from the DC bus, tower 1 is balancing
    "adc.u_acc": 479.4,
    "battery.voltage": 479.3,
    "battery.bat_status": 2**11,
    "battery.cells[0]": encode_module_status([(21, 3301, 0), (24, 3312, 0)]),
    "battery_placeholder[0].cells[5]": encode_module_status([(30, 3280, 0)]),
    **{
        f"battery_placeholder[0].cells_resist[{index}]": encode_module_resistance(
            [0.75, 0.75]
        )
        for index in range(5)
    },
    "battery_placeholder[0].cells_resist[5]": encode_module_resistance([0.5, 1.0]),
}


def get_value(name: str) -> ApiResponseValue:
    object_id = REGISTRY.get_by_name(name).object_id
    value = RAW_VALUES[name]
    if isinstance(value, bytes):
        return decode_value(get_response_data_type(object_id), value)  # type: ignore
    return value


async def fake_get_data(object_ids: list[int]) -> RctPowerData:
    names = {REGISTRY.get_by_name(name).object_id: name for name in RAW_VALUES}
    return {
        object_id: ValidApiResponse(
            object_id=object_id,
            time=datetime.now(tz=UTC),
            value=get_value(names[object_id]),
            raw=raw if isinstance(raw := RAW_VALUES[names[object_id]], bytes) else None,
        )
        for object_id in object_ids
        if object_id in names
    }


def get_state(hass: HomeAssistant, entity_id_suffix: str) -> State:
    """Find a state by the end of its entity id, which is prefixed by the device name."""
    [state] = [
        state
        for state in hass.states.async_all("sensor")
        if state.entity_id.endswith(f"_{entity_id_suffix}")
    ]
    return state


async def test_battery_module_sensors(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "localhost",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: "Master",
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=fake_get_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = get_state(hass, "master_battery_module_1_max_cell_voltage")
    assert state.state == "3.312"
    assert state.attributes["cell_voltages"] == [3.301, 3.312]
    assert state.attributes["cell_temperatures"] == [21, 24]

    state = get_state(hass, "master_battery_module_1_cell_voltage_spread")
    assert state.state == "11"

    state = get_state(hass, "master_battery_tower_2_module_6_max_cell_temperature")
    assert state.state == "30"

    state = get_state(hass, "master_battery_tower_2_module_6_max_cell_resistance")
    assert state.state == "1.0"
    assert state.attributes["cell_resistances"] == [0.5, 1.0]

    state = get_state(hass, "master_battery_tower_2_max_cell_voltage")
    assert state.state == "3.312"

    state = get_state(hass, "master_battery_tower_2_max_cell_resistance_deviation")
    assert state.state == "33.3"
    assert state.attributes["max_resistance_cell"] == "M6/C2"

    # modules 2-6 of the first tower have no data, so the tower has no value
    state = get_state(hass, "master_battery_weakest_cell_deviation")
    assert state.state == "unavailable"

    state = get_state(hass, "master_battery_tower_2_state_of_charge")
    assert state.state == "42.0"
    assert state.attributes["unit_of_measurement"] == "%"

    state = get_state(hass, "master_battery_tower_2_voltage")
    assert state.state == "463.9"
    assert state.attributes["unit_of_measurement"] == "V"

    # modules without data are unavailable
    state = get_state(hass, "master_battery_module_2_max_cell_voltage")
    assert state.state == "unavailable"

    # the second tower is a device of its own
    entity_entry = er.async_get(hass).async_get(
        get_state(
            hass, "master_battery_tower_2_module_6_max_cell_temperature"
        ).entity_id
    )
    assert entity_entry is not None and entity_entry.device_id is not None
    device = dr.async_get(hass).async_get(entity_entry.device_id)
    assert device is not None
    assert (DOMAIN, "BMS2") in device.identifiers

    # battery towers hang off the inverter, linked without the deprecated via_device
    inverter = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, "INV1")})
    assert inverter is not None
    assert device.via_device_id == inverter.id
    assert "via_device" not in caplog.text

    def get_binary_state(entity_id_suffix: str) -> State:
        [state] = [
            state
            for state in hass.states.async_all("binary_sensor")
            if state.entity_id.endswith(f"_{entity_id_suffix}")
        ]
        return state

    state = get_binary_state("master_battery_tower_2_connection")
    assert state.state == "off"
    assert state.attributes["voltage_difference"] == -15.5
    assert "unit_of_measurement" not in state.attributes
    assert get_binary_state("master_battery_connection").state == "on"
    assert get_binary_state("master_battery_balancing").state == "on"
    assert get_binary_state("master_battery_calibration").state == "off"
    assert get_binary_state("allow_external_power").state == "on"
    assert get_state(hass, "island_flag").state == "2"
    island_flag_object_id = REGISTRY.get_by_name("prim_sm.island_flag").object_id
    assert (
        island_flag_object_id
        in config_entry.runtime_data.update_coordinators[
            EntityUpdatePriority.FREQUENT
        ].object_ids
    )

    state = get_state(hass, "external_energy_production_total")
    assert state.state == "unknown"
    assert "non-finite" not in caplog.text

    # diagnostics expose decoded values and raw payloads
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diagnostics["entry"]["data"][CONF_HOSTNAME] == "**REDACTED**"
    tower_2_cells = diagnostics["objects"]["battery_placeholder[0].cells[5]"]
    assert tower_2_cells["valid"] is True
    assert tower_2_cells["raw"] == RAW_VALUES["battery_placeholder[0].cells[5]"].hex()  # type: ignore
    assert tower_2_cells["value"]["cells"]["0"]["voltage_mv"] == 3280
    assert diagnostics["objects"]["battery.cells[1]"]["valid"] is False

    # devices with live entities can't be removed, orphaned ones can
    assert not await async_remove_config_entry_device(hass, config_entry, device)
    orphan = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, "None")}
    )
    assert await async_remove_config_entry_device(hass, config_entry, orphan)


async def test_device_without_serial_numbers(hass: HomeAssistant) -> None:
    """A failed serial number read must not create a device called "None"."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "localhost",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: "Master",
        },
        entry_id="test",
        unique_id="INV-FROM-FLOW",
    )
    config_entry.add_to_hass(hass)

    async def no_data(object_ids: list[int]) -> RctPowerData:
        return {}

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=no_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    identifiers = {
        identifier
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), config_entry.entry_id
        )
        for identifier in device.identifiers
    }
    assert (DOMAIN, "None") not in identifiers
    assert (DOMAIN, "INV-FROM-FLOW") in identifiers
    assert (DOMAIN, "INV-FROM-FLOW-tower-1") in identifiers
    assert (DOMAIN, "INV-FROM-FLOW-tower-2") in identifiers
