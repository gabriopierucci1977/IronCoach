"""Pure Garmin-runtime to :class:`ActualSession` P0 adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
from math import isfinite
from sys import float_info

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

# Keep untrusted evidence comfortably below Python's recursion limit.  The
# walk itself is iterative, so even hostile nesting fails deterministically.
_MAX_EVIDENCE_DEPTH = 100
_MAX_JSON_INTEGER = 10 ** 4300 - 1


def validate_runtime_string(value: str, label: str) -> None:
    """Reject strings that cannot be represented as strict UTF-8."""
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise RuntimeActivityValidationError(
            f"{label} contains invalid Unicode"
        ) from error


def validate_runtime_unicode_tree(value: object, label: str) -> None:
    """Validate strings in a runtime tree without walking past the depth limit."""
    pending = [(value, label, 0)]
    visited = set()
    while pending:
        item, path, depth = pending.pop()
        if type(item) is str:
            validate_runtime_string(item, path)
        elif type(item) in (dict, list, tuple):
            if depth >= _MAX_EVIDENCE_DEPTH:
                raise RuntimeActivityValidationError(f"{path} is nested too deeply")
            identity = id(item)
            if identity in visited:
                continue
            visited.add(identity)
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is str:
                        validate_runtime_string(key, path)
                    pending.append((child, f"{path}[{key!r}]", depth + 1))
            else:
                pending.extend((child, f"{path}[{index}]", depth + 1)
                               for index, child in enumerate(item))


def _validate_evidence_tree(value: object, label: str) -> None:
    """Validate the exact JSON-shaped domain accepted as runtime evidence.

    Lists and tuples are both accepted because the immutable model turns both
    into tuples.  Mappings must be exact dictionaries with string keys.  This
    deliberately excludes codec-adjacent Python objects (sets, custom
    mappings, bytes and iterators) from the external Garmin trust boundary.
    """
    pending = [(value, label, 0, frozenset())]
    while pending:
        item, path, depth, ancestors = pending.pop()
        item_type = type(item)
        if item_type is str:
            validate_runtime_string(item, path)
            continue
        if item is None or item_type is bool:
            continue
        if item_type is int:
            if abs(item) > _MAX_JSON_INTEGER:
                raise RuntimeActivityValidationError(
                    f"{path} contains an integer that cannot be serialized"
                )
            continue
        if item_type is float:
            if not isfinite(item):
                raise RuntimeActivityValidationError(
                    f"{path} contains a non-finite number"
                )
            continue
        if item_type not in (dict, list, tuple):
            raise RuntimeActivityValidationError(
                f"{path} contains an unsupported runtime value"
            )
        if depth >= _MAX_EVIDENCE_DEPTH:
            raise RuntimeActivityValidationError(f"{path} is nested too deeply")
        identity = id(item)
        if identity in ancestors:
            raise RuntimeActivityValidationError(f"{path} contains a recursive container")
        child_ancestors = ancestors | {identity}
        if item_type is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise RuntimeActivityValidationError(
                        f"{path} contains a non-string mapping key"
                    )
                validate_runtime_string(key, path)
                pending.append((child, f"{path}[{key!r}]", depth + 1,
                                child_ancestors))
        else:
            for index, child in enumerate(item):
                pending.append((child, f"{path}[{index}]", depth + 1,
                                child_ancestors))


def validate_process_timestamp(value: object, label: str, *, optional: bool = False) -> None:
    """Validate a caller-supplied process timestamp at the trust boundary."""
    if optional and value is None:
        return
    if type(value) is not datetime:
        raise RuntimeActivityValidationError(f"{label} must be timezone-aware")
    try:
        aware = value.tzinfo is not None and value.utcoffset() is not None
    except (TypeError, ValueError, AttributeError) as error:
        raise RuntimeActivityValidationError(
            f"{label} must be timezone-aware"
        ) from error
    if not aware:
        raise RuntimeActivityValidationError(f"{label} must be timezone-aware")


def _classifier(value: object, label: str) -> str:
    """Return a structurally valid classifier without normalizing its meaning."""
    if type(value) is not str or not value.strip():
        raise RuntimeActivityValidationError(
            f"{label} must be an explicit non-empty string"
        )
    validate_runtime_string(value, label)
    return value


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
    validate_runtime_string(value, label)
    return value


def _aware_timestamp(value: object, label: str) -> tuple[datetime, str]:
    if type(value) is not str:
        raise RuntimeActivityValidationError(f"{label} must be an explicit timestamp string")
    validate_runtime_string(value, label)
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


def _validated_number(value: object, label: str) -> int | float:
    if type(value) not in (int, float):
        raise RuntimeActivityValidationError(
            f"{label} must be a finite non-negative number"
        )
    try:
        supported = float(value)
        valid = (isfinite(supported) and supported >= 0
                 and not (type(value) is int and value > float_info.max))
    except (OverflowError, TypeError, ValueError) as error:
        raise RuntimeActivityValidationError(
            f"{label} must be a finite non-negative number"
        ) from error
    if not valid:
        raise RuntimeActivityValidationError(
            f"{label} must be a finite non-negative number"
        )
    return value


def _number(payload: dict, name: str) -> int | float | None:
    if name not in payload or payload[name] is None:
        return None
    return _validated_number(payload[name], name)


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
        result[field] = _validated_number(raw[field], f"{group}.{field}")
    return result or None


def build_actual_session(payload: dict, subject_ref: str, *, normalized_at: datetime,
                         captured_at: datetime | None = None):
    """Validate and normalize one untrusted projected Garmin activity."""
    # Phase 1: exhaustively validate the structural contract.  Do not perform
    # any classification in this phase: callers deliberately treat
    # UnsupportedRuntimeActivity as a non-error, so raising it before all
    # structural checks would hide corrupt input.
    if type(payload) is not dict:
        raise RuntimeActivityValidationError("activity must be an exact dict")
    subject = _required_identifier(subject_ref, "subject_ref")
    _validate_evidence_tree(payload, "activity")
    activity_id = _required_identifier(payload.get("activity_id"), "activity_id")
    validate_process_timestamp(normalized_at, "normalized_at")
    validate_process_timestamp(captured_at, "captured_at", optional=True)

    raw = payload.get("raw")
    if type(raw) is not dict:
        raise RuntimeActivityValidationError("raw must be an object")
    activity_type = (_classifier(raw["activity_type"], "raw.activity_type")
                     if "activity_type" in raw else None)
    sport = None
    if "sport" in payload:
        sport = _classifier(payload["sport"], "sport")

    segments = payload.get("segments")
    segment_classifiers = []
    if segments is not None:
        if type(segments) is not list:
            raise RuntimeActivityValidationError("segments must be a list")
        _validate_evidence_tree(segments, "segments")
        for segment in segments:
            if type(segment) is not dict:
                raise RuntimeActivityValidationError("segments must contain objects")
            # Validate every present classifier before performing any lookup or
            # comparing their meanings.  In particular, unhashable values must
            # never reach ``dict.get``.
            present = [(name, _classifier(segment[name], f"segment.{name}"))
                       for name in ("activity_type", "sport") if name in segment]
            segment_classifiers.append(present)

    start, timezone_name = _aware_timestamp(payload.get("date"), "date")
    end = None
    if payload.get("end") is not None:
        end, _ = _aware_timestamp(payload["end"], "end")
        if end < start:
            raise RuntimeActivityValidationError("end must not precede start")
    duration = _number(payload, "duration_minutes")
    # Duration missingness is already preserved by ActivityNormalizer, so the
    # canonical top-level value is the observation.  The raw field is optional
    # provenance rather than a required duplicate, but validate it whenever it
    # is supplied so malformed source data cannot be hidden by a valid
    # projection.
    _number(raw, "duration_minutes")
    projected_distance = _number(payload, "distance_km")
    raw_distance = _number(raw, "distance_km")
    # Distance is preserved only where explicit provenance distinguishes it
    # from ActivityNormalizer's synthetic zero.
    distance = projected_distance if raw_distance is not None else None
    heart_rate = _telemetry(payload, "heart_rate", ("average", "max"))
    power = _telemetry(payload, "power", ("average", "normalized"))
    metadata = payload.get("metadata")
    if metadata is not None and type(metadata) is not dict:
        raise RuntimeActivityValidationError("metadata must be an object")
    if metadata is not None:
        _validate_evidence_tree(metadata, "metadata")
    for name in ("source_id", "file_hash"):
        if name in payload and payload[name] is not None:
            _required_identifier(payload[name], name)

    # Phase 2: now, and only now, resolve the meaning of every classifier.
    if activity_type is None:
        raise UnsupportedRuntimeActivity("raw.activity_type is required")
    discipline = _DISCIPLINES.get(activity_type)
    if discipline is None:
        raise UnsupportedRuntimeActivity("raw.activity_type is unsupported")
    if sport is not None:
        if sport not in {item.value for item in Discipline}:
            raise UnsupportedRuntimeActivity("sport is unsupported")
        if sport != discipline.value:
            raise UnsupportedRuntimeActivity("sport contradicts raw.activity_type")
    for present in segment_classifiers:
        classifiers = []
        for name, classifier in present:
            if name == "activity_type":
                classifiers.append(_DISCIPLINES.get(classifier))
            else:
                classifiers.append(next((item for item in Discipline
                                         if item.value == classifier), None))
        if not classifiers or any(item is None for item in classifiers):
            raise UnsupportedRuntimeActivity("segment classification is unsupported")
        if len(set(classifiers)) != 1 or classifiers[0] is not discipline:
            raise UnsupportedRuntimeActivity("multi-discipline segments are unsupported")

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
