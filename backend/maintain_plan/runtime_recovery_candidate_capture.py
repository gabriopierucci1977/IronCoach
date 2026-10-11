"""Opt-in capture and persistence of explicit recovery candidate sets."""

from __future__ import annotations

from .repository import MaintainPlanRepository
from .runtime_recovery_adapter import (
    RuntimeRecoveryAdapterError,
    build_recovery_candidate_set,
)
from .stability_models import RecoveryAssessmentCandidateSet
from .stability_validators import validate_recovery_candidate_set


class RecoveryCandidateSetCaptureError(ValueError):
    def __init__(self, errors, *, code="INPUT_INVALID"):
        self.code = code
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def build_recovery_candidate_set_capture(
    *,
    records,
    actual_session_ref,
    subject_ref,
    captured_at,
    evaluated_cutoff_at,
    provenance_ref,
    analyzer_ref=None,
) -> RecoveryAssessmentCandidateSet:
    """Build one candidate set from caller-scoped records without source lookup."""
    try:
        value = build_recovery_candidate_set(
            records,
            actual_session_ref=actual_session_ref,
            subject_ref=subject_ref,
            captured_at=captured_at,
            evaluated_cutoff_at=evaluated_cutoff_at,
            provenance_ref=provenance_ref,
            analyzer_ref=analyzer_ref,
        )
    except RuntimeRecoveryAdapterError as error:
        raise RecoveryCandidateSetCaptureError(error.errors, code=error.code) from error
    except ValueError as error:
        if isinstance(error, RecoveryCandidateSetCaptureError):
            raise
        raise RecoveryCandidateSetCaptureError((str(error),)) from error
    errors = validate_recovery_candidate_set(value)
    if errors:
        raise RecoveryCandidateSetCaptureError(errors)
    return value


class RuntimeRecoveryCandidateSetCapture:
    def __init__(self, repository_factory=MaintainPlanRepository):
        self._repository_factory = repository_factory

    def capture(self, *, candidate_set_id, enabled=False, database_path=None, **inputs):
        """Validate before opening SQLite; disabled calls have no side effects."""
        if enabled is not True:
            return None
        if type(candidate_set_id) is not str or not candidate_set_id.strip():
            raise RecoveryCandidateSetCaptureError(
                ("candidate_set_id must be a non-empty string",),
                code="INPUT_MISSING",
            )
        value = build_recovery_candidate_set_capture(**inputs)
        if database_path is None:
            raise RecoveryCandidateSetCaptureError(
                ("database_path is required",), code="INPUT_MISSING",
            )
        repository = self._repository_factory(database_path)
        return repository.acquire_recovery_candidate_set(candidate_set_id, value)
