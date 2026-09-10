"""All-or-nothing structural validation for final outcome aggregation."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType, UnionType
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from .models import CoverageStatus, EvaluationCoverage, ExecutionEvaluation, OverallStatus
from .stability_models import (
    ActualSessionBoundary, GeneralStabilityEvaluation, PrescriptionBaselineBinding,
    ProvenanceRef, RecoveryAssessmentCandidateSetRef, StabilityResult,
    VersionedArtifactRef, STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID,
    STABILITY_POLICY_VERSION,
)


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


def validate_final_outcome_inputs(
    execution: ExecutionEvaluation,
    stability: GeneralStabilityEvaluation,
) -> tuple[str, ...]:
    errors = _validate(execution, ExecutionEvaluation, "execution")
    errors.extend(_validate(stability, GeneralStabilityEvaluation, "stability"))
    if type(execution) is not ExecutionEvaluation or type(stability) is not GeneralStabilityEvaluation:
        return tuple(errors)

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
    candidate_ref = stability.candidate_set_ref
    if type(candidate_ref) is RecoveryAssessmentCandidateSetRef:
        if type(boundary) is ActualSessionBoundary and candidate_ref.actual_session_ref != boundary.actual_session_ref:
            errors.append("stability candidate set and actual session refs must agree")
        if candidate_ref.subject_ref != stability.subject_ref:
            errors.append("stability candidate set ownership must agree")
    if (stability.contract_version, stability.policy_id, stability.policy_version) != (
            STABILITY_CONTRACT_VERSION, STABILITY_POLICY_ID, STABILITY_POLICY_VERSION):
        errors.append("stability contract and policy versions must be exact")
    if type(stability.overall) is not StabilityResult:
        errors.append("stability.overall must be StabilityResult")
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
