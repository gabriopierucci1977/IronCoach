"""Pure validation boundary for future runtime outcome orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .final_outcome_validators import (
    validate_final_metadata,
    validate_final_outcome_inputs,
)
from .models import ExecutionEvaluation
from .stability_models import (
    GeneralStabilityEvaluation,
    ProvenanceRef,
)


@dataclass(frozen=True)
class RuntimeOutcomeInput:
    """Validated, caller-supplied inputs for a future final outcome evaluation."""

    execution: ExecutionEvaluation
    stability: GeneralStabilityEvaluation
    evaluation_id: str
    evaluated_at: datetime
    provenance_ref: ProvenanceRef


class RuntimeOutcomeInputError(ValueError):
    """The runtime outcome boundary received invalid canonical inputs."""

    def __init__(self, errors: tuple[str, ...] | list[str]) -> None:
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


def build_runtime_outcome_input(
    *,
    execution: object,
    stability: object,
    evaluation_id: object,
    evaluated_at: object,
    provenance_ref: object,
) -> RuntimeOutcomeInput:
    """Validate only explicit in-memory canonical inputs.

    This boundary does not discover artifacts, open repositories, persist data,
    evaluate the final outcome, alter decisions, or publish learning evidence.
    """
    errors: list[str] = []

    execution_valid = type(execution) is ExecutionEvaluation
    stability_valid = type(stability) is GeneralStabilityEvaluation

    if not execution_valid:
        errors.append("execution must be an ExecutionEvaluation")
    if not stability_valid:
        errors.append("stability must be a GeneralStabilityEvaluation")

    if execution_valid and stability_valid:
        errors.extend(
            validate_final_outcome_inputs(
                execution,
                stability,
            )
        )

    errors.extend(
        validate_final_metadata(
            evaluation_id,
            evaluated_at,
            provenance_ref,
            stability,
        )
    )

    if errors:
        raise RuntimeOutcomeInputError(errors)

    assert isinstance(execution, ExecutionEvaluation)
    assert isinstance(stability, GeneralStabilityEvaluation)
    assert isinstance(evaluation_id, str)
    assert isinstance(evaluated_at, datetime)
    assert isinstance(provenance_ref, ProvenanceRef)

    return RuntimeOutcomeInput(
        execution=execution,
        stability=stability,
        evaluation_id=evaluation_id,
        evaluated_at=evaluated_at,
        provenance_ref=provenance_ref,
    )
