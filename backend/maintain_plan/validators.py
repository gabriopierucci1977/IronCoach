"""Pure structural validators for the draft MAINTAIN_PLAN contracts."""

from __future__ import annotations

from collections import Counter
from dataclasses import fields, is_dataclass
from typing import Iterable

from .models import (
    ActualSession, ComponentEvaluation, Composition, CoverageStatus, DoseEvaluation,
    DoseStatus, EvaluationApplicability, ExecutionEvaluation, MatchStatus,
    Applicability, MatchingStatus, PolicyRef, PrescriptionMapping, PrescriptionSnapshot,
    PlannedComponent, PlannedComponentRef, PrescribedTarget, QuantityMetric,
    Requiredness, SessionType, SupportStatus,
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


def _validate_target(target: PrescribedTarget | None, name: str, *, required: bool) -> list[str]:
    if target is None:
        return [f"{name} target is required"] if required else []
    errors: list[str] = []
    if target.value is None and target.lower_bound is None and target.upper_bound is None:
        errors.append(f"{name} target must contain an authored value or bound")
    if ((target.lower_bound is None) != (target.upper_bound is None)):
        errors.append(f"{name} target range must contain both bounds")
    if (target.lower_bound is not None and target.upper_bound is not None and
            target.lower_bound > target.upper_bound):
        errors.append(f"{name} target range bounds are incoherent")
    return errors


def _validate_planned_component(component: PlannedComponent) -> list[str]:
    errors = list(validate_policy_ref(component.capability_policy, required=True))
    errors.extend(validate_policy_ref(component.identity_policy, required=True))
    if component.applicability is not Applicability.REQUIRED:
        errors.append("planned component applicability must be REQUIRED")
    for substitution in component.allowed_substitutions:
        errors.extend(validate_policy_ref(substitution.policy, required=True))

    quantity = component.quantity
    if quantity.applicability is not Applicability.REQUIRED:
        errors.append("quantity applicability must be REQUIRED")
    errors.extend(_validate_target(quantity.target, "quantity", required=True))
    if not quantity.unit:
        errors.append("quantity unit is required")
    errors.extend(validate_policy_ref(quantity.policy, required=True))
    distance_policy_required = (quantity.primary_metric is QuantityMetric.DISTANCE and
                                component.structure.session_type is SessionType.CONTINUOUS)
    errors.extend(validate_policy_ref(quantity.quantity_band_policy_ref,
                                      required=distance_policy_required))
    if not distance_policy_required and quantity.quantity_band_policy_ref.policy_id is not None:
        errors.append("quantity band policy is only applicable to continuous distance-based quantity")

    intensity = component.intensity
    if intensity.applicability is not Applicability.REQUIRED:
        errors.append("intensity applicability must be REQUIRED")
    errors.extend(_validate_target(intensity.target, "intensity", required=True))
    if not intensity.unit:
        errors.append("intensity unit is required")
    errors.extend(validate_policy_ref(intensity.policy, required=True))

    structure = component.structure
    if structure.applicability is not Applicability.REQUIRED:
        errors.append("structure applicability must be REQUIRED")
    errors.extend(validate_policy_ref(structure.policy, required=True))
    expected_intensity_policy = ("maintain-plan-interval-intensity"
                                 if structure.session_type is SessionType.INTERVALS
                                 else "maintain-plan-continuous-intensity")
    if intensity.policy.policy_id != expected_intensity_policy:
        errors.append("intensity policy must match the prescribed session_type")
    if not structure.blocks:
        errors.append("structure requires prescribed blocks")
    if _duplicates(block.block_id for block in structure.blocks):
        errors.append(f"block_id must be unique in planned component {component.component_id}")
    if _duplicates(str(block.block_index) for block in structure.blocks):
        errors.append(f"block_index must be unique in planned component {component.component_id}")
    for block in structure.blocks:
        errors.extend(validate_policy_ref(block.policy, required=True))
        errors.extend(validate_policy_ref(block.coverage_policy))
        errors.extend(_validate_target(block.quantity_target, "block quantity", required=False))
        errors.extend(_validate_target(block.intensity_target, "block intensity", required=False))
        errors.extend(_validate_target(block.target_range, "block range", required=False))
        intensity_fields = (block.intensity_target, block.method, block.unit,
                            block.target_range, block.evaluation_window)
        if any(value is not None for value in intensity_fields) and not all(
                value is not None for value in intensity_fields):
            errors.append("block intensity target, method, unit, range, and evaluation window must be complete")
        if block.intensity_target is not None:
            errors.extend(validate_policy_ref(block.coverage_policy, required=True))
        elif block.coverage_policy.policy_id is not None:
            errors.append("block without intensity target must not have a coverage policy")
        if block.planned_repetitions is not None and block.planned_repetitions <= 0:
            errors.append("planned_repetitions must be positive when prescribed")
        recovery_required = block.recovery.applicability is Applicability.REQUIRED
        errors.extend(_validate_target(block.recovery.target, "recovery", required=recovery_required))
        if not recovery_required and block.recovery.target is not None:
            errors.append("NOT_APPLICABLE recovery requires a null target")

    dose = component.dose
    if dose.applicability is not Applicability.REQUIRED:
        errors.append("dose applicability must be REQUIRED")
    errors.extend(validate_policy_ref(dose.policy, required=True))
    if not dose.quantity_dimension_ref or not dose.intensity_dimension_ref:
        errors.append("dose requires quantity and intensity dimension references")
    return errors


def validate_prescription(snapshot: PrescriptionSnapshot) -> tuple[str, ...]:
    errors = list(validate_policy_ref(snapshot.matching_policy, required=True))
    errors.extend(validate_policy_ref(snapshot.brick_policy,
                                      required=snapshot.composition is Composition.BRICK))
    if snapshot.composition is not Composition.BRICK and snapshot.brick_policy.policy_id is not None:
        errors.append("brick policy is only applicable to BRICK prescriptions")
    if snapshot.scheduled_window.start > snapshot.scheduled_window.end:
        errors.append("scheduled window start must not follow end")
    if not snapshot.scheduled_window.timezone:
        errors.append("scheduled window timezone is required")
    if not snapshot.provenance.source:
        errors.append("prescription provenance source is required")
    component_count = len(snapshot.components)
    if snapshot.composition is Composition.SINGLE and component_count != 1:
        errors.append("SINGLE prescription requires exactly one planned component")
    if snapshot.composition in (Composition.BRICK, Composition.MULTISPORT) and component_count < 2:
        errors.append(f"{snapshot.composition.name} prescription requires at least two planned components")
    if _duplicates(c.component_id for c in snapshot.components):
        errors.append("planned component_id must be unique in prescription snapshot")
    if _duplicates(str(c.component_index) for c in snapshot.components):
        errors.append("planned component_index must be unique in prescription snapshot")
    if _duplicates(t.transition_id for t in snapshot.transitions):
        errors.append("transition_id must be unique in prescription snapshot")
    component_ids = {component.component_id for component in snapshot.components}
    for transition in snapshot.transitions:
        errors.extend(validate_policy_ref(transition.policy, required=True))
        if (transition.from_component_id not in component_ids or
                transition.to_component_id not in component_ids):
            errors.append("transition endpoints must reference planned components")
    for component in snapshot.components:
        errors.extend(_validate_planned_component(component))
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
