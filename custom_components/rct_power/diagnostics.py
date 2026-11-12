"""Diagnostics support for RCT Power."""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import RctConfigEntry
from .const import CONF_HOSTNAME
from .lib.api import ValidApiResponse
from .lib.registry import REGISTRY

TO_REDACT = {CONF_HOSTNAME}


def _to_json(value: Any) -> Any:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _to_json(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_json(item) for key, item in value.items()}  # pyright: ignore [reportUnknownVariableType]
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]  # pyright: ignore [reportUnknownVariableType]
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RctConfigEntry
) -> dict[str, Any]:
    """Return the latest responses of the inverter, including raw payloads."""
    objects: dict[str, Any] = {}

    for priority, coordinator in entry.runtime_data.update_coordinators.items():
        for object_id in coordinator.object_ids:
            response = coordinator.get_latest_response(object_id)
            object_info = REGISTRY.get_by_id(object_id)
            objects[object_info.name] = {
                "object_id": f"0x{object_id:08X}",
                "update_priority": priority.name,
                "valid": isinstance(response, ValidApiResponse),
                "value": _to_json(response.value)
                if isinstance(response, ValidApiResponse)
                else None,
                "cause": None
                if response is None or isinstance(response, ValidApiResponse)
                else response.cause,
                "raw": response.raw.hex()
                if response is not None and response.raw is not None
                else None,
            }

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "objects": dict(sorted(objects.items())),
    }
