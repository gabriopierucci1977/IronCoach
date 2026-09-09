"""Frozen, persistence-free contracts for MAINTAIN_PLAN general stability P0."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from typing import Any

STABILITY_CONTRACT_VERSION = "maintain-plan-stability/1.0.0-draft"
STABILITY_POLICY_ID = "maintain-plan-stability"
STABILITY_POLICY_VERSION = "1.0.0-draft"
MISSING_PATHS_VERSION = "maintain-plan-stability-missing-paths/1.0.0-draft"


class ValueEnum(str, Enum):
    pass


class StabilityResult(ValueEnum):
    STABLE = "STABLE"
    DETERIORATED = "DETERIORATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class RecoveryCategory(ValueEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CategoryMissingness(ValueEnum):
    NOT_MISSING = "NOT_MISSING"
    MISSING = "MISSING"
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


class CompatibilityStatus(ValueEnum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNDETERMINED = "UNDETERMINED"


class CompatibilityField(ValueEnum):
    CONTRACT_VERSION = "CONTRACT_VERSION"
    ANALYZER_ID = "ANALYZER_ID"
    ANALYZER_VERSION = "ANALYZER_VERSION"
    ASSESSMENT_SCHEMA_VERSION = "ASSESSMENT_SCHEMA_VERSION"
    SUBJECT_REF = "SUBJECT_REF"


class FieldComparison(ValueEnum):
    EQUAL = "EQUAL"
    DIFFERENT = "DIFFERENT"
    MISSING = "MISSING"


class CandidateDisposition(ValueEnum):
    SELECTED = "SELECTED"
    ELIGIBLE_NOT_SELECTED = "ELIGIBLE_NOT_SELECTED"
    EXCLUDED = "EXCLUDED"


class CandidateDispositionReason(ValueEnum):
    SELECTED_EARLIEST = "SELECTED_EARLIEST"
    LATER_THAN_SELECTED = "LATER_THAN_SELECTED"
    DUPLICATE_IDENTICAL = "DUPLICATE_IDENTICAL"
    FOREIGN_SUBJECT = "FOREIGN_SUBJECT"
    INCOMPATIBLE = "INCOMPATIBLE"
    COMPATIBILITY_UNDETERMINED = "COMPATIBILITY_UNDETERMINED"
    OBSERVED_AT_OR_BEFORE_SESSION_END = "OBSERVED_AT_OR_BEFORE_SESSION_END"
    ASSESSED_AT_OR_BEFORE_SESSION_END = "ASSESSED_AT_OR_BEFORE_SESSION_END"
    OBSERVED_AT_OR_AFTER_NEXT_DECISION = "OBSERVED_AT_OR_AFTER_NEXT_DECISION"
    ASSESSED_AT_OR_AFTER_NEXT_DECISION = "ASSESSED_AT_OR_AFTER_NEXT_DECISION"
    CATEGORY_UNAVAILABLE = "CATEGORY_UNAVAILABLE"
    FIRST_TIMESTAMP_AMBIGUITY = "FIRST_TIMESTAMP_AMBIGUITY"


class TemporalEligibility(ValueEnum):
    ELIGIBLE = "ELIGIBLE"
    EXCLUDED = "EXCLUDED"
    UNDETERMINED = "UNDETERMINED"


class Freshness(ValueEnum):
    IN_WINDOW = "IN_WINDOW"
    OUT_OF_WINDOW = "OUT_OF_WINDOW"
    UNDETERMINED = "UNDETERMINED"


class FollowUpSelectionStatus(ValueEnum):
    SELECTED = "SELECTED"
    NO_ELIGIBLE_CANDIDATE = "NO_ELIGIBLE_CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"


class ProjectionStatus(ValueEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ChannelCheckStatus(ValueEnum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


class ReportedProblemsResult(ValueEnum):
    NO_KNOWN_ISSUE = "NO_KNOWN_ISSUE"
    ISSUE_REPORTED = "ISSUE_REPORTED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EventBoundary(ValueEnum):
    EXCLUSIVE = "EXCLUSIVE"
    INCLUSIVE = "INCLUSIVE"


class PerformanceApplicability(ValueEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"


class _DeepFrozen:
    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if isinstance(value, list):
                value = tuple(value)
            elif isinstance(value, set):
                value = frozenset(value)
            object.__setattr__(self, item.name, value)


@dataclass(frozen=True)
class VersionedArtifactRef(_DeepFrozen):
    artifact_type: str
    artifact_id: str
    artifact_version: str


@dataclass(frozen=True)
class ProvenanceRef(_DeepFrozen):
    producer: VersionedArtifactRef
    provenance_type: str
    provenance_id: str
    provenance_version: str


@dataclass(frozen=True)
class AnalyzerRef(_DeepFrozen):
    analyzer_id: str | None
    analyzer_version: str | None
    assessment_schema_version: str | None


@dataclass(frozen=True)
class RecoveryAssessment(_DeepFrozen):
    assessment_id: str
    contract_version: str
    analyzer_ref: AnalyzerRef
    subject_ref: str
    observed_at: datetime
    assessed_at: datetime
    category: RecoveryCategory | None
    category_missingness: CategoryMissingness
    evidence_refs: tuple[VersionedArtifactRef, ...]
    provenance_ref: ProvenanceRef
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecoveryAssessmentRef(_DeepFrozen):
    assessment_id: str
    contract_version: str
    analyzer_ref: AnalyzerRef
    subject_ref: str
    observed_at: datetime
    assessed_at: datetime


@dataclass(frozen=True)
class CompatibilityFieldRecord(_DeepFrozen):
    field: CompatibilityField
    comparison: FieldComparison
    baseline_value: str | None
    follow_up_value: str | None


@dataclass(frozen=True)
class RecoveryAssessmentCompatibility(_DeepFrozen):
    baseline_ref: RecoveryAssessmentRef
    follow_up_ref: RecoveryAssessmentRef
    status: CompatibilityStatus
    field_records: tuple[CompatibilityFieldRecord, ...]
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PrescriptionBaselineBinding(_DeepFrozen):
    prescription_snapshot_ref: VersionedArtifactRef
    decision_ref: VersionedArtifactRef
    subject_ref: str
    prescription_communicated_at: datetime
    baseline_assessment_ref: RecoveryAssessmentRef | None
    baseline_use_attestation_ref: VersionedArtifactRef
    provenance_ref: ProvenanceRef


@dataclass(frozen=True)
class ActualSessionBoundary(_DeepFrozen):
    actual_session_ref: VersionedArtifactRef
    subject_ref: str
    session_end: datetime | None
    provenance_ref: ProvenanceRef | None


@dataclass(frozen=True)
class NextDecisionBoundary(_DeepFrozen):
    decision_ref: VersionedArtifactRef
    subject_ref: str
    decision_at: datetime


@dataclass(frozen=True)
class RecoveryAssessmentCandidateSet(_DeepFrozen):
    contract_version: str
    actual_session_ref: VersionedArtifactRef
    subject_ref: str
    captured_at: datetime
    evaluated_cutoff_at: datetime
    candidates: tuple[RecoveryAssessment, ...]
    provenance_ref: ProvenanceRef


@dataclass(frozen=True)
class RecoveryAssessmentCandidateOccurrence(_DeepFrozen):
    candidate_ref: RecoveryAssessmentRef
    occurrence_count: int


@dataclass(frozen=True)
class RecoveryAssessmentCandidateSetRef(_DeepFrozen):
    contract_version: str
    actual_session_ref: VersionedArtifactRef
    subject_ref: str
    captured_at: datetime
    evaluated_cutoff_at: datetime
    logical_candidates: tuple[RecoveryAssessmentCandidateOccurrence, ...]


@dataclass(frozen=True)
class CandidateSelectionRecord(_DeepFrozen):
    candidate_ref: RecoveryAssessmentRef
    disposition: CandidateDisposition
    reasons: tuple[CandidateDispositionReason, ...]
    compatibility: RecoveryAssessmentCompatibility
    temporal_eligibility: TemporalEligibility
    freshness: Freshness
    occurrence_count: int
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FollowUpSelectionEvidence(_DeepFrozen):
    candidate_set_ref: RecoveryAssessmentCandidateSetRef
    records: tuple[CandidateSelectionRecord, ...]
    selected_follow_up_ref: RecoveryAssessmentRef | None
    status: FollowUpSelectionStatus
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportedProblemsEventCursor(_DeepFrozen):
    event_id: str
    event_sequence: int


@dataclass(frozen=True)
class ReportedProblemsEventWindow(_DeepFrozen):
    start_at: datetime
    start_boundary: EventBoundary
    end_at: datetime
    end_boundary: EventBoundary


@dataclass(frozen=True)
class ReportedProblemsProjectionSnapshot(_DeepFrozen):
    projection_id: str
    projection_version: str | None
    projection_schema_version: str | None
    actual_session_ref: VersionedArtifactRef
    subject_ref: str
    projection_status: ProjectionStatus | None
    event_cursor: ReportedProblemsEventCursor | None
    event_window: ReportedProblemsEventWindow | None
    checked_through_at: datetime | None
    channel_check_status: ChannelCheckStatus | None
    result: ReportedProblemsResult | None
    reliable_canonical_safety_signal: bool | None
    safety_signal_evidence_refs: tuple[VersionedArtifactRef, ...]
    provenance_ref: ProvenanceRef
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReportedProblemsProjectionRef(_DeepFrozen):
    projection_id: str
    projection_version: str
    projection_schema_version: str
    actual_session_ref: VersionedArtifactRef
    subject_ref: str
    event_cursor: ReportedProblemsEventCursor | None
    checked_through_at: datetime | None


@dataclass(frozen=True)
class ReportedProblemsEvaluation(_DeepFrozen):
    projection_ref: ReportedProblemsProjectionRef | None
    cutoff_at: datetime
    result: ReportedProblemsResult
    stability_result: StabilityResult
    evidence_refs: tuple[VersionedArtifactRef, ...]
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class GeneralStabilityInput(_DeepFrozen):
    contract_version: str
    policy_id: str
    policy_version: str
    prescription_binding: PrescriptionBaselineBinding
    baseline_assessment: RecoveryAssessment | None
    actual_session_boundary: ActualSessionBoundary
    candidate_set: RecoveryAssessmentCandidateSet
    next_decision_boundary: NextDecisionBoundary | None
    evaluated_at: datetime
    reported_problems_projection: ReportedProblemsProjectionSnapshot | None
    provenance_ref: ProvenanceRef


@dataclass(frozen=True)
class GeneralStabilityEvaluation(_DeepFrozen):
    evaluation_id: str
    contract_version: str
    policy_id: str
    policy_version: str
    evaluated_at: datetime
    subject_ref: str
    prescription_binding: PrescriptionBaselineBinding
    actual_session_boundary: ActualSessionBoundary
    baseline_ref: RecoveryAssessmentRef | None
    candidate_set_ref: RecoveryAssessmentCandidateSetRef
    selected_follow_up_ref: RecoveryAssessmentRef | None
    compatibility: RecoveryAssessmentCompatibility | None
    selection_evidence: FollowUpSelectionEvidence
    recovery_result: StabilityResult
    reported_problems: ReportedProblemsEvaluation
    performance_applicability: PerformanceApplicability
    overall: StabilityResult
    provenance_ref: ProvenanceRef
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


# Explicit semantic aliases used in contract prose; no legacy domain is reused.
GeneralStabilityStatus = StabilityResult
RecoveryAssessmentCategory = RecoveryCategory
RecoveryCategoryMissingness = CategoryMissingness
CompatibilityComparison = FieldComparison
SelectionStatus = FollowUpSelectionStatus
ReportedProblemsProjectionStatus = ProjectionStatus
ReportedProblemsChannelCheckStatus = ChannelCheckStatus
ReportedProblemsEventBoundary = EventBoundary
