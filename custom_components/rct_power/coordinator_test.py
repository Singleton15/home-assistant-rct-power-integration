"""Test polling coordinator response tolerance."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power.coordinator import RctPowerDataUpdateCoordinator
from custom_components.rct_power.lib.api import InvalidApiResponse, ValidApiResponse

OBJECT_ID = 1


def valid_response(value: int) -> ValidApiResponse:
    return ValidApiResponse(
        object_id=OBJECT_ID,
        time=datetime.now(tz=UTC),
        value=value,
    )


def invalid_response() -> InvalidApiResponse:
    return InvalidApiResponse(
        object_id=OBJECT_ID,
        time=datetime.now(tz=UTC),
        cause="OBJECT_READ_TIMEOUT",
    )


async def refresh(
    coordinator: RctPowerDataUpdateCoordinator,
) -> dict[int, ValidApiResponse | InvalidApiResponse]:
    data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(data)
    return data


async def test_tolerated_misses_keep_last_value_until_limit(
    hass: HomeAssistant,
) -> None:
    client = AsyncMock()
    client.async_get_data.side_effect = [
        {OBJECT_ID: valid_response(42)},
        {OBJECT_ID: invalid_response()},
        {OBJECT_ID: invalid_response()},
        {},
        {OBJECT_ID: invalid_response()},
        {OBJECT_ID: valid_response(99)},
        {OBJECT_ID: invalid_response()},
    ]
    coordinator = RctPowerDataUpdateCoordinator(
        hass,
        MockConfigEntry(domain="rct_power", data={}),
        client=client,
        name_suffix="frequent",
        object_ids=[OBJECT_ID],
        update_interval=30,
        missed_response_tolerance=3,
    )

    assert (await refresh(coordinator))[OBJECT_ID].value == 42
    for _ in range(3):
        assert (await refresh(coordinator))[OBJECT_ID].value == 42
        assert coordinator.has_valid_value(OBJECT_ID)

    assert isinstance((await refresh(coordinator))[OBJECT_ID], InvalidApiResponse)
    assert not coordinator.has_valid_value(OBJECT_ID)

    assert (await refresh(coordinator))[OBJECT_ID].value == 99
    assert (await refresh(coordinator))[OBJECT_ID].value == 99


async def test_zero_tolerance_preserves_immediate_unavailability(
    hass: HomeAssistant,
) -> None:
    client = AsyncMock()
    client.async_get_data.side_effect = [
        {OBJECT_ID: valid_response(42)},
        {OBJECT_ID: invalid_response()},
    ]
    coordinator = RctPowerDataUpdateCoordinator(
        hass,
        MockConfigEntry(domain="rct_power", data={}),
        client=client,
        name_suffix="frequent",
        object_ids=[OBJECT_ID],
        update_interval=30,
    )

    await refresh(coordinator)
    assert isinstance((await refresh(coordinator))[OBJECT_ID], InvalidApiResponse)
    assert not coordinator.has_valid_value(OBJECT_ID)
