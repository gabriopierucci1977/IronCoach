"""Explicit acquisition boundary for communicated prescription snapshots.

Callers must present a complete canonical prescription wrapped as an explicit
communication event; this boundary never looks up or infers prescription data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import ContextManager, Protocol

from .models import PrescriptionSnapshot
from .serialization import deserialize_contract, serialize_contract
from .validators import validate_prescription


class PrescriptionSnapshotTransaction(Protocol):
    """Operations performed under one write-locked repository transaction."""

    def create(self, value: PrescriptionSnapshot) -> None: ...

    def get(self, identifier: str) -> PrescriptionSnapshot | None: ...

    def get_by_decision_id(
        self, decision_id: str
    ) -> tuple[PrescriptionSnapshot, ...]: ...


class PrescriptionSnapshotRepository(Protocol):
    """Repository boundary needed for atomic snapshot acquisition."""

    def prescription_snapshot_transaction(
        self,
    ) -> ContextManager[PrescriptionSnapshotTransaction]: ...


@dataclass(frozen=True)
class CommunicatedPrescription:
    """A caller's explicit declaration that this exact prescription was communicated."""

    snapshot: PrescriptionSnapshot


class PrescriptionSnapshotConflictError(ValueError):
    """An identifier was retried with different prescription content."""


def _retry_equivalent(
    stored: PrescriptionSnapshot,
    candidate: PrescriptionSnapshot,
) -> bool:
    """Compare retry payloads while excluding their two capture timestamps."""
    return replace(
        stored,
        communicated_at=candidate.communicated_at,
        provenance=replace(
            stored.provenance,
            captured_at=candidate.provenance.captured_at,
        ),
    ) == candidate


class PrescriptionSnapshotService:
    """Validate, defensively copy, and insert a communicated prescription."""

    def __init__(self, repository: PrescriptionSnapshotRepository):
        self._repository = repository

    def acquire(self, communicated: CommunicatedPrescription) -> PrescriptionSnapshot:
        """Persist one immutable snapshot and return its canonical stored value.

        No legacy workout, training context, observed activity, matching result,
        or evaluation is accepted by this API.  Every authored value, identifier,
        and timestamp therefore comes solely from ``communicated.snapshot``.
        """
        if not isinstance(communicated, CommunicatedPrescription):
            raise TypeError("acquire requires an explicitly CommunicatedPrescription")

        # Codec round-tripping is the canonical defensive copy.  It recursively
        # rebuilds every contract container and freezes nested mappings/sets.
        snapshot = deserialize_contract(
            serialize_contract(communicated.snapshot), PrescriptionSnapshot
        )
        errors = validate_prescription(snapshot)
        if errors:
            raise ValueError("; ".join(errors))

        # BEGIN IMMEDIATE is acquired by this boundary before either lookup. It
        # serializes the decision check and insert across independent SQLite
        # connections without changing the append-only schema.
        with self._repository.prescription_snapshot_transaction() as transaction:
            matches = transaction.get_by_decision_id(snapshot.decision_id)
            if len(matches) > 1:
                raise PrescriptionSnapshotConflictError(
                    "multiple prescription snapshots already exist for decision_id"
                )

            existing = transaction.get(snapshot.prescription_snapshot_id)
            if existing is None and matches:
                existing = matches[0]
            if existing is not None:
                if _retry_equivalent(existing, snapshot):
                    return existing
                raise PrescriptionSnapshotConflictError(
                    "prescription snapshot decision_id already has different content"
                )

            transaction.create(snapshot)
            stored = transaction.get(snapshot.prescription_snapshot_id)
            if stored is None or stored != snapshot:
                raise RuntimeError("persisted prescription snapshot failed canonical round-trip")
            return stored
