"""Pure shadow chain fed by a typed stability input provider."""

from __future__ import annotations

from dataclasses import dataclass

from .runtime_shadow_chain import RuntimeShadowChainResult, evaluate_runtime_shadow_chain
from .runtime_stability_provider import RuntimeStabilityProviderResult, provide_runtime_stability


@dataclass(frozen=True)
class RuntimeTypedShadowChainResult:
    stability: RuntimeStabilityProviderResult
    chain: RuntimeShadowChainResult


def evaluate_runtime_typed_shadow_chain(
    *,
    subject_ref: object,
    matching: object,
    snapshot: object,
    session: object,
    mapping: object,
    execution: object,
    stability_input: object,
    stability_evaluation_id: object,
    outcome_evaluation_id: object,
    evaluated_at: object,
    provenance_ref: object,
) -> RuntimeTypedShadowChainResult:
    """Provide typed stability, then run consistency and outcome shadow."""
    stability = provide_runtime_stability(
        stability_input,
        evaluation_id=stability_evaluation_id,
    )
    chain = evaluate_runtime_shadow_chain(
        subject_ref=subject_ref,
        matching=matching,
        snapshot=snapshot,
        session=session,
        mapping=mapping,
        execution=execution,
        stability=stability.evaluation,
        evaluation_id=outcome_evaluation_id,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
    )
    return RuntimeTypedShadowChainResult(stability=stability, chain=chain)
