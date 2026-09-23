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
        "component_order": all(right.component_index == left.component_index + 1
                               for left, right in zip(observed, observed[1:])),
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
    for position, (left, right) in enumerate(zip(observed, observed[1:])):
        if left.start is None or left.end is None or right.start is None:
            return False, "component timing is incomplete"
        if right.start < left.end:
            return False, "components overlap"
        if len(observed) != len(planned):
            return False, "component sequence is not consecutive"
        limit = limits.get((planned[position].component_id,
                            planned[position + 1].component_id))
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
    for component_position in range(max(len(planned), len(observed))):
        p = planned[component_position] if component_position < len(planned) else None
        o = observed[component_position] if component_position < len(observed) else None
        planned_blocks = () if p is None else tuple(sorted(p.structure.blocks,
                                                           key=lambda value: value.block_index))
        observed_blocks = () if o is None else tuple(sorted(o.blocks,
                                                            key=lambda value: value.block_index))
        for block_position in range(max(len(planned_blocks), len(observed_blocks))):
            pb = planned_blocks[block_position] if block_position < len(planned_blocks) else None
            ob = observed_blocks[block_position] if block_position < len(observed_blocks) else None
            block_status = (MatchStatus.MATCHED if pb is not None and ob is not None else
                            MatchStatus.PLANNED_ONLY if pb is not None else MatchStatus.OBSERVED_ONLY)
            blocks.append(BlockMapping(
                None if pb is None else PlannedBlockRef(
                    snapshot.prescription_snapshot_id, p.component_id, pb.block_id),
                None if ob is None else ObservedBlockRef(
                    session.session_id, o.component_id, ob.block_id), block_status))
            planned_count = 0 if pb is None or pb.planned_repetitions is None else pb.planned_repetitions
            observed_repetitions = () if ob is None else tuple(sorted(
                ob.repetitions, key=lambda value: value.repetition_index))
            for repetition_position in range(max(planned_count, len(observed_repetitions))):
                repetition = (observed_repetitions[repetition_position]
                              if repetition_position < len(observed_repetitions) else None)
                repetition_status = (MatchStatus.MATCHED
                                     if repetition_position < planned_count and repetition is not None else
                                     MatchStatus.PLANNED_ONLY if repetition_position < planned_count else
                                     MatchStatus.OBSERVED_ONLY)
                repetitions.append(RepetitionMapping(
                    None if repetition_position >= planned_count else PlannedRepetitionRef(
                        snapshot.prescription_snapshot_id, p.component_id, pb.block_id,
                        repetition_position),
                    None if repetition is None else ObservedRepetitionRef(
                        session.session_id, o.component_id, ob.block_id, repetition.repetition_id),
                    repetition_status))
    # Transition tuple order is not semantic.  Resolve endpoints through the
    # component pairs already established above, and only associate a unique
    # planned/observed endpoint pair.  Missing, extra, or duplicate endpoint
    # pairs remain explicit rather than being paired positionally.
    component_links = {
        item.planned_component_ref.component_id: item.observed_component_ref.component_id
        for item in components
        if (item.planned_component_ref is not None and
            item.observed_component_ref is not None and
            item.match_status is MatchStatus.MATCHED)
    }
    planned_by_observed_endpoints = {}
    for item in snapshot.transitions:
        mapped_from = component_links.get(item.from_component_id)
        mapped_to = component_links.get(item.to_component_id)
        key = None if mapped_from is None or mapped_to is None else (mapped_from, mapped_to)
        planned_by_observed_endpoints.setdefault(key, []).append(item)
    observed_by_endpoints = {}
    for item in session.transitions:
        key = (item.from_component_ref, item.to_component_ref)
        observed_by_endpoints.setdefault(key, []).append(item)

    transitions = []
    matched_observed_ids = set()
    for planned_transition in snapshot.transitions:
        mapped_from = component_links.get(planned_transition.from_component_id)
        mapped_to = component_links.get(planned_transition.to_component_id)
        key = None if mapped_from is None or mapped_to is None else (mapped_from, mapped_to)
        planned_candidates = planned_by_observed_endpoints.get(key, ())
        observed_candidates = observed_by_endpoints.get(key, ()) if key is not None else ()
        observed_transition = (observed_candidates[0]
                               if len(planned_candidates) == len(observed_candidates) == 1
                               else None)
        if observed_transition is not None:
            matched_observed_ids.add(observed_transition.transition_id)
        transitions.append(TransitionMapping(
            PlannedTransitionRef(snapshot.prescription_snapshot_id,
                                 planned_transition.transition_id),
            None if observed_transition is None else ObservedTransitionRef(
                session.session_id, observed_transition.transition_id),
            MatchStatus.PLANNED_ONLY if observed_transition is None else MatchStatus.MATCHED,
        ))
    transitions.extend(
        TransitionMapping(
            None,
            ObservedTransitionRef(session.session_id, item.transition_id),
            MatchStatus.OBSERVED_ONLY,
        )
        for item in session.transitions
        if item.transition_id not in matched_observed_ids
    )
    value = PrescriptionMapping(mapping_id, snapshot.prescription_snapshot_id, session.session_id,
                                resolution_method, tuple(components), tuple(blocks),
                                tuple(repetitions), tuple(transitions), confirmation_ref, actor,
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
            ("composed session requires an explicit consecutivity policy",),
            tuple(sorted(session.session_id for session in sessions)))
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
                                  None, provenance or {}, (), ("direct ID is invalid, dangling, contradictory, or ambiguous",),
                                  tuple(sorted(by_id)))
        session = by_id[next(iter(direct_sessions))]
        mapping = build_mapping(snapshot, session, mapping_id=mapping_id, created_at=created_at,
                                resolution_method=ResolutionMethod.AUTOMATIC,
                                provenance=provenance)
        return MatchingResult(matching_result_id, MatchingStatus.MATCHED, mapping,
                              snapshot.matching_policy, snapshot.prescription_snapshot_id,
                              (session.session_id,), (), None, provenance or {}, (), (), tuple(sorted(by_id)))

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
                          None, provenance or {}, (), warnings, tuple(sorted(by_id)))
