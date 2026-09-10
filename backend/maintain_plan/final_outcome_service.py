"""Pure, draft-only final MAINTAIN_PLAN outcome aggregation."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime

from .final_outcome_models import (
    FINAL_OUTCOME_EVALUATION_VERSION, FINAL_OUTCOME_POLICY,
    ExecutionEvaluationRef, MaintainPlanFinalEvaluation, MaintainPlanOutcome,
    StabilityEvaluationRef,
)
from .final_outcome_validators import validate_final_metadata, validate_final_outcome_inputs
from .models import CoverageStatus, ExecutionEvaluation, OverallStatus
from .stability_models import GeneralStabilityEvaluation, ProvenanceRef, StabilityResult


def _diagnostics(value: object, field_name: str) -> set[str]:
    """Collect already-validated diagnostic tuples without inspecting payload maps."""
    collected: set[str] = set()
    if is_dataclass(value):
        for field in fields(value):
            item = getattr(value, field.name)
            if field.name == field_name:
                collected.update(item)
            elif is_dataclass(item):
                collected.update(_diagnostics(item, field_name))
            elif type(item) is tuple:
                for member in item:
                    if is_dataclass(member):
                        collected.update(_diagnostics(member, field_name))
    return collected


def evaluate_final_outcome(
    execution: ExecutionEvaluation,
    stability: GeneralStabilityEvaluation,
    *,
    evaluation_id: str,
    evaluated_at: datetime,
    provenance_ref: ProvenanceRef,
) -> MaintainPlanFinalEvaluation:
    """Apply only the approved coverage gate and execution × stability matrix."""
    errors = (*validate_final_outcome_inputs(execution, stability),
              *validate_final_metadata(evaluation_id, evaluated_at, provenance_ref, stability))
    if errors:
        raise ValueError("; ".join(errors))

    coverage = execution.evaluation_coverage.status
    execution_overall = execution.overall
    stability_overall = stability.overall
    outcome = None
    if coverage is CoverageStatus.FULLY_SUPPORTED:
        if execution_overall is OverallStatus.INSUFFICIENT_DATA or stability_overall is StabilityResult.INSUFFICIENT_DATA:
            outcome = MaintainPlanOutcome.INSUFFICIENT_DATA
        elif stability_overall is StabilityResult.DETERIORATED:
            outcome = MaintainPlanOutcome.NEGATIVE
        else:
            outcome = {
                OverallStatus.IN_LINE: MaintainPlanOutcome.POSITIVE,
                OverallStatus.PARTIALLY_IN_LINE: MaintainPlanOutcome.NEUTRAL,
                OverallStatus.DIFFERENT: MaintainPlanOutcome.NEGATIVE,
            }[execution_overall]

    binding = stability.prescription_binding
    boundary = stability.actual_session_boundary
    return MaintainPlanFinalEvaluation(
        evaluation_id=evaluation_id,
        evaluation_version=FINAL_OUTCOME_EVALUATION_VERSION,
        execution_ref=ExecutionEvaluationRef(
            execution.evaluation_id, execution.prescription_mapping_ref,
            execution.prescription_snapshot_ref, execution.actual_session_ref),
        stability_ref=StabilityEvaluationRef(
            stability.evaluation_id, stability.contract_version,
            binding.prescription_snapshot_ref, boundary.actual_session_ref,
            stability.subject_ref),
        coverage=coverage,
        execution_overall=execution_overall,
        stability_overall=stability_overall,
        outcome=outcome,
        policy=FINAL_OUTCOME_POLICY,
        provenance_ref=provenance_ref,
        evaluated_at=evaluated_at,
        missing_fields=tuple(sorted(_diagnostics(execution, "missing_fields") |
                                    _diagnostics(stability, "missing_fields"))),
        warnings=tuple(sorted(_diagnostics(execution, "warnings") |
                              _diagnostics(stability, "warnings"))),
    )


class FinalOutcomeService:
    """Stateless package-internal facade; deliberately not runtime-wired."""

    def evaluate(self, execution: ExecutionEvaluation, stability: GeneralStabilityEvaluation,
                 *, evaluation_id: str, evaluated_at: datetime,
                 provenance_ref: ProvenanceRef) -> MaintainPlanFinalEvaluation:
        return evaluate_final_outcome(execution, stability, evaluation_id=evaluation_id,
                                      evaluated_at=evaluated_at, provenance_ref=provenance_ref)
