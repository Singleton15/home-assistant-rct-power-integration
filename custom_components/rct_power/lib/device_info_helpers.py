from __future__ import annotations

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from ..const import BATTERY_MODEL, DOMAIN, INVERTER_MODEL, NAME
from .entity import RctPowerEntity


def get_inverter_sn(entity: RctPowerEntity) -> str:
    """Return the inverter serial number.

    Falls back to the serial number stored by the config flow, so that a
    failed read doesn't create a device with the serial number "None".
    """
    inverter_sn = entity.get_valid_api_response_value_by_name("inverter_sn", None)
    if inverter_sn:
        return str(inverter_sn)
    return str(entity.config_entry.unique_id or entity.config_entry.entry_id)


def get_inverter_device_id(entity: RctPowerEntity) -> dict[str, str]:
    """Link a battery device to the inverter device, if it is registered.

    The sensor platform registers the inverter device before adding any
    entities, so it is normally found.
    """
    device = dr.async_get(entity.hass).async_get_device_by_identifier(
        identifier=(DOMAIN, get_inverter_sn(entity)),
        config_entry_id=entity.config_entry.entry_id,
    )
    return {"via_device_id": device.id} if device else {}


def get_inverter_device_info(entity: RctPowerEntity) -> DeviceInfo:
    inverter_sn = get_inverter_sn(entity)

    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                "STORAGE",
                inverter_sn,
            ),
            (
                DOMAIN,
                inverter_sn,
            ),
        },  # type: ignore
        name=str(
            entity.get_valid_api_response_value_by_name("android_description", ""),
        ),
        sw_version=str(entity.get_valid_api_response_value_by_name("svnversion", "")),
        model=INVERTER_MODEL,
        manufacturer=NAME,
    )


def get_battery_device_info(entity: RctPowerEntity) -> DeviceInfo:
    inverter_sn = get_inverter_sn(entity)
    bms_sn = entity.get_valid_api_response_value_by_name("battery.bms_sn", None)
    # same fallback as for the second tower, see below
    bms_sn = str(bms_sn) if bms_sn else f"{inverter_sn}-tower-1"

    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                "BATTERY",
                bms_sn,
            ),
            (
                DOMAIN,
                bms_sn,
            ),
        },  # type: ignore
        name=f"Battery at {entity.get_valid_api_response_value_by_name('android_description', '')}",
        sw_version=str(
            entity.get_valid_api_response_value_by_name(
                "battery.bms_software_version", ""
            )
        ),
        model=BATTERY_MODEL,
        manufacturer=NAME,
        **get_inverter_device_id(entity),
    )


def get_battery_tower_2_device_info(entity: RctPowerEntity) -> DeviceInfo:
    inverter_sn = get_inverter_sn(entity)
    bms_sn = entity.get_valid_api_response_value_by_name(
        "battery_placeholder[0].bms_sn", None
    )
    # fall back to the inverter serial number so that inverters without a
    # second tower don't end up sharing a device
    tower_id = str(bms_sn) if bms_sn else f"{inverter_sn}-tower-2"

    return DeviceInfo(
        identifiers={
            (
                DOMAIN,
                "BATTERY",
                tower_id,
            ),
            (
                DOMAIN,
                tower_id,
            ),
        },  # type: ignore
        name=f"Battery Tower 2 at {entity.get_valid_api_response_value_by_name('android_description', '')}",
        sw_version=str(
            entity.get_valid_api_response_value_by_name(
                "battery_placeholder[0].bms_software_version", ""
            )
        ),
        model=BATTERY_MODEL,
        manufacturer=NAME,
        **get_inverter_device_id(entity),
    )
