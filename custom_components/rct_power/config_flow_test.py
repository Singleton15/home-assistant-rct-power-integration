"""Test RCT Power config and options flows."""

from __future__ import annotations

import hashlib

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power import config_flow
from custom_components.rct_power.const import (
    CONF_ALLOW_WRITES,
    CONF_GOD_MODE,
    CONF_GOD_MODE_PASSWORD,
    CONF_SERVICE_PASSWORD,
    CONF_WRITE_ACCESS,
    DOMAIN,
    WriteAccess,
)


async def test_config_form_supplies_repo_url(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )

    assert result["type"] == "form"
    assert result["description_placeholders"] == {"repo_url": config_flow.REPO_URL}


async def test_none_access_does_not_require_password(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_WRITE_ACCESS: WriteAccess.NONE}
    )

    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_ALLOW_WRITES] is False
    assert config_entry.options[CONF_GOD_MODE] is False


@pytest.mark.parametrize(
    ("options", "write_access"),
    [
        ({CONF_ALLOW_WRITES: True, CONF_GOD_MODE: False}, WriteAccess.SERVICE),
        ({CONF_ALLOW_WRITES: True, CONF_GOD_MODE: True}, WriteAccess.FACTORY),
    ],
)
async def test_unchanged_write_access_does_not_require_password(
    hass: HomeAssistant,
    options: dict,
    write_access: WriteAccess,
) -> None:
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options=options)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_WRITE_ACCESS: write_access},
    )

    assert result["type"] == "create_entry"


async def test_service_access_requires_service_password(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_WRITE_ACCESS: WriteAccess.SERVICE}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_service_access"
    assert config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SERVICE_PASSWORD: "wrong"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_service_password"}
    assert config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SERVICE_PASSWORD: "installer"}
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_ALLOW_WRITES] is True
    assert config_entry.options[CONF_GOD_MODE] is False
    assert CONF_SERVICE_PASSWORD not in config_entry.options


async def test_factory_access_requires_god_mode_password(
    hass: HomeAssistant, monkeypatch
) -> None:
    """Factory access enables both Service and God mode write access."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_WRITE_ACCESS: WriteAccess.FACTORY}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_factory_access"
    assert config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_GOD_MODE_PASSWORD: "wrong"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_factory_password"}
    assert config_entry.options == {}

    monkeypatch.setattr(
        config_flow,
        "_verify_god_mode_password",
        lambda password: password == "test-pass",
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_GOD_MODE_PASSWORD: "test-pass"}
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_ALLOW_WRITES] is True
    assert config_entry.options[CONF_GOD_MODE] is True


def test_service_password_matches_installer() -> None:
    assert config_flow._verify_service_password("installer")
    assert not config_flow._verify_service_password("wrong")


def test_god_mode_password_uses_salted_hash(monkeypatch) -> None:
    """Verify password matching uses the configured salt and iteration count."""
    salt = b"test-salt"
    password = "test-pass"
    monkeypatch.setattr(config_flow, "_PASSWORD_SALT", salt)
    monkeypatch.setattr(config_flow, "_PASSWORD_ITERATIONS", 1)
    monkeypatch.setattr(
        config_flow,
        "_GOD_MODE_PASSWORD_HASH",
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 1),
    )

    assert config_flow._verify_god_mode_password(password)
    assert not config_flow._verify_god_mode_password("wrong")
