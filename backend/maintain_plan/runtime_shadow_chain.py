"""Pure composition of runtime shadow consistency and outcome evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime_outcome_shadow import RuntimeOutcomeShadowResult, evaluate_runtime_outcome_shadow
from .runtime_shadow_consistency import RuntimeShadowConsistency, validate_runtime_shadow_consistency


@dataclass(frozen=True)
class RuntimeShadowChainResult:
    consistency: RuntimeShadowConsistency
    outcome: RuntimeOutcomeShadowResult


def evaluate_runtime_shadow_chain(
    *,
    subject_ref: object,
    matching: object,
    snapshot: object,
    session: object,
    mapping: object,
    execution: object,
    stability: object,
    evaluation_id: object,
    evaluated_at: object,
    provenance_ref: object,
) -> RuntimeShadowChainResult:
    """Evaluate one explicit chain without persistence, inference, or publication."""
    consistency = validate_runtime_shadow_consistency(
        subject_ref=subject_ref,
        matching=matching,
        snapshot=snapshot,
        session=session,
        mapping=mapping,
        execution=execution,
        stability=stability,
    )
    outcome = evaluate_runtime_outcome_shadow(
        execution=execution,
        stability=stability,
        evaluation_id=evaluation_id,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
    )
    return RuntimeShadowChainResult(consistency=consistency, outcome=outcome)
