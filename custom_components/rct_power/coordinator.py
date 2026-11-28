from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, EVENT_UPDATE_COMPLETE, LOGGER
from .lib.api import (
    ApiResponseValue,
    InvalidApiResponse,
    RctPowerApiClient,
    RctPowerData,
    ValidApiResponse,
)


class RctPowerDataUpdateCoordinator(DataUpdateCoordinator[RctPowerData]):
    """Class to manage fetching data from the rct power inverter API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        *,
        client: RctPowerApiClient,
        name_suffix: str,
        object_ids: list[int],
        update_interval: int,  # in seconds
        missed_response_tolerance: int = 0,
    ) -> None:
        self.client = client
        self.object_ids = object_ids
        self.update_priority = name_suffix
        self.missed_response_tolerance = missed_response_tolerance
        self._missed_responses: dict[int, int] = {}
        self._last_valid_responses: dict[int, ValidApiResponse] = {}
        self.last_update_had_valid_response = False
        self._update_completed = False
        super().__init__(
            hass=hass,
            config_entry=entry,
            logger=LOGGER,
            name=f"{DOMAIN} {entry.unique_id} {name_suffix}",
            update_interval=timedelta(seconds=update_interval),
        )

    def get_latest_response(
        self, object_id: int
    ) -> ValidApiResponse | InvalidApiResponse | None:
        return (self.data or {}).get(object_id)

    def get_valid_value_or(
        self, object_id: int, default_value: ApiResponseValue
    ) -> ApiResponseValue:
        latest_response = self.get_latest_response(object_id)

        if isinstance(latest_response, ValidApiResponse):
            return latest_response.value
        return default_value

    def has_valid_value(self, object_id: int) -> bool:
        return isinstance(self.get_latest_response(object_id), ValidApiResponse)

    @property
    def has_available_values(self) -> bool:
        return self.last_update_success and any(
            self.has_valid_value(object_id) for object_id in self.object_ids
        )

    def record_valid_response(self, response: ValidApiResponse) -> None:
        """Track a successful write as the latest valid response."""
        self._missed_responses[response.object_id] = 0
        self._last_valid_responses[response.object_id] = response

    async def _async_update_data(self) -> RctPowerData:
        self.last_update_had_valid_response = False
        if not self.object_ids:
            self._update_completed = True
            return {}
        responses = await self.client.async_get_data(object_ids=self.object_ids)
        self.last_update_had_valid_response = any(
            isinstance(response, ValidApiResponse) for response in responses.values()
        )
        data: RctPowerData = {}
        for object_id in self.object_ids:
            response = responses.get(object_id)
            if isinstance(response, ValidApiResponse):
                self._missed_responses[object_id] = 0
                self._last_valid_responses[object_id] = response
                data[object_id] = response
                continue

            missed_responses = self._missed_responses.get(object_id, 0) + 1
            self._missed_responses[object_id] = missed_responses
            if (
                missed_responses <= self.missed_response_tolerance
                and object_id in self._last_valid_responses
            ):
                data[object_id] = self._last_valid_responses[object_id]
            elif response is not None:
                data[object_id] = response

        self._update_completed = True
        return data

    async def _async_refresh(
        self,
        log_failures: bool = True,
        raise_on_auth_failed: bool = False,
        scheduled: bool = False,
        raise_on_entry_error: bool = False,
    ) -> None:
        """Refresh data and fire an event after coordinator listeners are updated."""
        self._update_completed = False
        await super()._async_refresh(
            log_failures=log_failures,
            raise_on_auth_failed=raise_on_auth_failed,
            scheduled=scheduled,
            raise_on_entry_error=raise_on_entry_error,
        )
        if self._update_completed:
            self.hass.bus.async_fire(
                EVENT_UPDATE_COMPLETE,
                {
                    "config_entry_id": self.config_entry.entry_id,
                    "update_priority": self.update_priority,
                },
            )
