"""Pure structural validators for the draft MAINTAIN_PLAN contracts."""

from __future__ import annotations

from collections import Counter
from dataclasses import fields, is_dataclass
from typing import Iterable

from .models import (
    ActualSession, ComponentEvaluation, Composition, CoverageStatus, DoseEvaluation,
    DoseStatus, EvaluationApplicability, ExecutionEvaluation, MatchStatus,
    MatchingStatus, PolicyRef, PrescriptionMapping, PrescriptionSnapshot,
    PlannedComponentRef, Requiredness, SupportStatus,
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
    component_count = len(snapshot.components)
    if snapshot.composition is Composition.SINGLE and component_count != 1:
        errors.append("SINGLE prescription requires exactly one planned component")
    if snapshot.composition in (Composition.BRICK, Composition.MULTISPORT) and component_count < 2:
        errors.append(f"{snapshot.composition.name} prescription requires at least two planned components")
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
    planned_refs = [item.planned_component_ref for item in mapping.component_mappings]
    observed_refs = [item.observed_component_ref for item in mapping.component_mappings
                     if item.observed_component_ref is not None]
    if len(set(planned_refs)) != len(planned_refs):
        errors.append("planned component reference must occur at most once in canonical mapping")
    if len(set(observed_refs)) != len(observed_refs):
        errors.append("non-null observed component reference must occur at most once in canonical mapping")
    for item in mapping.component_mappings:
        if item.planned_component_ref.prescription_snapshot_id != mapping.prescription_snapshot_ref:
            errors.append("planned component reference is not qualified by mapped snapshot")
        if (item.observed_component_ref is not None and
                item.observed_component_ref.session_id != mapping.actual_session_ref):
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
    if evaluated and (dose.direction is None or dose.severity_band is None or
                      dose.quantity_result_ref is None or dose.intensity_result_ref is None):
        errors.append("EVALUATED dose requires quantity, intensity, direction, and severity")
    if not evaluated and (dose.direction is not None or dose.severity_band is not None or
                          dose.quantity_result_ref is not None or dose.intensity_result_ref is not None or
                          dose.policy != PolicyRef(None, None)):
        errors.append("INSUFFICIENT_DATA dose requires null input references, direction, severity, and policy")
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
        if result.dose.status is DoseStatus.EVALUATED and (
                result.quantity is None or result.intensity is None or
                result.dose.quantity_result_ref != result.quantity.result_id or
                result.dose.intensity_result_ref != result.intensity.result_id):
            errors.append("component dose must reference its own quantity and intensity results")
    return tuple(errors)


def expected_coverage(snapshot: PrescriptionSnapshot) -> CoverageStatus:
    required = [component for component in snapshot.components
                if component.requiredness is Requiredness.REQUIRED]
    if not required:
        return CoverageStatus.NO_REQUIRED_COMPONENTS
    supported = sum(r.support_status is SupportStatus.SUPPORTED for r in required)
    if supported == len(required):
        return CoverageStatus.FULLY_SUPPORTED
    if supported == 0:
        return CoverageStatus.UNSUPPORTED
    return CoverageStatus.PARTIALLY_UNSUPPORTED


def validate_execution_evaluation(
    evaluation: ExecutionEvaluation,
    mapping: PrescriptionMapping,
    snapshot: PrescriptionSnapshot,
) -> tuple[str, ...]:
    errors = list(validate_mapping(mapping))
    if evaluation.prescription_mapping_ref != mapping.mapping_id:
        errors.append("execution evaluation must reference the identified canonical mapping")
    if evaluation.prescription_snapshot_ref != mapping.prescription_snapshot_ref or evaluation.actual_session_ref != mapping.actual_session_ref:
        errors.append("execution evaluation snapshot/session references must match mapping")
    if snapshot.prescription_snapshot_id != mapping.prescription_snapshot_ref:
        errors.append("authoritative prescription snapshot must match canonical mapping")
    if _duplicates(r.component_result_id for r in evaluation.component_results):
        errors.append("component_result_id must be unique in execution evaluation")
    dose_ids = [r.dose.dose_result_id for r in evaluation.component_results if r.dose]
    if evaluation.dose_aggregate:
        dose_ids.append(evaluation.dose_aggregate.dose_result_id)
    if _duplicates(dose_ids):
        errors.append("dose_result_id must be unique in execution evaluation")
    for result in evaluation.component_results:
        errors.extend(validate_component_evaluation(result))
    planned = {component.component_id: component for component in snapshot.components}
    mapping_by_planned = {
        item.planned_component_ref.component_id: item for item in mapping.component_mappings
        if item.planned_component_ref.prescription_snapshot_id == snapshot.prescription_snapshot_id
    }
    for component_id, item in mapping_by_planned.items():
        component = planned.get(component_id)
        if component is None:
            errors.append("canonical mapping contains unknown planned component reference")
        elif (item.requiredness is not component.requiredness or
              item.support_status is not component.support_status):
            errors.append("canonical mapping requiredness/support must match authoritative prescription")
    results_by_planned: dict[str, list[ComponentEvaluation]] = {}
    for result in evaluation.component_results:
        ref = result.planned_component_ref
        if ref is None:
            continue
        if ref.prescription_snapshot_id != snapshot.prescription_snapshot_id or ref.component_id not in planned:
            errors.append("component result contains unknown or cross-snapshot planned reference")
            continue
        results_by_planned.setdefault(ref.component_id, []).append(result)
        component = planned[ref.component_id]
        item = mapping_by_planned.get(ref.component_id)
        if (result.requiredness is not component.requiredness or
                result.support_status is not component.support_status):
            errors.append("component result requiredness/support must match authoritative prescription")
        if item is None or result.observed_component_ref != item.observed_component_ref:
            errors.append("component result references must resolve through canonical mapping")
    required_components = [component for component in snapshot.components
                           if component.requiredness is Requiredness.REQUIRED]
    for component in required_components:
        if len(results_by_planned.get(component.component_id, ())) != 1:
            errors.append("each required planned component must have exactly one component result")
    expected_status = expected_coverage(snapshot)
    if evaluation.evaluation_coverage.status is not expected_status:
        errors.append("evaluation coverage does not match required component support")
    expected_supported = tuple(
        PlannedComponentRef(snapshot.prescription_snapshot_id, component.component_id)
        for component in required_components if component.support_status is SupportStatus.SUPPORTED
    )
    expected_unsupported = tuple(
        PlannedComponentRef(snapshot.prescription_snapshot_id, component.component_id)
        for component in required_components if component.support_status is SupportStatus.UNSUPPORTED
    )
    expected_optional_unsupported = tuple(
        PlannedComponentRef(snapshot.prescription_snapshot_id, component.component_id)
        for component in snapshot.components
        if component.requiredness is Requiredness.OPTIONAL and component.support_status is SupportStatus.UNSUPPORTED
    )
    coverage = evaluation.evaluation_coverage
    if (coverage.required_supported_component_refs != expected_supported or
            coverage.required_unsupported_component_refs != expected_unsupported or
            coverage.optional_unsupported_component_refs != expected_optional_unsupported):
        errors.append("evaluation coverage references must match authoritative prescription")
    aggregates = (evaluation.identity_aggregate, evaluation.quantity_aggregate,
                  evaluation.intensity_aggregate, evaluation.structure_aggregate)
    if evaluation.evaluation_coverage.status is CoverageStatus.FULLY_SUPPORTED:
        if any(item is None for item in aggregates) or evaluation.dose_aggregate is None or evaluation.overall is None:
            errors.append("FULLY_SUPPORTED requires all dimensional aggregates, dose, and overall")
        applicable_ids = {
            results_by_planned[component.component_id][0].component_result_id
            for component in required_components
            if component.support_status is SupportStatus.SUPPORTED
            and len(results_by_planned.get(component.component_id, ())) == 1
            and results_by_planned[component.component_id][0].evaluation_applicability
            is EvaluationApplicability.APPLICABLE
        }
        for name, aggregate in zip(("identity", "quantity", "intensity", "structure"), aggregates):
            if aggregate is not None and (len(aggregate.component_result_refs) != len(set(aggregate.component_result_refs)) or
                                          set(aggregate.component_result_refs) != applicable_ids):
                errors.append(f"{name} aggregate must reference each applicable required component result exactly once")
    elif any(item is not None for item in aggregates) or evaluation.dose_aggregate is not None or evaluation.overall is not None:
        errors.append("non-FULLY_SUPPORTED coverage requires null aggregates, dose, and overall")
    if evaluation.dose_aggregate:
        errors.extend(validate_dose(evaluation.dose_aggregate))
        if (evaluation.quantity_aggregate is None or evaluation.intensity_aggregate is None or
                evaluation.dose_aggregate.quantity_result_ref != evaluation.quantity_aggregate.result_id or
                evaluation.dose_aggregate.intensity_result_ref != evaluation.intensity_aggregate.result_id):
            errors.append("aggregate dose must reference this evaluation's quantity and intensity aggregates")
    errors.extend(validate_policy_ref(evaluation.evaluation_coverage.policy, required=True))
    errors.extend(validate_policy_ref(evaluation.policy, required=True))
    return tuple(errors)


def dataclass_is_frozen(instance: object) -> bool:
    """Return whether an instance belongs to a frozen dataclass contract."""
    return is_dataclass(instance) and getattr(type(instance), "__dataclass_params__").frozen and bool(fields(instance))
