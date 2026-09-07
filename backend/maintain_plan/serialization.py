"""Deterministic JSON serialization for the immutable MAINTAIN_PLAN contracts."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from . import models


PAYLOAD_SCHEMA_VERSION = "maintain-plan-json/1"

_DATACLASSES = {
    name: value
    for name, value in vars(models).items()
    if isinstance(value, type) and is_dataclass(value) and value.__module__ == models.__name__
}
_ENUMS = {
    name: value
    for name, value in vars(models).items()
    if isinstance(value, type) and issubclass(value, Enum) and value.__module__ == models.__name__
}


def _require_keys(value: dict[str, Any], expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError("malformed MAINTAIN_PLAN payload object")


def _encode(value: Any) -> Any:
    if is_dataclass(value) and value.__class__.__module__ == models.__name__:
        return {
            "$type": "dataclass",
            "name": value.__class__.__name__,
            "fields": {field.name: _encode(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, Enum) and value.__class__.__module__ == models.__name__:
        return {"$type": "enum", "name": value.__class__.__name__, "value": value.value}
    if isinstance(value, datetime):
        return {"$type": "datetime", "value": value.isoformat()}
    if isinstance(value, tuple):
        return {"$type": "tuple", "items": [_encode(item) for item in value]}
    if isinstance(value, frozenset):
        encoded = [_encode(item) for item in value]
        encoded.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        return {"$type": "frozenset", "items": encoded}
    if isinstance(value, dict) or hasattr(value, "items"):
        entries = [[_encode(key), _encode(item)] for key, item in value.items()]
        entries.sort(key=lambda item: json.dumps(item[0], sort_keys=True, separators=(",", ":")))
        return {"$type": "mapping", "items": entries}
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"unsupported MAINTAIN_PLAN payload value: {type(value).__name__}")


def _decode(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if not isinstance(value, dict) or "$type" not in value:
        raise ValueError("untagged container in MAINTAIN_PLAN payload")
    kind = value["$type"]
    if kind == "dataclass":
        _require_keys(value, {"$type", "name", "fields"})
        try:
            cls = _DATACLASSES[value["name"]]
        except KeyError as error:
            raise ValueError("unknown MAINTAIN_PLAN dataclass") from error
        if not isinstance(value["fields"], dict):
            raise ValueError("invalid MAINTAIN_PLAN dataclass fields")
        expected_fields = {field.name for field in fields(cls)}
        if set(value["fields"]) != expected_fields:
            raise ValueError("MAINTAIN_PLAN dataclass fields do not match its type")
        return cls(**{name: _decode(item) for name, item in value["fields"].items()})
    if kind == "enum":
        _require_keys(value, {"$type", "name", "value"})
        try:
            return _ENUMS[value["name"]](value["value"])
        except (KeyError, ValueError) as error:
            raise ValueError("unknown MAINTAIN_PLAN enum or value") from error
    if kind == "datetime":
        _require_keys(value, {"$type", "value"})
        try:
            return datetime.fromisoformat(value["value"])
        except (TypeError, ValueError) as error:
            raise ValueError("invalid MAINTAIN_PLAN datetime") from error
    if kind == "tuple":
        _require_keys(value, {"$type", "items"})
        if not isinstance(value["items"], list):
            raise ValueError("invalid MAINTAIN_PLAN tuple")
        return tuple(_decode(item) for item in value["items"])
    if kind == "frozenset":
        _require_keys(value, {"$type", "items"})
        if not isinstance(value["items"], list):
            raise ValueError("invalid MAINTAIN_PLAN frozenset")
        return frozenset(_decode(item) for item in value["items"])
    if kind == "mapping":
        _require_keys(value, {"$type", "items"})
        if not isinstance(value["items"], list):
            raise ValueError("invalid MAINTAIN_PLAN mapping")
        result = {}
        for entry in value["items"]:
            if not isinstance(entry, list) or len(entry) != 2:
                raise ValueError("invalid MAINTAIN_PLAN mapping entry")
            key = _decode(entry[0])
            if key in result:
                raise ValueError("duplicate MAINTAIN_PLAN mapping key")
            result[key] = _decode(entry[1])
        return result
    raise ValueError(f"unknown MAINTAIN_PLAN payload tag: {kind}")


def serialize_contract(value: Any) -> str:
    """Return canonical UTF-8-compatible JSON with an explicit envelope version."""
    envelope = {"payload_schema_version": PAYLOAD_SCHEMA_VERSION, "payload": _encode(value)}
    return json.dumps(
        envelope, allow_nan=False, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def deserialize_contract(payload: str, expected_type: type[Any]) -> Any:
    """Rebuild a canonical immutable contract object, rejecting wrong versions/types."""
    try:
        envelope = json.loads(
            payload,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant: {value}")
            ),
        )
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("invalid MAINTAIN_PLAN JSON payload") from error
    if not isinstance(envelope, dict) or set(envelope) != {"payload_schema_version", "payload"}:
        raise ValueError("invalid MAINTAIN_PLAN payload envelope")
    if envelope.get("payload_schema_version") != PAYLOAD_SCHEMA_VERSION:
        raise ValueError("unsupported MAINTAIN_PLAN payload schema version")
    value = _decode(envelope["payload"])
    if not isinstance(value, expected_type):
        raise ValueError(f"expected {expected_type.__name__} payload")
    return value
