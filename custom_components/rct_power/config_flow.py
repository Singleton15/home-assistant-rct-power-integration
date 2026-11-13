"""Adds config flow for RCT Power."""

from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.core import callback

from .const import (
    CONF_ALLOW_BATTERY_WRITES,
    CONF_ALLOW_WRITES,
    CONF_ENTITY_PREFIX,
    CONF_GOD_MODE,
    CONF_GOD_MODE_CONFIRMATION,
    CONF_HOSTNAME,
    CONF_RESTART_SERIAL_NUMBER,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_PORT,
    DOMAIN,
    ConfScanInterval,
    ScanIntervalDefault,
)
from .lib.api import RctPowerApiClient


class RctPowerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for rct_power."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = RctPowerApiClient(
                hostname=user_input[CONF_HOSTNAME],
                port=user_input[CONF_PORT],
            )
            serial_number = await client.get_serial_number()

            if serial_number is not None:
                await self.async_set_unique_id(serial_number)

                return self.async_create_entry(
                    title=self.get_title(user_input),
                    data=user_input,
                    description_placeholders={
                        "repo_url": "https://github.com/weltenwort/home-assistant-rct-power-integration"
                    },
                )
            else:
                errors["base"] = "connect"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_FLOW_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def get_title(user_input: dict[str, Any]) -> str:
        return (
            f"RCT Power Inverter at {user_input[CONF_HOSTNAME]}:{user_input[CONF_PORT]}"
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RctPowerOptionsFlowHandler:
        return RctPowerOptionsFlowHandler()


class RctPowerOptionsFlowHandler(config_entries.OptionsFlow):
    """Config flow options handler for rct_power."""

    _pending_options: dict[str, Any] | None = None

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_user(user_input=user_input)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if user_input.get(
                CONF_GOD_MODE, False
            ) and not self.config_entry.options.get(CONF_GOD_MODE, False):
                self._pending_options = user_input
                return await self.async_step_confirm_god_mode()
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    **self.config_entry.options,
                    CONF_RESTART_SERIAL_NUMBER: self.config_entry.options.get(
                        CONF_RESTART_SERIAL_NUMBER, self.config_entry.unique_id
                    ),
                },
            ),
        )

    async def async_step_confirm_god_mode(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_GOD_MODE_CONFIRMATION, False):
                assert self._pending_options is not None
                return self.async_create_entry(data=self._pending_options)
            errors["base"] = "confirmation_required"

        return self.async_show_form(
            step_id="confirm_god_mode",
            data_schema=vol.Schema(
                {vol.Required(CONF_GOD_MODE_CONFIRMATION, default=False): bool}
            ),
            errors=errors,
        )


CONFIG_FLOW_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOSTNAME): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_ENTITY_PREFIX, default=DEFAULT_ENTITY_PREFIX): str,
    }
)


OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(
            ConfScanInterval.VERY_FREQUENT.value,
            default=ScanIntervalDefault.VERY_FREQUENT,
        ): cv.positive_int,
        vol.Optional(
            ConfScanInterval.FREQUENT.value, default=ScanIntervalDefault.FREQUENT
        ): cv.positive_int,
        vol.Optional(
            ConfScanInterval.INFREQUENT.value, default=ScanIntervalDefault.INFREQUENT
        ): cv.positive_int,
        vol.Optional(
            ConfScanInterval.STATIC.value, default=ScanIntervalDefault.STATIC
        ): cv.positive_int,
        # only enable on the inverter that controls the plant (the master)
        vol.Optional(CONF_ALLOW_WRITES, default=False): bool,
        # every inverter keeps its own battery settings
        vol.Optional(CONF_ALLOW_BATTERY_WRITES, default=False): bool,
        vol.Optional(CONF_GOD_MODE, default=False): bool,
        vol.Optional(CONF_RESTART_SERIAL_NUMBER): vol.All(str, vol.Length(min=1)),
    }
)
