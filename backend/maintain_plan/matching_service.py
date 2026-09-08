"""Deterministic matching of explicit immutable MAINTAIN_PLAN inputs.

This module neither discovers nor normalizes activities and deliberately does
not evaluate adherence.  All identifiers and timestamps used in its outputs
are supplied by the caller.
"""

from __future__ import annotations

from datetime import datetime

from .models import (
    ActualSession, BlockMapping, CandidateEvidence, ComponentMapping,
    DirectIdEvidence, MatchStatus, MatchingResult, MatchingStatus,
    ObservedBlockRef, ObservedComponentRef, ObservedRepetitionRef,
    ObservedTransitionRef, PlannedBlockRef, PlannedComponentRef,
    PlannedRepetitionRef, PlannedTransitionRef, PrescriptionMapping,
    PrescriptionSnapshot, RepetitionMapping, ResolutionMethod,
    SupportStatus, TransitionMapping,
)
from .validators import validate_actual_session, validate_mapping, validate_prescription


def _component_checks(snapshot: PrescriptionSnapshot, session: ActualSession) -> dict[str, bool]:
    planned = tuple(sorted(snapshot.components, key=lambda value: value.component_index))
    observed = tuple(sorted(session.components, key=lambda value: value.component_index))
    def compatible(expected, actual) -> bool:
        if expected.discipline is actual.discipline:
            return True
        return any(substitution.discipline is actual.discipline and
                   (substitution.environment is None or substitution.environment is actual.environment) and
                   (substitution.mode is None or substitution.mode is actual.mode)
                   for substitution in expected.allowed_substitutions)
    disciplines_match = len(planned) == len(observed) and all(
        compatible(expected, actual) for expected, actual in zip(planned, observed))
    return {
        "scheduled_window": snapshot.scheduled_window.start <= session.start <= snapshot.scheduled_window.end,
        "composition": session.composition is snapshot.composition,
        "component_cardinality": len(observed) == len(planned),
        "component_order": tuple(item.component_index for item in observed) == tuple(range(len(observed))),
        "disciplines": disciplines_match,
    }


def _consecutivity(snapshot: PrescriptionSnapshot, session: ActualSession) -> tuple[bool, str | None]:
    if snapshot.composition.value == "single":
        return True, None
    if snapshot.brick_policy.policy_id is None or snapshot.brick_policy.policy_version is None:
        return False, "composed session requires an explicit consecutivity policy"
    planned = tuple(sorted(snapshot.components, key=lambda value: value.component_index))
    observed = tuple(sorted(session.components, key=lambda value: value.component_index))
    limits = {(item.from_component_id, item.to_component_id): item.applicable_limit_minutes
              for item in snapshot.transitions}
    transitions = {(item.from_component_ref, item.to_component_ref): item
                   for item in session.transitions}
    for left, right in zip(observed, observed[1:]):
        if left.start is None or left.end is None or right.start is None:
            return False, "component timing is incomplete"
        if right.start < left.end:
            return False, "components overlap"
        if len(observed) != len(planned):
            return False, "component sequence is not consecutive"
        limit = limits.get((planned[left.component_index].component_id,
                            planned[right.component_index].component_id))
        if limit is None:
            return False, "transition gap policy is missing"
        gap = (right.start - left.end).total_seconds() / 60
        if gap > limit:
            return False, "transition gap exceeds the declared policy"
        transition = transitions.get((left.component_id, right.component_id))
        if transition is None:
            return False, "observed transition is missing or dangling"
        if transition.duration_minutes is not None and transition.duration_minutes != gap:
            return False, "observed transition duration is incoherent"
    if any(item.from_component_ref not in {c.component_id for c in observed} or
           item.to_component_ref not in {c.component_id for c in observed}
           for item in session.transitions):
        return False, "observed transition is dangling"
    return True, None


