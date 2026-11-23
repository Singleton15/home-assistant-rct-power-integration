"""Test the battery tower and module sensors."""

from __future__ import annotations

import struct
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry
from rctclient.utils import decode_value

from custom_components.rct_power import async_remove_config_entry_device
from custom_components.rct_power.const import (
    CONF_ENTITY_PREFIX,
    CONF_GOD_MODE,
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
from custom_components.rct_power.lib.registry import REGISTRY

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
    "phase_power_offset[0]": struct.pack(">f", 0.5),
    "phase_power_offset[1]": struct.pack(">f", -1.5),
    "phase_power_offset[2]": struct.pack(">f", 2.5),
    "power_mng.soc_charge_power": struct.pack(">f", 1500.5),
    "power_mng.calib_charge_power": struct.pack(">f", 3000.0),
    "p_rec_lim[1]": struct.pack(">f", 3000.0),
    "acc_conv.i_charge_max": struct.pack(">f", 25.0),
    "acc_conv.i_discharge_max": struct.pack(">f", 25.0),
    "csc[0].gain": struct.pack(">f", 0.999758),
    "csc[1].gain": struct.pack(">f", 1.000246),
    "csc[2].gain": struct.pack(">f", 0.998765),
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
        options={CONF_GOD_MODE: True},
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

    state = get_state(hass, "battery_calibration_charge_power")
    assert state.state == "3000.0"
    assert state.attributes["unit_of_measurement"] == "W"

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

    for phase, object_id, expected_value in (
        (1, 0x8114F393, 0.5),
        (2, 0x9521F6C7, -1.5),
        (3, 0xEED7904F, 2.5),
    ):
        assert (
            REGISTRY.get_by_name(f"phase_power_offset[{phase - 1}]").object_id
            == object_id
        )
        state = get_state(hass, f"power_sensor_phase_{phase}_offset_correction")
        assert float(state.state) == pytest.approx(expected_value)

    charge_power_id = REGISTRY.get_by_name("power_mng.soc_charge_power").object_id
    assert charge_power_id == 0x1D2994EA
    state = get_state(hass, "maintenance_charge_power")
    assert float(state.state) == pytest.approx(1500.5)
    assert state.attributes["unit_of_measurement"] == "W"
    assert (
        charge_power_id
        in config_entry.runtime_data.update_coordinators[
            EntityUpdatePriority.INFREQUENT
        ].object_ids
    )

    max_battery_to_grid_power_id = REGISTRY.get_by_name("p_rec_lim[1]").object_id
    assert max_battery_to_grid_power_id == 0x54829753
    state = get_state(hass, "max_battery_to_grid_power")
    assert float(state.state) == pytest.approx(3000.0)
    assert state.attributes["unit_of_measurement"] == "W"
    assert (
        max_battery_to_grid_power_id
        in config_entry.runtime_data.update_coordinators[
            EntityUpdatePriority.INFREQUENT
        ].object_ids
    )

    for object_name, object_id, entity_suffix in (
        (
            "acc_conv.i_charge_max",
            0xB0FA4D23,
            "battery_converter_maximum_charging_current",
        ),
        (
            "acc_conv.i_discharge_max",
            0xC642B9D6,
            "battery_converter_maximum_discharging_current",
        ),
    ):
        assert REGISTRY.get_by_name(object_name).object_id == object_id
        state = get_state(hass, entity_suffix)
        assert float(state.state) == pytest.approx(25.0)
        assert state.attributes["unit_of_measurement"] == "A"
        assert (
            object_id
            in config_entry.runtime_data.update_coordinators[
                EntityUpdatePriority.INFREQUENT
            ].object_ids
        )

    for phase, object_id, expected_value in (
        (1, 0x6A9A9FED, 0.999758),
        (2, 0x93FAD04A, 1.000246),
        (3, 0x86ABDAC9, 0.998765),
    ):
        assert REGISTRY.get_by_name(f"csc[{phase - 1}].gain").object_id == object_id
        state = get_state(hass, f"power_sensor_phase_{phase}_gain_correction")
        assert float(state.state) == pytest.approx(expected_value, abs=1e-6)
        assert state.state != "1.0"

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


async def test_power_sensor_correction_sensors_require_god_mode(
    hass: HomeAssistant,
) -> None:
    """Do not create or poll power sensor correction sensors unless enabled."""
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
    requested_object_ids: set[int] = set()

    async def no_data(object_ids: list[int]) -> RctPowerData:
        requested_object_ids.update(object_ids)
        return {}

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=no_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    correction_names = [
        *(f"phase_power_offset[{phase}]" for phase in range(3)),
        *(f"csc[{phase}].gain" for phase in range(3)),
        "power_mng.soc_charge_power",
        "acc_conv.i_charge_max",
        "acc_conv.i_discharge_max",
    ]
    correction_object_ids = {
        REGISTRY.get_by_name(name).object_id for name in correction_names
    }
    assert requested_object_ids.isdisjoint(correction_object_ids)
    assert not any(
        entity_entry.entity_id.endswith(
            f"power_sensor_phase_{phase}_{correction_type}_correction"
        )
        for entity_entry in er.async_entries_for_config_entry(
            er.async_get(hass), config_entry.entry_id
        )
        for phase in range(1, 4)
        for correction_type in ("offset", "gain")
    )
    assert hass.states.get("sensor.master_maintenance_charge_power") is None
    assert (
        hass.states.get(
            "sensor.master_battery_converter_maximum_charging_current"
        )
        is None
    )
    assert (
        hass.states.get(
            "sensor.master_battery_converter_maximum_discharging_current"
        )
        is None
    )
    max_battery_to_grid_power_id = REGISTRY.get_by_name("p_rec_lim[1]").object_id
    assert max_battery_to_grid_power_id in requested_object_ids
    assert hass.states.get("sensor.master_max_battery_to_grid_power") is not None


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


async def test_update_entity_refreshes_its_polling_coordinator(
    hass: HomeAssistant,
) -> None:
    """A manual update refreshes all values in the entity's polling group."""
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
    assert await async_setup_component(hass, "homeassistant", {})
    target_object_id = REGISTRY.get_by_name("g_sync.p_ac_grid_sum_lp").object_id
    battery_power_object_id = REGISTRY.get_by_name("g_sync.p_acc_lp").object_id
    requested_object_ids: list[list[int]] = []
    should_update = False

    async def get_data(object_ids: list[int]) -> RctPowerData:
        data = await fake_get_data(object_ids)
        if should_update:
            requested_object_ids.append(object_ids)
            data[target_object_id] = ValidApiResponse(
                object_id=target_object_id,
                time=datetime.now(tz=UTC),
                value=3,
            )
        return data

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=get_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = config_entry.runtime_data.update_coordinators[
            EntityUpdatePriority.VERY_FREQUENT
        ]
        should_update = True
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": "sensor.master_grid_power"},
            blocking=True,
        )

    assert len(requested_object_ids) == 1
    assert set(requested_object_ids[0]) == set(coordinator.object_ids)
    assert target_object_id in requested_object_ids[0]
    assert battery_power_object_id in requested_object_ids[0]
    assert hass.states.get("sensor.master_grid_power").state == "3"
