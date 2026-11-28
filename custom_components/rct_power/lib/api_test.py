"""Tests for the RCT Power API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from custom_components.rct_power.lib.api import (
    InvalidApiResponse,
    RctPowerApiClient,
)


async def test_connection_error_returns_invalid_responses() -> None:
    client = RctPowerApiClient(hostname="192.0.2.10", port=8899)
    object_ids = [1, 2]

    with patch(
        "custom_components.rct_power.lib.api.open_connection",
        new_callable=AsyncMock,
        side_effect=OSError("No route to host"),
    ):
        responses = await client.async_get_data(object_ids)

    assert set(responses) == set(object_ids)
    assert all(
        isinstance(response, InvalidApiResponse)
        and response.cause == "CONNECTION_ERROR"
        for response in responses.values()
    )
