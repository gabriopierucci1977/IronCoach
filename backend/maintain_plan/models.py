"""Immutable, runtime-independent domain contracts for MAINTAIN_PLAN.

The module deliberately models data only.  It contains no matching or evaluation
algorithm and the draft contract is not wired into the application runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Mapping


CONTRACT_VERSION = "maintain-plan/1.0.0-draft"


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


class OverallStatus(ValueEnum):
    IN_LINE = "IN_LINE"
    PARTIALLY_IN_LINE = "PARTIALLY_IN_LINE"
    DIFFERENT = "DIFFERENT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class PolicyRef:
    policy_id: str | None
    policy_version: str | None


@dataclass(frozen=True)
class PlannedComponentRef:
    prescription_snapshot_id: str
    component_id: str


@dataclass(frozen=True)
class ObservedComponentRef:
    session_id: str
    component_id: str


@dataclass(frozen=True)
class PlannedBlockRef:
    prescription_snapshot_id: str
    component_id: str
    block_id: str


@dataclass(frozen=True)
class ObservedBlockRef:
    session_id: str
    component_id: str
    block_id: str


@dataclass(frozen=True)
class PlannedRepetitionRef:
    prescription_snapshot_id: str
    component_id: str
    block_id: str
    repetition_index: int


@dataclass(frozen=True)
class ObservedRepetitionRef:
    session_id: str
    component_id: str
    block_id: str
    repetition_id: str


@dataclass(frozen=True)
class PlannedTransitionRef:
    prescription_snapshot_id: str
    transition_id: str


@dataclass(frozen=True)
class ObservedTransitionRef:
    session_id: str
    transition_id: str


@dataclass(frozen=True)
class Objective:
    evaluability: ObjectiveEvaluability
    code: str | None
    success_criteria: tuple[Mapping[str, Any], ...] = ()
    context_text: str | None = None
    policy: PolicyRef = PolicyRef(None, None)


@dataclass(frozen=True)
class PlannedComponent:
    component_id: str
    component_index: int
    discipline: Discipline
    requiredness: Requiredness
    support_status: SupportStatus
    capability_policy: PolicyRef


@dataclass(frozen=True)
class PrescriptionSnapshot:
    prescription_snapshot_id: str
    workout_id: str
    decision_id: str
    communicated_at: datetime
    composition: Composition
    components: tuple[PlannedComponent, ...]
    objective: Objective
    matching_policy: PolicyRef
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ObservedBlock:
    block_id: str
    block_index: int
    repetitions: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObservedComponent:
    component_id: str
    component_index: int
    discipline: Discipline | None
    blocks: tuple[ObservedBlock, ...] = ()
    quantity_observation: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class ActualSession:
    session_id: str
    start: datetime
    composition: Composition | None
    components: tuple[ObservedComponent, ...]
    transition_ids: tuple[str, ...] = ()
    contract_version: str = CONTRACT_VERSION


@dataclass(frozen=True)
class ComponentMapping:
    planned_component_ref: PlannedComponentRef
    observed_component_ref: ObservedComponentRef
    requiredness: Requiredness
    support_status: SupportStatus
    capability_policy: PolicyRef


@dataclass(frozen=True)
class PrescriptionMapping:
    mapping_id: str
    prescription_snapshot_ref: str
    actual_session_ref: str
    resolution_method: ResolutionMethod
    component_mappings: tuple[ComponentMapping, ...]


@dataclass(frozen=True)
class MatchingResult:
    matching_result_id: str
    status: MatchingStatus
    prescription_mapping: PrescriptionMapping | None
    policy: PolicyRef


@dataclass(frozen=True)
class DimensionResult:
    result_id: str
    status: AdherenceStatus
    policy: PolicyRef
    direction: Direction | None = None
    band: SeverityBand | None = None


@dataclass(frozen=True)
class DoseEvaluation:
    dose_result_id: str
    status: DoseStatus
    direction: Direction | None
    severity_band: SeverityBand | None
    quantity_result_ref: str | None
    intensity_result_ref: str | None
    policy: PolicyRef


@dataclass(frozen=True)
class ComponentEvaluation:
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


@dataclass(frozen=True)
class SessionCompositionResult:
    composition_result_id: str
    status: AdherenceStatus
    relevant_planned_component_refs: tuple[PlannedComponentRef, ...]
    observed_component_refs: tuple[ObservedComponentRef, ...]
    extra_observed_component_refs: tuple[ObservedComponentRef, ...]
    missing_planned_component_refs: tuple[PlannedComponentRef, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class EvaluationCoverage:
    status: CoverageStatus
    required_supported_component_refs: tuple[PlannedComponentRef, ...]
    required_unsupported_component_refs: tuple[PlannedComponentRef, ...]
    optional_unsupported_component_refs: tuple[PlannedComponentRef, ...]
    policy: PolicyRef


@dataclass(frozen=True)
class DimensionAggregate:
    result_id: str
    status: AdherenceStatus
    component_result_refs: tuple[str, ...]
    policy: PolicyRef
    direction: Direction | None = None


@dataclass(frozen=True)
class ExecutionEvaluation:
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
