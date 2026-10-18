"""Bridge from imported Garmin FIT activities to runtime capture payloads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any


def _mapping(value: object) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError("activity must be a dataclass, mapping, or object")


def _timestamp(value: object) -> str:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace(
            "+00:00",
            "Z",
        )

    if not isinstance(value, str) or not value.strip():
        raise ValueError("activity start_time must be present")

    result = value.strip().replace(" ", "T")

    if result.endswith("Z") or "+" in result[10:]:
        return result

    return f"{result}Z"


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def source_activity_to_runtime_payload(
    activity: object,
    file_hash: str,
) -> dict[str, Any]:
    source = _mapping(activity)

    if not isinstance(file_hash, str) or not file_hash.strip():
        raise ValueError("file_hash must be a non-empty string")

    file_hash = file_hash.strip()

    activity_id = str(
        source.get("activity_id")
        or source.get("source_id")
        or file_hash
    )

    source_id = str(source.get("source_id") or file_hash)
    sport = _enum_value(source.get("sport") or "BIKE")
    activity_type = _enum_value(
        source.get("activity_type") or "unknown"
    )

    duration_seconds = source.get("duration_seconds")
    distance_meters = source.get("distance_meters")

    payload: dict[str, Any] = {
        "activity_id": activity_id,
        "source_id": source_id,
        "file_hash": file_hash,
        "date": _timestamp(source.get("start_time")),
        "sport": str(sport).upper(),
        "segments": source.get("segments") or [],
        "metadata": source.get("metadata") or {},
        "raw": {
            "activity_type": str(activity_type),
        },
    }

    if source.get("end_time") is not None:
        payload["end"] = _timestamp(source["end_time"])

    if duration_seconds is not None:
        duration_minutes = float(duration_seconds) / 60.0
        payload["duration_minutes"] = duration_minutes
        payload["raw"]["duration_minutes"] = duration_minutes

    if distance_meters is not None:
        distance_km = float(distance_meters) / 1000.0
        payload["distance_km"] = distance_km
        payload["raw"]["distance_km"] = distance_km

    heart_rate = {}
    if source.get("avg_hr") is not None:
        heart_rate["average"] = source["avg_hr"]
    if source.get("max_hr") is not None:
        heart_rate["max"] = source["max_hr"]
    payload["heart_rate"] = heart_rate

    power = {}
    if source.get("avg_power") is not None:
        power["average"] = source["avg_power"]
    if source.get("normalized_power") is not None:
        power["normalized"] = source["normalized_power"]
    payload["power"] = power

    return payload