def build_mapping(snapshot: PrescriptionSnapshot, session: ActualSession, *, mapping_id: str,
                  created_at: datetime, resolution_method: ResolutionMethod,
                  confirmation_ref: str | None = None, actor: str | None = None,
                  provenance=None) -> PrescriptionMapping:
    """Build a canonical positional mapping, retaining missing and extra components."""
    planned = tuple(sorted(snapshot.components, key=lambda value: value.component_index))
    observed = tuple(sorted(session.components, key=lambda value: value.component_index))
    components = []
    for index in range(max(len(planned), len(observed))):
        p = planned[index] if index < len(planned) else None
        o = observed[index] if index < len(observed) else None
        status = MatchStatus.MATCHED if p and o else (MatchStatus.PLANNED_ONLY if p else MatchStatus.OBSERVED_ONLY)
        components.append(ComponentMapping(
            None if p is None else PlannedComponentRef(snapshot.prescription_snapshot_id, p.component_id),
            None if o is None else ObservedComponentRef(session.session_id, o.component_id),
            None if p is None else p.requiredness,
            SupportStatus.SUPPORTED if p is None else p.support_status,
            snapshot.components[0].capability_policy if p is None else p.capability_policy,
            status,
        ))
    blocks, repetitions = [], []
    for p, o in zip(planned, observed):
        for pb, ob in zip(sorted(p.structure.blocks, key=lambda x: x.block_index),
                          sorted(o.blocks, key=lambda x: x.block_index)):
            blocks.append(BlockMapping(
                PlannedBlockRef(snapshot.prescription_snapshot_id, p.component_id, pb.block_id),
                ObservedBlockRef(session.session_id, o.component_id, ob.block_id)))
            for position, repetition in enumerate(ob.repetitions):
                repetitions.append(RepetitionMapping(
                    PlannedRepetitionRef(snapshot.prescription_snapshot_id, p.component_id,
                                         pb.block_id, position),
                    ObservedRepetitionRef(session.session_id, o.component_id, ob.block_id,
                                          repetition.repetition_id)))
    transitions = tuple(TransitionMapping(
        PlannedTransitionRef(snapshot.prescription_snapshot_id, p.transition_id),
        ObservedTransitionRef(session.session_id, o.transition_id))
        for p, o in zip(snapshot.transitions, session.transitions))
    value = PrescriptionMapping(mapping_id, snapshot.prescription_snapshot_id, session.session_id,
                                resolution_method, tuple(components), tuple(blocks),
                                tuple(repetitions), transitions, confirmation_ref, actor,
                                created_at if confirmation_ref else None, created_at,
                                provenance or {})
    errors = validate_mapping(value)
    if errors:
        raise ValueError("; ".join(errors))
    return value


def match(snapshot: PrescriptionSnapshot, sessions: tuple[ActualSession, ...], *,
          matching_result_id: str, mapping_id: str, created_at: datetime,
          direct_id_evidence: tuple[DirectIdEvidence, ...] = (), provenance=None) -> MatchingResult:
    """Match only the supplied canonical sessions, without ranking or fallback tie-breaks."""
    if snapshot.composition.value != "single" and (
            snapshot.brick_policy.policy_id is None or snapshot.brick_policy.policy_version is None):
        return MatchingResult(
            matching_result_id, MatchingStatus.NOT_EVALUABLE, None,
            snapshot.matching_policy, snapshot.prescription_snapshot_id, (), (), None,
            provenance or {}, ("brick_policy",),
            ("composed session requires an explicit consecutivity policy",))
    errors = validate_prescription(snapshot)
    if errors:
        raise ValueError("; ".join(errors))
    by_id = {session.session_id: session for session in sessions}
    if len(by_id) != len(sessions) or any(validate_actual_session(value) for value in sessions):
        raise ValueError("sessions must be unique valid canonical inputs")
    direct = [item for item in direct_id_evidence
              if item.returned_prescription_id in {snapshot.prescription_snapshot_id, snapshot.workout_id}
              and item.session_id in by_id]
    mentioned = [item for item in direct_id_evidence if item.returned_prescription_id is not None]
    if mentioned:
        direct_sessions = {item.session_id for item in direct}
        if len(direct) != 1 or len(direct_sessions) != 1:
            return MatchingResult(matching_result_id, MatchingStatus.CONFIRMATION_REQUIRED, None,
                                  snapshot.matching_policy, snapshot.prescription_snapshot_id, (), (),
                                  None, provenance or {}, (), ("direct ID is invalid, dangling, contradictory, or ambiguous",))
        session = by_id[next(iter(direct_sessions))]
        mapping = build_mapping(snapshot, session, mapping_id=mapping_id, created_at=created_at,
                                resolution_method=ResolutionMethod.AUTOMATIC,
                                provenance=provenance)
        return MatchingResult(matching_result_id, MatchingStatus.MATCHED, mapping,
                              snapshot.matching_policy, snapshot.prescription_snapshot_id,
                              (session.session_id,), (), None, provenance or {})

    evidence, candidates, policy_missing = [], [], False
    for session in sorted(sessions, key=lambda value: value.session_id):
        checks = _component_checks(snapshot, session)
        consecutive, reason = _consecutivity(snapshot, session)
        checks["consecutivity"] = consecutive
        included = all(checks.values())
        policy_missing |= reason in {
            "composed session requires an explicit consecutivity policy",
            "transition gap policy is missing",
        }
        reasons = tuple(key for key, passed in checks.items() if not passed)
        if reason:
            reasons += (reason,)
        evidence.append(CandidateEvidence(session.session_id, included, checks, reasons))
        if included:
            candidates.append(session.session_id)
    status = MatchingStatus.NOT_EVALUABLE if policy_missing else (
        MatchingStatus.MATCHED if len(candidates) == 1 else MatchingStatus.CONFIRMATION_REQUIRED)
    mapping = None
    if status is MatchingStatus.MATCHED:
        mapping = build_mapping(snapshot, by_id[candidates[0]], mapping_id=mapping_id,
                                created_at=created_at, resolution_method=ResolutionMethod.AUTOMATIC,
                                provenance=provenance)
    warnings = ()
    if not candidates:
        warnings = ("Non ho trovato un'attività associabile alla seduta prevista",)
    return MatchingResult(matching_result_id, status, mapping, snapshot.matching_policy,
                          snapshot.prescription_snapshot_id, tuple(candidates), tuple(evidence),
                          None, provenance or {}, (), warnings)
