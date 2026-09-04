"""Pure structural validators for the draft MAINTAIN_PLAN contracts."""

from __future__ import annotations

from collections import Counter
from dataclasses import fields, is_dataclass
from typing import Iterable

from .models import (
    ActualSession, ComponentEvaluation, CoverageStatus, DoseEvaluation,
    DoseStatus, EvaluationApplicability, ExecutionEvaluation, MatchStatus,
    MatchingStatus, PolicyRef, PrescriptionMapping, PrescriptionSnapshot,
    Requiredness, SupportStatus,
)


def _duplicates(values: Iterable[str]) -> set[str]:
    counts = Counter(values)
    return {value for value, count in counts.items() if count > 1}


def validate_policy_ref(policy: PolicyRef, *, required: bool = False) -> tuple[str, ...]:
    complete = policy.policy_id is not None and policy.policy_version is not None
    empty = policy.policy_id is None and policy.policy_version is None
    if not (complete or empty):
        return ("policy_id and policy_version must be both set or both null",)
    if required and not complete:
        return ("policy is required",)
    return ()


def validate_prescription(snapshot: PrescriptionSnapshot) -> tuple[str, ...]:
    errors = list(validate_policy_ref(snapshot.matching_policy, required=True))
    if _duplicates(c.component_id for c in snapshot.components):
        errors.append("planned component_id must be unique in prescription snapshot")
    if _duplicates(str(c.component_index) for c in snapshot.components):
        errors.append("planned component_index must be unique in prescription snapshot")
    for component in snapshot.components:
        errors.extend(validate_policy_ref(component.capability_policy, required=True))
        if component.discipline.value == "STRENGTH" and component.support_status is not SupportStatus.UNSUPPORTED:
            errors.append("STRENGTH must be UNSUPPORTED in v1")
    objective = snapshot.objective
    if objective.evaluability.value == "STRUCTURED":
        if not objective.code:
            errors.append("STRUCTURED objective requires a stable code")
        errors.extend(validate_policy_ref(objective.policy, required=True))
    elif validate_policy_ref(objective.policy) or objective.policy.policy_id is not None:
        errors.append("non-STRUCTURED objective must not have a policy")
    return tuple(errors)


def validate_actual_session(session: ActualSession) -> tuple[str, ...]:
    errors: list[str] = []
    if _duplicates(c.component_id for c in session.components):
        errors.append("observed component_id must be unique in actual session")
    if _duplicates(session.transition_ids):
        errors.append("transition_id must be unique in actual session")
    for component in session.components:
        if _duplicates(b.block_id for b in component.blocks):
            errors.append(f"block_id must be unique in observed component {component.component_id}")
        for block in component.blocks:
            if _duplicates(block.repetitions):
                errors.append(f"repetition_id must be unique in observed block {block.block_id}")
    return tuple(errors)


def validate_mapping(mapping: PrescriptionMapping) -> tuple[str, ...]:
    errors: list[str] = []
    for item in mapping.component_mappings:
        if item.planned_component_ref.prescription_snapshot_id != mapping.prescription_snapshot_ref:
            errors.append("planned component reference is not qualified by mapped snapshot")
        if item.observed_component_ref.session_id != mapping.actual_session_ref:
            errors.append("observed component reference is not qualified by mapped session")
        errors.extend(validate_policy_ref(item.capability_policy, required=True))
    return tuple(errors)


def validate_matching_result(result) -> tuple[str, ...]:
    errors = list(validate_policy_ref(result.policy, required=True))
    if result.status is MatchingStatus.MATCHED and result.prescription_mapping is None:
        errors.append("MATCHED result requires a prescription mapping")
    if result.status is not MatchingStatus.MATCHED and result.prescription_mapping is not None:
        errors.append("unresolved matching result must not contain a mapping")
    if result.prescription_mapping:
        errors.extend(validate_mapping(result.prescription_mapping))
    return tuple(errors)


def validate_dose(dose: DoseEvaluation) -> tuple[str, ...]:
    errors: list[str] = []
    evaluated = dose.status is DoseStatus.EVALUATED
    errors.extend(validate_policy_ref(dose.policy, required=evaluated))
    if evaluated and (dose.direction is None or dose.severity_band is None):
        errors.append("EVALUATED dose requires direction and severity")
    if not evaluated and (dose.direction is not None or dose.severity_band is not None or dose.policy != PolicyRef(None, None)):
        errors.append("INSUFFICIENT_DATA dose requires null direction, severity, and policy")
    return tuple(errors)


