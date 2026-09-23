"""Pure structural compatibility for one persisted snapshot/session pair.

This boundary deliberately performs no discovery, direct-ID handling, candidate
cardinality, outcome derivation, or persistence.  BRICK interposition cannot be
proved by the current canonical artifacts, so a BRICK that passes every other
structural predicate remains unsupported rather than compatible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
import math
from typing import Iterable

from .models import (
    ActualSession, Composition, Discipline, Environment, Mode, ObservedComponent,
    ObservedTransition, PlannedComponent, PlannedTransition, PrescriptionSnapshot,
    SupportStatus,
)
from .validators import validate_actual_session, validate_prescription


DEFAULT_BRICK_MAXIMUM_GAP = timedelta(minutes=15)


class CompatibilityState(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNSUPPORTED = "UNSUPPORTED"


class CompatibilityReason(str, Enum):
    SCHEDULED_WINDOW = "SCHEDULED_WINDOW"
    COMPOSITION_MISMATCH = "COMPOSITION_MISMATCH"
    COMPONENT_CARDINALITY = "COMPONENT_CARDINALITY"
    COMPONENT_ORDER = "COMPONENT_ORDER"
    COMPONENT_DISCIPLINE = "COMPONENT_DISCIPLINE"
    COMPONENT_ENVIRONMENT = "COMPONENT_ENVIRONMENT"
    COMPONENT_MODE = "COMPONENT_MODE"
    CAPABILITY_UNSUPPORTED = "CAPABILITY_UNSUPPORTED"
    BRICK_TRANSITION_INVALID = "BRICK_TRANSITION_INVALID"
    BRICK_TIMING_INSUFFICIENT = "BRICK_TIMING_INSUFFICIENT"
    BRICK_COMPONENT_OVERLAP = "BRICK_COMPONENT_OVERLAP"
    BRICK_MAXIMUM_GAP_EXCEEDED = "BRICK_MAXIMUM_GAP_EXCEEDED"
    BRICK_INTERPOSITION_UNPROVABLE = "BRICK_INTERPOSITION_UNPROVABLE"


@dataclass(frozen=True)
class StructuralCompatibility:
    state: CompatibilityState
    reasons: tuple[CompatibilityReason, ...] = ()


class CompatibilityInputError(ValueError):
    """An authoritative artifact is malformed or has undecodable values."""

    def __init__(self, errors: Iterable[str]):
        self.errors = tuple(sorted(set(errors)))
        super().__init__("; ".join(self.errors))


def _validated(snapshot: object, session: object) -> tuple[PrescriptionSnapshot, ActualSession]:
    errors: list[str] = []
    if not isinstance(snapshot, PrescriptionSnapshot):
        errors.append("snapshot must be a PrescriptionSnapshot")
    if not isinstance(session, ActualSession):
        errors.append("session must be an ActualSession")
    if errors:
        raise CompatibilityInputError(errors)
    assert isinstance(snapshot, PrescriptionSnapshot)
    assert isinstance(session, ActualSession)
    if type(snapshot.composition) is not Composition:
        errors.append("snapshot composition is unknown or undecodable")
    if type(session.composition) is not Composition:
        errors.append("session composition is unknown or undecodable")
    if errors:
        raise CompatibilityInputError(errors)
    for label, components in (("snapshot", snapshot.components), ("session", session.components)):
        for component in components:
            expected_type = PlannedComponent if label == "snapshot" else ObservedComponent
            if not isinstance(component, expected_type):
                errors.append(f"{label} component is malformed")
                continue
            if type(component.component_index) is not int or component.component_index < 0:
                errors.append(f"{label} component_index is malformed")
            if type(component.discipline) is not Discipline:
                errors.append(f"{label} component discipline is unknown or undecodable")
            if component.environment is not None and type(component.environment) is not Environment:
                errors.append(f"{label} component environment is unknown or undecodable")
            if component.mode is not None and type(component.mode) is not Mode:
                errors.append(f"{label} component mode is unknown or undecodable")
            if label == "snapshot":
                if type(component.support_status) is not SupportStatus:
                    errors.append("snapshot component support status is unknown or undecodable")
                for substitution in component.allowed_substitutions:
                    if type(substitution.discipline) is not Discipline:
                        errors.append("snapshot substitution discipline is unknown or undecodable")
                    if (substitution.environment is not None and
                            type(substitution.environment) is not Environment):
                        errors.append("snapshot substitution environment is unknown or undecodable")
                    if substitution.mode is not None and type(substitution.mode) is not Mode:
                        errors.append("snapshot substitution mode is unknown or undecodable")
    for label, transitions in (("snapshot", snapshot.transitions),
                               ("session", session.transitions)):
        expected_type = PlannedTransition if label == "snapshot" else ObservedTransition
        for transition in transitions:
            if not isinstance(transition, expected_type):
                errors.append(f"{label} transition is malformed")
    if errors:
        raise CompatibilityInputError(errors)
    try:
        errors.extend(f"snapshot: {error}" for error in validate_prescription(snapshot))
        errors.extend(f"session: {error}" for error in validate_actual_session(session))
    except (AttributeError, TypeError, ValueError, OverflowError) as error:
        raise CompatibilityInputError((f"authoritative artifact is malformed: {error}",)) from error
    if errors:
        raise CompatibilityInputError(errors)
    return snapshot, session


def _is_representable_nonnegative_minutes(value: object) -> bool:
    if type(value) not in (int, float) or value < 0:
        return False
    if type(value) is float and not math.isfinite(value):
        return False
    try:
        timedelta(minutes=value)
    except OverflowError:
        return False
    return True


def _validate_transition_numbers(snapshot: PrescriptionSnapshot, session: ActualSession) -> None:
    """Validate numeric limits on every authored transition before pair matching."""
    errors: list[str] = []
    for transition in snapshot.transitions:
        value = transition.applicable_limit_minutes
        if not _is_representable_nonnegative_minutes(value):
            errors.append("snapshot transition maximum gap is invalid")
    for transition in session.transitions:
        value = transition.duration_minutes
        if value is not None and not _is_representable_nonnegative_minutes(value):
            errors.append("observed transition duration is invalid")
    if errors:
        raise CompatibilityInputError(errors)


def _component_reasons(
        expected: PlannedComponent, observed: ObservedComponent) -> tuple[CompatibilityReason, ...]:
    if observed.discipline is expected.discipline:
        environment, mode = expected.environment, expected.mode
    else:
        matches = tuple(item for item in expected.allowed_substitutions
                        if item.discipline is observed.discipline)
        if not matches:
            return (CompatibilityReason.COMPONENT_DISCIPLINE,)
        # Multiple authored entries are alternatives.  Any fully compatible
        # entry admits the observed component; no chaining is performed.
        if any((item.environment is None or observed.environment is None or
                item.environment is observed.environment) and
               (item.mode is None or observed.mode is None or item.mode is observed.mode)
               for item in matches):
            return ()
        environment_mismatch = (observed.environment is not None and
                                all(item.environment is not None and
                                    item.environment is not observed.environment for item in matches))
        return ((CompatibilityReason.COMPONENT_ENVIRONMENT,) if environment_mismatch else
                (CompatibilityReason.COMPONENT_MODE,))

    reasons = []
    if (environment is not None and observed.environment is not None and
            environment is not observed.environment):
        reasons.append(CompatibilityReason.COMPONENT_ENVIRONMENT)
    if mode is not None and observed.mode is not None and mode is not observed.mode:
        reasons.append(CompatibilityReason.COMPONENT_MODE)
    return tuple(reasons)


def _common_reasons(snapshot: PrescriptionSnapshot, session: ActualSession):
    reasons: list[CompatibilityReason] = []
    if not snapshot.scheduled_window.start <= session.start <= snapshot.scheduled_window.end:
        reasons.append(CompatibilityReason.SCHEDULED_WINDOW)
    if session.composition is not snapshot.composition:
        reasons.append(CompatibilityReason.COMPOSITION_MISMATCH)

    planned = tuple(sorted(snapshot.components, key=lambda item: item.component_index))
    observed = tuple(sorted(session.components, key=lambda item: item.component_index))
    if len(planned) != len(observed):
        reasons.append(CompatibilityReason.COMPONENT_CARDINALITY)
    elif (tuple(item.component_index for item in planned) != tuple(range(len(planned))) or
          tuple(item.component_index for item in observed) != tuple(range(len(observed)))):
        reasons.append(CompatibilityReason.COMPONENT_ORDER)
    else:
        for expected, actual in zip(planned, observed):
            reasons.extend(_component_reasons(expected, actual))
    return planned, observed, reasons


def _brick_reasons(snapshot: PrescriptionSnapshot, session: ActualSession,
                   planned, observed) -> tuple[CompatibilityReason, ...]:
    reasons: list[CompatibilityReason] = []
    if len(planned) != len(observed):
        return ()

    if any(component.start is None or component.end is None for component in observed):
        reasons.append(CompatibilityReason.BRICK_TIMING_INSUFFICIENT)
        return tuple(reasons)

    observed_by_pair = {(item.from_component_ref, item.to_component_ref): item
                        for item in session.transitions}
    adjacent_observed = tuple((left.component_id, right.component_id)
                              for left, right in zip(observed, observed[1:]))
    if (len(observed_by_pair) != len(session.transitions) or
            set(observed_by_pair) != set(adjacent_observed)):
        reasons.append(CompatibilityReason.BRICK_TRANSITION_INVALID)

    planned_by_pair = {(item.from_component_id, item.to_component_id): item
                       for item in snapshot.transitions}
    adjacent_planned = tuple((left.component_id, right.component_id)
                             for left, right in zip(planned, planned[1:]))
    if planned_by_pair and (len(planned_by_pair) != len(snapshot.transitions) or
                            set(planned_by_pair) != set(adjacent_planned)):
        reasons.append(CompatibilityReason.BRICK_TRANSITION_INVALID)

    for position, pair in enumerate(adjacent_observed):
        left, right = observed[position], observed[position + 1]
        assert left.end is not None and right.start is not None
        if right.start < left.end:
            reasons.append(CompatibilityReason.BRICK_COMPONENT_OVERLAP)
            continue
        limit = DEFAULT_BRICK_MAXIMUM_GAP
        authored = planned_by_pair.get(adjacent_planned[position])
        if authored is not None:
            value = authored.applicable_limit_minutes
            limit = timedelta(minutes=value)
        if right.start - left.end > limit:
            reasons.append(CompatibilityReason.BRICK_MAXIMUM_GAP_EXCEEDED)

        transition = observed_by_pair.get(pair)
        if transition is None:
            continue
        if transition.start is None or transition.end is None:
            reasons.append(CompatibilityReason.BRICK_TIMING_INSUFFICIENT)
            continue
        if not (left.end <= transition.start <= transition.end <= right.start):
            reasons.append(CompatibilityReason.BRICK_TRANSITION_INVALID)
        if transition.duration_minutes is not None:
            duration = transition.duration_minutes
            actual_duration = (transition.end - transition.start).total_seconds() / 60
            if duration != actual_duration:
                reasons.append(CompatibilityReason.BRICK_TRANSITION_INVALID)
    return tuple(reasons)


def evaluate_structural_compatibility(
        snapshot: PrescriptionSnapshot, session: ActualSession) -> StructuralCompatibility:
    """Evaluate only authoritative pair-local structural predicates."""
    snapshot, session = _validated(snapshot, session)
    _validate_transition_numbers(snapshot, session)
    planned, observed, reasons = _common_reasons(snapshot, session)

    if snapshot.composition is Composition.BRICK:
        reasons.extend(_brick_reasons(snapshot, session, planned, observed))

    unique_reasons = tuple(dict.fromkeys(reasons))
    if unique_reasons:
        return StructuralCompatibility(CompatibilityState.INCOMPATIBLE, unique_reasons)

    if any(item.support_status is SupportStatus.UNSUPPORTED for item in planned):
        return StructuralCompatibility(
            CompatibilityState.UNSUPPORTED, (CompatibilityReason.CAPABILITY_UNSUPPORTED,))

    if snapshot.composition is Composition.BRICK:
        return StructuralCompatibility(
            CompatibilityState.UNSUPPORTED,
            (CompatibilityReason.BRICK_INTERPOSITION_UNPROVABLE,),
        )
    return StructuralCompatibility(CompatibilityState.COMPATIBLE)
