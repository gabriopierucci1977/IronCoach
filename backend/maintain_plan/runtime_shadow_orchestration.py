"""Pure orchestration boundary between matching and outcome shadow evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import ExecutionEvaluation
from .runtime_matching_decision import (
    CandidatePair,
    DecisionStatus,
    MatchingDecision,
)
from .runtime_outcome_shadow import (
    RuntimeOutcomeShadowResult,
    evaluate_runtime_outcome_shadow,
)


class RuntimeShadowOrchestrationStatus(str, Enum):
    MATCHING_NOT_RESOLVED = "MATCHING_NOT_RESOLVED"
    MATCHED_OUTCOME_INPUTS_MISSING = "MATCHED_OUTCOME_INPUTS_MISSING"
    OUTCOME_EVALUATED = "OUTCOME_EVALUATED"


class RuntimeShadowOrchestrationReason(str, Enum):
    MATCHING_NOT_RESOLVED = "MATCHING_NOT_RESOLVED"
    OUTCOME_INPUTS_MISSING = "OUTCOME_INPUTS_MISSING"


@dataclass(frozen=True)
class RuntimeShadowOrchestrationResult:
    """Explicit result of one non-publishing shadow orchestration attempt."""

    matching: MatchingDecision
    status: RuntimeShadowOrchestrationStatus
    outcome: RuntimeOutcomeShadowResult | None
    reasons: tuple[RuntimeShadowOrchestrationReason, ...] = ()


class RuntimeShadowOrchestrationError(ValueError):
    """The orchestration boundary received an invalid or contradictory scope."""

    def __init__(self, errors: tuple[str, ...] | list[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


def orchestrate_runtime_shadow(
    *,
    matching: object,
    execution: object | None = None,
    stability: object | None = None,
    evaluation_id: object | None = None,
    evaluated_at: object | None = None,
    provenance_ref: object | None = None,
) -> RuntimeShadowOrchestrationResult:
    """Advance only explicit, already-produced artifacts.

    A selected matching pair never creates a mapping or an evaluation by itself.
    Outcome shadow evaluation requires the complete explicit outcome input set.
    """
    if type(matching) is not MatchingDecision:
        raise RuntimeShadowOrchestrationError(
            ("matching must be a MatchingDecision",)
        )

    outcome_values = (
        execution,
        stability,
        evaluation_id,
        evaluated_at,
        provenance_ref,
    )
    supplied = tuple(value is not None for value in outcome_values)

    if matching.status is not DecisionStatus.MATCHED:
        if any(supplied):
            raise RuntimeShadowOrchestrationError(
                (
                    "outcome inputs require a MATCHED runtime decision",
                    "outcome inputs cannot be inferred from an unresolved match",
                )
            )
        return RuntimeShadowOrchestrationResult(
            matching=matching,
            status=RuntimeShadowOrchestrationStatus.MATCHING_NOT_RESOLVED,
            outcome=None,
            reasons=(
                RuntimeShadowOrchestrationReason.MATCHING_NOT_RESOLVED,
            ),
        )

    selected = matching.selected_pair
    if type(selected) is not CandidatePair:
        raise RuntimeShadowOrchestrationError(
            ("MATCHED decision requires one selected CandidatePair",)
        )

    if not any(supplied):
        return RuntimeShadowOrchestrationResult(
            matching=matching,
            status=RuntimeShadowOrchestrationStatus.MATCHED_OUTCOME_INPUTS_MISSING,
            outcome=None,
            reasons=(
                RuntimeShadowOrchestrationReason.OUTCOME_INPUTS_MISSING,
            ),
        )

    if not all(supplied):
        raise RuntimeShadowOrchestrationError(
            ("outcome input set must be complete",)
        )

    if type(execution) is ExecutionEvaluation:
        if execution.prescription_snapshot_ref != selected.prescription_snapshot_id:
            raise RuntimeShadowOrchestrationError(
                ("execution snapshot ref must equal the selected pair",)
            )
        if execution.actual_session_ref != selected.session_id:
            raise RuntimeShadowOrchestrationError(
                ("execution session ref must equal the selected pair",)
            )

    outcome = evaluate_runtime_outcome_shadow(
        execution=execution,
        stability=stability,
        evaluation_id=evaluation_id,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
    )

    return RuntimeShadowOrchestrationResult(
        matching=matching,
        status=RuntimeShadowOrchestrationStatus.OUTCOME_EVALUATED,
        outcome=outcome,
    )
