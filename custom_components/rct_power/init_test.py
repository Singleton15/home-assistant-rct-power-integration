"""Test RCT Power setup process."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.rct_power import (
    RctData,
    _async_send_restart_request,
    async_setup_entry,
    object_ids_for_update_priority,
)
from custom_components.rct_power.const import (
    CONF_CONFIG_ENTRY_ID,
    CONF_ENTITY_PREFIX,
    CONF_HOSTNAME,
    CONF_RESTART_SERIAL_NUMBER,
    DEFAULT_ENTITY_PREFIX,
    DEFAULT_PORT,
    DOMAIN,
    RESTART_WAIT_SECONDS,
    SERVICE_RESTART_COMMUNICATION,
    EntityUpdatePriority,
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


def test_god_mode_object_ids_are_only_polled_when_enabled(monkeypatch) -> None:
    """God mode correction values are excluded from polling by default."""
    descriptions = [
        description
        for description in all_entity_descriptions
        if description.requires_god_mode
        and description.update_priority == EntityUpdatePriority.STATIC
    ]
    assert len(descriptions) == 7
    monkeypatch.setattr(
        "custom_components.rct_power.all_entity_descriptions", descriptions
    )

    assert (
        object_ids_for_update_priority(
            EntityUpdatePriority.STATIC, "test-entry", {}, god_mode_enabled=False
        )
        == []
    )
    assert set(
        object_ids_for_update_priority(
            EntityUpdatePriority.STATIC, "test-entry", {}, god_mode_enabled=True
        )
    ) == {
        object_info.object_id
        for description in descriptions
        for object_info in resolve_object_infos(description)
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


@pytest.mark.usefixtures("bypass_get_data")
async def test_restart_service_stops_restarts_waits_and_resumes(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Restart communication using the configured serial and restore the entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOSTNAME: "192.0.2.10",
            CONF_PORT: DEFAULT_PORT,
            CONF_ENTITY_PREFIX: DEFAULT_ENTITY_PREFIX,
        },
        options={CONF_RESTART_SERIAL_NUMBER: "configured-serial"},
        entry_id="test",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    events: list[tuple[str, object]] = []

    async def unload(entry_id: str) -> bool:
        events.append(("unload", entry_id))
        return True

    async def send_restart_request(
        hass: HomeAssistant, entry: MockConfigEntry, serial_number: str
    ) -> None:
        events.append(("restart", serial_number))

    async def wait(seconds: int) -> None:
        events.append(("wait", seconds))

    async def setup(entry_id: str) -> bool:
        events.append(("setup", entry_id))
        return True

    monkeypatch.setattr(hass.config_entries, "async_unload", unload)
    monkeypatch.setattr(hass.config_entries, "async_setup", setup)
    monkeypatch.setattr(
        "custom_components.rct_power._async_send_restart_request",
        send_restart_request,
    )
    monkeypatch.setattr("custom_components.rct_power.asyncio.sleep", wait)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_RESTART_COMMUNICATION,
        {CONF_CONFIG_ENTRY_ID: config_entry.entry_id},
        blocking=True,
    )

    assert events == [
        ("unload", config_entry.entry_id),
        ("restart", "configured-serial"),
        ("wait", RESTART_WAIT_SECONDS),
        ("setup", config_entry.entry_id),
    ]


@pytest.mark.parametrize(
    ("body", "confirmed"),
    [
        (b"<h2>Rebooting...</h2>", True),
        (b"<h2>Restart failed</h2>", False),
    ],
)
async def test_restart_request_checks_inverter_confirmation(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    body: bytes,
    confirmed: bool,
) -> None:
    """Use the configured inverter host and serial for the restart request."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOSTNAME: "192.0.2.10"},
        entry_id="test",
    )
    response = Mock()
    response.raise_for_status = Mock()
    response.read = AsyncMock(return_value=body)
    response_context = MagicMock()
    response_context.__aenter__ = AsyncMock(return_value=response)
    response_context.__aexit__ = AsyncMock(return_value=None)
    session = Mock()
    session.get = Mock(return_value=response_context)
    monkeypatch.setattr(
        "custom_components.rct_power.async_get_clientsession",
        Mock(return_value=session),
    )

    if confirmed:
        await _async_send_restart_request(hass, entry, "configured-serial")
    else:
        with pytest.raises(
            HomeAssistantError,
            match="did not confirm that it is rebooting",
        ):
            await _async_send_restart_request(hass, entry, "configured-serial")

    session.get.assert_called_once()
    response.read.assert_awaited_once()
    url = session.get.call_args.args[0]
    request_options = session.get.call_args.kwargs
    assert url == "http://192.0.2.10/EN/restart.html"
    assert request_options["headers"]["Authorization"] == aiohttp.encode_basic_auth(
        "admin", "configured-serial"
    )
    assert request_options["timeout"] == aiohttp.ClientTimeout(total=10)
