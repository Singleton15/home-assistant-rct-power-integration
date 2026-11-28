"""Sample API Client."""

from __future__ import annotations

import asyncio
import re
import struct
from asyncio import StreamReader, StreamWriter, open_connection
from asyncio.locks import Lock
from dataclasses import dataclass, field
from datetime import UTC, datetime

from homeassistant.helpers.update_coordinator import UpdateFailed
from rctclient.exceptions import FrameCRCMismatch, FrameLengthExceeded, InvalidCommand
from rctclient.frame import ReceiveFrame, SendFrame
from rctclient.types import (
    BatteryModuleResistance,
    BatteryModuleStatistics,
    BatteryModuleStatus,
    Command,
    DataType,
    EventEntry,
)
from rctclient.utils import decode_value, encode_value

from ..const import LOGGER
from .registry import REGISTRY

CONNECTION_TIMEOUT = 20
READ_TIMEOUT = 2
INVERTER_SN_OID = 0x7924ABD9

type ApiResponseValue = (
    bool
    | bytes
    | float
    | int
    | str
    | tuple[datetime, dict[datetime, int]]
    | tuple[datetime, dict[datetime, EventEntry]]
    | BatteryModuleStatus
    | BatteryModuleStatistics
    | BatteryModuleResistance
)

# The registry lists some objects of the second battery tower
# (`battery_placeholder[0]`) as strings, although they carry the same payload
# as their counterparts of the first tower (`battery`).
_RESPONSE_DATA_TYPE_OVERRIDE_PATTERNS: dict[str, DataType] = {
    r"^battery_placeholder\[0\]\.cells\[\d+\]$": DataType.BATTERY_MODULE_STATUS,
    r"^battery_placeholder\[0\]\.cells_stat\[\d+\]$": DataType.BATTERY_MODULE_STATISTICS,
    r"^battery_placeholder\[0\]\.cells_resist\[\d+\]$": DataType.BATTERY_MODULE_RESISTANCE,
}

RESPONSE_DATA_TYPE_OVERRIDES: dict[int, DataType] = {
    object_info.object_id: data_type
    for object_info in REGISTRY.all()
    for pattern, data_type in _RESPONSE_DATA_TYPE_OVERRIDE_PATTERNS.items()
    if re.match(pattern, object_info.name)
}


def get_response_data_type(object_id: int) -> DataType:
    return RESPONSE_DATA_TYPE_OVERRIDES.get(
        object_id, REGISTRY.get_by_id(object_id).response_data_type
    )


@dataclass
class BaseApiResponse:
    object_id: int
    time: datetime
    # the undecoded payload, kept for diagnostics
    raw: bytes | None = field(default=None, kw_only=True, repr=False)


@dataclass
class ValidApiResponse(BaseApiResponse):
    value: ApiResponseValue


@dataclass
class InvalidApiResponse(BaseApiResponse):
    cause: str


type ApiResponse = ValidApiResponse | InvalidApiResponse
type RctPowerData = dict[int, ApiResponse]


def get_valid_response_value_or[R](
    response: ApiResponse | None, defaultValue: R
) -> ApiResponseValue | R:
    if isinstance(response, ValidApiResponse):
        return response.value
    else:
        return defaultValue


