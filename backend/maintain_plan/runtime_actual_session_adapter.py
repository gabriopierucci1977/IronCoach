"""Pure Garmin-runtime to :class:`ActualSession` P0 adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from math import isfinite

from .actual_session_normalizer import (
    ActualSessionInput, ActualSessionNormalizer, ComponentObservationInput,
    SourceActivityInput,
)
from .models import Composition, Discipline


class UnsupportedRuntimeActivity(ValueError):
    """A well-formed runtime item has an unsupported classification."""


class RuntimeActivityValidationError(ValueError):
    """A runtime activity violates the structural input contract."""


_DISCIPLINES = {
    "running": Discipline.RUN, "track_running": Discipline.RUN,
    "street_running": Discipline.RUN, "trail_running": Discipline.RUN,
    "treadmill_running": Discipline.RUN, "cycling": Discipline.BIKE,
    "road_biking": Discipline.BIKE, "indoor_cycling": Discipline.BIKE,
    "virtual_ride": Discipline.BIKE, "mountain_biking": Discipline.BIKE,
    "gravel_cycling": Discipline.BIKE, "lap_swimming": Discipline.SWIM,
    "open_water_swimming": Discipline.SWIM, "swimming": Discipline.SWIM,
}


def runtime_actual_session_id(subject_ref: str, activity_id: str) -> str:
    """Return the exact normative P0 identity (without Unicode rewriting)."""
    payload = {"original_activity_id": activity_id, "source": "garmin",
               "subject_ref": subject_ref}
    preimage = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    return "maintain-plan:actual-session:sha256:" + sha256(preimage).hexdigest()


# Friendly aliases for callers/tests describing the identity by domain name.
build_session_id = runtime_actual_session_id
derive_session_id = runtime_actual_session_id


def _required_identifier(value: object, label: str) -> str:
    if type(value) is not str or not value or not value.strip():
        raise RuntimeActivityValidationError(f"{label} must be an explicit non-empty string")
    return value


def _aware_timestamp(value: object, label: str) -> tuple[datetime, str]:
    if type(value) is not str:
        raise RuntimeActivityValidationError(f"{label} must be an explicit timestamp string")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as error:
        raise RuntimeActivityValidationError(f"{label} must be a valid timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RuntimeActivityValidationError(f"{label} must be timezone-aware")
    zone = "UTC" if value.endswith("Z") else parsed.strftime("%z")
    if zone != "UTC":
        zone = zone[:3] + ":" + zone[3:]
    return parsed, zone


def _number(payload: dict, name: str) -> int | float | None:
    if name not in payload or payload[name] is None:
        return None
    value = payload[name]
    if type(value) not in (int, float) or not isfinite(value) or value < 0:
        raise RuntimeActivityValidationError(f"{name} must be a finite non-negative number")
    return value


def _telemetry(payload: dict, group: str, fields: tuple[str, ...]) -> dict | None:
    raw = payload.get(group)
    if raw is None:
        return None
    if type(raw) is not dict:
        raise RuntimeActivityValidationError(f"{group} must be an object")
    result = {}
    for field in fields:
        if field not in raw or raw[field] is None:
            continue
        value = raw[field]
        if type(value) not in (int, float) or not isfinite(value) or value < 0:
            raise RuntimeActivityValidationError(f"{group}.{field} must be valid")
        result[field] = value
    return result or None


def build_actual_session(payload: dict, subject_ref: str, *, normalized_at: datetime,
                         captured_at: datetime | None = None):
    """Validate and normalize one untrusted projected Garmin activity."""
    if type(payload) is not dict:
        raise RuntimeActivityValidationError("activity must be an exact dict")
    subject = _required_identifier(subject_ref, "subject_ref")
    activity_id = _required_identifier(payload.get("activity_id"), "activity_id")
    if type(normalized_at) is not datetime or normalized_at.tzinfo is None or normalized_at.utcoffset() is None:
        raise RuntimeActivityValidationError("normalized_at must be timezone-aware")
    if captured_at is not None and (type(captured_at) is not datetime or captured_at.tzinfo is None or captured_at.utcoffset() is None):
        raise RuntimeActivityValidationError("captured_at must be timezone-aware")

    raw = payload.get("raw")
    if type(raw) is not dict:
        raise RuntimeActivityValidationError("raw must be an object")
    if type(raw.get("activity_type")) is not str:
        raise UnsupportedRuntimeActivity("raw.activity_type is required")
    discipline = _DISCIPLINES.get(raw["activity_type"])
    if discipline is None:
        raise UnsupportedRuntimeActivity("raw.activity_type is unsupported")
    sport = payload.get("sport")
    if sport is not None:
        if type(sport) is not str or sport not in {item.value for item in Discipline}:
            raise UnsupportedRuntimeActivity("sport is unsupported")
        if sport != discipline.value:
            raise UnsupportedRuntimeActivity("sport contradicts raw.activity_type")

    segments = payload.get("segments")
    if segments is not None:
        if type(segments) is not list:
            raise RuntimeActivityValidationError("segments must be a list")
        for segment in segments:
            if type(segment) is not dict:
                raise RuntimeActivityValidationError("segments must contain objects")
            classifiers = []
            if "activity_type" in segment:
                classifiers.append(_DISCIPLINES.get(segment["activity_type"]))
            if "sport" in segment:
                raw_sport = segment["sport"]
                classifiers.append(next((item for item in Discipline
                                         if item.value == raw_sport), None))
            if not classifiers or any(item is None for item in classifiers):
                raise UnsupportedRuntimeActivity("segment classification is unsupported")
            if len(set(classifiers)) != 1 or classifiers[0] is not discipline:
                raise UnsupportedRuntimeActivity("multi-discipline segments are unsupported")

    start, timezone_name = _aware_timestamp(payload.get("date"), "date")
    end = None
    if payload.get("end") is not None:
        end, _ = _aware_timestamp(payload["end"], "end")
        if end < start:
            raise RuntimeActivityValidationError("end must not precede start")
    duration = _number(payload, "duration_minutes")
    if raw.get("duration_minutes") is None:
        duration = None
    # Distance is preserved only where explicit provenance distinguishes it
    # from ActivityNormalizer's synthetic zero.
    distance = (_number(payload, "distance_km")
                if raw.get("distance_km") is not None else None)
    heart_rate = _telemetry(payload, "heart_rate", ("average", "max"))
    power = _telemetry(payload, "power", ("average", "normalized"))
    metadata = payload.get("metadata")
    if metadata is not None and type(metadata) is not dict:
        raise RuntimeActivityValidationError("metadata must be an object")

    raw_ids = {"activity_id": activity_id}
    for name in ("source_id", "file_hash"):
        if payload.get(name) is not None:
            raw_ids[name] = deepcopy(payload[name])
    evidence = {"segments": deepcopy(segments or []),
                "metadata": deepcopy(metadata or {})}
    if captured_at is not None:
        evidence["captured_at"] = captured_at
    secondary = []
    if duration is not None:
        secondary.append({"metric": "duration", "value": duration, "unit": "min"})
    if distance is not None:
        secondary.append({"metric": "distance", "value": distance, "unit": "km"})
    intensity = {}
    if heart_rate is not None:
        intensity["heart_rate"] = heart_rate
    if power is not None:
        intensity["power"] = power
    component_id = activity_id + ":component:0"
    source = SourceActivityInput("garmin", activity_id, raw_ids, evidence)
    component = ComponentObservationInput(
        component_id, 0, discipline, (activity_id,), start=start, end=end,
        secondary_metrics=tuple(secondary),
        intensity_observations=intensity or None, provenance=evidence,
        missing_fields=("environment", "mode", "quantity_primary_metric",
                        "intensity_methods", "blocks"),
    )
    value = ActualSessionInput(
        runtime_actual_session_id(subject, activity_id), (source,), start, end,
        timezone_name, Composition.SINGLE, (component,), normalized_at,
        missing_fields=("completion", "athlete_feedback", "weather_context"),
    )
    return ActualSessionNormalizer.normalize(value)


adapt_runtime_actual_session = build_actual_session
