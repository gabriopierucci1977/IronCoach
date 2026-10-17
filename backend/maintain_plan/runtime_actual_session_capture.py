"""Opt-in runtime capture of atomic Garmin ActualSession records."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .repository import ActualSessionConflictError, MaintainPlanRepository
from .runtime_actual_session_adapter import (
    RuntimeActivityValidationError,
    UnsupportedRuntimeActivity,
    build_actual_session,
    validate_process_timestamp,
    validate_runtime_string,
    validate_runtime_unicode_tree,
)
from .serialization import serialize_contract
from .models import ActualSession


@dataclass(frozen=True)
class RuntimeActualSessionCaptureResult:
    created: tuple[str, ...] = ()
    reused: tuple[str, ...] = ()
    unsupported: tuple[int, ...] = ()
    captured_sessions: tuple[ActualSession, ...] = field(
        default=(),
        compare=False,
        repr=False,
    )


def _semantic(value: Any) -> Any:
    data = json.loads(serialize_contract(value))

    def scrub(item):
        if isinstance(item, dict):
            return {
                key: scrub(child)
                for key, child in item.items()
                if key not in {"normalized_at", "captured_at"}
            }
        if isinstance(item, list):
            return [scrub(child) for child in item]
        return item

    return scrub(data)


def _contains_manual_fit(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            if (
                isinstance(key, str)
                and key.casefold() in {
                    "file_name",
                    "filename",
                    "fit_file",
                    "fit_filename",
                }
                and isinstance(child, str)
                and child.casefold().endswith(".fit")
            ):
                return True
            if _contains_manual_fit(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_manual_fit(child) for child in value)

    return False


def _duplicate_key(payload: object) -> tuple[object, ...] | None:
    if not isinstance(payload, dict):
        return None

    raw = payload.get("raw")
    if not isinstance(raw, dict):
        raw = {}

    start_value = payload.get("date")
    discipline = payload.get("sport") or raw.get("activity_type")
    duration = payload.get("duration_minutes")
    distance = payload.get("distance_km")

    if (
        not isinstance(start_value, str)
        or not isinstance(discipline, str)
        or not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or not isinstance(distance, (int, float))
        or isinstance(distance, bool)
    ):
        return None

    try:
        start = datetime.fromisoformat(
            start_value[:-1] + "+00:00"
            if start_value.endswith("Z")
            else start_value
        )
        if start.tzinfo is not None and start.utcoffset() is not None:
            start = start.astimezone(timezone.utc)

        start = start.replace(second=0, microsecond=0)

        return (
            start.isoformat(),
            discipline.casefold().replace("_", " "),
            round(float(duration)),
            round(float(distance), 1),
        )
    except (TypeError, ValueError, OverflowError):
        return None


def _deduplicate_candidate_records(records):
    grouped = {}
    for record in records:
        key = _duplicate_key(record[1])
        if key is not None:
            grouped.setdefault(key, []).append(record)

    selected_ids = set()

    for group in grouped.values():
        fit_records = [
            record
            for record in group
            if _contains_manual_fit(record[1])
        ]

        if fit_records:
            selected_ids.update(id(record) for record in fit_records)
        else:
            selected_ids.update(id(record) for record in group)

    selected = []
    for record in records:
        key = _duplicate_key(record[1])

        if key is None or id(record) in selected_ids:
            selected.append(record)

    return selected


class RuntimeActualSessionCapture:
    def __init__(
        self,
        repository_factory: Callable[[str], object] = MaintainPlanRepository,
    ):
        self._repository_factory = repository_factory

    def capture(
        self,
        *,
        runtime_config,
        athlete,
        garmin_training_history,
        normalized_at: datetime,
        captured_at: datetime | None = None,
    ):
        enabled = getattr(
            runtime_config,
            "maintain_plan_actual_session_enabled",
            None,
        )

        if enabled is not True:
            return None

        if type(enabled) is not bool:
            return None

        if type(athlete) is not dict:
            raise RuntimeActivityValidationError(
                "athlete must be an exact dict"
            )

        validate_runtime_unicode_tree(athlete, "athlete")
        subject_ref = athlete.get("source_id")

        if (
            type(subject_ref) is not str
            or not subject_ref
            or not subject_ref.strip()
        ):
            raise RuntimeActivityValidationError(
                "athlete.source_id must be an explicit non-empty string"
            )

        validate_runtime_string(subject_ref, "athlete.source_id")

        if type(garmin_training_history) is not list:
            raise RuntimeActivityValidationError(
                "garmin_training_history must be an exact list"
            )

        validate_process_timestamp(normalized_at, "normalized_at")
        validate_process_timestamp(
            captured_at,
            "captured_at",
            optional=True,
        )

        candidate_records = []
        unsupported = []

        for index, payload in enumerate(garmin_training_history):
            try:
                candidate_records.append(
                    (
                        index,
                        payload,
                        build_actual_session(
                            payload,
                            subject_ref,
                            normalized_at=normalized_at,
                            captured_at=captured_at,
                        ),
                    )
                )
            except UnsupportedRuntimeActivity:
                unsupported.append(index)

        candidate_records = _deduplicate_candidate_records(
            candidate_records
        )
        candidates = [record[2] for record in candidate_records]

        if not candidates:
            return RuntimeActualSessionCaptureResult(
                unsupported=tuple(unsupported),
                captured_sessions=(),
            )

        repository = self._repository_factory(
            runtime_config.maintain_plan_database_path
        )

        created = []
        reused = []

        with repository.actual_session_capture_transaction() as transaction:
            for candidate in candidates:
                existing = transaction.get_all(candidate.session_id)

                if existing:
                    if any(
                        _semantic(item) != _semantic(existing[0])
                        for item in existing[1:]
                    ):
                        raise ActualSessionConflictError(
                            "divergent duplicate stored sessions"
                        )

                    if _semantic(existing[0]) != _semantic(candidate):
                        raise ActualSessionConflictError(
                            "session_id has a different payload"
                        )

                    reused.append(candidate.session_id)
                else:
                    transaction.create(candidate)
                    created.append(candidate.session_id)

        return RuntimeActualSessionCaptureResult(
            tuple(created),
            tuple(reused),
            tuple(unsupported),
            tuple(candidates),
        )
