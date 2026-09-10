"""Frozen contracts for the isolated MAINTAIN_PLAN final draft outcome."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import CoverageStatus, OverallStatus, PolicyRef, ValueEnum, _DeepFrozen
from .stability_models import ProvenanceRef, StabilityResult, VersionedArtifactRef


FINAL_OUTCOME_EVALUATION_VERSION = "maintain-plan-final-outcome/1.0.0-draft"
FINAL_OUTCOME_POLICY = PolicyRef("maintain-plan-final-outcome", "1.0.0-draft")


class MaintainPlanOutcome(ValueEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class ExecutionEvaluationRef(_DeepFrozen):
    evaluation_id: str
    prescription_mapping_ref: str
    prescription_snapshot_ref: str
    actual_session_ref: str


@dataclass(frozen=True)
class StabilityEvaluationRef(_DeepFrozen):
    evaluation_id: str
    contract_version: str
    prescription_snapshot_ref: VersionedArtifactRef
    actual_session_ref: VersionedArtifactRef
    subject_ref: str


@dataclass(frozen=True)
class MaintainPlanFinalEvaluation(_DeepFrozen):
    evaluation_id: str
    evaluation_version: str
    execution_ref: ExecutionEvaluationRef
    stability_ref: StabilityEvaluationRef
    coverage: CoverageStatus
    execution_overall: OverallStatus | None
    stability_overall: StabilityResult
    outcome: MaintainPlanOutcome | None
    policy: PolicyRef
    provenance_ref: ProvenanceRef
    evaluated_at: datetime
    missing_fields: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
