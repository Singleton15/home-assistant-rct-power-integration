from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ENTITY_PREFIX, DOMAIN, EVENT_UPDATE_COMPLETE, LOGGER
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
    ) -> None:
        self.client = client
        self.object_ids = object_ids
        self.update_priority = name_suffix
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
        return self.data.get(object_id)

    def get_valid_value_or(
        self, object_id: int, default_value: ApiResponseValue
    ) -> ApiResponseValue:
        latest_response = self.get_latest_response(object_id)

        if isinstance(latest_response, ValidApiResponse):
            return latest_response.value
        return default_value

    def has_valid_value(self, object_id: int) -> bool:
        return isinstance(self.get_latest_response(object_id), ValidApiResponse)

    async def _async_update_data(self) -> RctPowerData:
        if not self.object_ids:
            self._update_completed = True
            return {}
        data = await self.client.async_get_data(object_ids=self.object_ids)
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
                    "entity_prefix": self.config_entry.data[CONF_ENTITY_PREFIX],
                    "update_priority": self.update_priority,
                },
            )
