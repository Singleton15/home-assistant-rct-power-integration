"""RCT object registry extended with objects not yet known to rctclient."""

from __future__ import annotations

from rctclient.registry import REGISTRY as RCT_REGISTRY
from rctclient.registry import ObjectInfo, Registry
from rctclient.types import DataType, ObjectGroup

_PHASE_POWER_OFFSET_OBJECTS = [
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0x8114F393,
        index=0,
        name="phase_power_offset[0]",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0x9521F6C7,
        index=1,
        name="phase_power_offset[1]",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0xEED7904F,
        index=2,
        name="phase_power_offset[2]",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
]

_CURRENT_SENSOR_GAIN_OBJECTS = [
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0x6A9A9FED,
        index=0,
        name="csc[0].gain",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0x93FAD04A,
        index=1,
        name="csc[1].gain",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
    ObjectInfo(
        group=ObjectGroup.OTHERS,
        object_id=0x86ABDAC9,
        index=2,
        name="csc[2].gain",
        request_data_type=DataType.FLOAT,
        response_data_type=DataType.FLOAT,
    ),
]

REGISTRY = Registry(
    [*RCT_REGISTRY.all(), *_PHASE_POWER_OFFSET_OBJECTS, *_CURRENT_SENSOR_GAIN_OBJECTS]
)
