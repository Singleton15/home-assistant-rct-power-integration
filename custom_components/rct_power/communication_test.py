"""Tests for inverter communication status detection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Self
from unittest.mock import patch

import aiohttp
import pytest
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power.const import (
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    DEFAULT_PORT,
    DOMAIN,
    ConfMissedResponseTolerance,
    EntityUpdatePriority,
)
from custom_components.rct_power.lib.api import RctPowerData, ValidApiResponse
from custom_components.rct_power.lib.registry import REGISTRY


@pytest.mark.parametrize(
    ("http_reachable", "expected_state"),
    [(True, "stale"), (False, "offline")],
)
async def test_status_uses_http_probe_after_fast_polling_fails(
    hass: HomeAssistant,
    http_reachable: bool,
    expected_state: str,
) -> None:
    """Only classify an outage after both fast polling groups stop responding."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "192.0.2.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: "Master",
        },
        options={
            ConfMissedResponseTolerance.VERY_FREQUENT: 1,
            ConfMissedResponseTolerance.FREQUENT: 1,
        },
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    very_frequent_id = REGISTRY.get_by_name("g_sync.p_ac_grid_sum_lp").object_id
    frequent_id = REGISTRY.get_by_name("battery.voltage").object_id
    failing = False

    async def get_data(object_ids: list[int]) -> RctPowerData:
        if failing:
            return {}
        return {
            object_id: ValidApiResponse(
                object_id=object_id,
                time=datetime.now(tz=UTC),
                value=1.0,
            )
            for object_id in object_ids
            if object_id in {very_frequent_id, frequent_id}
        }

    class HttpResponse:
        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

    class HttpSession:
        def get(self, *args: object, **kwargs: object) -> HttpResponse:
            if not http_reachable:
                raise aiohttp.ClientError
            return HttpResponse()

    with (
        patch(
            "custom_components.rct_power.RctPowerApiClient.async_get_data",
            side_effect=get_data,
        ),
        patch(
            "custom_components.rct_power.sensor.async_get_clientsession",
            return_value=HttpSession(),
        ),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.master_communication_status").state == "online"

        failing = True
        coordinators = config_entry.runtime_data.update_coordinators
        very_frequent = coordinators[EntityUpdatePriority.VERY_FREQUENT]
        frequent = coordinators[EntityUpdatePriority.FREQUENT]

        data = await very_frequent._async_update_data()
        very_frequent.async_set_updated_data(data)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.master_communication_status").state == "online"

        data = await frequent._async_update_data()
        frequent.async_set_updated_data(data)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.master_communication_status").state == "online"

        data = await very_frequent._async_update_data()
        very_frequent.async_set_updated_data(data)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.master_communication_status").state == "online"

        data = await frequent._async_update_data()
        frequent.async_set_updated_data(data)
        await hass.async_block_till_done()

    assert hass.states.get("sensor.master_communication_status").state == expected_state
    assert hass.states.get("sensor.master_grid_power").state == "unavailable"
    assert hass.states.get("sensor.battery_at_master_battery_voltage").state == (
        "unavailable"
    )
    assert hass.states.get("sensor.master_communication_status").attributes[
        "options"
    ] == ["online", "offline", "stale"]
