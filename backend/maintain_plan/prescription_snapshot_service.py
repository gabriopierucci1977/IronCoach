"""Explicit acquisition boundary for communicated prescription snapshots.

Callers must present a complete canonical prescription wrapped as an explicit
communication event; this boundary never looks up or infers prescription data.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Protocol

from .models import PrescriptionSnapshot
from .serialization import deserialize_contract, serialize_contract
from .validators import validate_prescription


class PrescriptionSnapshotRepository(Protocol):
    """The insert-only repository operations used by the acquisition boundary."""

    def create_prescription_snapshot(self, value: PrescriptionSnapshot) -> None: ...

    def get_prescription_snapshot(self, identifier: str) -> PrescriptionSnapshot | None: ...

    def get_prescription_snapshot_by_decision_id(
        self, decision_id: str
    ) -> PrescriptionSnapshot | None: ...


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

        existing = self._repository.get_prescription_snapshot(
            snapshot.prescription_snapshot_id
        )
        if existing is None:
            existing = self._repository.get_prescription_snapshot_by_decision_id(
                snapshot.decision_id
            )
        if existing is not None:
            if _retry_equivalent(existing, snapshot):
                return existing
            raise PrescriptionSnapshotConflictError(
                "prescription snapshot decision_id already has different content"
            )

        # The repository operation is one SQLite INSERT transaction.  Any write
        # failure rolls it back rather than replacing prior state.
        self._repository.create_prescription_snapshot(snapshot)
        stored = self._repository.get_prescription_snapshot(
            snapshot.prescription_snapshot_id
        )
        if stored is None or stored != snapshot:
            raise RuntimeError("persisted prescription snapshot failed canonical round-trip")
        return stored
