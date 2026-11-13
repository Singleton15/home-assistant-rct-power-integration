"""Test RCT Power config and options flows."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power.const import (
    CONF_GOD_MODE,
    CONF_GOD_MODE_CONFIRMATION,
    DOMAIN,
)


async def test_enabling_god_mode_requires_confirmation(hass: HomeAssistant) -> None:
    """Enabling God mode presents a warning and requires acknowledgement."""
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
        result["flow_id"], user_input={CONF_GOD_MODE_CONFIRMATION: False}
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "confirmation_required"}
    assert config_entry.options == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_GOD_MODE_CONFIRMATION: True}
    )
    assert result["type"] == "create_entry"
    assert config_entry.options[CONF_GOD_MODE] is True
