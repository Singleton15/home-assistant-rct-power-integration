"""Test writing the external power setting."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from homeassistant.const import ATTR_ENTITY_ID, CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from rctclient.registry import REGISTRY

from custom_components.rct_power.const import (
    CONF_ALLOW_WRITES,
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    DEFAULT_PORT,
    DOMAIN,
)
from custom_components.rct_power.lib.api import RctPowerData, ValidApiResponse

SWITCH_ID = REGISTRY.get_by_name("power_mng.use_grid_power_enable").object_id
SWITCH_ENTITY_ID = "switch.master_allow_external_power"


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


async def fake_get_data(object_ids: list[int]) -> RctPowerData:
    values = {
        REGISTRY.get_by_name("inverter_sn").object_id: "INV1",
        REGISTRY.get_by_name("android_description").object_id: "Master",
        SWITCH_ID: False,
    }
    return {
        object_id: ValidApiResponse(
            object_id=object_id,
            time=datetime.now(tz=UTC),
            value=values[object_id],
        )
        for object_id in object_ids
        if object_id in values
    }


async def setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_get_data",
        side_effect=fake_get_data,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def turn_switch(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(
        "switch",
        service,
        {ATTR_ENTITY_ID: SWITCH_ENTITY_ID},
        blocking=True,
    )


def response(value: bool) -> ValidApiResponse:
    return ValidApiResponse(
        object_id=SWITCH_ID,
        time=datetime.now(tz=UTC),
        value=value,
    )


async def test_no_switch_without_allow_writes(hass: HomeAssistant) -> None:
    await setup(hass, create_entry(hass, {}))
    assert hass.states.async_all("switch") == []


async def test_write_allow_external_power(hass: HomeAssistant) -> None:
    await setup(hass, create_entry(hass, {CONF_ALLOW_WRITES: True}))
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state is not None
    assert state.state == "off"

    with patch(
        "custom_components.rct_power.RctPowerApiClient.async_write_value",
        new=AsyncMock(side_effect=lambda object_id, value: response(value)),
    ) as write:
        await turn_switch(hass, "turn_on")
        write.assert_awaited_once_with(SWITCH_ID, True)
        assert hass.states.get(SWITCH_ENTITY_ID).state == "on"  # type: ignore

        await turn_switch(hass, "turn_off")
        assert write.await_count == 2
        write.assert_awaited_with(SWITCH_ID, False)
        assert hass.states.get(SWITCH_ENTITY_ID).state == "off"  # type: ignore
