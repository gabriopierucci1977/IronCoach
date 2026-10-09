"""Pure, non-publishing shadow evaluation for final MAINTAIN_PLAN outcome."""

from __future__ import annotations

from dataclasses import dataclass

from .final_outcome_models import MaintainPlanFinalEvaluation
from .final_outcome_service import evaluate_final_outcome
from .runtime_outcome_boundary import (
    RuntimeOutcomeInput,
    build_runtime_outcome_input,
)


@dataclass(frozen=True)
class RuntimeOutcomeShadowResult:
    """Draft outcome calculated from one explicit in-memory input set."""

    runtime_input: RuntimeOutcomeInput
    evaluation: MaintainPlanFinalEvaluation


def evaluate_runtime_outcome_shadow(
    *,
    execution: object,
    stability: object,
    evaluation_id: object,
    evaluated_at: object,
    provenance_ref: object,
) -> RuntimeOutcomeShadowResult:
    """Validate and evaluate explicit inputs without publication or persistence."""
    runtime_input = build_runtime_outcome_input(
        execution=execution,
        stability=stability,
        evaluation_id=evaluation_id,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
    )

    evaluation = evaluate_final_outcome(
        runtime_input.execution,
        runtime_input.stability,
        evaluation_id=runtime_input.evaluation_id,
        evaluated_at=runtime_input.evaluated_at,
        provenance_ref=runtime_input.provenance_ref,
    )

    return RuntimeOutcomeShadowResult(
        runtime_input=runtime_input,
        evaluation=evaluation,
    )