def validate_component_evaluation(result: ComponentEvaluation) -> tuple[str, ...]:
    errors = list(validate_policy_ref(result.capability_policy, required=True))
    planned, observed = result.planned_component_ref, result.observed_component_ref
    if result.match_status is MatchStatus.MATCHED and (planned is None or observed is None):
        errors.append("MATCHED component requires planned and observed references")
    if result.match_status is MatchStatus.PLANNED_ONLY and (planned is None or observed is not None):
        errors.append("PLANNED_ONLY component requires only a planned reference")
    if result.match_status is MatchStatus.OBSERVED_ONLY:
        if planned is not None or observed is None or result.requiredness is not None:
            errors.append("OBSERVED_ONLY requires only an observed reference and null requiredness")
    elif result.requiredness is None:
        errors.append("planned component evaluation requires requiredness")
    dimension_values = (result.identity, result.quantity, result.intensity, result.structure, result.dose)
    if result.support_status is SupportStatus.UNSUPPORTED and any(value is not None for value in dimension_values):
        errors.append("UNSUPPORTED component must have null dimensional results")
    optional_omission = result.match_status is MatchStatus.PLANNED_ONLY and result.requiredness is Requiredness.OPTIONAL
    if optional_omission and (result.evaluation_applicability is not EvaluationApplicability.NOT_APPLICABLE or any(value is not None for value in dimension_values)):
        errors.append("optional PLANNED_ONLY component must be NOT_APPLICABLE with null results")
    if result.evaluation_applicability is EvaluationApplicability.NOT_APPLICABLE and any(value is not None for value in dimension_values):
        errors.append("NOT_APPLICABLE component must have null dimensional results")
    if result.dose:
        errors.extend(validate_dose(result.dose))
    return tuple(errors)


def expected_coverage(results: tuple[ComponentEvaluation, ...]) -> CoverageStatus:
    required = [r for r in results if r.requiredness is Requiredness.REQUIRED]
    if not required:
        return CoverageStatus.NO_REQUIRED_COMPONENTS
    supported = sum(r.support_status is SupportStatus.SUPPORTED for r in required)
    if supported == len(required):
        return CoverageStatus.FULLY_SUPPORTED
    if supported == 0:
        return CoverageStatus.UNSUPPORTED
    return CoverageStatus.PARTIALLY_UNSUPPORTED


def validate_execution_evaluation(evaluation: ExecutionEvaluation, mapping: PrescriptionMapping) -> tuple[str, ...]:
    errors: list[str] = []
    if evaluation.prescription_mapping_ref != mapping.mapping_id:
        errors.append("execution evaluation must reference the identified canonical mapping")
    if evaluation.prescription_snapshot_ref != mapping.prescription_snapshot_ref or evaluation.actual_session_ref != mapping.actual_session_ref:
        errors.append("execution evaluation snapshot/session references must match mapping")
    if _duplicates(r.component_result_id for r in evaluation.component_results):
        errors.append("component_result_id must be unique in execution evaluation")
    dose_ids = [r.dose.dose_result_id for r in evaluation.component_results if r.dose]
    if evaluation.dose_aggregate:
        dose_ids.append(evaluation.dose_aggregate.dose_result_id)
    if _duplicates(dose_ids):
        errors.append("dose_result_id must be unique in execution evaluation")
    for result in evaluation.component_results:
        errors.extend(validate_component_evaluation(result))
    if evaluation.evaluation_coverage.status is not expected_coverage(evaluation.component_results):
        errors.append("evaluation coverage does not match required component support")
    aggregates = (evaluation.identity_aggregate, evaluation.quantity_aggregate,
                  evaluation.intensity_aggregate, evaluation.structure_aggregate)
    if evaluation.evaluation_coverage.status is CoverageStatus.FULLY_SUPPORTED:
        if any(item is None for item in aggregates) or evaluation.dose_aggregate is None or evaluation.overall is None:
            errors.append("FULLY_SUPPORTED requires all dimensional aggregates, dose, and overall")
    elif any(item is not None for item in aggregates) or evaluation.dose_aggregate is not None or evaluation.overall is not None:
        errors.append("non-FULLY_SUPPORTED coverage requires null aggregates, dose, and overall")
    if evaluation.dose_aggregate:
        errors.extend(validate_dose(evaluation.dose_aggregate))
    errors.extend(validate_policy_ref(evaluation.evaluation_coverage.policy, required=True))
    errors.extend(validate_policy_ref(evaluation.policy, required=True))
    return tuple(errors)


def dataclass_is_frozen(instance: object) -> bool:
    """Return whether an instance belongs to a frozen dataclass contract."""
    return is_dataclass(instance) and getattr(type(instance), "__dataclass_params__").frozen and bool(fields(instance))
