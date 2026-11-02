"""Test RCT Power setup process."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power import (
    RctData,
    async_setup_entry,
    object_ids_for_update_priority,
)
from custom_components.rct_power.const import (
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_PORT,
    DOMAIN,
)
from custom_components.rct_power.lib.entities import all_entity_descriptions
from custom_components.rct_power.lib.entity import resolve_object_infos


def test_object_ids_excludes_registry_disabled_entity(monkeypatch) -> None:
    """Object IDs used only by a disabled entity are not polled."""
    entity_description = next(
        description
        for description in all_entity_descriptions
        if description.unique_id is not None
    )
    monkeypatch.setattr(
        "custom_components.rct_power.all_entity_descriptions", [entity_description]
    )

    assert (
        object_ids_for_update_priority(
            entity_description.update_priority,
            "test-entry",
            {f"test-entry-{entity_description.unique_id}": False},
        )
        == []
    )


def test_object_ids_excludes_default_disabled_entity(monkeypatch) -> None:
    """Object IDs for entities disabled by default are not polled."""
    entity_description = next(
        description
        for description in all_entity_descriptions
        if description.entity_registry_enabled_default is False
    )
    monkeypatch.setattr(
        "custom_components.rct_power.all_entity_descriptions", [entity_description]
    )

    assert (
        object_ids_for_update_priority(
            entity_description.update_priority, "test-entry", {}
        )
        == []
    )


def test_object_ids_includes_user_enabled_default_disabled_entity(
    monkeypatch,
) -> None:
    """An explicit registry enablement overrides the default-disabled setting."""
    entity_description = next(
        description
        for description in all_entity_descriptions
        if description.entity_registry_enabled_default is False
    )
    monkeypatch.setattr(
        "custom_components.rct_power.all_entity_descriptions", [entity_description]
    )
    unique_id = (
        f"test-entry-{entity_description.unique_id}"
        if entity_description.unique_id
        else "-".join(
            [
                "test-entry",
                *(
                    str(object_info.object_id)
                    for object_info in resolve_object_infos(entity_description)
                ),
            ]
        )
    )

    assert set(
        object_ids_for_update_priority(
            entity_description.update_priority,
            "test-entry",
            {unique_id: True},
        )
    ) == {
        object_info.object_id
        for object_info in resolve_object_infos(entity_description)
    }


# We can pass fixtures as defined in conftest.py to tell pytest to use the fixture
# for a given test. We can also leverage fixtures and mocks that are available in
# Home Assistant using the pytest_homeassistant_custom_component plugin.
# Assertions allow you to verify that the return value of whatever is on the left
# side of the assertion matches with the right side.
@pytest.mark.usefixtures("bypass_get_data")
async def test_setup_unload_and_reload_entry(hass: HomeAssistant) -> None:
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "localhost",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: DEFAULT_ENTITY_PREFIX,
        },
        entry_id="test",
    )

    config_entry.add_to_hass(hass)
    # Set up the entry and assert that the values set during setup are where we expect
    # them to be. Because we have patched the RctPowerDataUpdateCoordinator.async_get_data
    # call, no code from custom_components/rct_power/api.py actually runs.
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert isinstance(config_entry.runtime_data, RctData)

    # Reload the entry and assert that the data from above is still there
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert isinstance(config_entry.runtime_data, RctData)


@pytest.mark.usefixtures("error_on_get_data")
async def test_setup_entry_exception(hass: HomeAssistant) -> None:
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "localhost",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: DEFAULT_ENTITY_PREFIX,
        },
        entry_id="test",
    )
    config_entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady using the `error_on_get_data` fixture which simulates
    # an error.
    with pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)
