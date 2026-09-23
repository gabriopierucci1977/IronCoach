"""Pure, global decision layer for validated runtime-matching inputs.

The layer deliberately has no repository dependency and creates no persisted
mapping.  It evaluates the complete bipartite scope before describing whether
there are zero, one, or multiple possible relationships.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .runtime_matching_compatibility import (
    CompatibilityState,
    StructuralCompatibility,
    evaluate_structural_compatibility,
)
from .runtime_matching_scope import (
    DirectIdEvidenceIssue,
    RuntimeMatchingScope,
    returned_prescription_id_issue,
)


class CandidateCardinality(str, Enum):
    ZERO = "ZERO"
    ONE = "ONE"
    MULTIPLE = "MULTIPLE"


class DecisionStatus(str, Enum):
    MATCHED = "MATCHED"
    CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class DecisionReason(str, Enum):
    NO_CANDIDATE = "NO_CANDIDATE"
    MULTIPLE_CANDIDATES = "MULTIPLE_CANDIDATES"
    SESSION_COMPETITION = "SESSION_COMPETITION"
    PRESCRIPTION_COMPETITION = "PRESCRIPTION_COMPETITION"
    DIRECT_ID_MISSING = "DIRECT_ID_MISSING"
    DIRECT_ID_MALFORMED = "DIRECT_ID_MALFORMED"
    DIRECT_ID_DANGLING = "DIRECT_ID_DANGLING"
    DIRECT_ID_CONTRADICTORY = "DIRECT_ID_CONTRADICTORY"
    DIRECT_ID_DUPLICATE = "DIRECT_ID_DUPLICATE"
    UNSUPPORTED_COMPATIBILITY = "UNSUPPORTED_COMPATIBILITY"


@dataclass(frozen=True, order=True)
class CandidatePair:
    prescription_snapshot_id: str
    session_id: str
    direct: bool = False


@dataclass(frozen=True)
class PairEvaluation:
    prescription_snapshot_id: str
    session_id: str
    compatibility: StructuralCompatibility
    suppressed_by_direct_evidence: bool = False


@dataclass(frozen=True)
class MatchingDecision:
    status: DecisionStatus
    cardinality: CandidateCardinality
    selected_pair: CandidatePair | None
    candidates: tuple[CandidatePair, ...]
    pair_evaluations: tuple[PairEvaluation, ...]
    reasons: tuple[DecisionReason, ...]
    involved_prescription_ids: tuple[str, ...]
    involved_session_ids: tuple[str, ...]


class MatchingDecisionInputError(TypeError):
    """The decision layer was not given the validated scope boundary."""


def _issue_reasons(scope: RuntimeMatchingScope) -> set[DecisionReason]:
    mapping = {
        DirectIdEvidenceIssue.MISSING_RETURNED_PRESCRIPTION_ID:
            DecisionReason.DIRECT_ID_MISSING,
        DirectIdEvidenceIssue.MALFORMED_RETURNED_PRESCRIPTION_ID:
            DecisionReason.DIRECT_ID_MALFORMED,
        DirectIdEvidenceIssue.DUPLICATE_ASSERTION:
            DecisionReason.DIRECT_ID_DUPLICATE,
        DirectIdEvidenceIssue.CONTRADICTORY_ASSERTIONS:
            DecisionReason.DIRECT_ID_CONTRADICTORY,
    }
    return {mapping[issue] for issue in scope.direct_id_evidence_issues}


def decide_runtime_matching(scope: RuntimeMatchingScope) -> MatchingDecision:
    """Decide over every snapshot and session in a previously validated scope.

    Explicit IDs resolve exclusively against ``prescription_snapshot_id``.
    Evidence that does not resolve cleanly blocks structural fallback for its
    session and is surfaced for later coach confirmation.
    """
    if not isinstance(scope, RuntimeMatchingScope):
        raise MatchingDecisionInputError(
            "scope must be a RuntimeMatchingScope produced by validation")

    snapshot_by_id = {item.prescription_snapshot_id: item for item in scope.snapshots}
    evidence_by_session = {item.session_id: [] for item in scope.direct_id_evidence}
    for item in scope.direct_id_evidence:
        evidence_by_session[item.session_id].append(item)

    # A clean, single direct assertion reserves its prescription before the
    # structural matrix is turned into candidates.  Pair evaluation still
    # covers the full matrix, but another session cannot compete merely because
    # it looks similar.  Multiple direct assertions are deliberately not
    # collapsed here: they remain visible as real direct-ID conflicts.
    reserved_direct_prescription_ids: set[str] = set()
    for evidence in evidence_by_session.values():
        valid_targets = [item.returned_prescription_id for item in evidence
                         if returned_prescription_id_issue(
                             item.returned_prescription_id) is None]
        if len(evidence) == 1 and len(valid_targets) == 1:
            target = valid_targets[0]
            assert isinstance(target, str)
            if target in snapshot_by_id:
                reserved_direct_prescription_ids.add(target)

    candidates: set[CandidatePair] = set()
    evaluations: list[PairEvaluation] = []
    reasons = _issue_reasons(scope)
    involved_prescriptions: set[str] = set()
    involved_sessions: set[str] = set()
    blocking_unsupported = False

    # Evaluate the full matrix even when direct evidence will select or suppress
    # a row.  This prevents input iteration order from becoming a tie-break.
    for session in scope.sessions:
        has_direct_envelope = session.session_id in evidence_by_session
        for snapshot in scope.snapshots:
            compatibility = evaluate_structural_compatibility(snapshot, session)
            evaluations.append(PairEvaluation(
                snapshot.prescription_snapshot_id,
                session.session_id,
                compatibility,
                has_direct_envelope,
            ))
            if compatibility.state is CompatibilityState.UNSUPPORTED:
                reasons.add(DecisionReason.UNSUPPORTED_COMPATIBILITY)
                involved_prescriptions.add(snapshot.prescription_snapshot_id)
                involved_sessions.add(session.session_id)
                blocking_unsupported |= (
                    not has_direct_envelope and
                    snapshot.prescription_snapshot_id not in
                    reserved_direct_prescription_ids)
            elif (not has_direct_envelope and
                  snapshot.prescription_snapshot_id not in
                  reserved_direct_prescription_ids and
                  compatibility.state is CompatibilityState.COMPATIBLE):
                candidates.add(CandidatePair(
                    snapshot.prescription_snapshot_id, session.session_id))

    # A valid envelope is authoritative, including when structure/window differ.
    # Multiple assertions are retained as multiple possibilities, never ranked.
    for session_id, evidence in evidence_by_session.items():
        involved_sessions.add(session_id)
        for item in evidence:
            target = item.returned_prescription_id
            # Validate before hashing or comparing the untrusted target.  In
            # particular, frozen mappings and other containers are unhashable.
            if returned_prescription_id_issue(target) is not None:
                continue
            assert isinstance(target, str)
            if target in snapshot_by_id:
                candidates.add(CandidatePair(target, session_id, True))
                involved_prescriptions.add(target)
            else:
                # Deliberately do not try workout_id here.
                reasons.add(DecisionReason.DIRECT_ID_DANGLING)

    ordered_candidates = tuple(sorted(candidates))
    session_counts: dict[str, int] = {}
    prescription_counts: dict[str, int] = {}
    for candidate in ordered_candidates:
        session_counts[candidate.session_id] = session_counts.get(candidate.session_id, 0) + 1
        prescription_counts[candidate.prescription_snapshot_id] = (
            prescription_counts.get(candidate.prescription_snapshot_id, 0) + 1)
    if any(count > 1 for count in session_counts.values()):
        reasons.add(DecisionReason.SESSION_COMPETITION)
    if any(count > 1 for count in prescription_counts.values()):
        reasons.add(DecisionReason.PRESCRIPTION_COMPETITION)

    confirmation_reasons = {
        DecisionReason.DIRECT_ID_MISSING,
        DecisionReason.DIRECT_ID_MALFORMED,
        DecisionReason.DIRECT_ID_DANGLING,
        DecisionReason.DIRECT_ID_CONTRADICTORY,
        DecisionReason.DIRECT_ID_DUPLICATE,
    }
    uncertain_direct = bool(reasons & confirmation_reasons)
    if len(ordered_candidates) == 0:
        cardinality = CandidateCardinality.ZERO
    elif len(ordered_candidates) == 1:
        cardinality = CandidateCardinality.ONE
    else:
        cardinality = CandidateCardinality.MULTIPLE

    if uncertain_direct:
        status, selected = DecisionStatus.CONFIRMATION_REQUIRED, None
    elif cardinality is CandidateCardinality.MULTIPLE:
        status, selected = DecisionStatus.CONFIRMATION_REQUIRED, None
        reasons.add(DecisionReason.MULTIPLE_CANDIDATES)
    elif blocking_unsupported:
        status, selected = DecisionStatus.NOT_EVALUABLE, None
    elif cardinality is CandidateCardinality.ONE:
        status, selected = DecisionStatus.MATCHED, ordered_candidates[0]
    else:
        status, selected = DecisionStatus.NOT_EVALUABLE, None
        reasons.add(DecisionReason.NO_CANDIDATE)

    if cardinality is not CandidateCardinality.ONE:
        involved_prescriptions.update(item.prescription_snapshot_id
                                      for item in ordered_candidates)
        involved_sessions.update(item.session_id for item in ordered_candidates)
    return MatchingDecision(
        status, cardinality, selected, ordered_candidates, tuple(evaluations),
        tuple(sorted(reasons, key=lambda item: item.value)),
        tuple(sorted(involved_prescriptions, key=lambda value: value.encode("utf-8"))),
        tuple(sorted(involved_sessions, key=lambda value: value.encode("utf-8"))),
    )
