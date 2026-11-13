"""Test RCT Power config and options flows."""

from __future__ import annotations

import hashlib

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power import config_flow
from custom_components.rct_power.const import (
    CONF_GOD_MODE,
    CONF_GOD_MODE_PASSWORD,
    DOMAIN,
)


async def test_enabling_god_mode_requires_password(
    hass: HomeAssistant, monkeypatch
) -> None:
    """Enabling God mode requires the password in its confirmation step."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_GOD_MODE: True}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "confirm_god_mode"
    assert config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_GOD_MODE_PASSWORD: "wrong"}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "invalid_password"}
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
    assert config_entry.options[CONF_GOD_MODE] is True


def test_god_mode_password_uses_salted_hash(monkeypatch) -> None:
    """Verify password matching uses the configured salt and iteration count."""
    salt = b"test-salt"
    password = "test-pass"
    monkeypatch.setattr(config_flow, "_GOD_MODE_PASSWORD_SALT", salt)
    monkeypatch.setattr(config_flow, "_GOD_MODE_PASSWORD_ITERATIONS", 1)
    monkeypatch.setattr(
        config_flow,
        "_GOD_MODE_PASSWORD_HASH",
        hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 1),
    )

    assert config_flow._verify_god_mode_password(password)
    assert not config_flow._verify_god_mode_password("wrong")