class RctPowerApiClient:
    def __init__(self, hostname: str, port: int) -> None:
        """Sample API Client."""
        self._hostname = hostname
        self._port = port

        # ensure only one connection at a time is established because the
        # inverter's firmware doesn't handle it well at the time of writing
        self._connection_lock = Lock()

    async def get_serial_number(self) -> str | None:
        inverter_data = await self.async_get_data([INVERTER_SN_OID])

        inverter_sn_response = inverter_data.get(INVERTER_SN_OID)

        if isinstance(inverter_sn_response, ValidApiResponse) and isinstance(
            inverter_sn_response.value, str
        ):
            return inverter_sn_response.value
        else:
            return None

    async def async_get_data(self, object_ids: list[int]) -> RctPowerData:
        async with self._connection_lock:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                try:
                    reader, writer = await open_connection(
                        host=self._hostname, port=self._port
                    )
                except OSError as exc:
                    LOGGER.debug(
                        "Error connecting to RCT Power inverter at %s:%s: %s",
                        self._hostname,
                        self._port,
                        exc,
                    )
                    request_time = datetime.now(tz=UTC)
                    return {
                        object_id: InvalidApiResponse(
                            object_id=object_id,
                            time=request_time,
                            cause="CONNECTION_ERROR",
                        )
                        for object_id in object_ids
                    }

                try:
                    if reader.at_eof():
                        raise UpdateFailed("Read stream closed")

                    return {
                        object_id: await self._read_object(
                            reader=reader, writer=writer, object_id=object_id
                        )
                        for object_id in object_ids
                    }
                finally:
                    writer.close()

    async def async_write_value(self, object_id: int, value: float) -> ApiResponse:
        """Write a value to the inverter and return the value read back.

        The inverter keeps such settings permanently, so this should only be
        called when the value actually changes.
        """
        object_info = REGISTRY.get_by_id(object_id)
        payload = encode_value(object_info.request_data_type, value)  # type: ignore
        write_command_frame = SendFrame(
            command=Command.WRITE, id=object_id, payload=payload
        )

        async with self._connection_lock:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                reader, writer = await open_connection(
                    host=self._hostname, port=self._port
                )

                try:
                    LOGGER.info(
                        "Writing %s to RCT Power object %x (%s)",
                        value,
                        object_id,
                        object_info.name,
                    )
                    writer.write(write_command_frame.data)
                    await writer.drain()

                    # read the value back to confirm the inverter accepted it
                    return await self._read_object(
                        reader=reader, writer=writer, object_id=object_id
                    )
                finally:
                    writer.close()

    async def _read_object(
        self, reader: StreamReader, writer: StreamWriter, object_id: int
    ) -> ApiResponse:
        object_name = REGISTRY.get_by_id(object_id).name
        read_command_frame = SendFrame(command=Command.READ, id=object_id)

        LOGGER.debug(
            "Requesting RCT Power data for object %x (%s)...", object_id, object_name
        )
        request_time = datetime.now(tz=UTC)

        try:
            async with asyncio.timeout(READ_TIMEOUT):
                await writer.drain()
                writer.write(read_command_frame.data)

                # loop until we return or time out
                while True:
                    response_frame = ReceiveFrame()

                    while not response_frame.complete() and not reader.at_eof():
                        raw_response = await reader.read(1)

                        if len(raw_response) > 0:
                            response_frame.consume(raw_response)

                    if response_frame.complete():
                        response_object_info = REGISTRY.get_by_id(response_frame.id)
                        data_type = get_response_data_type(response_frame.id)
                        received_object_name = response_object_info.name

                        # ignore, if this is not the answer to the latest request
                        if object_id != response_frame.id:
                            LOGGER.debug(
                                "Mismatch of requested and received object ids: requested %x (%s), but received %x (%s)",
                                object_id,
                                object_name,
                                response_frame.id,
                                received_object_name,
                            )
                            continue

                        try:
                            decoded_value: ApiResponseValue = decode_value(
                                data_type,  # type: ignore
                                response_frame.data,
                            )  # type: ignore
                        except (struct.error, ValueError) as exc:
                            LOGGER.debug(
                                "Error decoding object %x (%s) as %s: %s (payload %s)",
                                object_id,
                                object_name,
                                data_type,
                                str(exc),
                                response_frame.data.hex(),
                            )
                            return InvalidApiResponse(
                                object_id=object_id,
                                time=request_time,
                                cause="PARSING_ERROR",
                                raw=response_frame.data,
                            )

                        LOGGER.debug(
                            "Decoded data for object %x (%s): %s",
                            response_frame.id,
                            received_object_name,
                            decoded_value,
                        )

                        return ValidApiResponse(
                            object_id=object_id,
                            time=request_time,
                            value=decoded_value,
                            raw=response_frame.data,
                        )
                    else:
                        LOGGER.debug(
                            "Error decoding object %x (%s): %s",
                            object_id,
                            object_name,
                            response_frame.data,
                        )
                        return InvalidApiResponse(
                            object_id=object_id, time=request_time, cause="INCOMPLETE"
                        )

        except TimeoutError as exc:
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id,
                time=request_time,
                cause="OBJECT_READ_TIMEOUT",
            )
        except FrameCRCMismatch as exc:
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id, time=request_time, cause="CRC_ERROR"
            )
        except FrameLengthExceeded as exc:
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id, time=request_time, cause="FRAME_LENGTH_EXCEEDED"
            )
        except InvalidCommand as exc:
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id, time=request_time, cause="INVALID_COMMAND"
            )
        except struct.error as exc:
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id, time=request_time, cause="PARSING_ERROR"
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.debug(
                "Error reading object %x (%s): %s", object_id, object_name, str(exc)
            )
            return InvalidApiResponse(
                object_id=object_id, time=request_time, cause="UNKNOWN_ERROR"
            )
