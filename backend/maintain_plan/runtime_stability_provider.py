"""Pure provider boundary for canonical stability input."""

from __future__ import annotations

from dataclasses import dataclass

from .general_stability_service import evaluate_general_stability
from .stability_models import GeneralStabilityEvaluation, GeneralStabilityInput
from .stability_validators import validate_general_stability_input


@dataclass(frozen=True)
class RuntimeStabilityProviderResult:
    stability_input: GeneralStabilityInput
    evaluation: GeneralStabilityEvaluation


class RuntimeStabilityProviderError(ValueError):
    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


def provide_runtime_stability(
    stability_input: object,
    *,
    evaluation_id: object,
) -> RuntimeStabilityProviderResult:
    """Evaluate one explicit typed stability input without persistence or I/O."""
    if type(stability_input) is not GeneralStabilityInput:
        raise RuntimeStabilityProviderError(("stability_input must be a GeneralStabilityInput",))
    if type(evaluation_id) is not str or not evaluation_id:
        raise RuntimeStabilityProviderError(("evaluation_id must be a non-empty string",))

    errors = validate_general_stability_input(stability_input)
    if errors:
        raise RuntimeStabilityProviderError(errors)

    evaluation = evaluate_general_stability(
        stability_input,
        evaluation_id=evaluation_id,
    )
    return RuntimeStabilityProviderResult(
        stability_input=stability_input,
        evaluation=evaluation,
    )
