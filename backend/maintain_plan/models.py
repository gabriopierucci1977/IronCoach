"""Immutable, runtime-independent domain contracts for MAINTAIN_PLAN.

The module deliberately models data only.  It contains no matching or evaluation
algorithm and the draft contract is not wired into the application runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping


CONTRACT_VERSION = "maintain-plan/1.0.0-draft"


def _deep_freeze(value: Any) -> Any:
    """Defensively copy contract containers into deeply immutable values."""
    if isinstance(value, Mapping):
        return MappingProxyType({_deep_freeze(key): _deep_freeze(item) for key, item in value.items()})
    if isinstance(value, tuple):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, list):
        return tuple(_deep_freeze(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return frozenset(_deep_freeze(item) for item in value)
    return value


class _DeepFrozen:
    def __post_init__(self) -> None:
        for field in fields(self):
            object.__setattr__(self, field.name, _deep_freeze(getattr(self, field.name)))


class ValueEnum(str, Enum):
    pass


class Composition(ValueEnum):
    SINGLE = "single"
    BRICK = "brick"
    MULTISPORT = "multisport"


class Discipline(ValueEnum):
    RUN = "RUN"
    BIKE = "BIKE"
    SWIM = "SWIM"
    STRENGTH = "STRENGTH"


class Requiredness(ValueEnum):
    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"


class SupportStatus(ValueEnum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"


class Environment(ValueEnum):
    INDOOR = "INDOOR"
    OUTDOOR = "OUTDOOR"


class Mode(ValueEnum):
    ROAD = "ROAD"
    TRAIL = "TRAIL"
    TRACK = "TRACK"
    TREADMILL = "TREADMILL"
    GRAVEL = "GRAVEL"
    MOUNTAIN_BIKE = "MOUNTAIN_BIKE"
    INDOOR_TRAINER = "INDOOR_TRAINER"
    POOL = "POOL"
    OPEN_WATER = "OPEN_WATER"


class Applicability(ValueEnum):
    REQUIRED = "REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class QuantityMetric(ValueEnum):
    ACTIVE_DURATION = "active_duration"
    DISTANCE = "distance"
    SETS_REPETITIONS = "sets_repetitions"
    PER_SEGMENT = "per_segment"


class IntensityMethod(ValueEnum):
    HR = "HR"
    POWER = "POWER"
    PACE_SPEED = "PACE_SPEED"
    RPE = "RPE"


class SessionType(ValueEnum):
    CONTINUOUS = "continuous"
    INTERVALS = "intervals"
    BRICK = "brick"
    OTHER = "other"


class BlockType(ValueEnum):
    WARMUP = "WARMUP"
    MAIN_SET = "MAIN_SET"
    WORK = "WORK"
    RECOVERY = "RECOVERY"
    COOLDOWN = "COOLDOWN"
    OTHER = "OTHER"


class EvaluationWindow(ValueEnum):
    WHOLE_BLOCK = "WHOLE_BLOCK"
    FINAL_PART = "FINAL_PART"
    AVERAGE = "AVERAGE"
    PEAK = "PEAK"
    TIME_IN_TARGET = "TIME_IN_TARGET"


class MatchStatus(ValueEnum):
    MATCHED = "MATCHED"
    PLANNED_ONLY = "PLANNED_ONLY"
    OBSERVED_ONLY = "OBSERVED_ONLY"


class EvaluationApplicability(ValueEnum):
    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class CoverageStatus(ValueEnum):
    FULLY_SUPPORTED = "FULLY_SUPPORTED"
    PARTIALLY_UNSUPPORTED = "PARTIALLY_UNSUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    NO_REQUIRED_COMPONENTS = "NO_REQUIRED_COMPONENTS"


class AdherenceStatus(ValueEnum):
    MET = "MET"
    PARTIALLY_MET = "PARTIALLY_MET"
    NOT_MET = "NOT_MET"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class Direction(ValueEnum):
    LOWER = "LOWER"
    IN_LINE = "IN_LINE"
    HIGHER = "HIGHER"
    MIXED = "MIXED"
    UNDETERMINED = "UNDETERMINED"


class SeverityBand(ValueEnum):
    MAIN = "MAIN"
    SECONDARY = "SECONDARY"
    OUT_OF_BAND = "OUT_OF_BAND"


class DoseStatus(ValueEnum):
    EVALUATED = "EVALUATED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ObjectiveEvaluability(ValueEnum):
    STRUCTURED = "STRUCTURED"
    CONTEXT_ONLY = "CONTEXT_ONLY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MatchingStatus(ValueEnum):
    MATCHED = "MATCHED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class ResolutionMethod(ValueEnum):
    AUTOMATIC = "AUTOMATIC"
    ATHLETE_CONFIRMATION = "ATHLETE_CONFIRMATION"


class ConfirmationStatus(ValueEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    REQUIRED = "REQUIRED"
    ANSWERED = "ANSWERED"
    UNKNOWN_ANSWER = "UNKNOWN_ANSWER"
    SUPERSEDED = "SUPERSEDED"


class ConfirmationAnswerType(ValueEnum):
    SELECT_CANDIDATE = "SELECT_CANDIDATE"
    NOT_PERFORMED = "NOT_PERFORMED"
    NOT_SYNCHRONIZED = "NOT_SYNCHRONIZED"
    MANUAL_ASSOCIATION = "MANUAL_ASSOCIATION"
    DONT_KNOW = "DONT_KNOW"


class OverallStatus(ValueEnum):
    IN_LINE = "IN_LINE"
    PARTIALLY_IN_LINE = "PARTIALLY_IN_LINE"
    DIFFERENT = "DIFFERENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ConflictImpactStatus(ValueEnum):
    EVALUATED = "EVALUATED"
    UNRESOLVED = "UNRESOLVED"


class AffectedDimension(ValueEnum):
    IDENTITY = "IDENTITY"
    QUANTITY = "QUANTITY"
    INTENSITY = "INTENSITY"
    STRUCTURE = "STRUCTURE"
    DOSE = "DOSE"
    DECISION = "DECISION"


@dataclass(frozen=True)
class PolicyRef(_DeepFrozen):
    policy_id: str | None
    policy_version: str | None


@dataclass(frozen=True)
class PlannedComponentRef(_DeepFrozen):
    prescription_snapshot_id: str
    component_id: str


@dataclass(frozen=True)
class ObservedComponentRef(_DeepFrozen):
    session_id: str
    component_id: str


@dataclass(frozen=True)
class PlannedBlockRef(_DeepFrozen):
    prescription_snapshot_id: str
    component_id: str
    block_id: str


@dataclass(frozen=True)
class ObservedBlockRef(_DeepFrozen):
    session_id: str
    component_id: str
    block_id: str


@dataclass(frozen=True)
class PlannedRepetitionRef(_DeepFrozen):
    prescription_snapshot_id: str
    component_id: str
    block_id: str
    repetition_index: int


@dataclass(frozen=True)
class ObservedRepetitionRef(_DeepFrozen):
    session_id: str
    component_id: str
    block_id: str
    repetition_id: str


@dataclass(frozen=True)
class PlannedTransitionRef(_DeepFrozen):
    prescription_snapshot_id: str
    transition_id: str


@dataclass(frozen=True)
class ObservedTransitionRef(_DeepFrozen):
    session_id: str
    transition_id: str


@dataclass(frozen=True)
class Objective(_DeepFrozen):
    evaluability: ObjectiveEvaluability
    code: str | None
    success_criteria: tuple[Mapping[str, Any], ...] = ()
    context_text: str | None = None
    policy: PolicyRef = PolicyRef(None, None)


@dataclass(frozen=True)
class PrescribedTarget(_DeepFrozen):
    """An authored value or inclusive range, retained without conversion."""
    value: int | float | str | None
    lower_bound: int | float | None = None
    upper_bound: int | float | None = None


@dataclass(frozen=True)
class QuantityContract(_DeepFrozen):
    applicability: Applicability
    primary_metric: QuantityMetric
    target: PrescribedTarget | None
    unit: str
    secondary_metrics: tuple[QuantityMetric, ...]
    policy: PolicyRef
    quantity_band_policy_ref: PolicyRef


@dataclass(frozen=True)
class IntensityContract(_DeepFrozen):
    applicability: Applicability
    primary_method: IntensityMethod
    target: PrescribedTarget | None
    unit: str
    allowed_secondary_methods: tuple[IntensityMethod, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class RecoveryContract(_DeepFrozen):
    applicability: Applicability
    target: PrescribedTarget | None


@dataclass(frozen=True)
class PlannedBlock(_DeepFrozen):
    block_id: str
    block_index: int
    block_type: BlockType
    requiredness: Requiredness
    quantity_target: PrescribedTarget | None
    intensity_target: PrescribedTarget | None
    method: IntensityMethod | None
    unit: str | None
    target_range: PrescribedTarget | None
    evaluation_window: EvaluationWindow | None
    coverage_policy: PolicyRef
    planned_repetitions: int | None
    recovery: RecoveryContract
    order_constraints: tuple[str, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class StructureContract(_DeepFrozen):
    applicability: Applicability
    session_type: SessionType
    policy: PolicyRef
    blocks: tuple[PlannedBlock, ...]


@dataclass(frozen=True)
class DoseContract(_DeepFrozen):
    applicability: Applicability
    policy: PolicyRef
    quantity_dimension_ref: str
    intensity_dimension_ref: str


@dataclass(frozen=True)
class AllowedSubstitution(_DeepFrozen):
    discipline: Discipline
    environment: Environment | None
    mode: Mode | None
    policy: PolicyRef


@dataclass(frozen=True)
class ScheduledWindow(_DeepFrozen):
    start: datetime
    end: datetime
    timezone: str
    derived_from_date_only: bool


@dataclass(frozen=True)
class PlannedTransition(_DeepFrozen):
    transition_id: str
    from_component_id: str
    to_component_id: str
    policy: PolicyRef
    applicable_limit_minutes: int | float


@dataclass(frozen=True)
class Provenance(_DeepFrozen):
    source: str
    captured_at: datetime


@dataclass(frozen=True)
class PrescriptionAudit(_DeepFrozen):
    original_plan_snapshot_id: str | None


@dataclass(frozen=True)
class PlannedComponent(_DeepFrozen):
    component_id: str
    component_index: int
    discipline: Discipline
    environment: Environment | None
    mode: Mode | None
    requiredness: Requiredness
    support_status: SupportStatus
    capability_policy: PolicyRef
    applicability: Applicability
    allowed_substitutions: tuple[AllowedSubstitution, ...]
    identity_policy: PolicyRef
    quantity: QuantityContract
    intensity: IntensityContract
    structure: StructureContract
    dose: DoseContract


@dataclass(frozen=True)
class PrescriptionSnapshot(_DeepFrozen):
    prescription_snapshot_id: str
    workout_id: str
    decision_id: str
    communicated_at: datetime
    scheduled_window: ScheduledWindow
    composition: Composition
    components: tuple[PlannedComponent, ...]
    transitions: tuple[PlannedTransition, ...]
    objective: Objective
    matching_policy: PolicyRef
    brick_policy: PolicyRef
    provenance: Provenance
    audit: PrescriptionAudit
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class SourceActivity(_DeepFrozen):
    source: str
    original_activity_id: str
    raw_ids: Mapping[str, Any]
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class ObservedRepetition(_DeepFrozen):
    repetition_id: str
    repetition_index: int
    block_ref: str
    quantity_observation: Mapping[str, Any] | None = None
    intensity_observation: Mapping[str, Any] | None = None
    valid_coverage: Mapping[str, Any] | None = None
    time_in_target: Mapping[str, Any] | None = None
    source_segment_refs: tuple[str, ...] = ()
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedBlock(_DeepFrozen):
    block_id: str
    block_index: int
    repetitions: tuple[ObservedRepetition, ...] = ()
    block_type: BlockType = BlockType.OTHER
    quantity_observation: Mapping[str, Any] | None = None
    intensity_observation: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedComponent(_DeepFrozen):
    component_id: str
    component_index: int
    discipline: Discipline | None
    blocks: tuple[ObservedBlock, ...] = ()
    quantity_observation: Mapping[str, Any] | None = None
    environment: Environment | None = None
    mode: Mode | None = None
    source_activity_refs: tuple[str, ...] = ()
    source_segment_refs: tuple[str, ...] = ()
    start: datetime | None = None
    end: datetime | None = None
    quantity_primary_metric: str | None = None
    quantity_unit: str | None = None
    secondary_metrics: tuple[Mapping[str, Any], ...] = ()
    intensity_methods: tuple[str, ...] = ()
    intensity_observations: Mapping[str, Any] | None = None
    temporal_coverage: Mapping[str, Any] | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    data_quality: Mapping[str, Any] = MappingProxyType({})


@dataclass(frozen=True)
class ObservedTransition(_DeepFrozen):
    transition_id: str
    from_component_ref: str
    to_component_ref: str
    start: datetime | None = None
    end: datetime | None = None
    duration_minutes: int | float | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompletionObservation(_DeepFrozen):
    status: str | None = None
    interruption_reason: str | None = None
    safety_interruption: bool | None = None


@dataclass(frozen=True)
class ActualSession(_DeepFrozen):
    session_id: str
    start: datetime
    composition: Composition | None
    components: tuple[ObservedComponent, ...]
    transition_ids: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION
    source_activities: tuple[SourceActivity, ...] = ()
    end: datetime | None = None
    timezone: str = "UTC"
    transitions: tuple[ObservedTransition, ...] = ()
    completion: CompletionObservation = CompletionObservation()
    athlete_feedback: Mapping[str, Any] | None = None
    weather_context: tuple[Mapping[str, Any], ...] = ()
    source_conflicts: tuple[Mapping[str, Any], ...] = ()
    data_quality: Mapping[str, Any] = MappingProxyType({})
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


# Append-only feedback and source-conflict lifecycle contracts.  Identifiers,
# versions and timestamps deliberately have no generated defaults.
class FeedbackEventType(ValueEnum):
    CAPTURED = "CAPTURED"
    CORRECTED = "CORRECTED"
    DELETED = "DELETED"


class FeedbackProjectionStatus(ValueEnum):
    ACTIVE = "ACTIVE"
    DELETED = "DELETED"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ConflictResolutionEventType(ValueEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN_ANSWER = "UNKNOWN_ANSWER"
    RESOLUTION_WITHDRAWN = "RESOLUTION_WITHDRAWN"


class SourceConflictProjectionStatus(ValueEnum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    DONT_KNOW = "DONT_KNOW"
    INVALID = "INVALID"


@dataclass(frozen=True)
class ActualSessionRef(_DeepFrozen):
    session_id: str


@dataclass(frozen=True)
class FeedbackRef(_DeepFrozen):
    session_id: str
    feedback_id: str


@dataclass(frozen=True)
class FeedbackLogRef(_DeepFrozen):
    feedback_log_id: str
    session_id: str
    feedback_id: str


@dataclass(frozen=True)
class FeedbackEventLog(_DeepFrozen):
    feedback_log_id: str
    schema_version: str
    feedback_ref: FeedbackRef
    actual_session_ref: ActualSessionRef


@dataclass(frozen=True)
class FeedbackEvent(_DeepFrozen):
    feedback_event_id: str
    feedback_log_ref: FeedbackLogRef
    feedback_ref: FeedbackRef
    actual_session_ref: ActualSessionRef
    event_type: FeedbackEventType
    baseline_schema_version: str
    baseline_payload_hash: str
    event_sequence: int
    stream_version: int
    occurred_at: datetime
    actor: str
    provenance: Mapping[str, Any]
    schema_version: str
    previous_event_id: str | None
    superseded_event_ref: str | None
    corrected_payload: Mapping[str, Any] | None
    deletion_reason_or_ref: str | None
    audit_metadata: Mapping[str, Any]
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class FeedbackProjection(_DeepFrozen):
    projection_id: str
    projection_version: str
    feedback_log_ref: FeedbackLogRef
    feedback_ref: FeedbackRef
    actual_session_ref: ActualSessionRef
    captured_event_id: str | None
    last_applied_event_id: str | None
    last_applied_sequence: int | None
    baseline_schema_version: str
    baseline_payload_hash: str
    status: FeedbackProjectionStatus
    projected_payload: Mapping[str, Any] | None
    provenance: Mapping[str, Any]
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class SourceConflictRef(_DeepFrozen):
    session_id: str
    conflict_id: str


@dataclass(frozen=True)
class ResolutionLogRef(_DeepFrozen):
    resolution_log_id: str
    source_conflict_id: str
    session_id: str


@dataclass(frozen=True)
class SourceConflictResolutionLog(_DeepFrozen):
    resolution_log_id: str
    schema_version: str
    conflict_ref: SourceConflictRef
    actual_session_ref: ActualSessionRef


@dataclass(frozen=True)
class SourceConflictResolutionEvent(_DeepFrozen):
    event_id: str
    resolution_log_ref: ResolutionLogRef
    resolution_log_id: str
    source_conflict_id: str
    actual_session_ref: ActualSessionRef
    event_sequence: int
    event_type: ConflictResolutionEventType
    selected_value: Any | None
    selected_source: str | None
    unknown_answer: bool
    actor: str
    occurred_at: datetime
    provenance: Mapping[str, Any]
    schema_version: str
    previous_event_id: str | None
    withdrawn_event_ref: str | None
    audit_metadata: Mapping[str, Any]


@dataclass(frozen=True)
class SourceConflictProjection(_DeepFrozen):
    projection_id: str
    projection_version: str
    projection_hash: str
    projection_hash_algorithm: str
    projection_serialization_policy_id: str
    projection_serialization_policy_version: str
    source_conflict_id: str
    actual_session_ref: ActualSessionRef
    resolution_log_ref: ResolutionLogRef
    through_event_id: str | None
    through_event_sequence: int | None
    status: SourceConflictProjectionStatus
    selected_value: Any | None
    selected_source: str | None
    policy_id: str
    policy_version: str
    provenance: Mapping[str, Any]
    computed_at: datetime
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ComponentMapping(_DeepFrozen):
    planned_component_ref: PlannedComponentRef | None
    observed_component_ref: ObservedComponentRef | None
    requiredness: Requiredness | None
    support_status: SupportStatus
    capability_policy: PolicyRef
    match_status: MatchStatus = MatchStatus.MATCHED
    evidence: Mapping[str, Any] = MappingProxyType({})
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class BlockMapping(_DeepFrozen):
    planned_block_ref: PlannedBlockRef | None
    observed_block_ref: ObservedBlockRef | None
    match_status: MatchStatus = MatchStatus.MATCHED


@dataclass(frozen=True)
class RepetitionMapping(_DeepFrozen):
    planned_repetition_ref: PlannedRepetitionRef | None
    observed_repetition_ref: ObservedRepetitionRef | None
    match_status: MatchStatus = MatchStatus.MATCHED


@dataclass(frozen=True)
class TransitionMapping(_DeepFrozen):
    planned_transition_ref: PlannedTransitionRef | None
    observed_transition_ref: ObservedTransitionRef | None
    match_status: MatchStatus = MatchStatus.MATCHED


@dataclass(frozen=True)
class PrescriptionMapping(_DeepFrozen):
    mapping_id: str
    prescription_snapshot_ref: str
    actual_session_ref: str
    resolution_method: ResolutionMethod
    component_mappings: tuple[ComponentMapping, ...]
    block_mappings: tuple[BlockMapping, ...] = ()
    repetition_mappings: tuple[RepetitionMapping, ...] = ()
    transition_mappings: tuple[TransitionMapping, ...] = ()
    confirmation_ref: str | None = None
    actor: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateEvidence(_DeepFrozen):
    session_id: str
    included: bool
    checks: Mapping[str, Any]
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class DirectIdEvidence(_DeepFrozen):
    evidence_id: str
    session_id: str
    returned_prescription_id: str | None
    source: str
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class Confirmation(_DeepFrozen):
    confirmation_id: str
    matching_result_ref: str
    prescription_snapshot_ref: str
    candidate_session_refs: tuple[str, ...]
    status: ConfirmationStatus
    question: str
    ambiguous_data: tuple[Mapping[str, Any], ...]
    interpretations: tuple[Mapping[str, Any], ...]
    answer_type: ConfirmationAnswerType | None
    selected_session_ref: str | None
    actor: str | None
    asked_at: datetime
    answered_at: datetime | None
    evidence: Mapping[str, Any]
    provenance: Mapping[str, Any]
    policy: PolicyRef = PolicyRef("ironcoach-confirmation-governance", "1.0.0-draft")
    declared_session_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class MatchingResult(_DeepFrozen):
    matching_result_id: str
    status: MatchingStatus
    prescription_mapping: PrescriptionMapping | None
    policy: PolicyRef
    prescription_snapshot_ref: str = ""
    candidate_set: tuple[str, ...] = ()
    candidate_evidence: tuple[CandidateEvidence, ...] = ()
    confirmation_ref: str | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    declared_session_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class DimensionResult(_DeepFrozen):
    result_id: str
    status: AdherenceStatus
    policy: PolicyRef
    direction: Direction | None = None
    band: SeverityBand | None = None
    evidence: Mapping[str, Any] = MappingProxyType({})
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoseEvaluation(_DeepFrozen):
    dose_result_id: str
    status: DoseStatus
    direction: Direction | None
    severity_band: SeverityBand | None
    quantity_result_ref: str | None
    intensity_result_ref: str | None
    policy: PolicyRef
    provenance: Mapping[str, Any] = MappingProxyType({})
    computed_at: datetime | None = None
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceConflictProjectionRef(_DeepFrozen):
    projection_id: str
    projection_version: str
    projection_hash: str
    projection_hash_algorithm: str
    projection_serialization_policy_id: str
    projection_serialization_policy_version: str


@dataclass(frozen=True)
class SourceConflictImpactEvaluation(_DeepFrozen):
    conflict_impact_evaluation_id: str
    evaluation_version: str
    source_conflict_ref: SourceConflictRef
    prescription_mapping_ref: str | None
    status: ConflictImpactStatus
    affected_dimensions: tuple[AffectedDimension, ...]
    policy: PolicyRef
    provenance: Mapping[str, Any]
    evaluated_at: datetime
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConflictImpactEvaluationRef(_DeepFrozen):
    conflict_impact_evaluation_id: str
    evaluation_version: str


@dataclass(frozen=True)
class ComponentEvaluation(_DeepFrozen):
    component_result_id: str
    match_status: MatchStatus
    requiredness: Requiredness | None
    evaluation_applicability: EvaluationApplicability
    support_status: SupportStatus
    capability_policy: PolicyRef
    planned_component_ref: PlannedComponentRef | None
    observed_component_ref: ObservedComponentRef | None
    identity: DimensionResult | None = None
    quantity: DimensionResult | None = None
    intensity: DimensionResult | None = None
    structure: DimensionResult | None = None
    dose: DoseEvaluation | None = None
    provenance: Mapping[str, Any] = MappingProxyType({})
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SessionCompositionResult(_DeepFrozen):
    composition_result_id: str
    status: AdherenceStatus
    relevant_planned_component_refs: tuple[PlannedComponentRef, ...]
    observed_component_refs: tuple[ObservedComponentRef, ...]
    extra_observed_component_refs: tuple[ObservedComponentRef, ...]
    missing_planned_component_refs: tuple[PlannedComponentRef, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class EvaluationCoverage(_DeepFrozen):
    status: CoverageStatus
    required_supported_component_refs: tuple[PlannedComponentRef, ...]
    required_unsupported_component_refs: tuple[PlannedComponentRef, ...]
    optional_unsupported_component_refs: tuple[PlannedComponentRef, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class DimensionAggregate(_DeepFrozen):
    result_id: str
    status: AdherenceStatus
    component_result_refs: tuple[str, ...]
    policy: PolicyRef
    direction: Direction | None = None


@dataclass(frozen=True)
class ExecutionEvaluation(_DeepFrozen):
    evaluation_id: str
    prescription_mapping_ref: str
    prescription_snapshot_ref: str
    actual_session_ref: str
    component_results: tuple[ComponentEvaluation, ...]
    session_composition_result: SessionCompositionResult | None
    evaluation_coverage: EvaluationCoverage
    identity_aggregate: DimensionAggregate | None
    quantity_aggregate: DimensionAggregate | None
    intensity_aggregate: DimensionAggregate | None
    structure_aggregate: DimensionAggregate | None
    dose_aggregate: DoseEvaluation | None
    overall: OverallStatus | None
    policy: PolicyRef
    source_conflict_projection_refs: tuple[SourceConflictProjectionRef, ...] = ()
    source_conflict_impact_evaluation_refs: tuple[ConflictImpactEvaluationRef, ...] = ()
    provenance: Mapping[str, Any] = MappingProxyType({})
