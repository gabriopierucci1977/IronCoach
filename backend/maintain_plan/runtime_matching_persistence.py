"""Narrow persistence bridge for a globally decided runtime match.

This module does not discover candidates and is not wired into the runtime.  It
only turns an already validated, globally unique decision into the existing
canonical mapping and asks the repository to persist it atomically.

The bridge cannot verify that the caller found every real activity: the reduced
scope carries no authoritative search-completeness or window-coverage proof.
Consequently it treats the caller-supplied scope as the decision boundary and
never turns ``ZERO`` (or any other non-unique outcome) into a write.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .matching_service import build_mapping
from .models import PrescriptionMapping, ResolutionMethod
from .repository import MaintainPlanRepository
from .runtime_matching_decision import (
    CandidateCardinality,
    DecisionStatus,
    MatchingDecision,
    decide_runtime_matching,
)
from .runtime_matching_scope import RuntimeMatchingScope, validate_runtime_matching_scope


class RuntimeMatchingPersistenceError(ValueError):
    """The supplied decision is not the decision for the supplied scope."""


def persist_runtime_matching_decision(
    repository: MaintainPlanRepository,
    scope: RuntimeMatchingScope,
    decision: MatchingDecision,
    *,
    mapping_id: str,
    created_at: datetime,
    provenance: Mapping[str, Any] | None = None,
) -> PrescriptionMapping | None:
    """Persist only an exact global ``MATCHED``/``ONE`` decision.

    Non-automatic outcomes are deliberate no-ops.  The decision is recomputed
    to reject a forged or stale decision object, while the repository rereads
    both artifacts and both mapping sides under its ``BEGIN IMMEDIATE`` lock.
    """
    # RuntimeMatchingScope is a public dataclass and can be instantiated without
    # passing through the canonical ownership, artifact, and evidence checks.
    # Rebuild it at this trust boundary rather than trusting its declared fields.
    canonical_scope = validate_runtime_matching_scope(
        scope.subject_ref,
        scope.snapshots,
        scope.sessions,
        scope.direct_id_evidence,
    )
    authoritative_decision = decide_runtime_matching(canonical_scope)
    if decision != authoritative_decision:
        raise RuntimeMatchingPersistenceError(
            "decision does not match the complete validated scope")
    if (decision.status is not DecisionStatus.MATCHED or
            decision.cardinality is not CandidateCardinality.ONE or
            decision.selected_pair is None):
        return None

    pair = decision.selected_pair
    snapshot = next(
        item for item in canonical_scope.snapshots
        if item.prescription_snapshot_id == pair.prescription_snapshot_id)
    session = next(
        item for item in canonical_scope.sessions if item.session_id == pair.session_id)
    mapping = build_mapping(
        snapshot,
        session,
        mapping_id=mapping_id,
        created_at=created_at,
        resolution_method=ResolutionMethod.AUTOMATIC,
        provenance=provenance,
    )
    return repository.persist_prescription_mapping(
        mapping,
        expected_scope=canonical_scope,
        expected_decision=authoritative_decision,
    )
