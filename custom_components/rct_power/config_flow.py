"""Adds config flow for RCT Power."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry, ConfigFlowResult
from homeassistant.const import CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_ALLOW_WRITES,
    CONF_ENTITY_PREFIX,
    CONF_GOD_MODE,
    CONF_GOD_MODE_PASSWORD,
    CONF_HOSTNAME,
    CONF_RESTART_SERIAL_NUMBER,
    CONF_SERVICE_PASSWORD,
    CONF_WRITE_ACCESS,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_PORT,
    DOMAIN,
    ConfMissedResponseTolerance,
    ConfScanInterval,
    MissedResponseToleranceDefault,
    ScanIntervalDefault,
    WriteAccess,
)
from .lib.api import RctPowerApiClient

_PASSWORD_SALT = bytes.fromhex("526b10a48ca2761a205d3ce91ed79293")
_GOD_MODE_PASSWORD_HASH = bytes.fromhex(
    "95f68bc7aaebd8ae37f925ecca6505425097a8ea49147a2aa7fce5b82cfd4125"
)
_SERVICE_PASSWORD_HASH = bytes.fromhex(
    "067fb99ac1cbf2de3a3321a7271381b2fdbba06469c08df53e1ebfab398b1e39"
)
_PASSWORD_ITERATIONS = 600_000
REPO_URL = "https://github.com/Singleton15/home-assistant-rct-power-integration"


def _verify_service_password(password: str) -> bool:
    """Verify the Service password against its salted key derivation."""
    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        _PASSWORD_SALT,
        _PASSWORD_ITERATIONS,
    )
    return hmac.compare_digest(candidate_hash, _SERVICE_PASSWORD_HASH)


def _verify_god_mode_password(password: str) -> bool:
    """Verify the God mode password against its salted key derivation."""
    candidate_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        _PASSWORD_SALT,
        _PASSWORD_ITERATIONS,
    )
    return hmac.compare_digest(candidate_hash, _GOD_MODE_PASSWORD_HASH)


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
                    description_placeholders={"repo_url": REPO_URL},
                )
            else:
                errors["base"] = "connect"

        return self.async_show_form(
            step_id="user",
            data_schema=CONFIG_FLOW_SCHEMA,
            errors=errors,
            description_placeholders={"repo_url": REPO_URL},
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
            self._pending_options = dict(user_input)
            write_access = WriteAccess(self._pending_options.pop(CONF_WRITE_ACCESS))
            write_access_changed = write_access != self._current_write_access()
            self._pending_options[CONF_ALLOW_WRITES] = write_access in (
                WriteAccess.SERVICE,
                WriteAccess.FACTORY,
            )
            self._pending_options[CONF_GOD_MODE] = write_access is WriteAccess.FACTORY

            if write_access_changed and write_access is WriteAccess.SERVICE:
                return await self.async_step_confirm_service_access()
            if write_access_changed and write_access is WriteAccess.FACTORY:
                return await self.async_step_confirm_factory_access()
            return self._create_pending_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                OPTIONS_SCHEMA,
                {
                    **self.config_entry.options,
                    CONF_WRITE_ACCESS: self._current_write_access(),
                    CONF_RESTART_SERIAL_NUMBER: self.config_entry.options.get(
                        CONF_RESTART_SERIAL_NUMBER, self.config_entry.unique_id
                    ),
                },
            ),
        )

    def _current_write_access(self) -> WriteAccess:
        if self.config_entry.options.get(CONF_GOD_MODE, False):
            return WriteAccess.FACTORY
        if self.config_entry.options.get(CONF_ALLOW_WRITES, False):
            return WriteAccess.SERVICE
        return WriteAccess.NONE

    def _create_pending_entry(self) -> ConfigFlowResult:
        assert self._pending_options is not None
        return self.async_create_entry(data=self._pending_options)

    async def async_step_confirm_service_access(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self.hass.async_add_executor_job(
                _verify_service_password,
                user_input[CONF_SERVICE_PASSWORD],
            ):
                return self._create_pending_entry()
            errors["base"] = "invalid_service_password"

        return self.async_show_form(
            step_id="confirm_service_access",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SERVICE_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_confirm_factory_access(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if await self.hass.async_add_executor_job(
                _verify_god_mode_password,
                user_input[CONF_GOD_MODE_PASSWORD],
            ):
                return self._create_pending_entry()
            errors["base"] = "invalid_factory_password"

        return self.async_show_form(
            step_id="confirm_factory_access",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_GOD_MODE_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    )
                }
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
        vol.Optional(
            ConfMissedResponseTolerance.VERY_FREQUENT,
            default=MissedResponseToleranceDefault.VERY_FREQUENT,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            ConfMissedResponseTolerance.FREQUENT,
            default=MissedResponseToleranceDefault.FREQUENT,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            ConfMissedResponseTolerance.INFREQUENT,
            default=MissedResponseToleranceDefault.INFREQUENT,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            ConfMissedResponseTolerance.STATIC,
            default=MissedResponseToleranceDefault.STATIC,
        ): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(
            CONF_WRITE_ACCESS,
            default=WriteAccess.NONE,
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    selector.SelectOptionDict(value=WriteAccess.NONE, label="None"),
                    selector.SelectOptionDict(
                        value=WriteAccess.SERVICE, label="Service"
                    ),
                    selector.SelectOptionDict(
                        value=WriteAccess.FACTORY, label="Factory"
                    ),
                ],
                mode=selector.SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_RESTART_SERIAL_NUMBER): vol.All(str, vol.Length(min=1)),
    }
)
