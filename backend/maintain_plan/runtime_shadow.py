"""Default-off, in-memory shadow boundary for runtime matching."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .models import ActualSession, DirectIdEvidence, PrescriptionSnapshot
from .runtime_matching_decision import MatchingDecision, decide_runtime_matching
from .runtime_matching_scope import validate_runtime_matching_scope


@dataclass(frozen=True)
class RuntimeMatchingShadowResult:
    subject_ref: str
    snapshot_count: int
    session_count: int
    decision: MatchingDecision


def evaluate_runtime_matching_shadow(
    *,
    subject_ref: object,
    snapshots: Iterable[PrescriptionSnapshot],
    sessions: Iterable[ActualSession],
    direct_id_evidence: Iterable[DirectIdEvidence] = (),
) -> RuntimeMatchingShadowResult:
    """Evaluate only caller-supplied in-memory artifacts."""
    snapshot_values = tuple(snapshots)
    session_values = tuple(sessions)
    evidence_values = tuple(direct_id_evidence)

    scope = validate_runtime_matching_scope(
        subject_ref,
        snapshot_values,
        session_values,
        evidence_values,
    )

    return RuntimeMatchingShadowResult(
        subject_ref=scope.subject_ref,
        snapshot_count=len(scope.snapshots),
        session_count=len(scope.sessions),
        decision=decide_runtime_matching(scope),
    )
