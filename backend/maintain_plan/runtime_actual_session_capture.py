"""Opt-in runtime capture of atomic Garmin ActualSession records."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .repository import ActualSessionConflictError, MaintainPlanRepository
from .runtime_actual_session_adapter import (
    UnsupportedRuntimeActivity, build_actual_session,
)
from .serialization import serialize_contract


@dataclass(frozen=True)
class RuntimeActualSessionCaptureResult:
    created: tuple[str, ...] = ()
    reused: tuple[str, ...] = ()
    unsupported: tuple[int, ...] = ()


def _semantic(value: Any) -> Any:
    data = json.loads(serialize_contract(value))
    def scrub(item):
        if isinstance(item, dict):
            return {key: scrub(child) for key, child in item.items()
                    if key not in {"normalized_at", "captured_at"}}
        if isinstance(item, list):
            return [scrub(child) for child in item]
        return item
    return scrub(data)


class RuntimeActualSessionCapture:
    def __init__(self, repository_factory: Callable[[str], object] = MaintainPlanRepository):
        self._repository_factory = repository_factory

    def capture(self, *, runtime_config, athlete, garmin_training_history,
                normalized_at: datetime, captured_at: datetime | None = None):
        enabled = getattr(runtime_config, "maintain_plan_actual_session_enabled", None)
        if enabled is not True:
            return None
        if type(enabled) is not bool:
            return None
        if type(athlete) is not dict:
            raise ValueError("athlete must be an exact dict")
        subject_ref = athlete.get("source_id")
        if type(subject_ref) is not str or not subject_ref or not subject_ref.strip():
            raise ValueError("athlete.source_id must be an explicit non-empty string")
        if type(garmin_training_history) is not list:
            raise ValueError("garmin_training_history must be an exact list")
        if (type(normalized_at) is not datetime or normalized_at.tzinfo is None
                or normalized_at.utcoffset() is None):
            raise ValueError("normalized_at must be timezone-aware")
        if (captured_at is not None and
                (type(captured_at) is not datetime or captured_at.tzinfo is None
                 or captured_at.utcoffset() is None)):
            raise ValueError("captured_at must be timezone-aware")

        candidates = []
        unsupported = []
        for index, payload in enumerate(garmin_training_history):
            try:
                candidates.append(build_actual_session(
                    payload, subject_ref, normalized_at=normalized_at,
                    captured_at=captured_at,
                ))
            except UnsupportedRuntimeActivity:
                unsupported.append(index)

        if not candidates:
            return RuntimeActualSessionCaptureResult(unsupported=tuple(unsupported))

        # All untrusted input has been classified/normalized before migrations.
        repository = self._repository_factory(runtime_config.maintain_plan_database_path)
        created, reused = [], []
        # One lock and one transaction cover the complete batch.  Besides making
        # concurrent idempotent retries deterministic, this ensures a conflict
        # discovered late in the batch rolls back every earlier insertion.
        with repository.actual_session_capture_transaction() as transaction:
            for candidate in candidates:
                existing = transaction.get_all(candidate.session_id)
                if existing:
                    if any(_semantic(item) != _semantic(existing[0]) for item in existing[1:]):
                        raise ActualSessionConflictError("divergent duplicate stored sessions")
                    if _semantic(existing[0]) != _semantic(candidate):
                        raise ActualSessionConflictError("session_id has a different payload")
                    reused.append(candidate.session_id)
                else:
                    transaction.create(candidate)
                    created.append(candidate.session_id)
        return RuntimeActualSessionCaptureResult(tuple(created), tuple(reused), tuple(unsupported))
