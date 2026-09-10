"""All-or-nothing structural validation for final outcome aggregation."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType, UnionType
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from .models import (
    AdherenceStatus, CoverageStatus, DimensionAggregate, Direction, DoseStatus,
    EvaluationApplicability, EvaluationCoverage, ExecutionEvaluation, OverallStatus,
    PolicyRef, Requiredness, SeverityBand, SupportStatus,
)
from .stability_models import (
    ActualSessionBoundary, GeneralStabilityEvaluation, PrescriptionBaselineBinding,
    ProvenanceRef, StabilityResult, VersionedArtifactRef,
)
from .stability_validators import validate_general_stability_evaluation
from .execution_evaluation_service import aggregate_adherence_status


EXECUTION_POLICY = PolicyRef("maintain-plan-execution-aggregation", "1.0.0-draft")
COVERAGE_POLICY = PolicyRef("maintain-plan-evaluator-capability", "1.0.0-draft")
AGGREGATE_POLICY = PolicyRef("maintain-plan-component-aggregation", "1.0.0-draft")
DOSE_POLICY = PolicyRef("maintain-plan-dose-matrix", "1.0.0-draft")
NULL_POLICY = PolicyRef(None, None)


def _aggregate_direction(directions: set[Direction | None]) -> Direction:
    if Direction.UNDETERMINED in directions:
        return Direction.UNDETERMINED
    if Direction.MIXED in directions or {Direction.LOWER, Direction.HIGHER} <= directions:
        return Direction.MIXED
    if Direction.HIGHER in directions:
        return Direction.HIGHER
    if Direction.LOWER in directions:
        return Direction.LOWER
    return Direction.IN_LINE


def _aware(value: object) -> bool:
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _matches(value: object, annotation: object, path: str, errors: list[str]) -> None:
    """Validate exact declared runtime types recursively, without coercion."""
    if annotation is Any:
        if value is None or type(value) in (str, int, float, bool):
            return
        if type(value) is tuple:
            for index, item in enumerate(value):
                _matches(item, Any, f"{path}[{index}]", errors)
            return
        if type(value) is frozenset:
            for item in value:
                _matches(item, Any, f"{path}{{item}}", errors)
            return
        if type(value) is MappingProxyType:
            for key, item in value.items():
                if type(key) is not str:
                    errors.append(f"{path} keys must be strings")
                _matches(item, Any, f"{path}[{key!r}]", errors)
            return
        errors.append(f"{path} contains an unsupported runtime type")
        return
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (UnionType, Union):
        if value is None and type(None) in args:
            return
        candidates = [item for item in args if item is not type(None)]
        if any(_is_shallow_match(value, item) for item in candidates):
            _matches(value, next(item for item in candidates if _is_shallow_match(value, item)), path, errors)
        else:
            errors.append(f"{path} has an invalid runtime type")
        return
    if origin is tuple:
        if type(value) is not tuple:
            errors.append(f"{path} must be a tuple")
            return
        item_type = args[0]
        for index, item in enumerate(value):
            _matches(item, item_type, f"{path}[{index}]", errors)
        return
    if origin in (dict, Mapping, MappingABC):
        if type(value) is not MappingProxyType:
            errors.append(f"{path} must be an immutable mapping")
            return
        key_type, value_type = args
        for key, item in value.items():
            _matches(key, key_type, f"{path}.key", errors)
            _matches(item, value_type, f"{path}[{key!r}]", errors)
        return
    if annotation is datetime:
        if not _aware(value):
            errors.append(f"{path} must be a timezone-aware datetime")
        return
    if annotation is str:
        if type(value) is not str or not value or value.isspace():
            errors.append(f"{path} must be a non-empty string")
        return
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        if type(value) is not annotation:
            errors.append(f"{path} must be {annotation.__name__}")
        return
    if isinstance(annotation, type) and is_dataclass(annotation):
        if type(value) is not annotation:
            errors.append(f"{path} must be {annotation.__name__}")
            return
        hints = get_type_hints(annotation)
        for field in fields(annotation):
            _matches(getattr(value, field.name), hints[field.name], f"{path}.{field.name}", errors)
        return
    if isinstance(annotation, type) and type(value) is not annotation:
        errors.append(f"{path} must be {annotation.__name__}")


def _is_shallow_match(value: object, annotation: object) -> bool:
    origin = get_origin(annotation)
    if origin is tuple:
        return type(value) is tuple
    if origin in (dict, Mapping, MappingABC):
        return type(value) is MappingProxyType
    return isinstance(annotation, type) and type(value) is annotation


def _validate(value: object, expected: type, name: str) -> list[str]:
    errors: list[str] = []
    _matches(value, expected, name, errors)
    return errors


def _validate_execution_evaluation(value: ExecutionEvaluation) -> tuple[str, ...]:
    """Validate output-only invariants; repository-owned inputs are unavailable here."""
    errors = _validate(value, ExecutionEvaluation, "execution")
    if errors:
        return tuple(errors)
    if value.policy != EXECUTION_POLICY:
        errors.append("execution policy and version must be exact")
    coverage = value.evaluation_coverage
    if type(coverage) is not EvaluationCoverage:
        return tuple(errors)
    if coverage.policy != COVERAGE_POLICY:
        errors.append("execution coverage policy and version must be exact")
    aggregates = (value.identity_aggregate, value.quantity_aggregate,
                  value.intensity_aggregate, value.structure_aggregate)
    if coverage.status is CoverageStatus.FULLY_SUPPORTED:
        if (any(type(item) is not DimensionAggregate for item in aggregates) or
                value.dose_aggregate is None or type(value.overall) is not OverallStatus):
            errors.append("full execution coverage requires all aggregates, dose, and overall")
        else:
            required = tuple(component for component in value.component_results
                             if component.requiredness is Requiredness.REQUIRED)
            if not required:
                errors.append("full execution coverage requires applicable required components")
            expected_refs = tuple(component.component_result_id for component in required)
            for name, aggregate in zip(("identity", "quantity", "intensity", "structure"),
                                       aggregates):
                if aggregate.policy != AGGREGATE_POLICY:
                    errors.append("execution aggregate policy and version must be exact")
                if aggregate.component_result_refs != expected_refs:
                    errors.append(f"execution {name} aggregate refs must exactly match required components")
                dimension_results = tuple(getattr(component, name) for component in required)
                if any(component.evaluation_applicability is not EvaluationApplicability.APPLICABLE or
                       component.support_status is not SupportStatus.SUPPORTED or result is None
                       for component, result in zip(required, dimension_results)):
                    errors.append(f"execution {name} aggregate requires applicable component results")
                else:
                    statuses = [result.status for result in dimension_results]
                    if name == "identity" and value.session_composition_result is not None:
                        statuses.append(value.session_composition_result.status)
                    expected_status = aggregate_adherence_status(statuses)
                    if aggregate.status is not expected_status:
                        errors.append(f"execution {name} aggregate status contradicts components")
            expected_overall = {
                AdherenceStatus.INSUFFICIENT_DATA: OverallStatus.INSUFFICIENT_DATA,
                AdherenceStatus.NOT_MET: OverallStatus.DIFFERENT,
                AdherenceStatus.PARTIALLY_MET: OverallStatus.PARTIALLY_IN_LINE,
                AdherenceStatus.MET: OverallStatus.IN_LINE,
            }[aggregate_adherence_status([item.status for item in aggregates])]
            if value.overall is not expected_overall:
                errors.append("execution overall contradicts its verified dimensional aggregates")
            component_doses = tuple(component.dose for component in required)
            if any(dose is None for dose in component_doses):
                errors.append("execution aggregate dose requires every component dose")
            else:
                for component, dose in zip(required, component_doses):
                    quantity, intensity = component.quantity, component.intensity
                    if (dose.quantity_result_ref != quantity.result_id or
                            dose.intensity_result_ref != intensity.result_id):
                        errors.append("execution component dose refs must match its dimensions")
                    insufficient = (quantity.status is AdherenceStatus.INSUFFICIENT_DATA or
                                    intensity.status is AdherenceStatus.INSUFFICIENT_DATA or
                                    quantity.band is None or intensity.band is None)
                    if insufficient:
                        if (dose.status is not DoseStatus.INSUFFICIENT_DATA or
                                dose.direction is not None or dose.severity_band is not None or
                                dose.policy != NULL_POLICY):
                            errors.append("execution component dose contradicts its dimensions")
                    else:
                        expected_direction = _aggregate_direction(
                            {quantity.direction, intensity.direction})
                        expected_severity = max((quantity.band, intensity.band),
                                                key=lambda item: list(SeverityBand).index(item))
                        if (dose.status is not DoseStatus.EVALUATED or
                                dose.direction is not expected_direction or
                                dose.severity_band is not expected_severity or
                                dose.policy != DOSE_POLICY):
                            errors.append("execution component dose contradicts its dimensions")
            if (all(dose is not None for dose in component_doses) and
                    any(dose.status is DoseStatus.INSUFFICIENT_DATA for dose in component_doses)):
                if (value.dose_aggregate.status is not DoseStatus.INSUFFICIENT_DATA or
                        value.dose_aggregate.direction is not None or
                        value.dose_aggregate.severity_band is not None or
                        value.dose_aggregate.policy != NULL_POLICY):
                    errors.append("execution insufficient aggregate dose contradicts component doses")
            elif all(dose is not None for dose in component_doses):
                expected_direction = _aggregate_direction({dose.direction for dose in component_doses})
                expected_severity = max((dose.severity_band for dose in component_doses),
                                        key=lambda item: list(SeverityBand).index(item))
                if (value.dose_aggregate.status is not DoseStatus.EVALUATED or
                        value.dose_aggregate.direction is not expected_direction or
                        value.dose_aggregate.severity_band is not expected_severity or
                        value.dose_aggregate.policy != DOSE_POLICY):
                    errors.append("execution aggregate dose contradicts component doses")
            if (value.dose_aggregate.quantity_result_ref != value.quantity_aggregate.result_id or
                    value.dose_aggregate.intensity_result_ref != value.intensity_aggregate.result_id):
                errors.append("execution dose refs must match quantity and intensity aggregates")
    elif any(item is not None for item in aggregates) or value.dose_aggregate is not None or value.overall is not None:
        errors.append("non-full execution coverage requires null aggregates, dose, and overall")
    for ref in (*coverage.required_supported_component_refs,
                *coverage.required_unsupported_component_refs,
                *coverage.optional_unsupported_component_refs):
        if ref.prescription_snapshot_id != value.prescription_snapshot_ref:
            errors.append("execution coverage contains a foreign prescription ref")
    for component in value.component_results:
        if (component.planned_component_ref is not None and
                component.planned_component_ref.prescription_snapshot_id != value.prescription_snapshot_ref):
            errors.append("execution component contains a foreign prescription ref")
        if (component.observed_component_ref is not None and
                component.observed_component_ref.session_id != value.actual_session_ref):
            errors.append("execution component contains a foreign session ref")
    return tuple(errors)


def validate_final_outcome_inputs(
    execution: ExecutionEvaluation,
    stability: GeneralStabilityEvaluation,
) -> tuple[str, ...]:
    errors = list(_validate_execution_evaluation(execution))
    stability_shape_errors = _validate(stability, GeneralStabilityEvaluation, "stability")
    errors.extend(stability_shape_errors)
    if type(execution) is not ExecutionEvaluation or type(stability) is not GeneralStabilityEvaluation:
        return tuple(errors)

    if not stability_shape_errors:
        errors.extend(validate_general_stability_evaluation(stability))

    coverage = execution.evaluation_coverage
    binding = stability.prescription_binding
    boundary = stability.actual_session_boundary
    if type(coverage) is EvaluationCoverage and type(coverage.status) is CoverageStatus:
        if coverage.status is CoverageStatus.FULLY_SUPPORTED:
            if type(execution.overall) is not OverallStatus:
                errors.append("execution.overall must be OverallStatus for full coverage")
        elif execution.overall is not None:
            errors.append("execution.overall must be null when coverage is not full")
    if type(binding) is PrescriptionBaselineBinding:
        snapshot = binding.prescription_snapshot_ref
        if type(snapshot) is VersionedArtifactRef and snapshot.artifact_id != execution.prescription_snapshot_ref:
            errors.append("execution and stability prescription snapshot refs must agree")
        if binding.subject_ref != stability.subject_ref:
            errors.append("stability prescription ownership must agree")
    if type(boundary) is ActualSessionBoundary and type(boundary.actual_session_ref) is VersionedArtifactRef:
        if boundary.actual_session_ref.artifact_id != execution.actual_session_ref:
            errors.append("execution and stability actual session refs must agree")
        if boundary.subject_ref != stability.subject_ref:
            errors.append("stability actual session ownership must agree")
    return tuple(errors)


def validate_final_metadata(evaluation_id: object, evaluated_at: object,
                            provenance_ref: object,
                            stability: object) -> tuple[str, ...]:
    errors: list[str] = []
    if type(evaluation_id) is not str or not evaluation_id or evaluation_id.isspace():
        errors.append("evaluation_id must be a non-empty string")
    if not _aware(evaluated_at):
        errors.append("evaluated_at must be a timezone-aware datetime")
    elif (type(stability) is GeneralStabilityEvaluation and _aware(stability.evaluated_at)
          and evaluated_at < stability.evaluated_at):
        errors.append("evaluated_at must not precede stability.evaluated_at")
    errors.extend(_validate(provenance_ref, ProvenanceRef, "provenance_ref"))
    return tuple(errors)
