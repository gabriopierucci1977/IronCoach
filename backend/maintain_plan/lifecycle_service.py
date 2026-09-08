"""Pure append-only lifecycle validation and deterministic projections."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import fields, is_dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, Sequence

from .models import (
    ActualSessionRef, ConflictResolutionEventType, FeedbackEvent, FeedbackEventLog, FeedbackEventType,
    FeedbackProjection, FeedbackProjectionStatus, ResolutionLogRef,
    SourceConflictProjection, SourceConflictProjectionStatus,
    SourceConflictResolutionEvent, SourceConflictResolutionLog,
)

FEEDBACK_LOG_SCHEMA = "maintain-plan-feedback-events/1.0.0-draft"
FEEDBACK_EVENT_SCHEMA = "maintain-plan-feedback-event/1.0.0-draft"
CONFLICT_LOG_SCHEMA = "maintain-plan-source-conflict-events/1.0.0-draft"
CONFLICT_EVENT_SCHEMA = "maintain-plan-source-conflict-event/1.0.0-draft"
CONFLICT_PROJECTION_POLICY_ID = "maintain-plan-source-conflict-projection"
CONFLICT_PROJECTION_POLICY_VERSION = "1.0.0-draft"
CONFLICT_SERIALIZATION_POLICY_ID = "maintain-plan-source-conflict-projection-canonical-json"
CONFLICT_SERIALIZATION_POLICY_VERSION = "1.0.0-draft"
PROJECTION_HASH_ALGORITHM = "SHA-256"
SUBJECTIVE_FEEDBACK_SCHEMA = "maintain-plan-subjective-feedback/1.0.0-draft"
_FEEDBACK_FIELDS = frozenset({
    "feedback_id", "schema_version", "payload_hash", "rpe", "pain",
    "unusual_fatigue", "interruption", "reason", "note", "captured_at",
    "provenance", "missing_fields", "warnings",
})
_IMMUTABLE_FEEDBACK_FIELDS = (
    "feedback_id", "schema_version", "payload_hash", "captured_at", "provenance",
)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _plain(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {field.name: _plain(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"unsupported canonical projection value: {type(value).__name__}")


def _valid_nested(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, Mapping):
        return all(isinstance(key, str) and _valid_nested(item)
                   for key, item in value.items())
    if isinstance(value, (tuple, list, set, frozenset)):
        return all(_valid_nested(item) for item in value)
    return False


def _structural_form(value: Any) -> Any:
    """Preserve every value while equating only approved container representations."""
    if isinstance(value, Mapping):
        items = [(_structural_form(key), _structural_form(item)) for key, item in value.items()]
        return ("mapping", tuple(sorted(items, key=repr)))
    if isinstance(value, (tuple, list)):
        return ("sequence", tuple(_structural_form(item) for item in value))
    if isinstance(value, (set, frozenset)):
        return ("set", tuple(sorted((_structural_form(item) for item in value), key=repr)))
    if isinstance(value, datetime):
        return ("datetime", value)
    if isinstance(value, Enum):
        return ("enum", type(value).__qualname__, value.value)
    return (type(value).__qualname__, value)


def structurally_equivalent(left: Any, right: Any) -> bool:
    return _structural_form(left) == _structural_form(right)


def _feedback_timestamp(value: Any) -> bool:
    if isinstance(value, datetime):
        return _aware(value)
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return False
    return _aware(parsed)


def validate_feedback_payload(payload: Mapping[str, Any] | None, *,
                              baseline: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    """Validate a complete subjective-feedback payload without coercion or repair."""
    errors: list[str] = []
    if not isinstance(payload, Mapping):
        return ("feedback payload must be a mapping",)
    if set(payload) != _FEEDBACK_FIELDS:
        errors.append("feedback payload fields do not exactly match the schema")
        return tuple(errors)
    if not isinstance(payload["feedback_id"], str) or not payload["feedback_id"]:
        errors.append("feedback_id must be a non-empty string")
    if payload["schema_version"] != SUBJECTIVE_FEEDBACK_SCHEMA:
        errors.append("feedback schema_version is unsupported")
    digest = payload["payload_hash"]
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        errors.append("feedback payload_hash must be a lowercase SHA-256 digest")
    for name, minimum in (("rpe", 1), ("pain", 0)):
        value = payload[name]
        if value is not None and (type(value) not in (int, float) or
                                  not math.isfinite(value) or value < minimum or value > 10):
            errors.append(
                f"feedback {name} must be null or a finite number from {minimum} to 10")
    if payload["unusual_fatigue"] not in (None, "NONE", "MILD", "MODERATE", "HIGH"):
        errors.append("feedback unusual_fatigue is invalid")
    if payload["interruption"] is not None and type(payload["interruption"]) is not bool:
        errors.append("feedback interruption must be boolean or null")
    if payload["reason"] not in (None, "HEALTH", "WORK_TIME", "WEATHER", "EQUIPMENT", "OTHER"):
        errors.append("feedback reason is invalid")
    if payload["note"] is not None and not isinstance(payload["note"], str):
        errors.append("feedback note must be a string or null")
    if not _feedback_timestamp(payload["captured_at"]):
        errors.append("feedback captured_at must be timezone-aware")
    if not isinstance(payload["provenance"], Mapping) or not payload["provenance"] or \
            not _valid_nested(payload["provenance"]):
        errors.append("feedback provenance must be a non-empty valid mapping")
    for name in ("missing_fields", "warnings"):
        values = payload[name]
        if not isinstance(values, (tuple, list)) or not all(isinstance(item, str) for item in values):
            errors.append(f"feedback {name} must be a list of strings")
        elif len(set(values)) != len(values):
            errors.append(f"feedback {name} must not contain duplicates")
    if baseline is not None:
        baseline_errors = validate_feedback_payload(baseline)
        if baseline_errors:
            errors.append("canonical feedback baseline is invalid")
        else:
            for name in _IMMUTABLE_FEEDBACK_FIELDS:
                if payload[name] != baseline[name]:
                    errors.append(f"feedback immutable field {name} differs from baseline")
    return tuple(errors)


def validate_feedback_log(log: FeedbackEventLog) -> tuple[str, ...]:
    errors = []
    if not log.feedback_log_id:
        errors.append("feedback_log_id is required")
    if log.schema_version != FEEDBACK_LOG_SCHEMA:
        errors.append("feedback log schema version is unsupported")
    if log.feedback_ref.session_id != log.actual_session_ref.session_id:
        errors.append("feedback log session references are incoherent")
    if not log.feedback_ref.feedback_id:
        errors.append("feedback_id is required")
    return tuple(errors)


def validate_feedback_event(event: FeedbackEvent, log: FeedbackEventLog,
                            baseline: Mapping[str, Any] | None = None) -> tuple[str, ...]:
    errors = list(validate_feedback_log(log))
    if event.schema_version != FEEDBACK_EVENT_SCHEMA:
        errors.append("feedback event schema version is unsupported")
    if not event.feedback_event_id or not event.actor or not _aware(event.occurred_at):
        errors.append("feedback event id, actor and timezone-aware occurred_at are required")
    expected_ref = (log.feedback_log_id, log.feedback_ref.session_id, log.feedback_ref.feedback_id)
    actual_ref = (event.feedback_log_ref.feedback_log_id, event.feedback_log_ref.session_id,
                  event.feedback_log_ref.feedback_id)
    if actual_ref != expected_ref or event.feedback_ref != log.feedback_ref or event.actual_session_ref != log.actual_session_ref:
        errors.append("feedback event references are incoherent")
    if event.event_sequence < 1 or event.stream_version != event.event_sequence:
        errors.append("feedback event sequence and stream version must be equal and positive")
    if not event.baseline_schema_version or not event.baseline_payload_hash:
        errors.append("feedback baseline schema and hash are required")
    if event.event_type is FeedbackEventType.CAPTURED:
        if event.event_sequence != 1 or event.previous_event_id is not None:
            errors.append("CAPTURED must be the first event")
        if any((event.corrected_payload is not None, event.superseded_event_ref is not None,
                event.deletion_reason_or_ref is not None)):
            errors.append("CAPTURED must not contain lifecycle payload")
    elif event.event_type is FeedbackEventType.CORRECTED:
        if event.corrected_payload is None or event.superseded_event_ref is None:
            errors.append("CORRECTED requires a complete payload and superseded event")
        if event.deletion_reason_or_ref is not None:
            errors.append("CORRECTED must not contain deletion metadata")
        if baseline is not None:
            errors.extend(validate_feedback_payload(event.corrected_payload, baseline=baseline))
    elif event.event_type is FeedbackEventType.DELETED:
        if event.corrected_payload is not None or event.deletion_reason_or_ref is None:
            errors.append("DELETED requires only deletion metadata")
    return tuple(errors)


def validate_resolution_log(log: SourceConflictResolutionLog) -> tuple[str, ...]:
    errors = []
    if not log.resolution_log_id:
        errors.append("resolution_log_id is required")
    if log.schema_version != CONFLICT_LOG_SCHEMA:
        errors.append("resolution log schema version is unsupported")
    if log.conflict_ref.session_id != log.actual_session_ref.session_id:
        errors.append("resolution log session references are incoherent")
    if not log.conflict_ref.conflict_id:
        errors.append("source conflict id is required")
    return tuple(errors)


def validate_resolution_event(event: SourceConflictResolutionEvent,
                              log: SourceConflictResolutionLog) -> tuple[str, ...]:
    errors = list(validate_resolution_log(log))
    expected = ResolutionLogRef(log.resolution_log_id, log.conflict_ref.conflict_id,
                                log.actual_session_ref.session_id)
    if (event.resolution_log_ref != expected or event.resolution_log_id != log.resolution_log_id or
            event.source_conflict_id != log.conflict_ref.conflict_id or
            event.actual_session_ref != log.actual_session_ref):
        errors.append("resolution event references are incoherent")
    if event.schema_version != CONFLICT_EVENT_SCHEMA:
        errors.append("resolution event schema version is unsupported")
    if not event.event_id or event.event_sequence < 1 or not event.actor or not _aware(event.occurred_at):
        errors.append("resolution event id, sequence, actor and timezone-aware occurred_at are required")
    if event.event_type is ConflictResolutionEventType.RESOLVED:
        if (event.selected_value is None or not event.selected_source or event.unknown_answer or
                event.withdrawn_event_ref is not None or not event.provenance):
            errors.append("RESOLVED selection fields are incoherent")
    elif event.event_type is ConflictResolutionEventType.UNKNOWN_ANSWER:
        if (event.selected_value is not None or event.selected_source is not None or
                not event.unknown_answer or event.withdrawn_event_ref is not None):
            errors.append("UNKNOWN_ANSWER fields are incoherent")
    elif event.event_type is ConflictResolutionEventType.RESOLUTION_WITHDRAWN:
        if (event.selected_value is not None or event.selected_source is not None or
                event.unknown_answer or event.withdrawn_event_ref is None):
            errors.append("RESOLUTION_WITHDRAWN fields are incoherent")
    return tuple(errors)


def _chain_errors(events: Sequence[Any], id_name: str) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    previous = None
    for expected_sequence, event in enumerate(events, 1):
        identifier = getattr(event, id_name)
        if identifier in seen:
            errors.append("duplicate event id")
        seen.add(identifier)
        if event.event_sequence != expected_sequence:
            errors.append("event sequence is incomplete or non-monotonic")
        if event.previous_event_id != previous:
            errors.append("previous_event_id chain is incoherent")
        previous = identifier
    return errors


def project_feedback(*, projection_id: str, projection_version: str,
                     log: FeedbackEventLog, baseline: Mapping[str, Any] | None,
                     events: Sequence[FeedbackEvent], provenance: Mapping[str, Any]) -> FeedbackProjection:
    errors = list(validate_feedback_log(log))
    errors.extend(validate_feedback_payload(baseline))
    for event in events:
        errors.extend(validate_feedback_event(event, log, baseline))
    errors.extend(_chain_errors(events, "feedback_event_id"))
    captured = [event for event in events if event.event_type is FeedbackEventType.CAPTURED]
    baseline_schema = "" if baseline is None else str(baseline.get("schema_version", ""))
    baseline_hash = "" if baseline is None else str(baseline.get("payload_hash", ""))
    if baseline is None:
        errors.append("feedback baseline is unavailable")
    if len(captured) != 1 or (captured and events and captured[0] is not events[0]):
        errors.append("feedback stream requires exactly one initial CAPTURED event")
    if captured and (captured[0].baseline_schema_version != baseline_schema or
                     captured[0].baseline_payload_hash != baseline_hash):
        errors.append("feedback baseline schema or hash mismatch")
    payload = baseline
    deleted = False
    if not errors:
        for index, event in enumerate(events[1:], 1):
            if event.baseline_schema_version != baseline_schema or event.baseline_payload_hash != baseline_hash:
                errors.append("feedback event baseline metadata mismatch")
                break
            if event.event_type is FeedbackEventType.CAPTURED:
                errors.append("duplicate CAPTURED event")
                break
            if deleted:
                errors.append("event after DELETED is invalid")
                break
            if event.superseded_event_ref is not None and event.superseded_event_ref != events[index - 1].feedback_event_id:
                errors.append("superseded feedback event is incoherent")
                break
            if event.event_type is FeedbackEventType.CORRECTED:
                payload = event.corrected_payload
            else:
                deleted = True
                payload = None
    status = (FeedbackProjectionStatus.INVALID if errors else
              FeedbackProjectionStatus.DELETED if deleted else FeedbackProjectionStatus.ACTIVE)
    last = events[-1] if events else None
    return FeedbackProjection(
        projection_id, projection_version,
        log_ref(log), log.feedback_ref, log.actual_session_ref,
        captured[0].feedback_event_id if len(captured) == 1 else None,
        None if last is None else last.feedback_event_id,
        None if last is None else last.event_sequence,
        baseline_schema, baseline_hash, status, None if errors or deleted else payload,
        provenance, tuple(errors), tuple(errors),
    )


def log_ref(log: FeedbackEventLog):
    from .models import FeedbackLogRef
    return FeedbackLogRef(log.feedback_log_id, log.feedback_ref.session_id,
                          log.feedback_ref.feedback_id)


_CONFLICT_PREIMAGE_FIELDS = (
    "projection_id", "projection_version", "projection_hash_algorithm",
    "projection_serialization_policy_id", "projection_serialization_policy_version",
    "source_conflict_id", "actual_session_ref", "resolution_log_ref",
    "through_event_id", "through_event_sequence", "status", "selected_value",
    "selected_source", "policy_id", "policy_version", "provenance", "computed_at",
    "missing_fields", "warnings",
)


def source_conflict_projection_preimage(value: SourceConflictProjection) -> bytes:
    canonical = {name: _plain(getattr(value, name)) for name in _CONFLICT_PREIMAGE_FIELDS}
    return json.dumps(canonical, allow_nan=False, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def source_conflict_projection_hash(value: SourceConflictProjection) -> str:
    return hashlib.sha256(source_conflict_projection_preimage(value)).hexdigest()


def project_source_conflict(*, projection_id: str, projection_version: str,
                            log: SourceConflictResolutionLog | None,
                            source_conflict: Mapping[str, Any] | None,
                            events: Sequence[SourceConflictResolutionEvent],
                            provenance: Mapping[str, Any], computed_at: datetime) -> SourceConflictProjection:
    errors: list[str] = []
    if not projection_id or not projection_version or not _aware(computed_at):
        errors.append("projection id, version and timezone-aware computed_at are required")
    if log is None:
        errors.append("resolution log is unavailable")
        # A fully qualified placeholder is still explicit and audit-friendly.
        ref = ResolutionLogRef("", "", "")
        conflict_id = ""
        session_ref = ActualSessionRef("")
    else:
        errors.extend(validate_resolution_log(log))
        ref = ResolutionLogRef(log.resolution_log_id, log.conflict_ref.conflict_id,
                               log.actual_session_ref.session_id)
        conflict_id = log.conflict_ref.conflict_id
        session_ref = log.actual_session_ref
    if source_conflict is None:
        errors.append("source conflict is unavailable")
    elif log is not None and (source_conflict.get("conflict_id") != conflict_id or
                              source_conflict.get("session_id", session_ref.session_id) != session_ref.session_id):
        errors.append("source conflict reference is incoherent")
    if log is not None:
        for event in events:
            errors.extend(validate_resolution_event(event, log))
    errors.extend(_chain_errors(events, "event_id"))
    status = SourceConflictProjectionStatus.UNRESOLVED
    selected_value = selected_source = None
    current_event_id: str | None = None
    if not errors:
        for event in events:
            if event.event_type is ConflictResolutionEventType.RESOLVED:
                if status not in (SourceConflictProjectionStatus.UNRESOLVED,):
                    errors.append("RESOLVED is invalid for the current state")
                    break
                status = SourceConflictProjectionStatus.RESOLVED
                selected_value, selected_source = event.selected_value, event.selected_source
                current_event_id = event.event_id
            elif event.event_type is ConflictResolutionEventType.UNKNOWN_ANSWER:
                if status is not SourceConflictProjectionStatus.UNRESOLVED:
                    errors.append("UNKNOWN_ANSWER is invalid for the current state")
                    break
                status = SourceConflictProjectionStatus.DONT_KNOW
                selected_value = selected_source = None
                current_event_id = event.event_id
            else:
                if status not in (SourceConflictProjectionStatus.RESOLVED,
                                   SourceConflictProjectionStatus.DONT_KNOW) or event.withdrawn_event_ref != current_event_id:
                    errors.append("RESOLUTION_WITHDRAWN does not identify the current resolution")
                    break
                status = SourceConflictProjectionStatus.UNRESOLVED
                selected_value = selected_source = current_event_id = None
    if errors:
        status = SourceConflictProjectionStatus.INVALID
        selected_value = selected_source = None
    last = events[-1] if events else None
    projection = SourceConflictProjection(
        projection_id, projection_version, "", PROJECTION_HASH_ALGORITHM,
        CONFLICT_SERIALIZATION_POLICY_ID, CONFLICT_SERIALIZATION_POLICY_VERSION,
        conflict_id, session_ref, ref, None if last is None else last.event_id,
        None if last is None else last.event_sequence, status, selected_value, selected_source,
        CONFLICT_PROJECTION_POLICY_ID, CONFLICT_PROJECTION_POLICY_VERSION, provenance,
        computed_at, tuple(errors), tuple(errors),
    )
    return replace(projection, projection_hash=source_conflict_projection_hash(projection))


def validate_source_conflict_projection(value: SourceConflictProjection) -> tuple[str, ...]:
    errors = []
    if value.projection_hash_algorithm != PROJECTION_HASH_ALGORITHM:
        errors.append("projection hash algorithm is unsupported")
    if (value.projection_serialization_policy_id != CONFLICT_SERIALIZATION_POLICY_ID or
            value.projection_serialization_policy_version != CONFLICT_SERIALIZATION_POLICY_VERSION):
        errors.append("projection serialization policy is unsupported")
    if (value.policy_id != CONFLICT_PROJECTION_POLICY_ID or
            value.policy_version != CONFLICT_PROJECTION_POLICY_VERSION):
        errors.append("projection policy is unsupported")
    if value.projection_hash != source_conflict_projection_hash(value):
        errors.append("projection hash mismatch")
    if (value.through_event_id is None) != (value.through_event_sequence is None):
        errors.append("projection event cursor is incoherent")
    if value.status is SourceConflictProjectionStatus.RESOLVED:
        if value.selected_value is None or not value.selected_source:
            errors.append("RESOLVED projection requires selection")
    elif value.selected_value is not None or value.selected_source is not None:
        errors.append("non-RESOLVED projection must not expose selection")
    return tuple(errors)
