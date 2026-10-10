"""Pure adapter from explicit runtime recovery records to stability contracts.

This module deliberately does not read the Garmin archive, perform I/O, or
derive a recovery category from a numeric readiness/body-battery value.  The
caller must provide the runtime timestamps and the subject-scoped context.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .runtime_stability_provider import (
    RuntimeStabilityProviderResult,
    provide_runtime_stability,
)
from .stability_models import (
    ActualSessionBoundary,
    AnalyzerRef,
    CategoryMissingness,
    GeneralStabilityInput,
    PrescriptionBaselineBinding,
    ProvenanceRef,
    RecoveryAssessment,
    RecoveryAssessmentCandidateSet,
    RecoveryCategory,
    STABILITY_CONTRACT_VERSION,
    STABILITY_POLICY_ID,
    STABILITY_POLICY_VERSION,
    VersionedArtifactRef,
)
from .stability_validators import validate_general_stability_input


RECOVERY_ASSESSMENT_SCHEMA_VERSION = "runtime-recovery-assessment/1.0.0"
RECOVERY_PROVENANCE_VERSION = "1"
RECOVERY_ARTIFACT_TYPE = "recovery-observation"
RECOVERY_PROVENANCE_TYPE = "runtime-recovery-record"
RECOVERY_ANALYZER_ID = "runtime-recovery-source"


class RuntimeRecoveryAdapterError(ValueError):
    """Fail-closed error at the runtime recovery trust boundary."""

    def __init__(self, errors: Iterable[str], *, code: str = "INPUT_INVALID"):
        self.code = code
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def _is_aware(value: object) -> bool:
    return isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None


def _parse_timestamp(value: object, field: str) -> datetime:
    if isinstance(value, datetime):
        if not _is_aware(value):
            raise RuntimeRecoveryAdapterError((f"{field} must be timezone-aware",))
        return value
    if type(value) is not str or not value.strip():
        raise RuntimeRecoveryAdapterError((f"{field} is required as an explicit timezone-aware timestamp",),
                                          code="INPUT_MISSING")
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
    except ValueError as exc:
        raise RuntimeRecoveryAdapterError((f"{field} is not a valid ISO-8601 timestamp",)) from exc
    if not _is_aware(parsed):
        raise RuntimeRecoveryAdapterError((f"{field} must be timezone-aware",))
    return parsed


def _required_text(record: dict[str, Any], field: str) -> str:
    value = record.get(field)
    if type(value) is not str or not value.strip():
        raise RuntimeRecoveryAdapterError((f"record.{field} is required",), code="INPUT_MISSING")
    return value.strip()


def _category(record: dict[str, Any]) -> tuple[RecoveryCategory | None, CategoryMissingness, tuple[str, ...]]:
    values = []
    for field in ("recovery_category", "category"):
        if field in record and record[field] is not None:
            values.append((field, record[field]))
    if not values:
        return None, CategoryMissingness.MISSING, ("candidate_set.candidates[].category",)
    first = values[0][1]
    if len(values) > 1 and values[1][1] != first:
        raise RuntimeRecoveryAdapterError(("record.recovery_category and record.category disagree",))
    if isinstance(first, RecoveryCategory):
        return first, CategoryMissingness.NOT_MISSING, ()
    if type(first) is not str:
        raise RuntimeRecoveryAdapterError(("record category must be one of LOW, MODERATE, HIGH, CRITICAL",))
    try:
        return RecoveryCategory(first), CategoryMissingness.NOT_MISSING, ()
    except ValueError as exc:
        raise RuntimeRecoveryAdapterError(("record category must be one of LOW, MODERATE, HIGH, CRITICAL",)) from exc


def _assessment_provenance(source_id: str) -> tuple[VersionedArtifactRef, ProvenanceRef]:
    evidence = VersionedArtifactRef(RECOVERY_ARTIFACT_TYPE, source_id, RECOVERY_PROVENANCE_VERSION)
    provenance = ProvenanceRef(
        producer=evidence,
        provenance_type=RECOVERY_PROVENANCE_TYPE,
        provenance_id=source_id,
        provenance_version=RECOVERY_PROVENANCE_VERSION,
    )
    return evidence, provenance


def build_recovery_assessment(
    record: object,
    *,
    subject_ref: object,
    missing_category_path: str = "candidate_set.candidates[].category",
) -> RecoveryAssessment:
    """Convert one source record using only explicit, typed evidence."""
    if type(record) is not dict:
        raise RuntimeRecoveryAdapterError(("record must be a dictionary",))
    if type(subject_ref) is not str or not subject_ref.strip():
        raise RuntimeRecoveryAdapterError(("subject_ref must be a non-empty string",))
    subject = subject_ref.strip()
    source = _required_text(record, "source")
    source_id = _required_text(record, "source_id")
    _required_text(record, "date")
    claimed_subject = record.get("subject_ref")
    if claimed_subject is not None and claimed_subject != subject:
        raise RuntimeRecoveryAdapterError(("record subject_ref does not match runtime subject",))
    observed_at = _parse_timestamp(record.get("observed_at"), "record.observed_at")
    assessed_at = _parse_timestamp(record.get("assessed_at"), "record.assessed_at")
    if observed_at > assessed_at:
        raise RuntimeRecoveryAdapterError(("record.observed_at must not follow record.assessed_at",))
    category, missingness, missing = _category(record)
    if missingness is CategoryMissingness.MISSING:
        missing = (missing_category_path,)
    evidence, provenance = _assessment_provenance(source_id)
    analyzer = AnalyzerRef(
        RECOVERY_ANALYZER_ID,
        RECOVERY_PROVENANCE_VERSION,
        RECOVERY_ASSESSMENT_SCHEMA_VERSION,
    )
    return RecoveryAssessment(
        assessment_id=f"maintain-plan:recovery-assessment:{source}:{source_id}",
        contract_version=STABILITY_CONTRACT_VERSION,
        analyzer_ref=analyzer,
        subject_ref=subject,
        observed_at=observed_at,
        assessed_at=assessed_at,
        category=category,
        category_missingness=missingness,
        evidence_refs=(evidence,),
        provenance_ref=provenance,
        missing_fields=missing,
        warnings=(),
    )


def build_recovery_candidate_set(
    records: object,
    *,
    actual_session_ref: object,
    subject_ref: object,
    captured_at: object,
    evaluated_cutoff_at: object,
    provenance_ref: object,
) -> RecoveryAssessmentCandidateSet:
    """Build the candidate set from an explicit, already scoped record list."""
    if type(records) not in (list, tuple):
        raise RuntimeRecoveryAdapterError(("records must be a list or tuple",))
    if type(actual_session_ref) is not VersionedArtifactRef:
        raise RuntimeRecoveryAdapterError(("actual_session_ref must be a VersionedArtifactRef",))
    if type(provenance_ref) is not ProvenanceRef:
        raise RuntimeRecoveryAdapterError(("provenance_ref must be a ProvenanceRef",))
    captured = _parse_timestamp(captured_at, "captured_at")
    cutoff = _parse_timestamp(evaluated_cutoff_at, "evaluated_cutoff_at")
    candidates = tuple(
        build_recovery_assessment(record, subject_ref=subject_ref)
        for record in records
    )
    return RecoveryAssessmentCandidateSet(
        contract_version=STABILITY_CONTRACT_VERSION,
        actual_session_ref=actual_session_ref,
        subject_ref=subject_ref,
        captured_at=captured,
        evaluated_cutoff_at=cutoff,
        candidates=candidates,
        provenance_ref=provenance_ref,
    )


def build_runtime_stability_input(
    *,
    prescription_binding: object,
    actual_session_boundary: object,
    records: object,
    captured_at: object,
    evaluated_at: object,
    provenance_ref: object,
    baseline_record: object = None,
) -> GeneralStabilityInput:
    """Build a complete typed input without persistence or source discovery."""
    if type(prescription_binding) is not PrescriptionBaselineBinding:
        raise RuntimeRecoveryAdapterError(("prescription_binding must be a PrescriptionBaselineBinding",))
    if type(actual_session_boundary) is not ActualSessionBoundary:
        raise RuntimeRecoveryAdapterError(("actual_session_boundary must be an ActualSessionBoundary",))
    evaluated = _parse_timestamp(evaluated_at, "evaluated_at")
    candidate_set = build_recovery_candidate_set(
        records,
        actual_session_ref=actual_session_boundary.actual_session_ref,
        subject_ref=prescription_binding.subject_ref,
        captured_at=captured_at,
        evaluated_cutoff_at=evaluated,
        provenance_ref=provenance_ref,
    )
    baseline = None
    if baseline_record is not None:
        baseline = build_recovery_assessment(
            baseline_record,
            subject_ref=prescription_binding.subject_ref,
            missing_category_path="baseline_assessment.category",
        )
    value = GeneralStabilityInput(
        contract_version=STABILITY_CONTRACT_VERSION,
        policy_id=STABILITY_POLICY_ID,
        policy_version=STABILITY_POLICY_VERSION,
        prescription_binding=prescription_binding,
        baseline_assessment=baseline,
        actual_session_boundary=actual_session_boundary,
        candidate_set=candidate_set,
        next_decision_boundary=None,
        evaluated_at=evaluated,
        reported_problems_projection=None,
        provenance_ref=provenance_ref,
    )
    errors = validate_general_stability_input(value)
    if errors:
        raise RuntimeRecoveryAdapterError(errors)
    return value


def provide_runtime_stability_from_recovery_records(
    *,
    prescription_binding: object,
    actual_session_boundary: object,
    records: object,
    captured_at: object,
    evaluated_at: object,
    provenance_ref: object,
    evaluation_id: object,
    baseline_record: object = None,
) -> RuntimeStabilityProviderResult:
    """Adapt explicit records and run the existing pure stability provider."""
    value = build_runtime_stability_input(
        prescription_binding=prescription_binding,
        actual_session_boundary=actual_session_boundary,
        records=records,
        captured_at=captured_at,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
        baseline_record=baseline_record,
    )
    try:
        return provide_runtime_stability(value, evaluation_id=evaluation_id)
    except ValueError as exc:
        if isinstance(exc, RuntimeRecoveryAdapterError):
            raise
        raise RuntimeRecoveryAdapterError((str(exc),)) from exc
