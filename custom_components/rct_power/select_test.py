"""Test writing the SOC strategy and the external battery power."""

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
from homeassistant.components.select import (
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
)
from homeassistant.components.select import (
    DOMAIN as SELECT_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from rctclient.registry import REGISTRY

from custom_components.rct_power.const import (
    CONF_ALLOW_BATTERY_WRITES,
    CONF_ALLOW_WRITES,
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    DEFAULT_PORT,
    DOMAIN,
)
from custom_components.rct_power.lib.api import RctPowerData, ValidApiResponse

STRATEGY_ID = REGISTRY.get_by_name("power_mng.soc_strategy").object_id
TARGET_ID = REGISTRY.get_by_name("power_mng.soc_target_set").object_id
POWER_ID = REGISTRY.get_by_name("power_mng.battery_power_extern").object_id
SELECT_ENTITY_ID = "select.battery_at_master_master_battery_state_of_charge_strategy"
NUMBER_ENTITY_ID = "number.battery_at_master_master_battery_external_power"


def response(object_id: int, value: float) -> ValidApiResponse:
    return ValidApiResponse(
        object_id=object_id, time=datetime.now(tz=UTC), value=value, raw=None
    )


async def fake_get_data(object_ids: list[int]) -> RctPowerData:
    data: RctPowerData = {}
    for object_id in object_ids:
        name = REGISTRY.get_by_id(object_id).name
        if name == "inverter_sn":
            data[object_id] = response(object_id, "INV1")  # type: ignore
        elif name == "android_description":
            data[object_id] = response(object_id, "Master")  # type: ignore
        elif object_id == STRATEGY_ID:
            data[object_id] = response(object_id, 4)
        elif object_id == TARGET_ID:
            data[object_id] = response(object_id, 0.97)
        elif object_id == POWER_ID:
            data[object_id] = response(object_id, 0.0)
    return data


async def setup(hass: HomeAssistant, options: dict) -> None:
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
    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=fake_get_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def select_option(hass: HomeAssistant, option: str) -> None:
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: SELECT_ENTITY_ID, ATTR_OPTION: option},
        blocking=True,
    )


async def test_no_select_without_allow_battery_writes(hass: HomeAssistant) -> None:
    """The power reduction option alone does not allow battery settings."""
    await setup(hass, {CONF_ALLOW_WRITES: True})
    assert hass.states.async_all(SELECT_DOMAIN) == []
    assert hass.states.get(NUMBER_ENTITY_ID) is None
    assert hass.states.get("number.master_external_power_reduction") is not None


async def test_write_soc_strategy(hass: HomeAssistant) -> None:
    await setup(hass, {CONF_ALLOW_BATTERY_WRITES: True})

    # the battery option alone does not allow the power reduction
    assert hass.states.get("number.master_external_power_reduction") is None

    state = hass.states.get(SELECT_ENTITY_ID)
    assert state is not None
    assert state.state == "Internal"
    assert "External" in state.attributes["options"]

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=response),
    ) as write:
        # an unchanged option is not written
        await select_option(hass, "Internal")
        write.assert_not_called()

        await select_option(hass, "External")
        write.assert_awaited_once_with(STRATEGY_ID, 2)

    assert hass.states.get(SELECT_ENTITY_ID).state == "External"  # type: ignore

    with pytest.raises(ServiceValidationError):
        await select_option(hass, "Middle battery voltage")


async def test_soc_strategy_not_accepted(hass: HomeAssistant) -> None:
    await setup(hass, {CONF_ALLOW_BATTERY_WRITES: True})

    with (
        patch(
            "custom_components.rct_power.RctPowerApiClient.async_write_value",
            new=AsyncMock(return_value=response(STRATEGY_ID, 4)),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await select_option(hass, "Constant")

    assert hass.states.get(SELECT_ENTITY_ID).state == "Internal"  # type: ignore


async def test_write_battery_external_power(hass: HomeAssistant) -> None:
    """Negative values charge the battery, positive values discharge it."""
    await setup(hass, {CONF_ALLOW_BATTERY_WRITES: True})

    state = hass.states.get(NUMBER_ENTITY_ID)
    assert state is not None
    assert state.state == "0.0"
    assert state.attributes["unit_of_measurement"] == "W"

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=response),
    ) as write:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: NUMBER_ENTITY_ID, ATTR_VALUE: -3000},
            blocking=True,
        )
        write.assert_awaited_once_with(POWER_ID, -3000)

    assert hass.states.get(NUMBER_ENTITY_ID).state == "-3000.0"  # type: ignore
    # the read-only sensor follows the written value
    assert (
        hass.states.get("sensor.battery_at_master_master_battery_external_power").state
        == "-3000.0"
    )  # type: ignore


async def test_write_constant_soc_target(hass: HomeAssistant) -> None:
    """The inverter takes a fraction, Home Assistant shows percent."""
    await setup(hass, {CONF_ALLOW_BATTERY_WRITES: True})

    entity_id = (
        "number.battery_at_master_master_battery_state_of_charge_constant_target"
    )
    assert hass.states.get(entity_id).state == "97.0"  # type: ignore

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=response),
    ) as write:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 96.5},
            blocking=True,
        )
        write.assert_awaited_once_with(TARGET_ID, 0.965)

    assert hass.states.get(entity_id).state == "96.5"  # type: ignore
